from datetime import datetime, UTC

from tests.utils import auth_headers, crear_usuario_activo

# Bitácora de revisión (segunda pasada, punto 2): estas pruebas verifican el
# comportamiento GENÉRICO de RBAC (401 sin token, 403 con rol insuficiente,
# bitácora de denegación, suspensión de sesión a las 5 denegaciones) -- usan
# un endpoint gateado real solo como ejemplo, no prueban nada específico de
# ese endpoint. Antes usaban `POST /parametros/zonas` (funcionalidad de
# zonas eliminada por completo); se reemplazó por `POST /parametros/
# comisiones`, mismo criterio de "reglas de dinero", gateado a los mismos
# roles de escritura (`admin_plataforma`/`gerencia`).
_COMISION_BODY = {"porcentaje": 0.2, "vigente_desde": datetime.now(UTC).isoformat()}


async def test_sin_token_devuelve_401(client):
    resp = await client.post("/parametros/comisiones", json=_COMISION_BODY)
    assert resp.status_code == 401


async def test_rol_insuficiente_devuelve_403_y_queda_en_bitacora(client, db):
    await crear_usuario_activo(db, usuario_id="u-pasajero", telefono="+593900000001", roles=["pasajero"])

    resp = await client.post(
        "/parametros/comisiones", json=_COMISION_BODY, headers=auth_headers("u-pasajero", ["pasajero"])
    )

    assert resp.status_code == 403
    assert resp.json()["code"] == "INSUFFICIENT_ROLE"
    evento = await db.bitacora.find_one({"actor_id": "u-pasajero", "accion": "ACCESO_DENEGADO"})
    assert evento is not None


async def test_rol_admin_plataforma_puede_crear_comision(client, db):
    await crear_usuario_activo(db, usuario_id="u-admin", telefono="+593900000002", roles=["admin_plataforma"])

    resp = await client.post(
        "/parametros/comisiones", json=_COMISION_BODY, headers=auth_headers("u-admin", ["admin_plataforma"])
    )

    assert resp.status_code == 201
    assert resp.json()["valores"]["porcentaje"] == 0.2


async def test_cinco_denegaciones_suspenden_la_sesion(client, db):
    await crear_usuario_activo(db, usuario_id="u-suspendido", telefono="+593900000003", roles=["pasajero"])
    headers = auth_headers("u-suspendido", ["pasajero"])

    for _ in range(5):
        resp = await client.post("/parametros/comisiones", json=_COMISION_BODY, headers=headers)
        assert resp.status_code == 403

    # Aunque luego se le otorgara el rol correcto, la sesión ya quedó
    # suspendida (CU-O18 A4) — se simula reenviando la misma sesión.
    await db.usuarios.update_one({"_id": "u-suspendido"}, {"$set": {"roles": ["admin_plataforma"]}})
    resp = await client.post("/parametros/comisiones", json=_COMISION_BODY, headers=headers)

    assert resp.status_code == 403
    assert resp.json()["code"] == "SESSION_SUSPENDED"
