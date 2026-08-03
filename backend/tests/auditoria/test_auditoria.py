from datetime import datetime, timedelta, UTC

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from tests.utils import auth_headers, crear_usuario_activo


async def test_listar_eventos_sin_rol_de_auditoria_devuelve_403(client, db):
    await crear_usuario_activo(db, usuario_id="u-pasajero-aud", telefono="+593900100001", roles=["pasajero"])

    resp = await client.get("/auditoria/eventos", headers=auth_headers("u-pasajero-aud", ["pasajero"]))

    assert resp.status_code == 403


async def test_supervisor_cumplimiento_puede_listar_y_filtrar_eventos(client, db):
    await crear_usuario_activo(
        db, usuario_id="u-supervisor", telefono="+593900100002", roles=["supervisor_cumplimiento"]
    )
    await write_audit_event(
        db,
        actor_id="conductor-1",
        rol="conductor",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id="viaje-1",
        resultado=ResultadoAuditoria.OK,
    )
    await write_audit_event(
        db,
        actor_id="conductor-2",
        rol="conductor",
        accion=AccionAuditoria.PAGO_REGISTRO,
        entidad="pagos",
        entidad_id="pago-1",
        resultado=ResultadoAuditoria.ERROR,
    )

    headers = auth_headers("u-supervisor", ["supervisor_cumplimiento"])

    todos = await client.get("/auditoria/eventos", headers=headers)
    assert todos.status_code == 200
    assert todos.json()["total"] == 2

    filtrado = await client.get("/auditoria/eventos", params={"actor_id": "conductor-1"}, headers=headers)
    assert filtrado.json()["total"] == 1
    assert filtrado.json()["items"][0]["entidad_id"] == "viaje-1"

    por_resultado = await client.get("/auditoria/eventos", params={"resultado": "ERROR"}, headers=headers)
    assert por_resultado.json()["total"] == 1
    assert por_resultado.json()["items"][0]["accion"] == "PAGO_REGISTRO"


async def test_filtros_por_entidad_accion_y_rango_de_fechas(client, db):
    await crear_usuario_activo(
        db, usuario_id="u-supervisor-3", telefono="+593900100004", roles=["supervisor_cumplimiento"]
    )
    await write_audit_event(
        db,
        actor_id="conductor-9",
        rol="conductor",
        accion=AccionAuditoria.VEHICULO_RETIRO,
        entidad="vehiculos",
        entidad_id="vehiculo-1",
        resultado=ResultadoAuditoria.OK,
    )

    headers = auth_headers("u-supervisor-3", ["supervisor_cumplimiento"])

    por_entidad = await client.get("/auditoria/eventos", params={"entidad": "vehiculos"}, headers=headers)
    assert por_entidad.json()["total"] == 1

    por_accion = await client.get(
        "/auditoria/eventos", params={"accion": "VEHICULO_RETIRO"}, headers=headers
    )
    assert por_accion.json()["total"] == 1

    ahora = datetime.now(UTC)
    en_rango = await client.get(
        "/auditoria/eventos",
        params={
            "desde": (ahora - timedelta(minutes=5)).isoformat(),
            "hasta": (ahora + timedelta(minutes=5)).isoformat(),
        },
        headers=headers,
    )
    assert en_rango.json()["total"] == 1

    fuera_de_rango = await client.get(
        "/auditoria/eventos",
        params={"desde": (ahora + timedelta(days=1)).isoformat()},
        headers=headers,
    )
    assert fuera_de_rango.json()["total"] == 0


async def test_paginacion_respeta_tamanio_de_pagina(client, db):
    await crear_usuario_activo(
        db, usuario_id="u-supervisor-2", telefono="+593900100003", roles=["supervisor_cumplimiento"]
    )
    for i in range(3):
        await write_audit_event(
            db,
            actor_id=f"actor-{i}",
            rol="conductor",
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=f"viaje-{i}",
            resultado=ResultadoAuditoria.OK,
        )

    resp = await client.get(
        "/auditoria/eventos",
        params={"tamanio_pagina": 2, "pagina": 1},
        headers=auth_headers("u-supervisor-2", ["supervisor_cumplimiento"]),
    )

    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
