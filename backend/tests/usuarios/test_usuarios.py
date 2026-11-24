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


async def test_crear_cuenta_staff_sin_password_genera_una_automatica(client, db):
    _, headers = await _admin(db)

    resp = await client.post(
        "/usuarios",
        headers=headers,
        json={"nombre": "Sin Password", "telefono": "+593900000950", "roles": ["jefe_mantenimiento"]},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["password_generada"] is not None
    assert len(body["password_generada"]) >= 12
    assert any(c.isalpha() for c in body["password_generada"])
    assert any(c.isdigit() for c in body["password_generada"])
    assert body["forzar_cambio_password"] is True

    # La contraseña generada debe servir de verdad para iniciar sesión.
    login = await client.post(
        "/auth/login", json={"identificador": "+593900000950", "password": body["password_generada"]}
    )
    assert login.status_code == 200


async def test_crear_cuenta_staff_con_password_propia_no_hace_eco(client, db):
    _, headers = await _admin(db)

    resp = await _crear_staff(
        client, headers, nombre="Con Password", telefono="+593900000951", roles=["jefe_mantenimiento"]
    )

    assert resp.status_code == 201
    assert resp.json()["password_generada"] is None


async def test_restablecer_password_requiere_admin_sistema(client, db):
    admin, _headers_admin = await _admin(db)
    await crear_usuario_activo(db, usuario_id="otro-1", telefono="+593900000952", roles=["jefe_mantenimiento"])
    headers_otro = auth_headers("otro-1", ["jefe_mantenimiento"])

    resp = await client.post(f"/usuarios/{admin['_id']}/restablecer-password", headers=headers_otro)
    assert resp.status_code == 403


async def test_restablecer_password_ok_genera_una_nueva_y_permite_login(client, db):
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="A Restablecer", telefono="+593900000953", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]

    resp = await client.post(f"/usuarios/{usuario_id}/restablecer-password", headers=headers)

    assert resp.status_code == 200
    nueva_password = resp.json()["password_generada"]
    assert len(nueva_password) >= 12

    # La contraseña vieja ya no sirve.
    login_vieja = await client.post(
        "/auth/login", json={"identificador": "+593900000953", "password": "clave-larga-123"}
    )
    assert login_vieja.status_code == 401

    # La nueva sí, y exige cambiarla.
    login_nueva = await client.post(
        "/auth/login", json={"identificador": "+593900000953", "password": nueva_password}
    )
    assert login_nueva.status_code == 200
    assert login_nueva.json()["debe_cambiar_password"] is True

    evento = await db.bitacora.find_one(
        {"accion": "USUARIO_PASSWORD_RESTABLECIDA", "entidad_id": usuario_id}
    )
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


async def test_listar_y_obtener_usuario_incluyen_foto_url(client, db):
    """Ronda de fotos en historial/usuarios: mismo campo general de
    `usuarios.foto_url` que ya expone `PerfilOut` (autoservicio) -- acá
    Administración lo consume vía el mismo `_to_out()` que ya usan tanto el
    listado como `GET /usuarios/{id}`."""
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Con Foto", telefono="+593900000920", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]
    await db.usuarios.update_one({"_id": usuario_id}, {"$set": {"foto_url": "archivo-foto-usuario-1"}})

    resp_lista = await client.get("/usuarios", headers=headers, params={"texto": "Con Foto"})
    assert resp_lista.status_code == 200
    assert resp_lista.json()["items"][0]["foto_url"] == "archivo-foto-usuario-1"

    resp_detalle = await client.get(f"/usuarios/{usuario_id}", headers=headers)
    assert resp_detalle.status_code == 200
    assert resp_detalle.json()["foto_url"] == "archivo-foto-usuario-1"


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


