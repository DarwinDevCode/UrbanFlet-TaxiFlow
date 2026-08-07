from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-sis-ver-1", telefono="+593900000650", roles=["admin_sistema"])
    return auth_headers("admin-sis-ver-1", ["admin_sistema"])


async def test_solo_admin_sistema_ve_la_version(client, db):
    await crear_usuario_activo(db, usuario_id="plataforma-ver-1", telefono="+593900000651", roles=["admin_plataforma"])
    headers = auth_headers("plataforma-ver-1", ["admin_plataforma"])

    resp = await client.get("/sistema/version", headers=headers)
    assert resp.status_code == 403


async def test_obtener_version_devuelve_backend_y_3_frontends(client, db):
    headers = await _admin(db)
    resp = await client.get("/sistema/version", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "0.1.0"
    assert body["web_pasajero"] == "0.1.0"
    assert body["web_conductor"] == "0.1.0"
    assert body["web_interno"] == "0.1.0"


async def test_registrar_y_listar_despliegue(client, db):
    headers = await _admin(db)

    body_creacion = {"componente": "backend", "version": "0.2.0", "notas": "Módulo 8.1"}
    creado = await client.post("/sistema/despliegues", headers=headers, json=body_creacion)
    assert creado.status_code == 201
    assert creado.json()["desplegado_por"] == "admin-sis-ver-1"

    listado = await client.get("/sistema/despliegues", headers=headers)
    assert listado.status_code == 200
    assert any(d["version"] == "0.2.0" for d in listado.json())

    evento = await db.bitacora.find_one({"accion": "DESPLIEGUE_REGISTRO", "entidad_id": creado.json()["id"]})
    assert evento is not None
    assert evento["datos_posteriores"] == {"componente": "backend", "version": "0.2.0"}
