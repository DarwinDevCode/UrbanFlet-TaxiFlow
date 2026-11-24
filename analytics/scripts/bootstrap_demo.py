"""Primera carga de la capa Gold (ClickHouse) para la demo con Docker
(servicio `airflow-bootstrap` de docker-compose.yml).

Los DAGs de dominio extraen de Mongo una ventana de UN día lógico (`ds`).
La siembra de demo (`backend/scripts/seed_demo_portafolio.py`) deja datos
de los últimos ~5 meses, así que hay que procesar cada día una vez para que
los paneles tácticos/estratégicos tengan historia.

No se usa `airflow dags backfill`: en este proyecto ya provocó un deadlock
real (BackfillJob + TriggerDagRunOperator hacia dag_publicar_indicadores,
ver CLAUDE.md §8.8). En su lugar se ejecutan las MISMAS funciones de las
tareas (PythonOperator.python_callable) en orden topológico, con un
contexto mínimo (`ds`, `ti` con XCom en memoria) -- sin pasar por el
scheduler y sin el TriggerDagRunOperator. Al final se corre una vez cada
tarea de `dag_publicar_indicadores` (publica los `rpt_*`) y se despausan
los DAGs para que el scheduler siga con la operación diaria normal.

Idempotente: si `corridas` (ClickHouse) ya tiene filas, no hace nada.

Uso (dentro de un contenedor de Airflow): python /opt/airflow/scripts/bootstrap_demo.py
"""

from __future__ import annotations

import inspect
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, "/opt/airflow/plugins")

from airflow.models import DagBag, DagModel  # noqa: E402
from airflow.operators.python import PythonOperator  # noqa: E402
from airflow.utils.session import create_session  # noqa: E402

import medallion  # noqa: E402

logging.basicConfig(level=logging.WARNING)

DIAS = int(os.environ.get("BOOTSTRAP_DIAS", "155"))
DAGS_DOMINIO = [
    "dag_captacion_gold", "dag_viajes_core", "dag_finanzas_gold",
    "dag_mantenimiento_gold", "dag_cumplimiento_gold", "dag_flota_gold",
]
# El histórico NYC necesita el CSV de 1.3M filas, que no viene en el repo.
NO_DESPAUSAR = {"dag_historico_nyc"}


class _TI:
    """TaskInstance mínima: solo lo que usan los DAGs del proyecto (XCom)."""

    def __init__(self, almacen: dict, task_id: str) -> None:
        self.almacen = almacen
        self.task_id = task_id

    def xcom_push(self, key: str, value) -> None:
        self.almacen[(self.task_id, key)] = value

    def xcom_pull(self, task_ids=None, key: str = "return_value", **_):
        if isinstance(task_ids, (list, tuple)):
            return [self.almacen.get((t, key)) for t in task_ids]
        return self.almacen.get((task_ids, key))


def _ejecutar(dag, ds: str) -> None:
    almacen: dict = {}
    for task in dag.topological_sort():
        if not isinstance(task, PythonOperator):
            continue  # TriggerDagRunOperator: la publicación se corre una sola vez al final
        ti = _TI(almacen, task.task_id)
        contexto = {"ds": ds, "ti": ti, "logical_date": datetime.fromisoformat(ds), "task": task, "dag": dag}
        firma = inspect.signature(task.python_callable)
        acepta_todo = any(p.kind is p.VAR_KEYWORD for p in firma.parameters.values())
        kwargs = dict(task.op_kwargs or {})
        kwargs.update(contexto if acepta_todo else {k: v for k, v in contexto.items() if k in firma.parameters})
        resultado = task.python_callable(*(task.op_args or []), **kwargs)
        almacen[(task.task_id, "return_value")] = resultado


def main() -> None:
    # Base y tablas Gold (idempotente, CREATE ... IF NOT EXISTS): en un
    # ClickHouse recién creado `urbanflet_gold` todavía no existe.
    medallion.ensure_schema()
    cliente = medallion.get_client()
    try:
        ya = cliente.query("SELECT count() FROM corridas").result_rows[0][0]
    except Exception:  # noqa: BLE001 -- la tabla aún no existe
        ya = 0
    if ya:
        print(f"La capa Gold ya tiene {ya} corridas registradas; bootstrap omitido.")
        return

    bag = DagBag("/opt/airflow/dags", include_examples=False)
    if bag.import_errors:
        print(f"Errores de importación de DAGs: {bag.import_errors}")
        sys.exit(1)

    hoy = date.today()
    inicio = time.monotonic()
    for dag_id in DAGS_DOMINIO:
        dag = bag.get_dag(dag_id)
        t = time.monotonic()
        for d in range(DIAS, -1, -1):
            _ejecutar(dag, (hoy - timedelta(days=d)).isoformat())
        print(f"{dag_id}: {DIAS + 1} días procesados en {time.monotonic() - t:.0f}s", flush=True)

    _ejecutar(bag.get_dag("dag_publicar_indicadores"), hoy.isoformat())
    print("dag_publicar_indicadores: rpt_* publicados", flush=True)

    # Registra los DAGs en el metastore (por si el scheduler aún no los
    # parseó) antes de despausarlos.
    bag.sync_to_db()
    with create_session() as session:
        for dag_id in bag.dag_ids:
            if dag_id in NO_DESPAUSAR:
                continue
            session.query(DagModel).filter(DagModel.dag_id == dag_id).update({"is_paused": False})
    print(f"Bootstrap analítico completo en {time.monotonic() - inicio:.0f}s.")


if __name__ == "__main__":
    main()
