from src.notificaciones.service import NotificationService, _push_habilitado
from tests.utils import auth_headers, crear_usuario_activo


async def _pasajero(db, usuario_id="pasajero-notif-1", telefono="+593900002000"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def test_notify_user_persiste_en_la_bandeja(db):
    await crear_usuario_activo(db, usuario_id="pasajero-notif-2", telefono="+593900002001", roles=["pasajero"])

    await NotificationService().notify_user("pasajero-notif-2", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})

    doc = await db.notificaciones_usuario.find_one({"usuario_id": "pasajero-notif-2"})
    assert doc is not None
    assert doc["tipo"] == "VIAJE_ASIGNADO"
    assert doc["categoria"] == "viaje"
    assert doc["leida"] is False
    assert doc["payload"] == {"viaje_id": "v-1"}


async def test_listar_mias_devuelve_items_y_contador_no_leidas(client, db):
    headers = await _pasajero(db)
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})
    await NotificationService().notify_user("pasajero-notif-1", "CONDUCTOR_EN_CAMINO", {"viaje_id": "v-1"})

    resp = await client.get("/notificaciones/mias", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["no_leidas"] == 2
    tipos = {i["tipo"] for i in body["items"]}
    assert tipos == {"VIAJE_ASIGNADO", "CONDUCTOR_EN_CAMINO"}


async def test_marcar_leida_actualiza_el_contador(client, db):
    headers = await _pasajero(db)
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})
    listado = await client.get("/notificaciones/mias", headers=headers)
    notificacion_id = listado.json()["items"][0]["id"]

    resp = await client.patch(f"/notificaciones/mias/{notificacion_id}/leida", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["leida"] is True

    listado2 = await client.get("/notificaciones/mias", headers=headers)
    assert listado2.json()["no_leidas"] == 0


async def test_marcar_leida_de_notificacion_ajena_devuelve_404(client, db):
    headers_a = await _pasajero(db, usuario_id="pasajero-notif-a", telefono="+593900002010")
    await _pasajero(db, usuario_id="pasajero-notif-b", telefono="+593900002011")
    await NotificationService().notify_user("pasajero-notif-b", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})
    doc = await db.notificaciones_usuario.find_one({"usuario_id": "pasajero-notif-b"})

    resp = await client.patch(f"/notificaciones/mias/{doc['_id']}/leida", headers=headers_a)

    assert resp.status_code == 404


async def test_notificaciones_requiere_autenticacion(client):
    resp = await client.get("/notificaciones/mias")
    assert resp.status_code == 401


async def test_listar_categorias_no_incluye_seguridad(client, db):
    headers = await _pasajero(db)
    resp = await client.get("/notificaciones/categorias", headers=headers)

    assert resp.status_code == 200
    valores = {c["valor"] for c in resp.json()}
    assert "seguridad" not in valores
    assert "viaje" in valores


async def test_categoria_seguridad_nunca_se_apaga_por_preferencia(db):
    await crear_usuario_activo(
        db, usuario_id="cumpl-notif-1", telefono="+593900002020", roles=["supervisor_cumplimiento"]
    )
    await db.preferencias_usuario.insert_one(
        {"_id": "cumpl-notif-1", "notificaciones_push": {"seguridad": False}}
    )

    # `_push_habilitado` ignora la preferencia para la categoría "seguridad"
    # -- es la garantía real detrás de la nota de la spec 1.4 ("las alertas
    # de seguridad son exclusivas del Módulo 6.3, un usuario final no puede
    # apagarlas").
    habilitado = await _push_habilitado(db, "cumpl-notif-1", "ALERTA_SEGURIDAD")
    assert habilitado is True


async def test_preferencia_desactivada_bloquea_el_push_de_esa_categoria(db):
    await crear_usuario_activo(db, usuario_id="pasajero-notif-pref", telefono="+593900002021", roles=["pasajero"])
    await db.preferencias_usuario.insert_one(
        {"_id": "pasajero-notif-pref", "notificaciones_push": {"viaje": False}}
    )

    habilitado = await _push_habilitado(db, "pasajero-notif-pref", "VIAJE_ASIGNADO")
    assert habilitado is False


# ---------------------------------------------------------------------------
# Sección completa del Centro de notificaciones -- filtros por tipo/estado/fecha
# ---------------------------------------------------------------------------


async def test_listar_mias_filtra_por_tipo(client, db):
    headers = await _pasajero(db)
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})
    await NotificationService().notify_user("pasajero-notif-1", "CONDUCTOR_EN_CAMINO", {"viaje_id": "v-1"})

    resp = await client.get("/notificaciones/mias", headers=headers, params={"tipo": "VIAJE_ASIGNADO"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["tipo"] == "VIAJE_ASIGNADO"


async def test_listar_mias_filtra_por_leida(client, db):
    headers = await _pasajero(db)
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_FINALIZADO", {"viaje_id": "v-1"})
    listado = await client.get("/notificaciones/mias", headers=headers)
    primero_id = listado.json()["items"][0]["id"]
    await client.patch(f"/notificaciones/mias/{primero_id}/leida", headers=headers)

    solo_no_leidas = await client.get("/notificaciones/mias", headers=headers, params={"leida": "false"})
    solo_leidas = await client.get("/notificaciones/mias", headers=headers, params={"leida": "true"})

    assert solo_no_leidas.json()["total"] == 1
    assert solo_leidas.json()["total"] == 1
    assert solo_leidas.json()["items"][0]["id"] == primero_id


async def test_el_contador_no_leidas_es_global_sin_importar_el_filtro(client, db):
    """El filtro acota la lista visible, pero `no_leidas` sigue siendo el
    conteo total real -- filtrar por un tipo con 0 pendientes no debe hacer
    parecer que la bandeja está al día si hay otras sin leer."""
    headers = await _pasajero(db)
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_FINALIZADO", {"viaje_id": "v-1"})

    resp = await client.get("/notificaciones/mias", headers=headers, params={"tipo": "VIAJE_FINALIZADO"})

    assert resp.json()["total"] == 1
    assert resp.json()["no_leidas"] == 2


async def test_listar_mias_filtra_por_rango_de_fecha(client, db):
    from datetime import UTC, datetime, timedelta

    headers = await _pasajero(db)
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_ASIGNADO", {"viaje_id": "v-1"})
    await db.notificaciones_usuario.update_one(
        {"usuario_id": "pasajero-notif-1"}, {"$set": {"ts": datetime.now(UTC) - timedelta(days=10)}}
    )
    await NotificationService().notify_user("pasajero-notif-1", "VIAJE_FINALIZADO", {"viaje_id": "v-1"})

    desde = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    resp = await client.get("/notificaciones/mias", headers=headers, params={"desde": desde})

    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["tipo"] == "VIAJE_FINALIZADO"


async def test_documento_vencido_y_por_vencer_tienen_categoria_cumplimiento(db):
    """Hallazgo real de esta ronda: los 2 tipos ya se disparaban desde
    `cumplimiento/service.py` pero no estaban en `CATEGORIA_POR_EVENTO` --
    caían en el fallback 'general', sin categoría real."""
    from src.notificaciones.service import _categoria

    assert _categoria("DOCUMENTO_VENCIDO") == "cumplimiento"
    assert _categoria("DOCUMENTO_POR_VENCER") == "cumplimiento"
