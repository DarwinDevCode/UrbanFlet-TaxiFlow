"""Reproduce EXACTAMENTE el caso encontrado en la revisión de Fase 1: la
auditoría de la DECISIÓN de una solicitud se escribe con éxito, pero la
auditoría de HABILITACIÓN DE VEHÍCULO (el segundo evento de la cadena de
aprobación) falla a mitad de camino.

Antes de envolver la cadena en una transacción (core/db_transaction.py), esto
dejaba la solicitud APROBADA sin vehículo ni rol de conductor — un estado
parcial inconsistente (ver la versión mongomock de este mismo caso en
tests/captacion/test_write_ahead.py, que documenta el comportamiento del
fallback sin sesión). Esta prueba corre contra un Mongo real con replica set
— mongomock no tiene rollback real que demostrar — y confirma que ahora nada
de la cadena queda aplicado: ni la decisión, ni el vehículo, ni el rol.

Usa el mismo MONGO_URI que el resto de la app (ver core/config.py) contra una
base de datos separada, solo para esta prueba. Está pensada para correr
dentro de la red de docker-compose, donde MONGO_URI ya apunta a `mongo:27017`
con el replica set inicializado:
`docker compose run --rm backend pytest tests/captacion/test_write_ahead_integration.py`.
Se salta automáticamente si no hay Mongo alcanzable.
"""

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from src.captacion import service as captacion_service
from src.core import db_mongo
from src.core.config import get_settings
from src.core.exceptions import AuditWriteError
from src.core.notifications import NoopNotificationDispatcher

_DB_NAME = "urbanflet_test_rollback_captacion"


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
            "`docker compose run --rm backend pytest tests/captacion/test_write_ahead_integration.py`."
        )

    # Crítico: `captacion.service.decidir_solicitud` arranca la sesión con
    # `core.db_mongo.get_mongo_client()` (el singleton real de la app). Si
    # `db` viniera de un cliente Motor distinto, la sesión de la transacción
    # sería inválida para esas operaciones y no gobernaría nada — exactamente
    # el bug que tenía la primera versión de esta prueba. Se parchea el
    # singleton para que sea EL MISMO cliente que el código de producción usaría.
    monkeypatch.setattr(db_mongo, "_client", client)
    db = client[_DB_NAME]
    yield db
    await db.solicitudes.delete_many({})
    await db.vehiculos.delete_many({})
    await db.usuarios.delete_many({})
    await db.documentos.delete_many({})
    await db.bitacora.delete_many({})
    await db.counters.delete_many({})
    client.close()


async def test_rollback_real_de_la_cadena_de_aprobacion(real_db, monkeypatch):
    db = real_db
    dispatcher = NoopNotificationDispatcher()

    solicitud_id = "sol-rollback-real"
    usuario_id = "usr-rollback-real"

    await db.usuarios.insert_one({"_id": usuario_id, "roles": [], "estado": "ACTIVO", "telefono": "+593940000001"})
    await db.solicitudes.insert_one(
        {
            "_id": solicitud_id,
            "usuario_id": usuario_id,
            "cedula": "5551112223",
            "licencia_numero": "LIC-ROLLBACK",
            "estado": "EN_VERIFICACION",
            "fecha_envio": None,
            "fecha_decision": None,
            "verificador_id": None,
            "motivo_rechazo": None,
            "vehiculo": {
                "placa": "ROL-0001",
                "marca": "Marca",
                "modelo": "Modelo",
                "anio": 2020,
                "color": "Negro",
                "capacidad": 4,
            },
            "documentos": [],
            "revision_reforzada": False,
        }
    )

    # Exactamente el mismo mecanismo de fallo que en la versión mongomock:
    # la PRIMERA escritura de auditoría (decisión) tiene éxito, la SEGUNDA
    # (habilitación de vehículo) falla. Motor usa una sola clase para TODAS
    # las colecciones, así que se filtra por `self.name` — si no, el
    # contador también contaría el insert_one de otras colecciones que
    # ocurran entre medio (ver el mismo comentario en
    # tests/mantenimiento/test_write_ahead_integration.py, donde esto sí
    # llegó a manifestarse).
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
        await captacion_service.decidir_solicitud(
            db,
            dispatcher,
            solicitud_id=solicitud_id,
            verificador_id="admin-rollback",
            verificador_rol="admin_captacion",
            decision="APROBADA",
            motivo=None,
        )

    # Con la transacción, TODA la cadena queda sin aplicar — no solo el
    # segundo efecto, sino también el primero que ya se había escrito.
    solicitud = await db.solicitudes.find_one({"_id": solicitud_id})
    assert solicitud["estado"] == "EN_VERIFICACION", "la decisión no debe quedar aplicada tras el rollback"

    assert await db.vehiculos.find_one({"placa": "ROL-0001"}) is None, "el vehículo no debe crearse tras el rollback"

    usuario = await db.usuarios.find_one({"_id": usuario_id})
    assert "conductor" not in usuario["roles"], "el rol de conductor no debe asignarse tras el rollback"

    # El primer evento de auditoría (la decisión) tampoco debe sobrevivir:
    # es la escritura que MongoDB descarta como parte del mismo abort.
    evento_decision = await db.bitacora.find_one({"entidad_id": solicitud_id, "accion": "SOLICITUD_CONDUCTOR_DECISION"})
    assert evento_decision is None, "la propia escritura de auditoría también se revierte con la transacción"
