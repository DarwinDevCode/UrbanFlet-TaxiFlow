"""Panel táctico "Rendimiento de Conductores" -- Punto 3 de la ronda de
mejoras de claridad y profundidad analítica (agosto 2026, ver CLAUDE.md §17.4).

Cobertura: RBAC (403 para un rol sin acceso), el merge por (conductor_id,
periodo) de las 2 tablas rpt_* de origen (grano de periodo distinto), y la
ventana reciente por defecto vs. el histórico completo opcional -- sin
requerir una instancia de ClickHouse viva (mismo patrón de
tests/estrategico/test_nivel_estrategico.py::_parchear_snapshots).
"""

from src.viajes import service as viajes_service
from tests.utils import auth_headers, crear_usuario_activo


class _ClienteNulo:
    def close(self):
        pass


def _parchear_snapshots(monkeypatch, *, desempeno=None, ingreso=None):
    por_tabla = {"rpt_desempeno_conductor": desempeno or [], "rpt_ingreso_conductor": ingreso or []}
    monkeypatch.setattr(viajes_service, "get_clickhouse_client", lambda: _ClienteNulo())
    monkeypatch.setattr(viajes_service, "fetch_latest_snapshot", lambda _c, tabla: por_tabla.get(tabla, []))


async def test_rol_sin_acceso_recibe_403(client, db):
    await crear_usuario_activo(db, usuario_id="u-pasajero-desc", telefono="+593900400001", roles=["pasajero"])

    resp = await client.get(
        "/viajes/panel-tactico/desempeno-conductores", headers=auth_headers("u-pasajero-desc", ["pasajero"])
    )

    assert resp.status_code == 403


async def test_combina_desempeno_e_ingreso_por_conductor_y_periodo(db, monkeypatch):
    """El caso central: 2 conductores, 1 mes -- uno con ingreso registrado
    (liquidación real, `fact_liquidacion`), otro sin ninguna todavía (recién
    incorporado, sin ciclo de liquidación cerrado) -- no debe reventar ni
    inventar un ingreso, va en `None`."""
    await crear_usuario_activo(db, usuario_id="cond-a", telefono="+593900400002", roles=["conductor"])
    await crear_usuario_activo(db, usuario_id="cond-b", telefono="+593900400003", roles=["conductor"])

    _parchear_snapshots(
        monkeypatch,
        desempeno=[
            {
                "conductor_id": "cond-a", "periodo": "2026-08", "viajes_completados": 18,
                "viajes_cancelados": 2, "pct_exito": 0.9, "calificacion_promedio": 4.8,
            },
            {
                "conductor_id": "cond-b", "periodo": "2026-08", "viajes_completados": 10,
                "viajes_cancelados": 0, "pct_exito": 1.0, "calificacion_promedio": None,
            },
        ],
        ingreso=[
            {"conductor_id": "cond-a", "periodo": "2026-08", "bruto": 500.0, "comisiones": 100.0, "neto": 400.0},
        ],
    )

    resultado = await viajes_service.obtener_panel_desempeno_conductores(db, meses=3)

    filas = {f["conductor_id"]: f for f in resultado["filas"]}
    assert filas["cond-a"]["neto"] == 400.0
    assert filas["cond-a"]["conductor_nombre"] == "Actor de prueba"
    assert filas["cond-b"]["neto"] is None
    assert filas["cond-b"]["calificacion_promedio"] is None
    assert resultado["metadata"]["advertencia_concentracion_historica"] is False


async def test_ventana_reciente_excluye_periodos_viejos_por_defecto(db, monkeypatch):
    """Ventana reciente pedida explícitamente (CLAUDE.md §17.4): con
    `meses=1` solo debe quedar el periodo más reciente, no el histórico
    completo (donde vive la concentración de los 5 conductores NYC)."""
    _parchear_snapshots(
        monkeypatch,
        desempeno=[
            {
                "conductor_id": "cond-a", "periodo": "2021-01", "viajes_completados": 270000,
                "viajes_cancelados": 0, "pct_exito": 1.0, "calificacion_promedio": None,
            },
            {
                "conductor_id": "cond-a", "periodo": "2026-08", "viajes_completados": 5,
                "viajes_cancelados": 0, "pct_exito": 1.0, "calificacion_promedio": None,
            },
        ],
    )

    reciente = await viajes_service.obtener_panel_desempeno_conductores(db, meses=1)
    completo = await viajes_service.obtener_panel_desempeno_conductores(db, meses=1, historico_completo=True)

    assert [f["periodo"] for f in reciente["filas"]] == ["2026-08"]
    assert {f["periodo"] for f in completo["filas"]} == {"2021-01", "2026-08"}
    assert completo["metadata"]["advertencia_concentracion_historica"] is True


async def test_ventana_reciente_no_evita_la_advertencia_si_igual_incluye_nyc(db, monkeypatch):
    """Hallazgo real de la verificación en navegador: con solo 3 periodos
    distintos EN TOTAL en este entorno (2021-01, 2021-02 de NYC, 2026-08 de
    la operación real -- 5 años de salto sin dato en medio), pedir `meses=3`
    ("ventana reciente") no excluye nada -- los 3 más recientes SON los 3
    únicos que existen. La advertencia debe encenderse igual, sin depender
    solo de `historico_completo`, porque la concentración real llegó al
    resultado de todas formas."""
    _parchear_snapshots(
        monkeypatch,
        desempeno=[
            {
                "conductor_id": "cond-a", "periodo": "2021-01", "viajes_completados": 247278,
                "viajes_cancelados": 0, "pct_exito": 1.0, "calificacion_promedio": None,
            },
            {
                "conductor_id": "cond-a", "periodo": "2021-02", "viajes_completados": 901,
                "viajes_cancelados": 0, "pct_exito": 1.0, "calificacion_promedio": None,
            },
            {
                "conductor_id": "cond-a", "periodo": "2026-08", "viajes_completados": 2,
                "viajes_cancelados": 0, "pct_exito": 1.0, "calificacion_promedio": 5.0,
            },
        ],
    )

    resultado = await viajes_service.obtener_panel_desempeno_conductores(db, meses=3)

    assert {f["periodo"] for f in resultado["filas"]} == {"2021-01", "2021-02", "2026-08"}
    assert resultado["metadata"]["historico_completo"] is False
    assert resultado["metadata"]["advertencia_concentracion_historica"] is True
