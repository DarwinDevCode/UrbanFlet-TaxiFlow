from datetime import datetime, UTC

from tests.utils import (
    auth_headers,
    crear_conductor_con_vehiculo,
    crear_usuario_activo,
    reportar_posicion_en_cache,
)


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-cfg-1", telefono="+593900000600", roles=["admin_sistema"])
    return auth_headers("admin-cfg-1", ["admin_sistema"])


async def test_default_antes_de_publicar_ninguna(client, db):
    headers = await _admin(db)
    resp = await client.get("/configuracion/parametros-sistema", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] is None
    assert body["radios_despacho_m"] == [300, 600, 1000]
    assert body["oferta_expira_segundos"] == 60


async def test_solo_admin_sistema_puede_publicar(client, db):
    await crear_usuario_activo(db, usuario_id="plataforma-1", telefono="+593900000601", roles=["admin_plataforma"])
    headers_plataforma = auth_headers("plataforma-1", ["admin_plataforma"])

    resp = await client.post(
        "/configuracion/parametros-sistema",
        headers=headers_plataforma,
        json={
            "idioma": "es",
            "zona_horaria": "America/Guayaquil",
            "radios_despacho_m": [500],
            "oferta_expira_segundos": 30,
            "vigente_desde": datetime.now(UTC).isoformat(),
        },
    )

    assert resp.status_code == 403


async def test_publicar_parametro_sistema_registra_antes_y_despues(client, db):
    headers = await _admin(db)
    body = {
        "idioma": "es",
        "zona_horaria": "America/Guayaquil",
        "radios_despacho_m": [400, 800],
        "oferta_expira_segundos": 25,
        "vigente_desde": datetime.now(UTC).isoformat(),
    }
    resp = await client.post("/configuracion/parametros-sistema", headers=headers, json=body)

    assert resp.status_code == 201
    assert resp.json()["radios_despacho_m"] == [400, 800]
    assert resp.json()["oferta_expira_segundos"] == 25

    evento = await db.bitacora.find_one({"accion": "PARAMETRO_SISTEMA_CAMBIO", "entidad": "parametro_sistema"})
    assert evento is not None
    assert evento["datos_previos"]["radios_despacho_m"] == [300, 600, 1000]
    assert evento["datos_posteriores"]["radios_despacho_m"] == [400, 800]

    vigente = await client.get("/configuracion/parametros-sistema", headers=headers)
    assert vigente.json()["radios_despacho_m"] == [400, 800]


async def test_radios_publicados_afectan_el_despacho_real(client, db, redis):
    """Confirma que `viajes/service_dispatch.py` lee de verdad la
    configuración publicada, no solo que el endpoint la guarda -- un
    candidato que hoy calificaría a 1000m queda fuera si se publica un
    radio máximo de 200m."""
    headers = await _admin(db)
    await client.post(
        "/configuracion/parametros-sistema",
        headers=headers,
        json={
            "idioma": "es",
            "zona_horaria": "America/Guayaquil",
            "radios_despacho_m": [100, 200],
            "oferta_expira_segundos": 20,
            "vigente_desde": datetime.now(UTC).isoformat(),
        },
    )

    await crear_usuario_activo(db, usuario_id="pd-cfg-1", telefono="+593900000602", roles=["pasajero"])
    headers_pasajero = auth_headers("pd-cfg-1", ["pasajero"])
    await crear_conductor_con_vehiculo(
        db, conductor_id="cd-cfg-1", telefono="+593900000603", vehiculo_id="vd-cfg-1", placa="PBC0001"
    )
    # ~890m -- calificaría con los radios por defecto (300/600/1000) pero no
    # con el radio máximo de 200m recién publicado.
    await reportar_posicion_en_cache(redis, vehiculo_id="vd-cfg-1", lat=-0.18 + 0.008, lon=-78.5)

    body = {"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"}
    resp = await client.post("/viajes", headers=headers_pasajero, json=body)

    assert resp.status_code == 201
    assert resp.json()["estado"] == "SIN_CONDUCTOR"
