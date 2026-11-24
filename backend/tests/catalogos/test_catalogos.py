from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-cat-1", telefono="+593900000550", roles=["admin_sistema"])
    return auth_headers("admin-cat-1", ["admin_sistema"])


async def test_solo_admin_sistema_gestiona_tipos_documento(client, db):
    await crear_usuario_activo(db, usuario_id="captacion-cat-1", telefono="+593900000551", roles=["admin_captacion"])
    headers = auth_headers("captacion-cat-1", ["admin_captacion"])

    resp = await client.post("/catalogos/tipos-documento", headers=headers, json={"nombre": "Cédula"})
    assert resp.status_code == 403


async def test_crear_listar_y_editar_tipo_documento(client, db):
    headers = await _admin(db)

    creado = await client.post(
        "/catalogos/tipos-documento", headers=headers, json={"nombre": "Licencia de conducir", "aplica_a": "conductor"}
    )
    assert creado.status_code == 201
    assert creado.json()["activo"] is True

    listado = await client.get("/catalogos/tipos-documento", headers=headers)
    assert any(t["nombre"] == "Licencia de conducir" for t in listado.json())

    tipo_id = creado.json()["id"]
    editado = await client.patch(f"/catalogos/tipos-documento/{tipo_id}", headers=headers, json={"activo": False})
    assert editado.status_code == 200
    assert editado.json()["activo"] is False

    evento = await db.bitacora.find_one({"accion": "CATALOGO_EDICION", "entidad_id": tipo_id})
    assert evento["datos_previos"] == {"activo": True}
    assert evento["datos_posteriores"] == {"activo": False}


