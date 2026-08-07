from tests.utils import auth_headers, crear_usuario_activo


async def test_admin_sistema_puede_crear_editar_y_eliminar_zona(client, db):
    await crear_usuario_activo(db, usuario_id="admin-zon-1", telefono="+593900000500", roles=["admin_sistema"])
    headers = auth_headers("admin-zon-1", ["admin_sistema"])

    creada = await client.post("/parametros/zonas", headers=headers, json={"nombre": "Zona Norte", "geometria": {}})
    assert creada.status_code == 201
    zona_id = creada.json()["id"]

    evento_creacion = await db.bitacora.find_one({"accion": "CATALOGO_CREACION", "entidad_id": zona_id})
    assert evento_creacion is not None

    editada = await client.patch(
        f"/parametros/zonas/{zona_id}", headers=headers, json={"nombre": "Zona Norte Renombrada", "geometria": {}}
    )
    assert editada.status_code == 200
    assert editada.json()["nombre"] == "Zona Norte Renombrada"

    evento_edicion = await db.bitacora.find_one({"accion": "CATALOGO_EDICION", "entidad_id": zona_id})
    assert evento_edicion["datos_previos"] == {"nombre": "Zona Norte"}
    assert evento_edicion["datos_posteriores"] == {"nombre": "Zona Norte Renombrada"}

    eliminada = await client.delete(f"/parametros/zonas/{zona_id}", headers=headers)
    assert eliminada.status_code == 204

    lista = await client.get("/parametros/zonas")
    assert zona_id not in [z["id"] for z in lista.json()]


async def test_admin_captacion_no_puede_gestionar_zonas(client, db):
    await crear_usuario_activo(db, usuario_id="captacion-zon-1", telefono="+593900000501", roles=["admin_captacion"])
    headers = auth_headers("captacion-zon-1", ["admin_captacion"])

    resp = await client.post("/parametros/zonas", headers=headers, json={"nombre": "Intento", "geometria": {}})
    assert resp.status_code == 403


async def test_eliminar_zona_en_uso_devuelve_409(client, db):
    await crear_usuario_activo(db, usuario_id="admin-zon-2", telefono="+593900000502", roles=["admin_sistema"])
    headers = auth_headers("admin-zon-2", ["admin_sistema"])

    creada = await client.post("/parametros/zonas", headers=headers, json={"nombre": "Zona En Uso", "geometria": {}})
    zona_id = creada.json()["id"]

    await db.viajes.insert_one({"_id": "viaje-zona-test", "zona_origen_id": zona_id, "estado": "PAGADO"})

    resp = await client.delete(f"/parametros/zonas/{zona_id}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "ZONA_EN_USO"


async def test_editar_zona_inexistente_devuelve_404(client, db):
    await crear_usuario_activo(db, usuario_id="admin-zon-3", telefono="+593900000503", roles=["admin_sistema"])
    headers = auth_headers("admin-zon-3", ["admin_sistema"])

    resp = await client.patch("/parametros/zonas/no-existe", headers=headers, json={"nombre": "X", "geometria": {}})
    assert resp.status_code == 404
