"""Prueba de rollback real para la cadena de registro de pago (CU-O09/O10),
contra un Mongo real con replica set — mongomock no tiene rollback real que
demostrar (ver la versión mongomock de este caso en test_pago.py, que solo
prueba que la excepción se propaga).

Se hace fallar la ÚLTIMA escritura de la cadena (los movimientos de
comisión/neto, CU-O10) para demostrar el caso que realmente exige una
transacción multi-documento: el pago YA se escribió como VALIDADO y el viaje
YA pasó a PAGADO cuando el fallo ocurre. Sin `with_transaction`, esto
dejaría un pago validado y un viaje PAGADO sin su contrapartida contable —
exactamente la clase de estado parcial que la "regla inviolable" del
encabezado de operativo_finanzas.md prohíbe. Con la transacción, MongoDB
descarta TODA la cadena.

Pensada para correr dentro de la red de docker-compose:
`docker compose run --rm backend pytest tests/recaudacion/test_pago_write_ahead_integration.py`.
Se salta automáticamente si no hay Mongo alcanzable.
"""

from datetime import UTC, datetime

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from src.core import db_mongo
from src.core.config import get_settings
from src.recaudacion import service as recaudacion_service

_DB_NAME = "urbanflet_test_rollback_pago"


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
            "`docker compose run --rm backend pytest tests/recaudacion/test_pago_write_ahead_integration.py`."
        )

    # Mismo motivo que en las demás pruebas de integración: la transacción
    # arranca la sesión desde el singleton real de la app
    # (core.db_mongo.get_mongo_client()) — si `db` viniera de otro cliente,
    # la sesión no gobernaría sus escrituras.
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


async def test_rollback_real_si_falla_la_creacion_de_movimientos(real_db, monkeypatch):
    db = real_db
    conductor_id = "cd-rollback-pago"
    viaje_id = "viaje-rollback-pago"

    await db.usuarios.insert_one(
        {
            "_id": conductor_id,
            "nombre": "Conductor Rollback Pago",
            "telefono": "+593940000097",
            "roles": ["conductor"],
            "estado": "ACTIVO",
            "conductor": {"estado_servicio": "DISPONIBLE"},
        }
    )
    await db.viajes.insert_one(
        {
            "_id": viaje_id,
            "pasajero_id": "pas-rollback-pago",
            "conductor_id": conductor_id,
            "vehiculo_id": "veh-rollback-pago",
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
            "tarifa_estimada": 3.5,
            "tarifa_final": 3.5,
        }
    )
    # Comisión vigente — necesaria para que la cadena llegue hasta el paso
    # que se va a hacer fallar (si no hubiera comisión vigente, fallaría
    # antes y no probaría lo que esta prueba quiere probar).
    await db.parametros.insert_one(
        {
            "_id": "com-rollback",
            "tipo": "comision",
            "valores": {"porcentaje": 0.20},
            "vigente_desde": datetime(2020, 1, 1, tzinfo=UTC),
            "vigente_hasta": None,
        }
    )

    # Falla la ÚLTIMA escritura de la cadena (movimientos.insert_many), después
    # de que el pago y el viaje YA se escribieron dentro de la transacción.
    original_insert_many = type(db.movimientos).insert_many

    async def _falla_al_crear_movimientos(self, *args, **kwargs):
        if self.name == "movimientos":
            raise PyMongoError("Mongo caído justo al crear los movimientos (simulado)")
        return await original_insert_many(self, *args, **kwargs)

    monkeypatch.setattr(type(db.movimientos), "insert_many", _falla_al_crear_movimientos)

    with pytest.raises(PyMongoError):
        await recaudacion_service.registrar_pago_efectivo(
            db, conductor_id=conductor_id, viaje_id=viaje_id, monto_cobrado=3.5
        )

    monkeypatch.setattr(type(db.movimientos), "insert_many", original_insert_many)

    # Con la transacción, NADA de la cadena queda aplicado.
    viaje = await db.viajes.find_one({"_id": viaje_id})
    assert viaje["estado"] == "FINALIZADO", "el viaje no debe quedar en PAGADO tras el rollback"

    pago = await db.pagos.find_one({"viaje_id": viaje_id})
    assert pago is None, "el pago no debe quedar registrado tras el rollback"

    movimientos = await db.movimientos.find({"viaje_id": viaje_id}).to_list(length=10)
    assert movimientos == []

    evento = await db.bitacora.find_one({"entidad_id": viaje_id, "accion": "VIAJE_TRANSICION_ESTADO"})
    assert evento is None, "el evento de auditoría de la transición del viaje también debe revertirse"
