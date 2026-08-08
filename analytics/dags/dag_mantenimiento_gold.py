"""CU-O15 -- dag_mantenimiento_gold

Diaria 04:30. Extrae de Mongo `ordenes` (backend/src/mantenimiento/schemas.py:
OrdenOut) las órdenes CERRADAS cuya `fecha_cierre` cae en el día lógico y
carga fact_orden_mantenimiento de forma idempotente.

Grano y partición -- por qué `fecha_cierre`, no `fecha_programada`: a
diferencia de los otros dominios, `ordenes` no tiene ningún timestamp de
creación (`backend/src/mantenimiento/service.py::crear_orden` no setea nada
tipo `ts_creacion`), y las órdenes ANULADA tampoco quedan con ninguna fecha
utilizable (`anular_orden` solo cambia `estado`+`motivo_anulacion`). El único
datetime real y siempre presente quedó en `fecha_cierre`, que además es
exactamente el momento en que el costo y el cumplimiento del plan se
confirman -- mismo criterio que `fact_viaje` usa `ts_fin`, no `ts_solicitud`.
Las órdenes ABIERTA/EN_TALLER/ANULADA quedan fuera de este fact (no tienen
costo ni fecha de cierre que aportar); no es una omisión, es coherente con
"un hecho == un evento de negocio confirmado".

Nota de alcance -- no existe una spec de nivel táctico en este repo
(`specs/nivel-tactico/` está vacío; ver CLAUDE.md §1) que defina la
agregación exacta de "cumplimiento del plan preventivo por mes" ni "costo de
mantenimiento por vehículo y periodo". El diseño de abajo es una
interpretación razonable, documentada, sobre los campos reales que expone
`OrdenOut`:
  - `cumple_plazo` (0/1, solo relevante para tipo=PREVENTIVA): la orden
    cerró en o antes de su `fecha_programada`. El informe de cumplimiento
    del plan preventivo agrega esto por mes, filtrando tipo=PREVENTIVA.
  - Costo por vehículo y periodo: suma de `costo_total` agrupada por
    `vehiculo_id` y mes de cierre -- ambos tipos de orden (PREVENTIVA y
    CORRECTIVA) cuentan para el costo total del vehículo.

Reglas Silver genéricas (el dominio no tiene tabla de reglas propia en la
spec, igual que finanzas/flota):
  - CAMPO_NULO: orden_id/vehiculo_id/tipo/fecha_programada ausentes.
  - TIPO_INVALIDO: tipo fuera de {PREVENTIVA, CORRECTIVA}.
  - MONTO_NEGATIVO: costo_total < 0.
  - Dedup por orden_id dentro del lote y contra Gold.

Piloto de Parquet versionado (`specs/nivel-estrategico/nivel_estrategico.md`
Sección 5, ver CLAUDE.md nota Airflow): este es el único de los 7 DAGs de
dominio con el paso `exportar_parquet` -- decisión consciente de probar
primero sobre el dominio de menor volumen/riesgo antes de tocar los 6
restantes (varios con historial de producción real, incluida la carga de
1.3M filas NYC). Escribe 3 archivos Parquet por corrida (uno por etapa:
Bronze crudo, Silver validado, Gold agregado) en
`/opt/airflow/exports/datos/<etapa-es>/mantenimiento/<fecha_logica>/<lote_id>.parquet`
(bind-mount `./analytics/exports` en `docker-compose.yml`, solo en
`airflow-scheduler` -- LocalExecutor ejecuta las tareas por fork() ahí
mismo). `lote_id` ya es único por corrida, así que nunca sobrescribe un
archivo anterior. Ver `medallion.py::exportar_parquet` para el detalle de
implementación (pandas + pyarrow, ambos ya presentes en la imagen base de
Airflow, sin dependencia nueva).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date, datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

sys.path.append("/opt/airflow/plugins")
import medallion  # noqa: E402

LOGGER = logging.getLogger("airflow.task")
DAG_ID = "dag_mantenimiento_gold"
TIPOS_VALIDOS = {"PREVENTIVA", "CORRECTIVA"}


def _extraer(**context):
    medallion.ensure_schema()
    ti = context["ti"]
    lote_id = medallion.registrar_inicio_corrida(DAG_ID, context["ds"])
    ti.xcom_push(key="lote_id", value=lote_id)
    ti.xcom_push(key="iniciado_en", value=datetime.utcnow().isoformat())
    t0 = time.time()

    from pymongo import MongoClient
    cliente = MongoClient(os.environ["MONGO_URI"])
    db = cliente[os.environ.get("MONGO_DB_NAME", "urbanflet")]

    inicio = datetime.fromisoformat(context["ds"])
    fin = inicio + timedelta(days=1)
    ordenes = list(db.ordenes.find({"estado": "CERRADA", "fecha_cierre": {"$gte": inicio, "$lt": fin}}))
    cliente.close()

    # `ordenes.fecha_programada` se guarda en Mongo como string ISO
    # (backend/src/mantenimiento/service.py::crear_orden hace
    # `fecha_programada.isoformat()`, no un BSON date) -- a diferencia de
    # `fecha_cierre`, que sí es un BSON date real y pymongo lo decodifica
    # como `datetime` automáticamente. clickhouse_connect necesita un
    # `date`/`datetime` real para una columna `Date` (hace aritmética de
    # días contra la época, no una conversión implícita de string), así que
    # se convierte acá antes de que llegue a Bronze.
    crudos = [{
        "orden_id": str(o.get("_id")) if o.get("_id") else None,
        "vehiculo_id": str(o.get("vehiculo_id")) if o.get("vehiculo_id") else None,
        "tipo": o.get("tipo"),
        "km_entrada": o.get("km_entrada"),
        "km_salida": o.get("km_salida"),
        "costo_total": o.get("costo_total"),
        "horas_taller": o.get("horas_taller"),
        "fecha_programada": date.fromisoformat(o["fecha_programada"]) if o.get("fecha_programada") else None,
        "fecha_cierre": o.get("fecha_cierre"),
    } for o in ordenes]

    n = medallion.insertar_bronze("bronze_ordenes_mantenimiento", crudos, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="crudos", value=crudos)
    ti.xcom_push(key="registros_extraidos", value=len(crudos))
    ti.xcom_push(key="duracion_bronze_seg", value=dur)
    LOGGER.info("Bronze mantenimiento: %d extraídos en %.2fs", n, dur)


def _silver_y_cuarentena(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    crudos = ti.xcom_pull(task_ids="extraer", key="crudos")
    t0 = time.time()

    # Se excluye la propia partición fecha_logica del chequeo de dedup contra
    # Gold -- mismo criterio que el resto de los DAGs (reprocesar la MISMA
    # fecha lógica no debe marcarse duplicado, solo otra fecha lógica sí).
    client = medallion.get_client()
    fecha_logica = context["ds"]
    existentes = set(row[0] for row in client.query(
        "SELECT DISTINCT orden_id FROM urbanflet_gold.fact_orden_mantenimiento WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    client.close()

    vistos = set()
    validos, rechazados = [], []
    for r in crudos:
        flag = None
        if not r.get("orden_id") or not r.get("vehiculo_id") or not r.get("tipo") or not r.get("fecha_programada"):
            flag = "CAMPO_NULO"
        elif r["tipo"] not in TIPOS_VALIDOS:
            flag = "TIPO_INVALIDO"
        elif r.get("costo_total") is not None and r["costo_total"] < 0:
            flag = "MONTO_NEGATIVO"
        else:
            if r["orden_id"] in vistos or r["orden_id"] in existentes:
                flag = "DUPLICADO"
            else:
                vistos.add(r["orden_id"])

        if flag is not None:
            rechazados.append({"id_origen": r.get("orden_id") or "?", "flag": flag, "valores": r})
        else:
            validos.append(r)

    n_cuarentena = medallion.insertar_cuarentena("mantenimiento", rechazados, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="validos", value=validos)
    ti.xcom_push(key="duracion_silver_seg", value=dur)
    ti.xcom_push(key="registros_validos", value=len(validos))
    ti.xcom_push(key="registros_cuarentena", value=n_cuarentena)
    LOGGER.info("Silver mantenimiento: %d válidos, %d en cuarentena en %.2fs", len(validos), n_cuarentena, dur)


def _gold(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="validos")
    fecha_logica = context["ds"]
    t0 = time.time()

    filas = []
    for r in validos:
        # `fecha_programada` ya llega como `date` real desde `_extraer`
        # (ver comentario ahí); XCom la pudo haber devuelto como string
        # ISO ("YYYY-MM-DD") tras el viaje de ida y vuelta por JSON -- se
        # normaliza de nuevo por si acaso, la columna Gold es `Date` y
        # necesita un objeto real, no un string.
        fecha_programada = r["fecha_programada"]
        fecha_programada_date = fecha_programada if isinstance(fecha_programada, date) else date.fromisoformat(str(fecha_programada)[:10])
        fecha_cierre = r["fecha_cierre"]
        fecha_cierre_date = fecha_cierre.date() if hasattr(fecha_cierre, "date") else date.fromisoformat(str(fecha_cierre)[:10])
        cumple_plazo = 1 if r["tipo"] == "PREVENTIVA" and fecha_cierre_date <= fecha_programada_date else 0
        filas.append({
            "orden_id": r["orden_id"], "vehiculo_id": r["vehiculo_id"], "tipo": r["tipo"],
            "km_entrada": r.get("km_entrada"), "km_salida": r.get("km_salida"),
            "costo_total": r.get("costo_total"), "horas_taller": r.get("horas_taller"),
            "fecha_programada": fecha_programada_date, "cumple_plazo": cumple_plazo,
            "fecha": fecha_logica, "lote_id": lote_id,
        })

    n = medallion.cargar_gold_idempotente("fact_orden_mantenimiento", filas, fecha_logica, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="duracion_gold_seg", value=dur)
    # Se re-empuja `filas` (no solo la duración) porque `_exportar_parquet`
    # necesita el mismo contenido Gold ya con fecha_programada/fecha_cierre
    # normalizados a `date` real -- recalcularlo en la tarea de export
    # duplicaría esta lógica de normalización sin ganar nada.
    ti.xcom_push(key="filas", value=filas)
    LOGGER.info("Gold mantenimiento: %d filas en fact_orden_mantenimiento (fecha=%s)", n, fecha_logica)


def _exportar_parquet(**context):
    """CU-O15 + nivel_estrategico.md Sección 5 (piloto): escribe un Parquet
    versionado por corrida para cada una de las 3 etapas Medallion de esta
    corrida (Bronze crudo, Silver validado, Gold agregado) -- respaldo/
    control de versiones granular por corrida ETL, independiente del
    respaldo completo de base de datos del Módulo 7 de Administración (ver
    nivel_estrategico.md §5). No reemplaza ninguna tabla de ClickHouse ya
    cargada por las tareas anteriores, es un paso adicional de solo
    escritura a disco."""
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    fecha_logica = context["ds"]
    crudos = ti.xcom_pull(task_ids="extraer", key="crudos") or []
    validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="validos") or []
    gold_filas = ti.xcom_pull(task_ids="gold", key="filas") or []

    rutas = {
        "extraccion": medallion.exportar_parquet("bronze", "mantenimiento", fecha_logica, lote_id, crudos),
        "transformacion": medallion.exportar_parquet("silver", "mantenimiento", fecha_logica, lote_id, validos),
        "carga": medallion.exportar_parquet("gold", "mantenimiento", fecha_logica, lote_id, gold_filas),
    }
    ti.xcom_push(key="rutas_parquet", value=rutas)
    LOGGER.info("Parquet versionado escrito para lote_id=%s: %s", lote_id, rutas)


def _metricas(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    iniciado_en = datetime.fromisoformat(ti.xcom_pull(task_ids="extraer", key="iniciado_en"))
    estado = medallion.finalizar_corrida(
        dag_id=DAG_ID, fecha_logica=context["ds"], lote_id=lote_id,
        registros_extraidos=ti.xcom_pull(task_ids="extraer", key="registros_extraidos"),
        registros_validos=ti.xcom_pull(task_ids="silver_y_cuarentena", key="registros_validos"),
        registros_cuarentena=ti.xcom_pull(task_ids="silver_y_cuarentena", key="registros_cuarentena"),
        duracion_bronze_seg=ti.xcom_pull(task_ids="extraer", key="duracion_bronze_seg"),
        duracion_silver_seg=ti.xcom_pull(task_ids="silver_y_cuarentena", key="duracion_silver_seg"),
        duracion_gold_seg=ti.xcom_pull(task_ids="gold", key="duracion_gold_seg"),
        iniciado_en=iniciado_en,
    )
    LOGGER.info("Corrida %s finalizada con estado=%s", lote_id, estado)


default_args = {
    "owner": "plataforma-bi",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=45),
    "on_failure_callback": medallion.on_failure_callback_factory(DAG_ID),
}

with DAG(
    dag_id=DAG_ID,
    description="CU-O15: Bronze->Silver->Gold diario de órdenes de mantenimiento cerradas (fact_orden_mantenimiento).",
    schedule_interval="30 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cu-o15", "medallion", "mantenimiento"],
) as dag:

    extraer = PythonOperator(task_id="extraer", python_callable=_extraer)
    silver_y_cuarentena = PythonOperator(task_id="silver_y_cuarentena", python_callable=_silver_y_cuarentena)
    gold = PythonOperator(task_id="gold", python_callable=_gold)
    # Piloto de Parquet versionado (nivel_estrategico.md §5, ver CLAUDE.md
    # nota Airflow) -- corre después de `gold` (necesita las 3 etapas ya
    # resueltas) y antes de `metricas`, para que un fallo de escritura a
    # disco quede reflejado en el estado de la corrida igual que cualquier
    # otra tarea, no como un efecto secundario silencioso post-cierre.
    exportar_parquet = PythonOperator(task_id="exportar_parquet", python_callable=_exportar_parquet)
    metricas = PythonOperator(task_id="metricas", python_callable=_metricas)
    # CU-O16 P1: dispara dag_publicar_indicadores como corrida propia (ver
    # comentario extenso en dag_finanzas_gold.py -- mismo mecanismo).
    disparar_publicacion = TriggerDagRunOperator(
        task_id="disparar_publicacion_indicadores",
        trigger_dag_id="dag_publicar_indicadores",
        wait_for_completion=False,
    )

    extraer >> silver_y_cuarentena >> gold >> exportar_parquet >> metricas >> disparar_publicacion