async def test_no_permite_dar_de_baja_con_viaje_activo(client, db):
    """Caso borde de la baja lógica (ronda de personalización/QA): un viaje
    vivo deja al pasajero esperando y al viaje sin actor que pueda cerrarlo,
    así que la baja se BLOQUEA con 409 en vez de permitirse en silencio."""
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Con Viaje", telefono="+593900000920", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]
    await db.viajes.insert_one(
        {"_id": "viaje-activo-baja", "conductor_id": usuario_id, "pasajero_id": "otro", "estado": "EN_CURSO"}
    )

    resp = await client.post(
        f"/usuarios/{usuario_id}/dar-de-baja", headers=headers, json={"motivo": "Renunció"}
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "BAJA_CON_VIAJE_ACTIVO"
    # La cuenta NO cambió de estado -- el guard corta antes de escribir.
    sigue = await client.get(f"/usuarios/{usuario_id}", headers=headers)
    assert sigue.json()["estado"] == "ACTIVO"


async def test_permite_dar_de_baja_con_viaje_ya_terminado(client, db):
    """Contraparte del test anterior: un viaje que ya no está vivo no bloquea
    nada -- si no, una cuenta con historial nunca podría darse de baja."""
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Sin Viaje Vivo", telefono="+593900000921", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]
    await db.viajes.insert_one(
        {"_id": "viaje-pagado-baja", "conductor_id": usuario_id, "pasajero_id": "otro", "estado": "PAGADO"}
    )

    resp = await client.post(
        f"/usuarios/{usuario_id}/dar-de-baja", headers=headers, json={"motivo": "Renunció"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "BAJA"


async def test_baja_de_socio_retira_su_vehiculo_de_la_flota(db, client):
    """Decisión 2: al dar de baja al socio, su vehículo HABILITADO sale
    automáticamente del pool de despacho, con el MISMO estado que usa la baja
    manual de un vehículo (`DADO_DE_BAJA`), y trazable al evento que lo
    originó."""
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Socio Con Auto", telefono="+593900000930", roles=["jefe_mantenimiento"]
    )
    usuario_id = creado.json()["id"]
    await db.vehiculos.insert_one(
        {
            "_id": "veh-baja-auto",
            "placa": "AUT-0001",
            "marca": "X",
            "modelo": "Y",
            "estado_habilitacion": "HABILITADO",
            "propietario_id": usuario_id,
        }
    )

    resp = await client.post(
        f"/usuarios/{usuario_id}/dar-de-baja", headers=headers, json={"motivo": "Dejó la cooperativa"}
    )

    assert resp.status_code == 200
    vehiculo = await db.vehiculos.find_one({"_id": "veh-baja-auto"})
    assert vehiculo["estado_habilitacion"] == "DADO_DE_BAJA"

    evento = await db.bitacora.find_one({"accion": "VEHICULO_BAJA", "entidad_id": "veh-baja-auto"})
    assert evento is not None
    # Trazable: referencia explícita a la baja de la cuenta que lo originó.
    assert evento["datos_posteriores"]["origen"] == f"usuario_baja:{usuario_id}"


async def test_baja_de_socio_sin_vehiculo_no_falla(db, client):
    """Contraparte: la mayoría del personal interno no tiene vehículo -- la
    baja no debe depender de que exista uno."""
    _, headers = await _admin(db)
    creado = await _crear_staff(
        client, headers, nombre="Sin Auto", telefono="+593900000931", roles=["admin_financiero"]
    )
    usuario_id = creado.json()["id"]

    resp = await client.post(
        f"/usuarios/{usuario_id}/dar-de-baja", headers=headers, json={"motivo": "Renunció"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "BAJA"


# ---------------------------------------------------------------------------
# Vencimiento del periodo de gracia (job diario)
# ---------------------------------------------------------------------------


async def test_procesar_bajas_vencidas_aplica_la_baja_logica(db):
    """Al vencer el plazo, la cuenta usa el MISMO mecanismo de baja lógica que
    la baja administrativa: estado BAJA, documento conservado. NO se dispara
    la anonimización de CU-O17 A2 -- son intenciones distintas."""
    from datetime import UTC, datetime, timedelta

    from src.usuarios import service as usuarios_service

    await crear_usuario_activo(db, usuario_id="venc-1", telefono="+593900003001", roles=["pasajero"])
    await db.usuarios.update_one(
        {"_id": "venc-1"},
        {"$set": {"baja_efectiva_en": datetime.now(UTC) - timedelta(days=1), "baja_solicitada_en": datetime.now(UTC)}},
    )

    resultado = await usuarios_service.procesar_bajas_vencidas(db)

    assert resultado["aplicadas"] == 1
    usuario = await db.usuarios.find_one({"_id": "venc-1"})
    assert usuario["estado"] == "BAJA"
    # El documento sigue existiendo y los datos personales NO se anonimizaron.
    assert usuario["telefono"] == "+593900003001"
    evento = await db.bitacora.find_one({"accion": "CUENTA_BAJA_EFECTIVA", "entidad_id": "venc-1"})
    assert evento is not None


async def test_procesar_bajas_no_toca_las_que_aun_no_vencen(db):
    from datetime import UTC, datetime, timedelta

    from src.usuarios import service as usuarios_service

    await crear_usuario_activo(db, usuario_id="venc-2", telefono="+593900003002", roles=["pasajero"])
    await db.usuarios.update_one(
        {"_id": "venc-2"}, {"$set": {"baja_efectiva_en": datetime.now(UTC) + timedelta(days=10)}}
    )

    resultado = await usuarios_service.procesar_bajas_vencidas(db)

    assert resultado["aplicadas"] == 0
    assert (await db.usuarios.find_one({"_id": "venc-2"}))["estado"] == "ACTIVO"


async def test_procesar_bajas_omite_cuenta_con_viaje_activo(db):
    """Si al vencer el plazo el titular está a mitad de un viaje, no se le
    corta el acceso -- queda para la corrida siguiente."""
    from datetime import UTC, datetime, timedelta

    from src.usuarios import service as usuarios_service

    await crear_usuario_activo(db, usuario_id="venc-3", telefono="+593900003003", roles=["conductor"])
    await db.usuarios.update_one(
        {"_id": "venc-3"}, {"$set": {"baja_efectiva_en": datetime.now(UTC) - timedelta(days=1)}}
    )
    await db.viajes.insert_one(
        {"_id": "viaje-venc-3", "conductor_id": "venc-3", "pasajero_id": "p", "estado": "EN_CURSO"}
    )

    resultado = await usuarios_service.procesar_bajas_vencidas(db)

    assert resultado["aplicadas"] == 0
    assert resultado["omitidas_por_viaje_activo"] == 1
    assert (await db.usuarios.find_one({"_id": "venc-3"}))["estado"] == "ACTIVO"


async def test_login_de_cuenta_dada_de_baja_da_mensaje_claro(client, db):
    """Punto 7: no un 'credenciales inválidas' genérico."""
    from src.core.security import hash_password

    await crear_usuario_activo(db, usuario_id="venc-4", telefono="+593900003004", roles=["pasajero"])
    await db.usuarios.update_one(
        {"_id": "venc-4"}, {"$set": {"estado": "BAJA", "hash_password": hash_password("ClaveLarga123!")}}
    )

    resp = await client.post(
        "/auth/login", json={"identificador": "+593900003004", "password": "ClaveLarga123!"}
    )

    assert resp.status_code == 403
    assert resp.json()["code"] == "CUENTA_DADA_DE_BAJA"
