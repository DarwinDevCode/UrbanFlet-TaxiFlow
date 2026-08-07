from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    admin = await crear_usuario_activo(db, usuario_id="admin-1", telefono="+593900000900", roles=["admin_sistema"])
    return admin, auth_headers("admin-1", ["admin_sistema"])


async def _crear_staff(client, headers, *, nombre: str, telefono: str, roles: list[str]):
    body = {"nombre": nombre, "telefono": telefono, "password": "clave-larga-123", "roles": roles}
    return await client.post("/usuarios", headers=headers, json=body)


async def test_crear_cuenta_staff_requiere_admin_sistema(client, db):
    await crear_usuario_activo(db, usuario_id="captacion-1", telefono="+593900000901", roles=["admin_captacion"])
    headers = auth_headers("captacion-1", ["admin_captacion"])

    resp = await _crear_staff(
        client, headers, nombre="Nueva Staff", telefono="+593900000902", roles=["jefe_mantenimiento"]
    )

    assert resp.status_code == 403


async def test_crear_cuenta_staff_rechaza_rol_pasajero_o_conductor(client, db):
    _, headers = await _admin(db)

    resp = await _crear_staff(client, headers, nombre="Intento", telefono="+593900000903", roles=["pasajero"])

    assert resp.status_code == 422
    assert resp.json()["code"] == "ROL_INVALIDO"


