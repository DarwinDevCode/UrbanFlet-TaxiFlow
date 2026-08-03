"""CORS no tenía cobertura: los tres clientes web corren en un origen
distinto al backend (localhost:517x vs localhost:8000), y sin este
middleware el navegador bloquea el preflight con 405 — algo que curl/pytest
nunca hubieran detectado, solo un navegador real cruzando orígenes."""


async def test_preflight_permite_origen_de_un_cliente_web(client):
    resp = await client.options(
        "/captacion/solicitudes",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5174"


async def test_preflight_rechaza_origen_no_registrado(client):
    resp = await client.options(
        "/captacion/solicitudes",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in resp.headers
