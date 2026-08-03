import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from src.core import db_mongo, db_redis
from src.parametros import service as parametros_service


@pytest.fixture(autouse=True)
def _reset_backing_stores(monkeypatch):
    """Cada test arranca con Mongo/Redis en blanco: se reemplazan los
    singletons de core/db_mongo.py y core/db_redis.py por dobles en memoria,
    sin tocar la lógica de negocio (que solo conoce get_database()/get_redis()).

    También se limpia el caché en memoria de parametros/service.py (TTL 30s
    en producción, deliberado — ver el propio módulo). Sin esto, un test que
    crea una tarifa/comisión deja el valor cacheado en el proceso de Python
    (no en Mongo, que sí se resetea arriba) y "contamina" un test posterior
    que depende de que ese parámetro NO exista — un caso real encontrado al
    escribir tests/recaudacion/test_pago.py."""
    mock_client = AsyncMongoMockClient()
    monkeypatch.setattr(db_mongo, "_client", mock_client)

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(db_redis, "_redis", fake_redis)

    parametros_service._cache.clear()

    yield

    monkeypatch.setattr(db_mongo, "_client", None)
    monkeypatch.setattr(db_redis, "_redis", None)
    parametros_service._cache.clear()


@pytest.fixture
def db():
    return db_mongo.get_database()


@pytest.fixture
def redis():
    return db_redis.get_redis()


@pytest.fixture
async def client():
    from src.main import app
    from src.notificaciones.service import NotificationService

    # httpx.ASGITransport no dispara los eventos de lifespan de la app, así
    # que se replica a mano lo que src/main.py hace en el startup real.
    await db_mongo.ensure_indexes()
    app.state.notification_dispatcher = NotificationService()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
