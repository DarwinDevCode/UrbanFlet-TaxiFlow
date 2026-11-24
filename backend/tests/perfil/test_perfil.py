import jwt

from src.archivos import service as archivos_service
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


async def test_editar_foto_perfil_no_exige_password(client, db, monkeypatch, tmp_path):
    """Ronda de foto de perfil: `PATCH /perfil/foto` es un endpoint separado
    de `PATCH /perfil` a propósito -- no exige `password_actual` (ver
    docstring de `PerfilFotoEditar`)."""
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    telefono = "+593900000910"
    headers = await _registrar_y_loguear(client, telefono=telefono)

    subida = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "foto_perfil"},
        files={"file": ("foto.jpg", b"una-foto-real", "image/jpeg")},
    )
    assert subida.status_code == 201
    archivo_id = subida.json()["id"]

    resp = await client.patch("/perfil/foto", headers=headers, json={"archivo_id": archivo_id})
    assert resp.status_code == 200
    assert resp.json()["foto_url"] == archivo_id

    usuario = await db.usuarios.find_one({"telefono": telefono})
    assert usuario["foto_url"] == archivo_id
    evento = await db.bitacora.find_one({"accion": "PERFIL_EDICION", "entidad_id": usuario["_id"]})
    assert evento is not None
    assert evento["datos_posteriores"] == {"foto_url": archivo_id}


async def test_editar_foto_perfil_con_null_la_quita(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    telefono = "+593900000911"
    headers = await _registrar_y_loguear(client, telefono=telefono)
    subida = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "foto_perfil"},
        files={"file": ("foto.jpg", b"otra-foto", "image/jpeg")},
    )
    archivo_id = subida.json()["id"]
    await client.patch("/perfil/foto", headers=headers, json={"archivo_id": archivo_id})

    resp = await client.patch("/perfil/foto", headers=headers, json={"archivo_id": None})
    assert resp.status_code == 200
    assert resp.json()["foto_url"] is None


async def test_editar_foto_perfil_rechaza_archivo_ajeno(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    headers_dueno = await _registrar_y_loguear(client, telefono="+593900000912", nombre="Dueño de la foto")
    subida = await client.post(
        "/archivos",
        headers=headers_dueno,
        data={"contexto": "foto_perfil"},
        files={"file": ("foto.jpg", b"foto-del-dueno", "image/jpeg")},
    )
    archivo_id = subida.json()["id"]

    headers_otro = await _registrar_y_loguear(client, telefono="+593900000913", nombre="Otro Usuario")
    resp = await client.patch("/perfil/foto", headers=headers_otro, json={"archivo_id": archivo_id})
    assert resp.status_code == 422
    assert resp.json()["code"] == "ARCHIVO_NO_VALIDO_PARA_FOTO"


async def test_editar_foto_perfil_rechaza_archivo_de_otro_contexto(client, db, monkeypatch, tmp_path):
    """Un archivo subido como evidencia de falla no se puede reciclar como
    foto de perfil, aunque sea del propio dueño -- contextos distintos."""
    monkeypatch.setattr(archivos_service, "_ruta_archivos", lambda: tmp_path)
    await crear_usuario_activo(db, usuario_id="cond-foto-1", telefono="+593900000914", roles=["conductor"])
    headers = auth_headers("cond-foto-1", ["conductor"])
    subida = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "reporte_falla"},
        files={"file": ("foto.jpg", b"evidencia-no-foto", "image/jpeg")},
    )
    archivo_id = subida.json()["id"]

    resp = await client.patch("/perfil/foto", headers=headers, json={"archivo_id": archivo_id})
    assert resp.status_code == 422
    assert resp.json()["code"] == "ARCHIVO_NO_VALIDO_PARA_FOTO"


async def test_cuenta_de_personal_interno_tambien_ve_su_propio_perfil(client, db):
    # Sección 3.1 de la spec: "Mi cuenta" debe ser visible para todos los
    # roles internos, no solo pasajero/conductor.
    await crear_usuario_activo(db, usuario_id="staff-perfil-1", telefono="+593900000907", roles=["jefe_mantenimiento"])
    headers_staff = auth_headers("staff-perfil-1", ["jefe_mantenimiento"])

    resp = await client.get("/perfil", headers=headers_staff)

    assert resp.status_code == 200
    assert "jefe_mantenimiento" in resp.json()["roles"]