async def test_tipo_documento_duplicado_devuelve_409(client, db):
    headers = await _admin(db)
    await client.post("/catalogos/tipos-documento", headers=headers, json={"nombre": "SOAT"})
    resp = await client.post("/catalogos/tipos-documento", headers=headers, json={"nombre": "SOAT"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "TIPO_DOCUMENTO_YA_EXISTE"


async def test_editar_tipo_documento_inexistente_devuelve_404(client, db):
    headers = await _admin(db)
    resp = await client.patch("/catalogos/tipos-documento/no-existe", headers=headers, json={"activo": False})
    assert resp.status_code == 404


async def test_crear_listar_y_editar_motivo(client, db):
    headers = await _admin(db)

    creado = await client.post(
        "/catalogos/motivos", headers=headers, json={"nombre": "Conductor no localizado", "categoria": "cancelacion"}
    )
    assert creado.status_code == 201

    listado = await client.get("/catalogos/motivos", headers=headers)
    assert any(m["nombre"] == "Conductor no localizado" for m in listado.json())

    motivo_id = creado.json()["id"]
    editado = await client.patch(
        f"/catalogos/motivos/{motivo_id}", headers=headers, json={"nombre": "Conductor no localizable"}
    )
    assert editado.status_code == 200
    assert editado.json()["nombre"] == "Conductor no localizable"


async def test_motivo_duplicado_devuelve_409(client, db):
    headers = await _admin(db)
    await client.post("/catalogos/motivos", headers=headers, json={"nombre": "GPS spoofing"})
    resp = await client.post("/catalogos/motivos", headers=headers, json={"nombre": "GPS spoofing"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "MOTIVO_YA_EXISTE"


async def test_crear_listar_y_editar_taller(client, db):
    headers = await _admin(db)

    creado = await client.post(
        "/catalogos/talleres", headers=headers, json={"nombre": "Taller Central", "direccion": "Av. Siempre Viva 123"}
    )
    assert creado.status_code == 201
    assert creado.json()["activo"] is True

    listado = await client.get("/catalogos/talleres", headers=headers)
    assert any(t["nombre"] == "Taller Central" for t in listado.json())

    taller_id = creado.json()["id"]
    editado = await client.patch(f"/catalogos/talleres/{taller_id}", headers=headers, json={"activo": False})
    assert editado.status_code == 200
    assert editado.json()["activo"] is False

    evento = await db.bitacora.find_one({"accion": "CATALOGO_EDICION", "entidad_id": taller_id})
    assert evento["datos_previos"] == {"activo": True}
    assert evento["datos_posteriores"] == {"activo": False}


async def test_taller_duplicado_devuelve_409(client, db):
    headers = await _admin(db)
    await client.post("/catalogos/talleres", headers=headers, json={"nombre": "Taller Norte"})
    resp = await client.post("/catalogos/talleres", headers=headers, json={"nombre": "Taller Norte"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "TALLER_YA_EXISTE"


async def test_editar_taller_inexistente_devuelve_404(client, db):
    headers = await _admin(db)
    resp = await client.patch("/catalogos/talleres/no-existe", headers=headers, json={"activo": False})
    assert resp.status_code == 404


async def test_solo_admin_sistema_gestiona_talleres(client, db):
    await crear_usuario_activo(db, usuario_id="mant-cat-1", telefono="+593900000552", roles=["jefe_mantenimiento"])
    headers = auth_headers("mant-cat-1", ["jefe_mantenimiento"])

    resp = await client.post("/catalogos/talleres", headers=headers, json={"nombre": "Taller Sur"})
    assert resp.status_code == 403


# --- Ola 3 de PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md (§3.2): repuestos ----


async def test_crear_listar_y_editar_repuesto(client, db):
    headers = await _admin(db)

    creado = await client.post(
        "/catalogos/repuestos",
        headers=headers,
        json={"nombre": "Filtro de aceite", "categoria": "Motor", "precio_referencial": 8.5, "unidad": "unidad"},
    )
    assert creado.status_code == 201
    body = creado.json()
    assert body["activo"] is True
    assert body["categoria"] == "Motor"
    assert body["precio_referencial"] == 8.5
    assert body["unidad"] == "unidad"

    listado = await client.get("/catalogos/repuestos", headers=headers)
    assert any(r["nombre"] == "Filtro de aceite" for r in listado.json())

    repuesto_id = body["id"]
    editado = await client.patch(
        f"/catalogos/repuestos/{repuesto_id}", headers=headers, json={"precio_referencial": 9.0}
    )
    assert editado.status_code == 200
    assert editado.json()["precio_referencial"] == 9.0

    evento = await db.bitacora.find_one({"accion": "CATALOGO_EDICION", "entidad_id": repuesto_id})
    assert evento["datos_previos"] == {"precio_referencial": 8.5}
    assert evento["datos_posteriores"] == {"precio_referencial": 9.0}


async def test_repuesto_duplicado_devuelve_409(client, db):
    headers = await _admin(db)
    body = {"nombre": "Bujías", "categoria": "Motor", "precio_referencial": 5.0, "unidad": "unidad"}
    await client.post("/catalogos/repuestos", headers=headers, json=body)
    resp = await client.post("/catalogos/repuestos", headers=headers, json=body)
    assert resp.status_code == 409
    assert resp.json()["code"] == "REPUESTO_CATALOGO_YA_EXISTE"


async def test_editar_repuesto_inexistente_devuelve_404(client, db):
    headers = await _admin(db)
    resp = await client.patch("/catalogos/repuestos/no-existe", headers=headers, json={"activo": False})
    assert resp.status_code == 404


async def test_repuesto_categoria_invalida_devuelve_422(client, db):
    headers = await _admin(db)
    resp = await client.post(
        "/catalogos/repuestos",
        headers=headers,
        json={"nombre": "Pieza rara", "categoria": "Carrocería", "precio_referencial": 5.0, "unidad": "unidad"},
    )
    assert resp.status_code == 422


async def test_repuesto_lectura_abierta_a_cualquier_actor_pero_escritura_solo_admin_sistema(client, db):
    await crear_usuario_activo(db, usuario_id="mant-cat-2", telefono="+593900000553", roles=["jefe_mantenimiento"])
    headers = auth_headers("mant-cat-2", ["jefe_mantenimiento"])

    resp_lectura = await client.get("/catalogos/repuestos", headers=headers)
    assert resp_lectura.status_code == 200

    resp_escritura = await client.post(
        "/catalogos/repuestos",
        headers=headers,
        json={"nombre": "Correa", "categoria": "Motor", "precio_referencial": 10.0, "unidad": "unidad"},
    )
    assert resp_escritura.status_code == 403
