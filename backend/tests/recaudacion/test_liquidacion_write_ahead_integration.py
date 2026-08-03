"""Prueba de rollback real para la cadena de emisión de una liquidación
(CU-O11 pasos 1-2), contra un Mongo real con replica set — mismo motivo que
las demás pruebas `*_write_ahead_integration.py`: mongomock no tiene
rollback real que demostrar.

Se hace fallar la ÚLTIMA escritura de la cadena (enlazar los movimientos del
periodo con la liquidación recién emitida) para probar que, si eso falla,
NO queda una liquidación insertada sin sus movimientos enlazados — eso
dejaría los movimientos disponibles para volver a "generar" en una corrida
futura mientras la liquidación fantasma ya existe, duplicando el neto del
socio.

Pensada para correr dentro de la red de docker-compose:
`docker compose run --rm backend pytest tests/recaudacion/test_liquidacion_write_ahead_integration.py`.
Se salta automáticamente si no hay Mongo alcanzable.
"""

from datetime import UTC, datetime, timedelta

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from src.core import db_mongo
from src.core.config import get_settings
from src.recaudacion import service as recaudacion_service
from src.recaudacion.service import _periodo_cerrado_mas_reciente

_DB_NAME = "urbanflet_test_rollback_liquidacion"


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
            "tests/recaudacion/test_liquidacion_write_ahead_integration.py`."
        )

    monkeypatch.setattr(db_mongo, "_client", client)
    db = client[_DB_NAME]
    yield db
    await db.viajes.delete_many({})
    await db.pagos.delete_many({})
    await db.movimientos.delete_many({})
    await db.liquidaciones.delete_many({})
    await db.usuarios.delete_many({})
    await db.bitacora.delete_many({})
    await db.counters.delete_many({})
    client.close()


async def test_rollback_real_si_falla_el_enlace_de_movimientos_a_la_liquidacion(real_db, monkeypatch):
    db = real_db
    conductor_id = "cd-rollback-liq"
    viaje_id = "viaje-rollback-liq"

    await db.usuarios.insert_one(
        {
            "_id": conductor_id,
            "nombre": "Conductor Rollback Liquidación",
            "telefono": "+593940000095",
            "roles": ["conductor"],
            "estado": "ACTIVO",
            "conductor": {"estado_servicio": "DISPONIBLE"},
        }
    )

    inicio, _fin = _periodo_cerrado_mas_reciente(datetime.now(UTC))
    ts = inicio + timedelta(hours=1)

    await db.viajes.insert_one(
        {
            "_id": viaje_id,
            "pasajero_id": "pas-rollback-liq",
            "conductor_id": conductor_id,
            "vehiculo_id": "veh-rollback-liq",
            "estado": "PAGADO",
            "origen_lat": -0.18,
            "origen_lon": -78.5,
            "origen_direccion": "Origen",
            "destino_lat": None,
            "destino_lon": None,
            "destino_direccion": None,
            "franja": "DIURNA",
            "ts_solicitud": ts,
            "ts_inicio": ts,
            "ts_fin": ts,
            "km_recorridos": 3.0,
            "min_espera": 0.0,
            "tarifa_estimada": 10.0,
            "tarifa_final": 10.0,
        }
    )
    await db.pagos.insert_one(
        {
            "_id": "pago-rollback-liq",
            "viaje_id": viaje_id,
            "conductor_id": conductor_id,
            "metodo": "EFECTIVO",
            "monto": 10.0,
            "tarifa_final": 10.0,
            "diferencia": None,
            "estado": "VALIDADO",
            "referencia_externa": None,
            "ts_registro": ts,
            "ts_confirmacion": ts,
            "resuelto": False,
            "resolucion_motivo": None,
            "resolucion_aceptado": None,
            "resolucion_autorizador_id": None,
            "resolucion_ts": None,
        }
    )
    await db.movimientos.insert_many(
        [
            {
                "_id": "mov-com-rollback-liq",
                "viaje_id": viaje_id,
                "tipo": "COMISION",
                "monto_firmado": -2.0,
                "comision_version_id": "com-x",
                "motivo": None,
                "autorizador_id": None,
                "ts": ts,
                "liquidacion_id": None,
            },
            {
                "_id": "mov-neto-rollback-liq",
                "viaje_id": viaje_id,
                "tipo": "NETO_SOCIO",
                "monto_firmado": 8.0,
                "comision_version_id": "com-x",
                "motivo": None,
                "autorizador_id": None,
                "ts": ts,
                "liquidacion_id": None,
            },
        ]
    )

    original_update_many = type(db.movimientos).update_many

    async def _falla_al_enlazar_movimientos(self, *args, **kwargs):
        if self.name == "movimientos":
            raise PyMongoError("Mongo caído justo al enlazar los movimientos (simulado)")
        return await original_update_many(self, *args, **kwargs)

    monkeypatch.setattr(type(db.movimientos), "update_many", _falla_al_enlazar_movimientos)

    with pytest.raises(PyMongoError):
        await recaudacion_service.generar_liquidaciones(db, autorizador_id="admin-rollback-liq")

    monkeypatch.setattr(type(db.movimientos), "update_many", original_update_many)

    liquidacion = await db.liquidaciones.find_one({"conductor_id": conductor_id})
    assert liquidacion is None, "no debe quedar una liquidación insertada sin sus movimientos enlazados"

    movimientos = await db.movimientos.find({"viaje_id": viaje_id}).to_list(length=10)
    assert all(m["liquidacion_id"] is None for m in movimientos), "los movimientos deben seguir libres tras el rollback"

    evento = await db.bitacora.find_one({"accion": "LIQUIDACION_EMISION", "entidad_id": {"$exists": True}})
    assert evento is None, "el evento de auditoría de la emisión también debe revertirse"
