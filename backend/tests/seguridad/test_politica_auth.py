from datetime import datetime, UTC

from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-seg-1", telefono="+593900000800", roles=["admin_sistema"])
    return auth_headers("admin-seg-1", ["admin_sistema"])


async def test_politica_default_antes_de_publicar_ninguna(client, db):
    headers = await _admin(db)
    resp = await client.get("/seguridad/politica-auth", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] is None
    assert body["longitud_minima_password"] == 8
    assert body["umbral_intentos_fallidos"] == 5


async def test_solo_admin_sistema_puede_publicar_politica(client, db):
    await crear_usuario_activo(db, usuario_id="gerencia-1", telefono="+593900000801", roles=["gerencia"])
    headers_gerencia = auth_headers("gerencia-1", ["gerencia"])

    resp = await client.post(
        "/seguridad/politica-auth",
        headers=headers_gerencia,
        json={
            "longitud_minima_password": 10,
            "umbral_intentos_fallidos": 3,
            "ventana_minutos": 10,
            "bloqueo_minutos": 20,
            "vigente_desde": datetime.now(UTC).isoformat(),
        },
    )

    assert resp.status_code == 403


async def test_publicar_politica_endurece_longitud_minima_de_password(client, db):
    headers = await _admin(db)
    await client.post(
        "/seguridad/politica-auth",
        headers=headers,
        json={
            "longitud_minima_password": 12,
            "umbral_intentos_fallidos": 5,
            "ventana_minutos": 15,
            "bloqueo_minutos": 15,
            "vigente_desde": datetime.now(UTC).isoformat(),
        },
    )

    corta = await client.post(
        "/auth/registro", json={"nombre": "Clave Corta", "telefono": "+593900000802", "password": "corta123"}
    )
    assert corta.status_code == 422
    assert corta.json()["code"] == "WEAK_PASSWORD"

    larga = await client.post(
        "/auth/registro",
        json={"nombre": "Clave Larga", "telefono": "+593900000803", "password": "esta-clave-es-suficientemente-larga"},
    )
    assert larga.status_code == 201


async def test_publicar_politica_cambia_umbral_de_bloqueo_de_login(client, db):
    headers = await _admin(db)
    telefono = "+593900000804"
    registro = {"nombre": "Umbral Bajo", "telefono": telefono, "password": "clave-larga-123"}
    await client.post("/auth/registro", json=registro)

    resp_politica = await client.post(
        "/seguridad/politica-auth",
        headers=headers,
        json={
            "longitud_minima_password": 8,
            "umbral_intentos_fallidos": 3,
            "ventana_minutos": 15,
            "bloqueo_minutos": 15,
            "vigente_desde": datetime.now(UTC).isoformat(),
        },
    )
    assert resp_politica.status_code == 201

    for _ in range(3):
        resp = await client.post("/auth/login", json={"identificador": telefono, "password": "mala"})
        assert resp.status_code == 401

    resp = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})
    assert resp.status_code == 429


async def test_publicar_politica_registra_antes_y_despues(client, db):
    headers = await _admin(db)
    await client.post(
        "/seguridad/politica-auth",
        headers=headers,
        json={
            "longitud_minima_password": 9,
            "umbral_intentos_fallidos": 4,
            "ventana_minutos": 15,
            "bloqueo_minutos": 15,
            "vigente_desde": datetime.now(UTC).isoformat(),
        },
    )

    evento = await db.bitacora.find_one({"accion": "POLITICA_AUTH_CAMBIO"})
    assert evento is not None
    assert evento["datos_previos"]["longitud_minima_password"] == 8
    assert evento["datos_posteriores"]["longitud_minima_password"] == 9
