from typing import Any

from src.notificaciones.service import disparar_alerta
from tests.utils import auth_headers, crear_usuario_activo


class _DispatcherFalso:
    def __init__(self) -> None:
        self.llamadas: list[tuple[str, str, dict[str, Any]]] = []

    async def notify_user(self, usuario_id: str, event: str, payload: dict[str, Any]) -> None:
        self.llamadas.append((usuario_id, event, payload))


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-alert-1", telefono="+593900001000", roles=["admin_sistema"])
    return auth_headers("admin-alert-1", ["admin_sistema"])


async def test_solo_admin_sistema_puede_ver_o_editar(client, db):
    await crear_usuario_activo(
        db, usuario_id="cumpl-alert-1", telefono="+593900001001", roles=["supervisor_cumplimiento"]
    )
    headers = auth_headers("cumpl-alert-1", ["supervisor_cumplimiento"])

    resp = await client.get("/notificaciones/alertas-config", headers=headers)
    assert resp.status_code == 403


async def test_listar_devuelve_las_3_alertas_con_defaults(client, db):
    headers = await _admin(db)
    resp = await client.get("/notificaciones/alertas-config", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    tipos = {a["tipo_alerta"] for a in body}
    assert tipos == {"denegaciones_rbac", "gps_spoofing", "pipeline_fallido"}
    for alerta in body:
        assert alerta["activo"] is True
        assert alerta["canal"] == "web_push"
        assert alerta["destinatarios_adicionales"] == []
    rol_default = {a["tipo_alerta"]: a["rol_destinatario_default"] for a in body}
    assert rol_default["denegaciones_rbac"] == "supervisor_cumplimiento"
    assert rol_default["pipeline_fallido"] == "responsable_plataforma"


async def test_actualizar_desactiva_una_alerta_y_lo_audita(client, db):
    headers = await _admin(db)
    resp = await client.patch(
        "/notificaciones/alertas-config/gps_spoofing",
        headers=headers,
        json={"canal": "web_push", "destinatarios_adicionales": ["backup-1"], "activo": False},
    )

    assert resp.status_code == 200
    assert resp.json()["activo"] is False
    assert resp.json()["destinatarios_adicionales"] == ["backup-1"]

    evento = await db.bitacora.find_one({"accion": "ALERTA_CONFIG_CAMBIO", "entidad_id": "gps_spoofing"})
    assert evento is not None
    assert evento["datos_previos"]["activo"] is True
    assert evento["datos_posteriores"]["activo"] is False


async def test_disparar_alerta_respeta_activo_false(db):
    await crear_usuario_activo(db, usuario_id="sup-1", telefono="+593900001002", roles=["supervisor_cumplimiento"])
    await db.configuracion_alertas.update_one(
        {"_id": "gps_spoofing"},
        {"$set": {"canal": "web_push", "destinatarios_adicionales": [], "activo": False}},
        upsert=True,
    )
    dispatcher = _DispatcherFalso()

    await disparar_alerta(db, dispatcher, tipo_alerta="gps_spoofing", motivo="prueba")

    assert dispatcher.llamadas == []


async def test_disparar_alerta_notifica_rol_default_y_destinatarios_adicionales(db):
    await crear_usuario_activo(db, usuario_id="sup-2", telefono="+593900001003", roles=["supervisor_cumplimiento"])
    await db.configuracion_alertas.update_one(
        {"_id": "gps_spoofing"},
        {"$set": {"canal": "web_push", "destinatarios_adicionales": ["backup-2"], "activo": True}},
        upsert=True,
    )
    dispatcher = _DispatcherFalso()

    await disparar_alerta(db, dispatcher, tipo_alerta="gps_spoofing", motivo="prueba real")

    destinatarios = {llamada[0] for llamada in dispatcher.llamadas}
    assert destinatarios == {"sup-2", "backup-2"}
    assert all(llamada[1] == "ALERTA_SEGURIDAD" for llamada in dispatcher.llamadas)
    assert all(llamada[2]["motivo"] == "prueba real" for llamada in dispatcher.llamadas)


async def test_reportar_posicion_con_salto_imposible_dispara_alerta_real(client, db, redis):
    from datetime import UTC, datetime

    from src.main import app
    from tests.utils import crear_conductor_con_vehiculo

    await crear_usuario_activo(db, usuario_id="sup-3", telefono="+593900001004", roles=["supervisor_cumplimiento"])
    await crear_conductor_con_vehiculo(
        db, conductor_id="c-alert-1", telefono="+593900001005", vehiculo_id="v-alert-1", placa="ALR0001",
        estado_servicio="DISPONIBLE",
    )
    headers = auth_headers("c-alert-1", ["conductor"])

    dispatcher = _DispatcherFalso()
    app.state.notification_dispatcher = dispatcher

    await client.post(
        "/flota/posiciones", headers=headers,
        json={"lat": -0.2, "lon": -78.5, "precision_m": 10, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )
    await client.post(
        "/flota/posiciones", headers=headers,
        json={"lat": 10.0, "lon": -78.5, "precision_m": 10, "ts_dispositivo": datetime.now(UTC).isoformat()},
    )

    destinatarios = {llamada[0] for llamada in dispatcher.llamadas}
    assert "sup-3" in destinatarios
