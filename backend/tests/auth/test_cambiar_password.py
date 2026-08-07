from tests.utils import auth_headers, crear_usuario_activo


async def _crear_staff(client, headers, *, nombre: str, telefono: str, roles: list[str]):
    body = {"nombre": nombre, "telefono": telefono, "password": "clave-larga-123", "roles": roles}
    return await client.post("/usuarios", headers=headers, json=body)


async def _login(client, identificador: str, password: str):
    return await client.post("/auth/login", json={"identificador": identificador, "password": password})


async def test_creacion_por_admin_fuerza_cambio_de_password_en_login(client, db):
    await crear_usuario_activo(db, usuario_id="admin-pw-1", telefono="+593900000700", roles=["admin_sistema"])
    headers = auth_headers("admin-pw-1", ["admin_sistema"])

    creado = await _crear_staff(
        client, headers, nombre="Nuevo Staff", telefono="+593900000701", roles=["jefe_mantenimiento"]
    )
    assert creado.status_code == 201

    login = await _login(client, "+593900000701", "clave-larga-123")
    assert login.status_code == 200
    assert login.json()["debe_cambiar_password"] is True


async def test_login_normal_no_exige_cambio_de_password(client):
    telefono = "+593900000702"
    registro = {"nombre": "Normal", "telefono": telefono, "password": "clave-larga-123"}
    await client.post("/auth/registro", json=registro)
    login = await _login(client, telefono, "clave-larga-123")
    assert login.json()["debe_cambiar_password"] is False


async def test_cambiar_password_requiere_password_actual_correcta(client):
    telefono = "+593900000703"
    registro = {"nombre": "Cambia Clave", "telefono": telefono, "password": "clave-larga-123"}
    await client.post("/auth/registro", json=registro)
    login = await _login(client, telefono, "clave-larga-123")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    body_malo = {"password_actual": "incorrecta", "password_nueva": "clave-nueva-456"}
    fallo = await client.post("/auth/cambiar-password", headers=headers, json=body_malo)
    assert fallo.status_code == 401

    body_ok = {"password_actual": "clave-larga-123", "password_nueva": "clave-nueva-456"}
    ok = await client.post("/auth/cambiar-password", headers=headers, json=body_ok)
    assert ok.status_code == 204

    relogin_viejo = await _login(client, telefono, "clave-larga-123")
    assert relogin_viejo.status_code == 401

    relogin_nuevo = await _login(client, telefono, "clave-nueva-456")
    assert relogin_nuevo.status_code == 200
    assert relogin_nuevo.json()["debe_cambiar_password"] is False


async def test_cambiar_password_limpia_el_forzar_cambio(client, db):
    await crear_usuario_activo(db, usuario_id="admin-pw-2", telefono="+593900000704", roles=["admin_sistema"])
    headers_admin = auth_headers("admin-pw-2", ["admin_sistema"])
    creado = await _crear_staff(
        client, headers_admin, nombre="Forzado", telefono="+593900000705", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]

    login = await _login(client, "+593900000705", "clave-larga-123")
    assert login.json()["debe_cambiar_password"] is True
    headers_afectado = {"Authorization": f"Bearer {login.json()['access_token']}"}

    body_cambio = {"password_actual": "clave-larga-123", "password_nueva": "otra-clave-789"}
    await client.post("/auth/cambiar-password", headers=headers_afectado, json=body_cambio)

    usuario = await db.usuarios.find_one({"_id": usuario_id})
    assert usuario["forzar_cambio_password"] is False

    relogin = await _login(client, "+593900000705", "otra-clave-789")
    assert relogin.json()["debe_cambiar_password"] is False