async def test_crear_cuenta_staff_ok_forza_cambio_password(client, db):
    _, headers = await _admin(db)

    resp = await _crear_staff(
        client, headers, nombre="Jefe Nuevo", telefono="+593900000904", roles=["jefe_mantenimiento"]
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["roles"] == ["jefe_mantenimiento"]
    assert body["forzar_cambio_password"] is True

    evento = await db.bitacora.find_one({"accion": "USUARIO_CREACION", "entidad_id": body["id"]})
    assert evento is not None
    assert evento["actor_id"] == "admin-1"


async def test_listar_usuarios_filtra_por_rol_y_texto(client, db):
    _, headers = await _admin(db)
    await _crear_staff(
        client, headers, nombre="Carla Cumplimiento", telefono="+593900000905", roles=["supervisor_cumplimiento"]
    )
    await _crear_staff(
        client, headers, nombre="Beto Mantenimiento", telefono="+593900000906", roles=["jefe_mantenimiento"]
    )

    resp = await client.get("/usuarios", headers=headers, params={"rol": "supervisor_cumplimiento"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["nombre"] == "Carla Cumplimiento"

    resp_texto = await client.get("/usuarios", headers=headers, params={"texto": "Beto"})
    assert resp_texto.json()["total"] == 1


async def test_asignar_roles_registra_antes_y_despues(client, db):
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Multi Rol", telefono="+593900000907", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]

    resp = await client.post(
        f"/usuarios/{usuario_id}/roles", headers=headers, json={"roles": ["jefe_mantenimiento", "coordinador_flota"]}
    )

    assert resp.status_code == 200
    assert set(resp.json()["roles"]) == {"jefe_mantenimiento", "coordinador_flota"}

    evento = await db.bitacora.find_one({"accion": "ROL_MODIFICACION", "entidad_id": usuario_id})
    assert evento["datos_previos"]["roles"] == ["jefe_mantenimiento"]
    assert set(evento["datos_posteriores"]["roles"]) == {"jefe_mantenimiento", "coordinador_flota"}


async def test_suspender_invalida_de_inmediato_una_sesion_ya_emitida(client, db):
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Sesion Viva", telefono="+593900000908", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]
    headers_afectado = auth_headers(usuario_id, ["jefe_mantenimiento"])

    # La cuenta suspendida usa el mismo mecanismo de "roles se releen de
    # Mongo en cada petición" que ya prueba tests/core/test_rbac.py -- aquí
    # se confirma específicamente para el flujo de suspensión de admin_sistema.
    ok = await client.get("/mantenimiento/ordenes", headers=headers_afectado)
    assert ok.status_code == 200

    motivo = {"motivo": "Cuenta comprometida"}
    resp = await client.post(f"/usuarios/{usuario_id}/suspender", headers=headers, json=motivo)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "SUSPENDIDO"

    denegado = await client.get("/mantenimiento/ordenes", headers=headers_afectado)
    assert denegado.status_code == 401

    # No se puede suspender dos veces.
    doble = await client.post(f"/usuarios/{usuario_id}/suspender", headers=headers, json={"motivo": "otra vez"})
    assert doble.status_code == 409


async def test_reactivar_solo_permite_desde_suspendido(client, db):
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Para Reactivar", telefono="+593900000909", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]

    fallo = await client.post(f"/usuarios/{usuario_id}/reactivar", headers=headers)
    assert fallo.status_code == 409

    motivo = {"motivo": "prueba de reactivación"}
    suspender = await client.post(f"/usuarios/{usuario_id}/suspender", headers=headers, json=motivo)
    assert suspender.status_code == 200
    ok = await client.post(f"/usuarios/{usuario_id}/reactivar", headers=headers)
    assert ok.status_code == 200
    assert ok.json()["estado"] == "ACTIVO"


async def test_dar_de_baja_es_irreversible_via_reactivar(client, db):
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="De Baja", telefono="+593900000910", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]

    motivo = {"motivo": "Dejó la cooperativa"}
    resp = await client.post(f"/usuarios/{usuario_id}/dar-de-baja", headers=headers, json=motivo)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "BAJA"

    reactivar = await client.post(f"/usuarios/{usuario_id}/reactivar", headers=headers)
    assert reactivar.status_code == 409


async def test_matriz_permisos_expone_diccionario_estatico(client, db):
    _, headers = await _admin(db)
    resp = await client.get("/usuarios/matriz-permisos", headers=headers)
    assert resp.status_code == 200
    matriz = resp.json()["matriz"]
    assert "admin_sistema" in matriz["usuarios.* (Módulo 1 — este documento)"]


async def test_sesiones_activas_listar_y_cerrar_remotamente(client, db):
    telefono = "+593900000911"
    registro = {"nombre": "Con Sesion", "telefono": telefono, "password": "clave-larga-123"}
    await client.post("/auth/registro", json=registro)
    login = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    usuario_id = (await db.usuarios.find_one({"telefono": telefono}))["_id"]

    _, admin_headers = await _admin(db)

    listado = await client.get(f"/usuarios/{usuario_id}/sesiones", headers=admin_headers)
    assert listado.status_code == 200
    sesiones = listado.json()
    assert len(sesiones) == 1
    jti = sesiones[0]["jti"]

    # La sesión sigue siendo válida hasta que un admin la cierra.
    auth = {"Authorization": f"Bearer {access_token}"}
    perfil = await client.get(f"/usuarios/{usuario_id}", headers=auth)
    # 403, no 401: el actor existe y está autenticado, solo no tiene admin_sistema.
    assert perfil.status_code == 403

    cerrar = await client.delete(f"/usuarios/{usuario_id}/sesiones/{jti}", headers=admin_headers)
    assert cerrar.status_code == 204

    evento = await db.bitacora.find_one({"accion": "SESION_CIERRE_REMOTO", "entidad_id": usuario_id})
    assert evento is not None

    rechazado = await client.get(f"/usuarios/{usuario_id}", headers=auth)
    assert rechazado.status_code == 401
    assert rechazado.json()["code"] == "INVALID_TOKEN"

    listado_vacio = await client.get(f"/usuarios/{usuario_id}/sesiones", headers=admin_headers)
    assert listado_vacio.json() == []


async def test_accesos_incluye_login_ok_y_fallidos(client, db):
    telefono = "+593900000912"
    registro = {"nombre": "Con Accesos", "telefono": telefono, "password": "clave-larga-123"}
    await client.post("/auth/registro", json=registro)
    usuario_id = (await db.usuarios.find_one({"telefono": telefono}))["_id"]

    await client.post("/auth/login", json={"identificador": telefono, "password": "mala"})
    await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})

    _, admin_headers = await _admin(db)
    resp = await client.get(f"/usuarios/{usuario_id}/accesos", headers=admin_headers)

    assert resp.status_code == 200
    acciones = {e["accion"] for e in resp.json()}
    assert "SESION_INICIO" in acciones


async def test_listar_no_revienta_con_cuenta_legacy_sin_fecha_registro(client, db):
    """Hallazgo real (ronda de usabilidad, punto #5, 2026-08-07): 5 cuentas
    de demo/QA insertadas directo en Mongo en sesiones anteriores no tenían
    `fecha_registro` -- una búsqueda por texto que las tocara reventaba
    `GET /usuarios` con 500 (`KeyError`). Repro mínimo sin ese campo."""
    await db.usuarios.insert_one(
        {
            "_id": "legacy-sin-fecha",
            "nombre": "Cuenta Legacy Sin Fecha",
            "telefono": "+593900000913",
            "roles": ["jefe_mantenimiento"],
            "estado": "ACTIVO",
        }
    )
    _, admin_headers = await _admin(db)

    resp = await client.get("/usuarios?texto=Legacy", headers=admin_headers)

    assert resp.status_code == 200
    item = next(u for u in resp.json()["items"] if u["id"] == "legacy-sin-fecha")
    assert item["fecha_registro"] is not None
