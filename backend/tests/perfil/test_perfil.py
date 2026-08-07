import jwt

from tests.utils import auth_headers, crear_usuario_activo


def _jti_del_header(headers: dict) -> str:
    token = headers["Authorization"].removeprefix("Bearer ")
    return jwt.decode(token, options={"verify_signature": False})["jti"]


async def _registrar_y_loguear(
    client, *, telefono: str, nombre: str = "Perfil Prueba", password: str = "clave-larga-123"
):
    # Se registra vía CU-O02 (pasajero) en vez de /auth/registro genérico --
    # este último no asigna ningún rol (`roles: []`), y los tests de este
    # archivo necesitan una cuenta con un rol real para probar `GET /perfil`.
    await client.post(
        "/captacion/pasajeros/registro",
        json={"nombre": nombre, "telefono": telefono, "password": password, "version_consentimiento": "v1-test"},
    )
    login = await client.post("/auth/login", json={"identificador": telefono, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_obtener_perfil_devuelve_los_datos_propios(client):
    telefono = "+593900000900"
    headers = await _registrar_y_loguear(client, telefono=telefono, nombre="Ver Mi Perfil")

    resp = await client.get("/perfil", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["nombre"] == "Ver Mi Perfil"
    assert body["telefono"] == telefono
    assert body["roles"] == ["pasajero"]


async def test_editar_perfil_requiere_password_actual_correcta(client, db):
    telefono = "+593900000901"
    headers = await _registrar_y_loguear(client, telefono=telefono)

    fallo = await client.patch(
        "/perfil", headers=headers, json={"nombre": "Nombre Nuevo", "password_actual": "incorrecta"}
    )
    assert fallo.status_code == 401

    usuario = await db.usuarios.find_one({"telefono": telefono})
    assert usuario["nombre"] != "Nombre Nuevo"


async def test_editar_perfil_cambia_nombre_y_queda_auditado(client, db):
    telefono = "+593900000902"
    headers = await _registrar_y_loguear(client, telefono=telefono)

    resp = await client.patch(
        "/perfil", headers=headers, json={"nombre": "Nombre Actualizado", "password_actual": "clave-larga-123"}
    )

    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Nombre Actualizado"

    usuario = await db.usuarios.find_one({"telefono": telefono})
    assert usuario["nombre"] == "Nombre Actualizado"

    evento = await db.bitacora.find_one({"accion": "PERFIL_EDICION", "entidad_id": usuario["_id"]})
    assert evento is not None
    assert evento["datos_posteriores"] == {"nombre": "Nombre Actualizado"}


async def test_editar_perfil_nunca_expone_roles_en_el_schema(client):
    telefono = "+593900000903"
    headers = await _registrar_y_loguear(client, telefono=telefono)

    resp = await client.patch(
        "/perfil",
        headers=headers,
        json={"nombre": "Intento Rol", "roles": ["admin_sistema"], "password_actual": "clave-larga-123"},
    )

    # `roles` no es un campo del schema `PerfilEditar` -- Pydantic lo ignora
    # (no falla, pero tampoco lo aplica), el rol real de la cuenta no cambia.
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["pasajero"]


async def test_editar_telefono_duplicado_devuelve_409(client):
    await _registrar_y_loguear(client, telefono="+593900000904", nombre="Dueño Original")
    headers_b = await _registrar_y_loguear(client, telefono="+593900000905", nombre="Segundo Usuario")

    resp = await client.patch(
        "/perfil", headers=headers_b, json={"telefono": "+593900000904", "password_actual": "clave-larga-123"}
    )

    assert resp.status_code == 409


async def test_listar_y_cerrar_una_segunda_sesion_propia(client):
    # Dos sesiones reales del mismo usuario (ej. dos dispositivos) -- se
    # cierra la SEGUNDA usando la PRIMERA, para no invalidar el propio
    # token con el que se hace la petición (cerrar tu sesión activa te
    # desloguea de inmediato, comportamiento correcto pero no lo que este
    # test quiere probar).
    telefono = "+593900000906"
    headers_1 = await _registrar_y_loguear(client, telefono=telefono)
    login_2 = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})
    headers_2 = {"Authorization": f"Bearer {login_2.json()['access_token']}"}

    listado = await client.get("/perfil/sesiones", headers=headers_1)
    assert listado.status_code == 200
    assert len(listado.json()) == 2

    jti_a_cerrar = next(s["jti"] for s in listado.json() if s["jti"] != _jti_del_header(headers_1))
    cierre = await client.delete(f"/perfil/sesiones/{jti_a_cerrar}", headers=headers_1)
    assert cierre.status_code == 204

    listado_tras_cierre = await client.get("/perfil/sesiones", headers=headers_1)
    assert len(listado_tras_cierre.json()) == 1
    assert listado_tras_cierre.json()[0]["jti"] != jti_a_cerrar

    # La sesión cerrada quedó realmente inválida -- headers_2 ya no sirve.
    reintento = await client.get("/perfil", headers=headers_2)
    assert reintento.status_code == 401


async def test_perfil_requiere_autenticacion(client):
    resp = await client.get("/perfil")
    assert resp.status_code == 401


async def test_cuenta_de_personal_interno_tambien_ve_su_propio_perfil(client, db):
    # Sección 3.1 de la spec: "Mi cuenta" debe ser visible para todos los
    # roles internos, no solo pasajero/conductor.
    await crear_usuario_activo(db, usuario_id="staff-perfil-1", telefono="+593900000907", roles=["jefe_mantenimiento"])
    headers_staff = auth_headers("staff-perfil-1", ["jefe_mantenimiento"])

    resp = await client.get("/perfil", headers=headers_staff)

    assert resp.status_code == 200
    assert "jefe_mantenimiento" in resp.json()["roles"]
