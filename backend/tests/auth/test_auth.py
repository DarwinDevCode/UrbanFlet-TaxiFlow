async def test_registro_con_telefono_crea_usuario_activo(client, db):
    resp = await client.post(
        "/auth/registro",
        json={"nombre": "Ana Pérez", "telefono": "+593911111111", "password": "clave-larga-123"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "ACTIVO"
    usuario = await db.usuarios.find_one({"_id": body["usuario_id"]})
    assert usuario["telefono"] == "+593911111111"
    assert usuario["estado"] == "ACTIVO"
    # La contraseña nunca se guarda en claro.
    assert usuario["hash_password"] != "clave-larga-123"


async def test_registro_con_solo_email_tambien_funciona(client, db):
    resp = await client.post(
        "/auth/registro",
        json={"nombre": "Luis Solo Email", "email": "luis@example.com", "password": "clave-larga-123"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["telefono"] is None
    usuario = await db.usuarios.find_one({"_id": body["usuario_id"]})
    assert "telefono" not in usuario
    assert usuario["email"] == "luis@example.com"


async def test_registro_sin_telefono_ni_email_devuelve_422(client):
    resp = await client.post("/auth/registro", json={"nombre": "Nadie", "password": "clave-larga-123"})

    assert resp.status_code == 422


async def test_registro_sin_password_devuelve_422(client):
    resp = await client.post("/auth/registro", json={"nombre": "Sin Clave", "telefono": "+593911111100"})

    assert resp.status_code == 422


async def test_registro_telefono_duplicado_devuelve_409(client):
    payload = {"nombre": "Ana", "telefono": "+593922222222", "password": "clave-larga-123"}
    await client.post("/auth/registro", json=payload)
    resp = await client.post("/auth/registro", json=payload)

    assert resp.status_code == 409
    assert resp.json()["code"] == "PHONE_ALREADY_REGISTERED"


async def test_registro_email_duplicado_devuelve_409(client):
    payload = {"nombre": "Beto", "email": "beto@example.com", "password": "clave-larga-123"}
    await client.post("/auth/registro", json=payload)
    resp = await client.post("/auth/registro", json={**payload, "nombre": "Beto Dos"})

    assert resp.status_code == 409
    assert resp.json()["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_login_con_telefono_correcto(client):
    telefono = "+593933333333"
    await client.post(
        "/auth/registro", json={"nombre": "Marta", "telefono": telefono, "password": "clave-larga-123"}
    )

    resp = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]


async def test_login_con_email_correcto(client):
    email = "sofia@example.com"
    await client.post("/auth/registro", json={"nombre": "Sofía", "email": email, "password": "clave-larga-123"})

    resp = await client.post("/auth/login", json={"identificador": email, "password": "clave-larga-123"})

    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_con_password_incorrecta_devuelve_401(client):
    telefono = "+593944444444"
    await client.post(
        "/auth/registro", json={"nombre": "Pedro", "telefono": telefono, "password": "clave-larga-123"}
    )

    resp = await client.post("/auth/login", json={"identificador": telefono, "password": "otra-clave"})

    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


async def test_login_con_identificador_inexistente_devuelve_401(client):
    resp = await client.post("/auth/login", json={"identificador": "+593955555555", "password": "cualquiera"})

    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


async def test_login_registra_evento_de_auditoria_antes_de_la_sesion(client, db):
    telefono = "+593966666666"
    registro = await client.post(
        "/auth/registro", json={"nombre": "Carla", "telefono": telefono, "password": "clave-larga-123"}
    )
    usuario_id = registro.json()["usuario_id"]

    resp = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})

    assert resp.status_code == 200
    evento = await db.bitacora.find_one({"accion": "SESION_INICIO", "entidad_id": usuario_id})
    assert evento is not None
    assert evento["datos_posteriores"]["metodo"] == "password"


async def test_login_bloquea_tras_intentos_fallidos_consecutivos(client, db):
    telefono = "+593977777777"
    await client.post(
        "/auth/registro", json={"nombre": "Iván", "telefono": telefono, "password": "clave-larga-123"}
    )

    for _ in range(5):
        resp = await client.post("/auth/login", json={"identificador": telefono, "password": "incorrecta"})
        assert resp.status_code == 401

    resp = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})

    assert resp.status_code == 429
    assert resp.json()["code"] == "TOO_MANY_LOGIN_ATTEMPTS"

    evento = await db.bitacora.find_one({"accion": "LOGIN_FALLIDO_CONSECUTIVO"})
    assert evento is not None


async def test_login_bloquea_identificador_inexistente_tras_intentos_fallidos(client):
    identificador = "+593977788899"

    for _ in range(5):
        resp = await client.post("/auth/login", json={"identificador": identificador, "password": "cualquiera"})
        assert resp.status_code == 401

    resp = await client.post("/auth/login", json={"identificador": identificador, "password": "cualquiera"})

    assert resp.status_code == 429
    assert resp.json()["code"] == "TOO_MANY_LOGIN_ATTEMPTS"


async def test_login_correcto_resetea_contador_de_fallos(client):
    telefono = "+593977766655"
    await client.post(
        "/auth/registro", json={"nombre": "Nora", "telefono": telefono, "password": "clave-larga-123"}
    )

    for _ in range(3):
        resp = await client.post("/auth/login", json={"identificador": telefono, "password": "incorrecta"})
        assert resp.status_code == 401

    resp = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})
    assert resp.status_code == 200

    for _ in range(3):
        resp = await client.post("/auth/login", json={"identificador": telefono, "password": "incorrecta"})
        assert resp.status_code == 401

    resp = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})
    assert resp.status_code == 200


async def test_flujo_completo_registro_login_refresh(client, db):
    telefono = "+593988811122"

    registro = await client.post(
        "/auth/registro", json={"nombre": "Carla Vera", "telefono": telefono, "password": "clave-larga-456"}
    )
    assert registro.status_code == 201
    assert registro.json()["estado"] == "ACTIVO"

    login = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-456"})
    assert login.status_code == 200
    tokens_login = login.json()
    assert tokens_login["access_token"] and tokens_login["refresh_token"]

    refresh = await client.post("/auth/refresh", json={"refresh_token": tokens_login["refresh_token"]})
    assert refresh.status_code == 200
    tokens_refrescados = refresh.json()
    assert tokens_refrescados["access_token"] != tokens_login["access_token"]