# ---------------------------------------------------------------------------
# Autoservicio de baja de cuenta (periodo de gracia de 30 días)
# ---------------------------------------------------------------------------


async def test_solicitar_baja_deja_la_cuenta_activa_con_30_dias(client, db):
    """Durante el periodo de gracia la cuenta sigue funcionando: el punto es
    poder arrepentirse, no perder el acceso de inmediato."""
    await crear_usuario_activo(db, usuario_id="baja-1", telefono="+593900002001", roles=["pasajero"])
    headers = auth_headers("baja-1", ["pasajero"])

    resp = await client.post("/perfil/baja-cuenta", headers=headers, json={"motivo": "Ya no lo uso"})

    assert resp.status_code == 200
    assert resp.json()["dias_restantes_baja"] == 29  # 30 días menos el parcial de hoy
    usuario = await db.usuarios.find_one({"_id": "baja-1"})
    assert usuario["estado"] == "ACTIVO"
    assert usuario["baja_efectiva_en"] is not None
    # Sigue pudiendo usar el sistema con normalidad.
    perfil = await client.get("/perfil", headers=headers)
    assert perfil.status_code == 200


async def test_cancelar_baja_borra_todo_rastro(client, db):
    await crear_usuario_activo(db, usuario_id="baja-2", telefono="+593900002002", roles=["pasajero"])
    headers = auth_headers("baja-2", ["pasajero"])
    await client.post("/perfil/baja-cuenta", headers=headers, json={"motivo": None})

    resp = await client.delete("/perfil/baja-cuenta", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["dias_restantes_baja"] is None
    usuario = await db.usuarios.find_one({"_id": "baja-2"})
    assert "baja_efectiva_en" not in usuario
    assert "baja_solicitada_en" not in usuario


async def test_no_permite_dos_bajas_simultaneas(client, db):
    await crear_usuario_activo(db, usuario_id="baja-3", telefono="+593900002003", roles=["pasajero"])
    headers = auth_headers("baja-3", ["pasajero"])
    await client.post("/perfil/baja-cuenta", headers=headers, json={"motivo": None})

    segunda = await client.post("/perfil/baja-cuenta", headers=headers, json={"motivo": None})

    assert segunda.status_code == 409
    assert segunda.json()["code"] == "BAJA_YA_SOLICITADA"


async def test_cancelar_sin_baja_en_curso_es_conflicto(client, db):
    await crear_usuario_activo(db, usuario_id="baja-4", telefono="+593900002004", roles=["pasajero"])
    headers = auth_headers("baja-4", ["pasajero"])

    resp = await client.delete("/perfil/baja-cuenta", headers=headers)

    assert resp.status_code == 409
    assert resp.json()["code"] == "SIN_BAJA_EN_CURSO"


async def test_no_permite_solicitar_baja_con_viaje_activo(client, db):
    """Reusa el MISMO guard que la baja administrativa -- no una copia."""
    await crear_usuario_activo(db, usuario_id="baja-5", telefono="+593900002005", roles=["pasajero"])
    headers = auth_headers("baja-5", ["pasajero"])
    await db.viajes.insert_one(
        {"_id": "viaje-baja-auto", "pasajero_id": "baja-5", "conductor_id": "x", "estado": "EN_CURSO"}
    )

    resp = await client.post("/perfil/baja-cuenta", headers=headers, json={"motivo": None})

    assert resp.status_code == 409
    assert resp.json()["code"] == "BAJA_CON_VIAJE_ACTIVO"


async def test_solicitar_baja_advierte_del_vehiculo_habilitado(client, db):
    """Caso borde 2 reusado, no duplicado: la baja NO se bloquea por tener un
    vehículo habilitado (a diferencia del viaje activo), pero sí se avisa qué
    saldrá de la flota -- mismo criterio que la baja administrativa."""
    usuario = await crear_usuario_activo(db, usuario_id="baja-veh", telefono="+593900004100", roles=["conductor"])
    await db.vehiculos.insert_one(
        {"_id": "veh-baja-1", "placa": "AAA-1111", "marca": "Chevrolet", "modelo": "Sail",
         "propietario_id": usuario["_id"], "estado_habilitacion": "HABILITADO"}
    )

    resp = await client.post(
        "/perfil/baja-cuenta", headers=auth_headers("baja-veh", ["conductor"]), json={}
    )

    assert resp.status_code == 200
    assert resp.json()["vehiculos_a_retirar"] == ["AAA-1111"]
    assert resp.json()["dias_restantes_baja"] == 29
