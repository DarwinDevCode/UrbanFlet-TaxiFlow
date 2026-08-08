"""Nivel estratégico (specs/nivel-estrategico/nivel_estrategico.md).

Cobertura: RBAC de los 9 dashboards (403/200), la agregación real del único
que no depende de ClickHouse (Gobernanza, OE6b, sobre `bitacora`), los
helpers de la segunda capa de agregación, y la fórmula de margen de OE4 con
snapshots `rpt_*` falsos -- no requiere una instancia de ClickHouse viva.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.core.agregacion_estrategica import promedio_ponderado, ultimos_periodos, variacion_pct
from src.estrategico import service as estrategico_service
from tests.utils import auth_headers, crear_usuario_activo

# (ruta, roles permitidos por la spec)
RUTAS_ESTRATEGICAS = [
    ("/captacion/panel-estrategico/crecimiento", ["gerencia", "admin_captacion"]),
    ("/viajes/panel-estrategico/confiabilidad", ["gerencia", "coordinador_operaciones"]),
    ("/mantenimiento/panel-estrategico/estado-costo-flota", ["gerencia", "jefe_mantenimiento"]),
    ("/plataforma/panel-estrategico/capacidades", ["gerencia", "responsable_plataforma"]),
    ("/liquidaciones/panel-estrategico/integridad-financiera", ["gerencia", "admin_financiero"]),
    ("/cumplimiento/panel-estrategico/cumplimiento-normativo", ["gerencia", "supervisor_cumplimiento"]),
    ("/auditoria/panel-estrategico/gobernanza", ["gerencia"]),
    ("/estrategico/rentabilidad-demanda", ["gerencia"]),
    ("/estrategico/tablero-ejecutivo", ["gerencia"]),
]


@pytest.mark.parametrize("ruta,_roles", RUTAS_ESTRATEGICAS)
async def test_rol_sin_acceso_recibe_403(client, db, ruta, _roles):
    await crear_usuario_activo(db, usuario_id="u-pasajero-est", telefono="+593900300001", roles=["pasajero"])

    resp = await client.get(ruta, headers=auth_headers("u-pasajero-est", ["pasajero"]))

    assert resp.status_code == 403


async def test_admin_sistema_no_ve_el_panel_de_gobernanza(client, db):
    """La spec (§3.6.b) declara este dashboard **exclusivo de `gerencia`**:
    deliberadamente NO se comparte con `admin_sistema`, que ya tiene su
    propia vista operativa de la misma bitácora en Administración."""
    await crear_usuario_activo(db, usuario_id="u-admsis-est", telefono="+593900300002", roles=["admin_sistema"])

    resp = await client.get(
        "/auditoria/panel-estrategico/gobernanza", headers=auth_headers("u-admsis-est", ["admin_sistema"])
    )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# OE6b — Panel de Gobernanza de Datos y Seguridad (agregación real sobre Mongo)
# ---------------------------------------------------------------------------


async def _sembrar_bitacora(db):
    ahora = datetime.now(UTC).replace(tzinfo=None)
    eventos = [
        # Ventana actual (últimos días)
        {"evento_id": 1, "ts": ahora, "accion": "USUARIO_CREACION", "entidad": "usuarios", "resultado": "OK"},
        {"evento_id": 2, "ts": ahora, "accion": "ROL_MODIFICACION", "entidad": "usuarios", "resultado": "OK"},
        {"evento_id": 3, "ts": ahora, "accion": "ACCESO_DENEGADO", "entidad": "/x", "resultado": "DENEGADO"},
        {"evento_id": 4, "ts": ahora, "accion": "POSIBLE_GPS_SPOOFING", "entidad": "flota", "resultado": "DENEGADO"},
        # Ruido: acción no administrativa y no de seguridad -- no debe contarse.
        {"evento_id": 5, "ts": ahora, "accion": "VIAJE_TRANSICION_ESTADO", "entidad": "viajes", "resultado": "OK"},
        # Fuera de la ventana de 1 mes: no debe entrar en los KPIs.
        {
            "evento_id": 6,
            "ts": ahora - timedelta(days=200),
            "accion": "USUARIO_BAJA",
            "entidad": "usuarios",
            "resultado": "OK",
        },
    ]
    for evento in eventos:
        evento.setdefault("actor_id", "u-actor")
        evento.setdefault("rol", "admin_sistema")
        evento.setdefault("entidad_id", None)
        evento.setdefault("ip", None)
        evento.setdefault("dispositivo", None)
    await db.bitacora.insert_many(eventos)


async def test_gobernanza_cuenta_solo_lo_que_corresponde(client, db):
    await crear_usuario_activo(db, usuario_id="u-gerencia-est", telefono="+593900300003", roles=["gerencia"])
    await _sembrar_bitacora(db)

    resp = await client.get(
        "/auditoria/panel-estrategico/gobernanza?meses=1",
        headers=auth_headers("u-gerencia-est", ["gerencia"]),
    )

    assert resp.status_code == 200
    body = resp.json()
    # 2 administrativos dentro de la ventana (el de hace 200 días queda fuera,
    # y VIAJE_TRANSICION_ESTADO no es una acción administrativa).
    assert body["kpis"]["eventos_administrativos"] == 2
    assert body["kpis"]["accesos_denegados"] == 1
    # ACCESO_DENEGADO tiene su propio KPI: no se cuenta también como alerta.
    assert body["kpis"]["alertas_seguridad"] == 1
    # La tabla dominante del patrón F solo trae eventos administrativos.
    assert {e["accion"] for e in body["eventos"]} == {"USUARIO_CREACION", "ROL_MODIFICACION"}
    assert body["metadata"]["meses"] == 1


async def test_gobernanza_sin_ventana_previa_no_fabrica_variacion(client, db):
    """Sin eventos en la ventana anterior, la variación es `None` y nunca 0%
    ni una división por cero."""
    await crear_usuario_activo(db, usuario_id="u-gerencia-est2", telefono="+593900300004", roles=["gerencia"])
    await _sembrar_bitacora(db)

    resp = await client.get(
        "/auditoria/panel-estrategico/gobernanza?meses=1",
        headers=auth_headers("u-gerencia-est2", ["gerencia"]),
    )

    assert resp.json()["kpis"]["variacion_accesos_denegados_pct"] is None


# ---------------------------------------------------------------------------
# Helpers de la segunda capa de agregación
# ---------------------------------------------------------------------------


def test_variacion_pct_nunca_divide_por_cero():
    assert variacion_pct(150, 100) == 50.0
    assert variacion_pct(50, 100) == -50.0
    assert variacion_pct(10, 0) is None
    assert variacion_pct(10, None) is None
    assert variacion_pct(None, 10) is None


def test_promedio_ponderado_usa_el_peso_y_no_la_media_simple():
    filas = [
        {"pct": 1.0, "n": 1},  # media simple daría 0.5
        {"pct": 0.0, "n": 99},
    ]
    assert promedio_ponderado(filas, "pct", "n") == 0.01


def test_promedio_ponderado_sin_peso_devuelve_none():
    assert promedio_ponderado([{"pct": 1.0, "n": 0}], "pct", "n") is None


def test_ultimos_periodos_toma_los_mas_recientes_en_orden_ascendente():
    periodos = ["2026-01", "2025-12", "2026-03", "2026-02", "2026-01"]
    assert ultimos_periodos(periodos, 2) == ["2026-02", "2026-03"]


# ---------------------------------------------------------------------------
# OE4 — fórmula de margen (con snapshots `rpt_*` falsos, sin ClickHouse real)
# ---------------------------------------------------------------------------


def _parchear_snapshots(monkeypatch, **por_tabla):
    monkeypatch.setattr(estrategico_service, "get_clickhouse_client", lambda: _ClienteNulo())
    monkeypatch.setattr(
        estrategico_service, "fetch_latest_snapshot", lambda _c, tabla: por_tabla.get(tabla, [])
    )


class _ClienteNulo:
    def close(self):
        pass


def test_rentabilidad_prorratea_con_dos_bases_distintas(monkeypatch):
    """Recaudación/comisión se reparten por demanda; el mantenimiento por
    capacidad expuesta. Es lo que hace que el margen difiera entre franjas
    -- si se usara una sola base, el margen_pct sería idéntico y el
    dashboard no serviría para comparar."""
    _parchear_snapshots(
        monkeypatch,
        rpt_margen_comision=[
            {"periodo": "2026-01", "margen": 0.2, "bruto_total": 1000.0, "comisiones_total": 200.0}
        ],
        rpt_costo_mantenimiento_vehiculo=[
            {"vehiculo_id": "v1", "periodo": "2026-01", "costo_total": 100.0, "total_ordenes": 1}
        ],
        # 75% de la demanda es DIURNA...
        rpt_tiempo_asignacion=[
            {"franja": "DIURNA", "total_registros": 75, "segundos_promedio": 10.0},
            {"franja": "NOCTURNA", "total_registros": 25, "segundos_promedio": 20.0},
        ],
        # ...pero la flota está expuesta sobre todo en el bucket 00-06, que es
        # 5/6 NOCTURNA: la nocturna carga más costo del que le corresponde por
        # demanda, y su margen cae.
        rpt_flota_activa_franja=[
            {"franja": "00-06", "pct_disponible": 1.0, "total_registros": 100},
            {"franja": "12-18", "pct_disponible": 1.0, "total_registros": 10},
        ],
    )

    panel = estrategico_service.obtener_panel_rentabilidad(meses=12)

    celdas = {c["franja"]: c for c in panel["matriz"]}
    assert celdas["DIURNA"]["recaudacion"] == 750.0
    assert celdas["NOCTURNA"]["recaudacion"] == 250.0
    assert celdas["DIURNA"]["comision"] == 150.0
    # El costo total (100) se reparte por capacidad, no por demanda.
    assert round(celdas["DIURNA"]["costo_mantenimiento"] + celdas["NOCTURNA"]["costo_mantenimiento"], 2) == 100.0
    assert celdas["NOCTURNA"]["costo_mantenimiento"] > celdas["DIURNA"]["costo_mantenimiento"]
    # ...y por eso los márgenes NO son iguales entre franjas.
    assert celdas["NOCTURNA"]["margen_pct"] < celdas["DIURNA"]["margen_pct"]
    assert panel["kpis"]["franja_menos_rentable"] == "NOCTURNA"
    # La dimensión zona no está disponible y se declara, no se disimula.
    assert panel["metadata"]["zona_disponible"] is False
    assert panel["metadata"]["demanda_viajes_disponible"] is False


def test_rentabilidad_sin_datos_no_revienta(monkeypatch):
    _parchear_snapshots(monkeypatch)

    panel = estrategico_service.obtener_panel_rentabilidad()

    assert panel["matriz"] == []
    assert panel["kpis"]["margen_promedio_pct"] is None


# ---------------------------------------------------------------------------
# CU-E01 — Tablero ejecutivo
# ---------------------------------------------------------------------------


async def test_tablero_ejecutivo_sirve_las_8_tarjetas_aunque_falten_fuentes(client, db, monkeypatch):
    """Un dominio sin datos (o con ClickHouse caído) sale como tarjeta
    `disponible=false`, no tumba el tablero entero."""
    await crear_usuario_activo(db, usuario_id="u-gerencia-tab", telefono="+593900300005", roles=["gerencia"])

    resp = await client.get("/estrategico/tablero-ejecutivo", headers=auth_headers("u-gerencia-tab", ["gerencia"]))

    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["total"] == 8
    assert len(body["tarjetas"]) == 8
    # Cada tarjeta declara a qué dashboard estratégico navega su "Ver detalle".
    assert {t["seccion"] for t in body["tarjetas"]} == {
        "crecimiento",
        "confiabilidad",
        "estado-costo-flota",
        "capacidades",
        "rentabilidad",
        "integridad-financiera",
        "cumplimiento-normativo",
        "gobernanza",
    }
