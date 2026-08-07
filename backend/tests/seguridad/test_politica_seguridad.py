from datetime import datetime, UTC

import jwt

from src.core.config import get_settings
from tests.utils import auth_headers, crear_usuario_activo

_ZONA_BODY = {"nombre": "Centro", "geometria": {}}


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-seg2-1", telefono="+593900000900", roles=["admin_sistema"])
    return auth_headers("admin-seg2-1", ["admin_sistema"])


def _body(**overrides):
    base = {
        "access_token_minutos": 15,
        "refresh_token_dias": 30,
        "refresh_umbral_fallos": 3,
        "refresh_ventana_minutos": 15,
        "rbac_umbral_denegaciones": 5,
        "rbac_ventana_minutos": 10,
        "rbac_suspension_minutos": 30,
        "vigente_desde": datetime.now(UTC).isoformat(),
    }
    base.update(overrides)
    return base


async def test_default_antes_de_publicar_ninguna(client, db):
    headers = await _admin(db)
    resp = await client.get("/seguridad/politica-seguridad", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] is None
    assert body["access_token_minutos"] == 15
    assert body["rbac_umbral_denegaciones"] == 5


async def test_solo_admin_sistema_puede_publicar(client, db):
    await crear_usuario_activo(db, usuario_id="gerencia-seg2-1", telefono="+593900000901", roles=["gerencia"])
    headers = auth_headers("gerencia-seg2-1", ["gerencia"])

    resp = await client.post("/seguridad/politica-seguridad", headers=headers, json=_body())
    assert resp.status_code == 403


async def test_publicar_politica_cambia_el_ttl_real_del_access_token(client, db):
    headers = await _admin(db)
    resp = await client.post("/seguridad/politica-seguridad", headers=headers, json=_body(access_token_minutos=5))
    assert resp.status_code == 201

    telefono = "+593900000902"
    registro = {"nombre": "Corta Vida", "telefono": telefono, "password": "clave-larga-123"}
    await client.post("/auth/registro", json=registro)
    login = await client.post("/auth/login", json={"identificador": telefono, "password": "clave-larga-123"})
    assert login.status_code == 200

    settings = get_settings()
    payload = jwt.decode(login.json()["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    vida_segundos = payload["exp"] - payload["iat"]
    assert vida_segundos == 5 * 60


async def test_publicar_politica_reduce_el_umbral_de_suspension_rbac(client, db):
    """Mismo escenario real que `tests/core/test_rbac.py::
    test_cinco_denegaciones_suspenden_la_sesion`, pero confirmando que un
    umbral publicado por Módulo 6.2 (3, el mínimo permitido, en vez del
    default de 5) es el que de verdad aplica."""
    headers = await _admin(db)
    resp = await client.post("/seguridad/politica-seguridad", headers=headers, json=_body(rbac_umbral_denegaciones=3))
    assert resp.status_code == 201

    await crear_usuario_activo(db, usuario_id="u-suspendido-cfg", telefono="+593900000903", roles=["pasajero"])
    headers_pasajero = auth_headers("u-suspendido-cfg", ["pasajero"])

    for _ in range(3):
        resp = await client.post("/parametros/zonas", json=_ZONA_BODY, headers=headers_pasajero)
        assert resp.status_code == 403

    await db.usuarios.update_one({"_id": "u-suspendido-cfg"}, {"$set": {"roles": ["admin_plataforma"]}})
    resp = await client.post("/parametros/zonas", json=_ZONA_BODY, headers=headers_pasajero)

    assert resp.status_code == 403
    assert resp.json()["code"] == "SESSION_SUSPENDED"


async def test_publicar_politica_registra_antes_y_despues(client, db):
    headers = await _admin(db)
    resp = await client.post("/seguridad/politica-seguridad", headers=headers, json=_body(rbac_umbral_denegaciones=7))
    assert resp.status_code == 201

    evento = await db.bitacora.find_one({"accion": "POLITICA_SEGURIDAD_CAMBIO"})
    assert evento is not None
    assert evento["datos_previos"]["rbac_umbral_denegaciones"] == 5
    assert evento["datos_posteriores"]["rbac_umbral_denegaciones"] == 7
