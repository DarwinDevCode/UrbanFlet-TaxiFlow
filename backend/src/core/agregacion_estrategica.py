"""Helpers de la segunda capa de agregación del nivel estratégico.

`specs/nivel-estrategico/nivel_estrategico.md` §2: ningún informe estratégico
se consulta directo de MongoDB — todos agregan **sobre** las vistas `rpt_*`
que el nivel táctico ya publicó. Estas 3 operaciones (variación entre dos
periodos, promedio ponderado, agrupado por clave) se repetían en 7 de los 9
dashboards; viven acá para que cada `service.py` de dominio no las reimplemente
con criterios ligeramente distintos.

Nota sobre de dónde sale la "tendencia extendida" de cada dashboard — hay dos
casos, y la diferencia importa:

1. Tablas `rpt_*` que YA traen una dimensión de periodo propia
   (`rpt_margen_comision.periodo`, `rpt_tasa_cancelacion.periodo`,
   `rpt_conversion_captacion.periodo`, `rpt_cumplimiento_plan_preventivo.periodo`,
   `rpt_costo_mantenimiento_vehiculo.periodo`, `rpt_tasa_discrepancias.fecha_periodo`):
   el ÚLTIMO snapshot ya contiene varios meses. Se usa `fetch_latest_snapshot`
   y se agrupa por ese periodo — no hace falta historial de snapshots.
2. Tablas `rpt_*` que son un corte puntual sin periodo propio
   (`rpt_flota_activa_franja`, `rpt_documentacion_vigente`,
   `rpt_tiempo_asignacion`, `rpt_cuarentena_dominio`): la tendencia sale de
   `fetch_snapshot_history` sobre `fecha_datos` (son MergeTree, no Replacing,
   así que conservan un corte por corrida).

En ningún caso se creó una tabla `rpt_estrategico_*` nueva ni un DAG nuevo.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence


def variacion_pct(actual: float | None, previo: float | None) -> float | None:
    """Variación porcentual de `actual` respecto de `previo`.

    Devuelve `None` (nunca 0.0 ni infinito) si falta cualquiera de los dos
    valores o si `previo` es 0 — se prefiere un "sin dato" honesto en la UI
    antes que un porcentaje fabricado a partir de una división por cero."""
    if actual is None or previo in (None, 0):
        return None
    return round((actual - previo) / previo * 100, 2)


def promedio_ponderado(filas: Iterable[dict], valor: str, peso: str) -> float | None:
    """Promedio de `valor` ponderado por `peso`.

    Necesario porque las tablas `rpt_*` traen porcentajes ya calculados por
    subgrupo (por franja, por canal, por tipo...): promediarlos sin ponderar
    por su volumen daría el mismo peso a una franja con 3 registros que a una
    con 30,000."""
    total_peso = 0.0
    acumulado = 0.0
    for fila in filas:
        p = float(fila.get(peso) or 0)
        v = fila.get(valor)
        if v is None or p <= 0:
            continue
        acumulado += float(v) * p
        total_peso += p
    return round(acumulado / total_peso, 4) if total_peso else None


def agrupar(filas: Iterable[dict], clave: str | Callable[[dict], str]) -> dict[str, list[dict]]:
    """Agrupa filas de un snapshot `rpt_*` por una columna (o función de fila)."""
    fn = clave if callable(clave) else (lambda f: str(f.get(clave)))
    grupos: dict[str, list[dict]] = {}
    for fila in filas:
        grupos.setdefault(fn(fila), []).append(fila)
    return grupos


def ultimos_periodos(periodos: Iterable[str], limite: int) -> list[str]:
    """Los `limite` periodos más recientes, en orden cronológico ascendente.

    Los periodos de las tablas `rpt_*` son strings `YYYY-MM` (o fechas ISO),
    ambos ordenables lexicográficamente sin parsear."""
    ordenados: Sequence[str] = sorted(set(periodos))
    return list(ordenados[-limite:]) if limite > 0 else list(ordenados)
