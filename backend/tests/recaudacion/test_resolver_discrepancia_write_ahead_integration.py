"""Prueba de rollback real para la cadena de resolución de una discrepancia
cuando el Administrador Financiero ACEPTA el monto cobrado (CU-O09 A1 →
CU-O10), contra un Mongo real con replica set — mismo motivo que
`test_pago_write_ahead_integration.py`: mongomock no tiene rollback real que
demostrar.

Se hace fallar la ÚLTIMA escritura de la cadena (los movimientos de
comisión/neto) para probar que, si eso falla, el pago NO queda marcado como
resuelto y el viaje NO pasa a PAGADO — de lo contrario quedaría un pago
"aceptado" sin su contrapartida contable, la misma clase de estado parcial
que la transacción existe para prevenir.

Pensada para correr dentro de la red de docker-compose:
`docker compose run --rm backend pytest tests/recaudacion/test_resolver_discrepancia_write_ahead_integration.py`.
Se salta automáticamente si no hay Mongo alcanzable.
"""

from datetime import UTC, datetime

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from src.core import db_mongo
from src.core.config import get_settings
from src.recaudacion import service as recaudacion_service

_DB_NAME = "urbanflet_test_rollback_resolver"


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
            "dentro de la red docker-compose: `docker compose run --rm backend pytest "
            "tests/recaudacion/test_resolver_discrepancia_write_ahead_integration.py`."
        )

    monkeypatch.setattr(db_mongo, "_client", client)
    db = client[_DB_NAME]
    yield db
    await db.viajes.delete_many({})
    await db.pagos.delete_many({})
    await db.movimientos.delete_many({})
    await db.parametros.delete_many({})
    await db.usuarios.delete_many({})
    await db.bitacora.delete_many({})
    await db.counters.delete_many({})
    client.close()


async def test_rollback_real_si_falla_la_creacion_de_movimientos_al_aceptar(real_db, monkeypatch):
    db = real_db
    conductor_id = "cd-rollback-resolver"
    viaje_id = "viaje-rollback-resolver"
    pago_id = "pago-rollback-resolver"

    await db.usuarios.insert_one(
        {
            "_id": conductor_id,
            "nombre": "Conductor Rollback Resolver",
            "telefono": "+593940000096",
            "roles": ["conductor"],
            "estado": "ACTIVO",
            "conductor": {"estado_servicio": "DISPONIBLE"},
        }
    )
    await db.viajes.insert_one(
        {
            "_id": viaje_id,
            "pasajero_id": "pas-rollback-resolver",
            "conductor_id": conductor_id,
            "vehiculo_id": "veh-rollback-resolver",
            "estado": "FINALIZADO",
            "origen_lat": -0.18,
            "origen_lon": -78.5,
            "origen_direccion": "Origen",
            "destino_lat": None,
            "destino_lon": None,
            "destino_direccion": None,
            "franja": "DIURNA",
            "ts_solicitud": datetime.now(UTC),
            "ts_inicio": datetime.now(UTC),
            "ts_fin": datetime.now(UTC),
            "km_recorridos": 3.0,
            "min_espera": 0.0,
            "tarifa_estimada": 4.0,
            "tarifa_final": 4.0,
        }
    )
    await db.pagos.insert_one(
        {
            "_id": pago_id,
            "viaje_id": viaje_id,
            "conductor_id": conductor_id,
            "metodo": "EFECTIVO",
            "monto": 3.0,
            "tarifa_final": 4.0,
            "diferencia": -1.0,
            "estado": "DISCREPANCIA",
            "referencia_externa": None,
            "ts_registro": datetime.now(UTC),
            "ts_confirmacion": None,
            "resuelto": False,
            "resolucion_motivo": None,
            "resolucion_aceptado": None,
            "resolucion_autorizador_id": None,
            "resolucion_ts": None,
        }
    )
    await db.parametros.insert_one(
        {
            "_id": "com-rollback-resolver",
            "tipo": "comision",
            "valores": {"porcentaje": 0.20},
            "vigente_desde": datetime(2020, 1, 1, tzinfo=UTC),
            "vigente_hasta": None,
        }
    )

    original_insert_many = type(db.movimientos).insert_many

    async def _falla_al_crear_movimientos(self, *args, **kwargs):
        if self.name == "movimientos":
            raise PyMongoError("Mongo caído justo al crear los movimientos (simulado)")
        return await original_insert_many(self, *args, **kwargs)

    monkeypatch.setattr(type(db.movimientos), "insert_many", _falla_al_crear_movimientos)

    with pytest.raises(PyMongoError):
        await recaudacion_service.resolver_discrepancia(
            db, pago_id=pago_id, autorizador_id="admin-rollback", aceptar=True, motivo="acepto el monto cobrado"
        )

    monkeypatch.setattr(type(db.movimientos), "insert_many", original_insert_many)

    pago = await db.pagos.find_one({"_id": pago_id})
    assert pago["resuelto"] is False, "el pago no debe quedar marcado como resuelto tras el rollback"
    assert pago["estado"] == "DISCREPANCIA"

    viaje = await db.viajes.find_one({"_id": viaje_id})
    assert viaje["estado"] == "FINALIZADO", "el viaje no debe quedar en PAGADO tras el rollback"

    movimientos = await db.movimientos.find({"viaje_id": viaje_id}).to_list(length=10)
    assert movimientos == []

    evento = await db.bitacora.find_one({"entidad_id": viaje_id, "accion": "VIAJE_TRANSICION_ESTADO"})
    assert evento is None, "el evento de auditoría de la transición del viaje también debe revertirse"
