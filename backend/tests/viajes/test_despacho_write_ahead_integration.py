"""Prueba de rollback real para la cadena de aceptación de oferta (CU-O05/O06),
contra un Mongo real con replica set — mongomock no tiene rollback real que
demostrar (ver la versión mongomock de este caso, que solo prueba que fallar
en la PRIMERA escritura de la cadena —la auditoría— no aplica nada, en
tests/viajes/test_despacho.py).

A diferencia de esa prueba, aquí se hace fallar la ÚLTIMA escritura de la
cadena (el paso a OCUPADO del conductor) para demostrar el caso que
realmente exige una transacción multi-documento: la auditoría YA se escribió
y el viaje YA pasó a ASIGNADO cuando el fallo ocurre. Sin `with_transaction`,
esto dejaría el viaje asignado con el conductor todavía DISPONIBLE — un
estado inconsistente. Con la transacción, MongoDB descarta TODA la cadena.

Pensada para correr dentro de la red de docker-compose:
`docker compose run --rm backend pytest tests/viajes/test_despacho_write_ahead_integration.py`.
Se salta automáticamente si no hay Mongo alcanzable.
"""

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from src.core import db_mongo
from src.core.config import get_settings
from src.viajes import service_dispatch
from tests.utils import reportar_posicion_en_cache

_DB_NAME = "urbanflet_test_rollback_despacho"


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
            "`docker compose run --rm backend pytest tests/viajes/test_despacho_write_ahead_integration.py`."
        )

    # Mismo motivo que en captacion/test_write_ahead_integration.py: la
    # transacción arranca la sesión desde el singleton real de la app
    # (core.db_mongo.get_mongo_client()) — si `db` viniera de otro cliente, la
    # sesión no gobernaría sus escrituras.
    monkeypatch.setattr(db_mongo, "_client", client)
    db = client[_DB_NAME]
    yield db
    await db.viajes.delete_many({})
    await db.ofertas.delete_many({})
    await db.usuarios.delete_many({})
    await db.vehiculos.delete_many({})
    await db.bitacora.delete_many({})
    await db.counters.delete_many({})
    client.close()


async def test_rollback_real_si_falla_la_ultima_escritura_al_aceptar_oferta(real_db, monkeypatch):
    from src.core import db_redis

    db = real_db
    conductor_id = "cd-rollback-real"
    vehiculo_id = "veh-rollback-real"
    viaje_id = "viaje-rollback-real"

    await db.usuarios.insert_one(
        {
            "_id": conductor_id,
            "nombre": "Conductor Rollback",
            "telefono": "+593940000099",
            "roles": ["conductor"],
            "estado": "ACTIVO",
            "conductor": {"estado_servicio": "DISPONIBLE", "calificacion_promedio": None},
        }
    )
    await db.vehiculos.insert_one(
        {
            "_id": vehiculo_id,
            "placa": "ROLB-001",
            "marca": "Marca",
            "modelo": "Modelo",
            "color": "Negro",
            "estado_habilitacion": "HABILITADO",
            "propietario_id": conductor_id,
        }
    )
    await db.usuarios.insert_one(
        {
            "_id": "pas-rollback-real",
            "nombre": "Pasajero Rollback",
            "telefono": "+593940000098",
            "roles": ["pasajero"],
            "estado": "ACTIVO",
        }
    )
    await db.viajes.insert_one(
        {
            "_id": viaje_id,
            "pasajero_id": "pas-rollback-real",
            "conductor_id": None,
            "vehiculo_id": None,
            "estado": "OFERTADO",
            "origen_lat": -0.18,
            "origen_lon": -78.5,
            "origen_direccion": "Origen",
            "destino_lat": None,
            "destino_lon": None,
            "destino_direccion": None,
            "franja": "DIURNA",
            "conductor_ofertado_id": conductor_id,
            "ts_oferta_emitida": None,
            "conductores_descartados": [conductor_id],
            "ofertas_totales": 1,
        }
    )
    await db.ofertas.insert_one(
        {
            "_id": "oferta-rollback-real",
            "viaje_id": viaje_id,
            "conductor_id": conductor_id,
            "ts_emision": None,
            "ts_respuesta": None,
            "resultado": None,
            "radio_m": 300,
        }
    )
    # `ts_oferta_emitida=None` haría fallar el chequeo de expiración de
    # avanzar_despacho antes de llegar a responder_oferta — se corrige aparte
    # para no acoplar esta prueba a esa validación, que no es lo que se prueba aquí.
    from datetime import UTC, datetime

    await db.viajes.update_one({"_id": viaje_id}, {"$set": {"ts_oferta_emitida": datetime.now(UTC)}})
    await db.ofertas.update_one({"_id": "oferta-rollback-real"}, {"$set": {"ts_emision": datetime.now(UTC)}})

    fake_redis = db_redis.get_redis()
    await reportar_posicion_en_cache(fake_redis, vehiculo_id=vehiculo_id, lat=-0.1801, lon=-78.5001)

    # Falla la ÚLTIMA escritura de la cadena de aceptación (usuarios.update_one
    # → OCUPADO), después de que la auditoría y el viaje YA se escribieron.
    original_update_one = type(db.usuarios).update_one

    async def _falla_al_marcar_ocupado(self, filtro, update, *args, **kwargs):
        if self.name == "usuarios" and update.get("$set", {}).get("conductor.estado_servicio") == "OCUPADO":
            raise PyMongoError("Mongo caído justo al marcar OCUPADO (simulado)")
        return await original_update_one(self, filtro, update, *args, **kwargs)

    monkeypatch.setattr(type(db.usuarios), "update_one", _falla_al_marcar_ocupado)

    with pytest.raises(PyMongoError):
        await service_dispatch.responder_oferta(db, conductor_id=conductor_id, aceptar=True)

    monkeypatch.setattr(type(db.usuarios), "update_one", original_update_one)

    # Con la transacción, NADA de la cadena queda aplicado — ni el viaje, ni
    # la oferta, ni (por supuesto) el estado del conductor.
    viaje = await db.viajes.find_one({"_id": viaje_id})
    assert viaje["estado"] == "OFERTADO", "el viaje no debe quedar en ASIGNADO tras el rollback"

    oferta = await db.ofertas.find_one({"_id": "oferta-rollback-real"})
    assert oferta["resultado"] is None, "la oferta no debe quedar ACEPTADA tras el rollback"

    conductor = await db.usuarios.find_one({"_id": conductor_id})
    assert conductor["conductor"]["estado_servicio"] == "DISPONIBLE", "el conductor no debe quedar OCUPADO"

    evento = await db.bitacora.find_one({"entidad_id": viaje_id, "accion": "VIAJE_TRANSICION_ESTADO"})
    assert evento is None, "el evento de auditoría también debe revertirse con la transacción"
