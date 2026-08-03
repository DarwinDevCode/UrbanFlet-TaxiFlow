from tests.utils import auth_headers, crear_usuario_activo

_ZONA_BODY = {"nombre": "Centro", "geometria": {"type": "Point", "coordinates": [0, 0]}}


async def test_sin_token_devuelve_401(client):
    resp = await client.post("/parametros/zonas", json=_ZONA_BODY)
    assert resp.status_code == 401


async def test_rol_insuficiente_devuelve_403_y_queda_en_bitacora(client, db):
    await crear_usuario_activo(db, usuario_id="u-pasajero", telefono="+593900000001", roles=["pasajero"])

    resp = await client.post("/parametros/zonas", json=_ZONA_BODY, headers=auth_headers("u-pasajero", ["pasajero"]))

    assert resp.status_code == 403
    assert resp.json()["code"] == "INSUFFICIENT_ROLE"
    evento = await db.bitacora.find_one({"actor_id": "u-pasajero", "accion": "ACCESO_DENEGADO"})
    assert evento is not None


async def test_rol_admin_plataforma_puede_crear_zona(client, db):
    await crear_usuario_activo(db, usuario_id="u-admin", telefono="+593900000002", roles=["admin_plataforma"])

    resp = await client.post(
        "/parametros/zonas", json=_ZONA_BODY, headers=auth_headers("u-admin", ["admin_plataforma"])
    )

    assert resp.status_code == 201
    assert resp.json()["nombre"] == "Centro"


async def test_cinco_denegaciones_suspenden_la_sesion(client, db):
    await crear_usuario_activo(db, usuario_id="u-suspendido", telefono="+593900000003", roles=["pasajero"])
    headers = auth_headers("u-suspendido", ["pasajero"])

    for _ in range(5):
        resp = await client.post("/parametros/zonas", json=_ZONA_BODY, headers=headers)
        assert resp.status_code == 403

    # Aunque luego se le otorgara el rol correcto, la sesión ya quedó
    # suspendida (CU-O18 A4) — se simula reenviando la misma sesión.
    await db.usuarios.update_one({"_id": "u-suspendido"}, {"$set": {"roles": ["admin_plataforma"]}})
    resp = await client.post("/parametros/zonas", json=_ZONA_BODY, headers=headers)

    assert resp.status_code == 403
    assert resp.json()["code"] == "SESSION_SUSPENDED"
