"""Prueba de rollback real (Mongo con replica set) para la cadena
transaccional de Mantenimiento — la segunda cadena en reusar
core/db_transaction.py después de Captación (Fase 1), confirmando que el
helper generaliza a un dominio distinto sin ajustes.

Se salta automáticamente si no hay Mongo con replica set alcanzable. Ver
tests/captacion/test_write_ahead_integration.py para la explicación completa
del mecanismo (por qué se reusa el mismo cliente Mongo que la app).
"""

from datetime import date

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from src.core import db_mongo
from src.core.config import get_settings
from src.core.exceptions import AuditWriteError
from src.core.notifications import NoopNotificationDispatcher
from src.mantenimiento import service as mantenimiento_service

_DB_NAME = "urbanflet_test_rollback_mantenimiento"


@pytest.fixture
async def real_db(monkeypatch):
    uri = get_settings().mongo_uri
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
    try:
        await client.admin.command("ping")
    except Exception:  # noqa: BLE001 — cualquier fallo de conexión debe saltar la prueba, no propagar
        client.close()
        pytest.skip(
            f"No hay un Mongo con replica set alcanzable en {uri} — corre esta prueba "
            "dentro de la red docker-compose: "
            "`docker compose run --rm backend pytest tests/mantenimiento/test_write_ahead_integration.py`."
        )

    monkeypatch.setattr(db_mongo, "_client", client)
    db = client[_DB_NAME]
    yield db
    await db.ordenes.delete_many({})
    await db.vehiculos.delete_many({})
    await db.usuarios.delete_many({})
    await db.bitacora.delete_many({})
    await db.counters.delete_many({})
    client.close()


async def test_rollback_real_de_creacion_de_orden_con_retiro(real_db, monkeypatch):
    db = real_db
    dispatcher = NoopNotificationDispatcher()

    await db.usuarios.insert_one({"_id": "c-rollback-mant", "roles": ["conductor"], "estado": "ACTIVO"})
    await db.vehiculos.insert_one(
        {
            "_id": "v-rollback-mant",
            "placa": "ROL-M001",
            "estado_habilitacion": "HABILITADO",
            "propietario_id": "c-rollback-mant",
        }
    )

    # Motor usa una sola clase (AsyncIOMotorCollection) para TODAS las
    # colecciones — parchear insert_one a nivel de clase intercepta también
    # el insert_one de `ordenes`, no solo el de `bitacora`. Se filtra por
    # `self.name` para que el contador de "segunda llamada" cuente
    # únicamente escrituras de auditoría, no cualquier insert_one de la
    # transacción.
    original_insert_one = type(db.bitacora).insert_one
    llamadas = {"n": 0}

    async def _falla_desde_la_segunda(self, *args, **kwargs):
        if self.name != "bitacora":
            return await original_insert_one(self, *args, **kwargs)
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return await original_insert_one(self, *args, **kwargs)
        raise PyMongoError("Mongo caído en la segunda escritura de auditoría")

    monkeypatch.setattr(type(db.bitacora), "insert_one", _falla_desde_la_segunda)

    with pytest.raises(AuditWriteError):
        await mantenimiento_service.crear_orden(
            db,
            dispatcher,
            actor_id="jefe-rollback",
            actor_rol="jefe_mantenimiento",
            vehiculo_id="v-rollback-mant",
            tipo="CORRECTIVA",
            descripcion="rollback test",
            km_entrada=100,
            taller="Taller",
            fecha_programada=date(2026, 8, 1),
            retirar_vehiculo=True,
            repuestos_estimados=[],
        )

    # Ni la orden (primer efecto, cuya auditoría sí se escribió) ni el
    # retiro del vehículo (segundo efecto, cuya auditoría falló) quedan
    # aplicados — la transacción descarta ambos.
    assert await db.ordenes.count_documents({}) == 0
    vehiculo = await db.vehiculos.find_one({"_id": "v-rollback-mant"})
    assert vehiculo["estado_habilitacion"] == "HABILITADO"
