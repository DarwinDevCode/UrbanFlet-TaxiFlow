from datetime import datetime, timedelta, UTC

from src.core.audit import ACCIONES_ADMINISTRATIVAS, AccionAuditoria, ResultadoAuditoria, write_audit_event
from tests.utils import auth_headers, crear_usuario_activo


async def test_acciones_administrativas_expone_el_catalogo_real(client, db):
    """Módulo 6.1: el frontend consume este endpoint en vez de mantener un
    mirror hardcodeado -- si este test pasa, el catálogo que ve el usuario
    en `AuditoriaAdmin.tsx` es, por construcción, el mismo que
    `ACCIONES_ADMINISTRATIVAS` en el backend (no puede desincronizarse)."""
    await crear_usuario_activo(db, usuario_id="u-admin-sis-cat", telefono="+593900100007", roles=["admin_sistema"])

    resp = await client.get(
        "/auditoria/acciones-administrativas", headers=auth_headers("u-admin-sis-cat", ["admin_sistema"])
    )

    assert resp.status_code == 200
    assert set(resp.json()) == {a.value for a in ACCIONES_ADMINISTRATIVAS}


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


async def test_filtro_por_multiples_acciones_usa_in(client, db):
    """Módulo 6.1 de admin_sistema: la vista filtrada de acciones
    administrativas necesita pedir varias acciones a la vez, no una."""
    await crear_usuario_activo(db, usuario_id="u-admin-sis-aud", telefono="+593900100005", roles=["admin_sistema"])
    await write_audit_event(
        db, actor_id="admin-1", rol="admin_sistema", accion=AccionAuditoria.USUARIO_SUSPENSION,
        entidad="usuarios", entidad_id="u-1", resultado=ResultadoAuditoria.OK,
    )
    await write_audit_event(
        db, actor_id="admin-1", rol="admin_sistema", accion=AccionAuditoria.FLAG_CREACION,
        entidad="feature_flags", entidad_id="f-1", resultado=ResultadoAuditoria.OK,
    )
    await write_audit_event(
        db, actor_id="conductor-1", rol="conductor", accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes", entidad_id="v-1", resultado=ResultadoAuditoria.OK,
    )

    headers = auth_headers("u-admin-sis-aud", ["admin_sistema"])
    resp = await client.get(
        "/auditoria/eventos",
        params=[("accion", "USUARIO_SUSPENSION"), ("accion", "FLAG_CREACION")],
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["total"] == 2
    acciones = {e["accion"] for e in resp.json()["items"]}
    assert acciones == {"USUARIO_SUSPENSION", "FLAG_CREACION"}


async def test_eventos_exponen_datos_previos_y_posteriores(client, db):
    await crear_usuario_activo(db, usuario_id="u-admin-sis-aud-2", telefono="+593900100006", roles=["admin_sistema"])
    await write_audit_event(
        db,
        actor_id="admin-1",
        rol="admin_sistema",
        accion=AccionAuditoria.ROL_MODIFICACION,
        entidad="usuarios",
        entidad_id="u-2",
        resultado=ResultadoAuditoria.OK,
        datos_previos={"roles": ["jefe_mantenimiento"]},
        datos_posteriores={"roles": ["jefe_mantenimiento", "coordinador_flota"]},
    )

    resp = await client.get(
        "/auditoria/eventos",
        params={"accion": "ROL_MODIFICACION"},
        headers=auth_headers("u-admin-sis-aud-2", ["admin_sistema"]),
    )

    evento = resp.json()["items"][0]
    assert evento["datos_previos"] == {"roles": ["jefe_mantenimiento"]}
    assert evento["datos_posteriores"] == {"roles": ["jefe_mantenimiento", "coordinador_flota"]}


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
