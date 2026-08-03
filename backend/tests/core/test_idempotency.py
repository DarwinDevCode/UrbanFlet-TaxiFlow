from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from src.core.idempotency import IdempotencyMiddleware

_calls = {"n": 0}


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    class Body(BaseModel):
        monto: float

    @app.post("/efecto-critico")
    async def efecto_critico(body: Body):
        _calls["n"] += 1
        return {"llamadas": _calls["n"], "monto": body.monto}

    return app


async def test_misma_clave_y_cuerpo_no_repite_el_efecto():
    _calls["n"] = 0
    transport = ASGITransport(app=_build_app())
    headers = {"Idempotency-Key": "clave-1"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        primera = await ac.post("/efecto-critico", json={"monto": 10}, headers=headers)
        segunda = await ac.post("/efecto-critico", json={"monto": 10}, headers=headers)

    assert primera.json()["llamadas"] == 1
    assert segunda.json()["llamadas"] == 1  # replay, no se ejecutó de nuevo
    assert primera.json() == segunda.json()


async def test_misma_clave_con_cuerpo_distinto_devuelve_409():
    _calls["n"] = 0
    transport = ASGITransport(app=_build_app())
    headers = {"Idempotency-Key": "clave-2"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/efecto-critico", json={"monto": 10}, headers=headers)
        conflicto = await ac.post("/efecto-critico", json={"monto": 999}, headers=headers)

    assert conflicto.status_code == 409
    assert conflicto.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"


async def test_sin_clave_ejecuta_el_efecto_cada_vez():
    _calls["n"] = 0
    transport = ASGITransport(app=_build_app())

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        primera = await ac.post("/efecto-critico", json={"monto": 10})
        segunda = await ac.post("/efecto-critico", json={"monto": 10})

    assert primera.json()["llamadas"] == 1
    assert segunda.json()["llamadas"] == 2
