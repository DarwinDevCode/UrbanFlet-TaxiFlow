from src.core import feature_flags
from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-flag-1", telefono="+593900000610", roles=["admin_sistema"])
    return auth_headers("admin-flag-1", ["admin_sistema"])


async def test_crear_listar_y_actualizar_flag(client, db):
    headers = await _admin(db)

    creado = await client.post(
        "/configuracion/flags", headers=headers, json={"nombre": "pago_electronico", "activo": False, "roles": []}
    )
    assert creado.status_code == 201
    assert creado.json()["activo"] is False

    listado = await client.get("/configuracion/flags", headers=headers)
    assert listado.status_code == 200
    assert any(f["nombre"] == "pago_electronico" for f in listado.json())

    actualizado = await client.patch(
        "/configuracion/flags/pago_electronico", headers=headers, json={"activo": True, "porcentaje": 50}
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["activo"] is True
    assert actualizado.json()["porcentaje"] == 50

    evento = await db.bitacora.find_one({"accion": "FLAG_MODIFICACION", "entidad_id": creado.json()["id"]})
    assert evento is not None
    assert evento["datos_posteriores"] == {"activo": True, "porcentaje": 50}


async def test_crear_flag_duplicado_devuelve_409(client, db):
    headers = await _admin(db)
    await client.post("/configuracion/flags", headers=headers, json={"nombre": "duplicado", "activo": True})
    resp = await client.post("/configuracion/flags", headers=headers, json={"nombre": "duplicado", "activo": True})
    assert resp.status_code == 409
    assert resp.json()["code"] == "FLAG_YA_EXISTE"


async def test_actualizar_flag_inexistente_devuelve_404(client, db):
    headers = await _admin(db)
    resp = await client.patch("/configuracion/flags/no-existe", headers=headers, json={"activo": True})
    assert resp.status_code == 404


async def test_is_enabled_flag_inexistente_es_false(db):
    assert await feature_flags.is_enabled(db, "no-existe") is False


async def test_is_enabled_respeta_activo_roles_y_porcentaje(db):
    await feature_flags.crear_flag(db, nombre="beta", activo=True, porcentaje=None, roles=["admin_financiero"])

    assert await feature_flags.is_enabled(db, "beta", roles=["admin_financiero"]) is True
    assert await feature_flags.is_enabled(db, "beta", roles=["jefe_mantenimiento"]) is False

    await feature_flags.actualizar_flag(db, nombre="beta", cambios={"roles": [], "porcentaje": 0})
    # porcentaje 0: nadie cae dentro del bucket.
    assert await feature_flags.is_enabled(db, "beta", actor_id="cualquier-usuario") is False

    await feature_flags.actualizar_flag(db, nombre="beta", cambios={"porcentaje": 100})
    assert await feature_flags.is_enabled(db, "beta", actor_id="cualquier-usuario") is True

    await feature_flags.actualizar_flag(db, nombre="beta", cambios={"activo": False})
    assert await feature_flags.is_enabled(db, "beta", actor_id="cualquier-usuario") is False
