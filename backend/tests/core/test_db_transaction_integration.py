"""Prueba del helper reutilizable de transacciones (core/db_transaction.py)
contra un Mongo real con replica set. `mongomock` (el resto de la suite) no
implementa sesiones — no puede demostrar un rollback real, solo el
comportamiento del fallback sin sesión (ver tests/captacion/test_write_ahead.py).
La reproducción exacta del caso de Captación que motivó este helper vive en
tests/captacion/test_write_ahead_integration.py.

Usa el mismo MONGO_URI que el resto de la app (ver core/config.py) contra una
base de datos separada, solo para esta prueba. Dentro de la red de
docker-compose eso ya apunta a `mongo:27017` con el replica set inicializado.
Si se corre desde el host (fuera de Docker), el miembro del replica set se
anuncia internamente como `mongo:27017` — un nombre que no resuelve fuera de
la red de Docker — así que esta prueba está pensada para correr dentro del
contenedor del backend: `docker compose run --rm backend pytest tests/core/test_db_transaction_integration.py`.
Se salta automáticamente si no hay Mongo alcanzable.
"""

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import get_settings
from src.core.db_transaction import with_transaction

_DB_NAME = "urbanflet_test_transaccion_helper"


@pytest.fixture
async def real_client():
    uri = get_settings().mongo_uri
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
    try:
        await client.admin.command("ping")
    except Exception:  # noqa: BLE001 — cualquier fallo de conexión debe saltar la prueba, no propagar
        pytest.skip(
            f"No hay un Mongo con replica set alcanzable en {uri} — corre esta prueba "
            "dentro de la red docker-compose: "
            "`docker compose run --rm backend pytest tests/core/test_db_transaction_integration.py`."
        )
    yield client
    await client[_DB_NAME].cosa.delete_many({})
    client.close()


async def test_with_transaction_hace_rollback_real_si_el_callback_falla(real_client):
    db = real_client[_DB_NAME]

    async def _callback(session):
        await db.cosa.insert_one({"_id": "x1"}, session=session)
        raise RuntimeError("fuerzo abort para probar el rollback")

    with pytest.raises(RuntimeError):
        await with_transaction(real_client, _callback)

    assert await db.cosa.find_one({"_id": "x1"}) is None


async def test_with_transaction_confirma_si_el_callback_tiene_exito(real_client):
    db = real_client[_DB_NAME]

    async def _callback(session):
        await db.cosa.insert_one({"_id": "x2"}, session=session)
        return "ok"

    resultado = await with_transaction(real_client, _callback)

    assert resultado == "ok"
    assert await db.cosa.find_one({"_id": "x2"}) is not None
