"""CU-O15 -- dag_cumplimiento_gold

Diaria 04:00. Dos fuentes Mongo:
  - `documentos` (backend/src/cumplimiento/schemas.py) -> fact_cumplimiento_documental
  - `bitacora` (backend/src/core/db_mongo.py índice [actor_id, ts]) -> fact_integracion_api
    (la bitácora de auditoría es la fuente más cercana a "uso de integraciones
    por endpoint" que existe en el dominio; se usa como aproximación documentada).

Reglas Silver genéricas:
  - documentos: CAMPO_NULO (tipo/propietario_id ausentes), TIPO_INVALIDO
    (propietario_tipo fuera de {CONDUCTOR, VEHICULO}), dedup por documento_id.
  - bitacora: CAMPO_NULO (actor_id/accion ausentes), dedup por evento_id.

Bug real encontrado y corregido (auditoría nivel estratégico, 2026-08-08):
`documentos.fecha_emision`/`fecha_vencimiento` se guardan como string ISO
(`"2025-06-29"`, ver `documentos/schemas.py` -- `model_dump(mode="json")`, mismo
patrón ya documentado en CLAUDE.md §7.5 punto 3 para `fecha_vencimiento`), pero
`_extraer` comparaba ese campo contra un `datetime` de Python (`$gte`/`$lt`) --
Mongo nunca hace match entre tipos BSON distintos, así que el filtro devolvía 0
filas en TODA corrida desde que existe el DAG, sin importar la fecha lógica.
`rpt_documentacion_vigente` llevaba 0 filas desde siempre por esto, no por falta
de corridas recientes. Además, `documentos` es un registro de estado (vigencia
de un documento), no un evento con timestamp de creación real -- filtrar por
"emitido en las últimas 24h" nunca habría reflejado el estado vigente del
universo completo de documentos, incluso arreglando el tipo. Corregido
extrayendo el snapshot COMPLETO de `documentos` en cada corrida (sin filtro de
fecha), igual que otros `rpt_*` de estado (p.ej. tablero de Flota) -- cada
partición diaria en `fact_cumplimiento_documental` sigue siendo idempotente por
`fecha_logica` (ver `_silver_y_cuarentena`, exclusión de dedup contra la propia
partición). `bitacora` (evento real con `ts` como BSON Date) se deja sin
cambios, sigue siendo extracción incremental diaria correcta.
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
DAG_ID = "dag_cumplimiento_gold"
TIPOS_PROPIETARIO_VALIDOS = {"CONDUCTOR", "VEHICULO"}


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

    # `documentos` es estado (vigencia), no evento -- se extrae el snapshot
    # completo en cada corrida, no una ventana por fecha_emision (ver docstring
    # del módulo: fecha_emision es string ISO, no BSON Date, y aunque lo fuera
    # una ventana de 24h nunca reflejaría el estado vigente del universo
    # completo). `fin`/`inicio` ya no se usan para documentos, solo para bitacora.
    documentos = list(db.documentos.find({}))
    bitacora = list(db.bitacora.find({"ts": {"$gte": inicio, "$lt": fin}}))
    cliente.close()

    def _a_fecha(valor):
        # `fecha_emision`/`fecha_vencimiento` en Mongo son string ISO
        # ("2025-06-29", model_dump(mode="json")), no BSON Date -- ClickHouse
        # necesita un date() real para la columna Nullable(Date) de Bronze.
        if not valor:
            return None
        if isinstance(valor, str):
            return date.fromisoformat(valor)
        if isinstance(valor, datetime):
            return valor.date()
        return valor

    doc_crudos = [{
        "documento_id": str(d.get("_id")), "tipo": d.get("tipo") or "",
        "propietario_tipo": d.get("propietario_tipo") or "",
        "propietario_id": str(d.get("propietario_id")) if d.get("propietario_id") else "",
        "estado": d.get("estado") or "",
        "fecha_emision": _a_fecha(d.get("fecha_emision")),
        "fecha_vencimiento": _a_fecha(d.get("fecha_vencimiento")),
    } for d in documentos]
    bit_crudos = [{
        "evento_id": str(b.get("_id")), "actor_id": str(b.get("actor_id")) if b.get("actor_id") else "",
        "accion": b.get("accion") or "", "endpoint": b.get("endpoint") or b.get("accion") or "",
        "ts": b.get("ts"),
    } for b in bitacora]

    n1 = medallion.insertar_bronze("bronze_documentos", doc_crudos, lote_id)
    n2 = medallion.insertar_bronze("bronze_bitacora", bit_crudos, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="doc_crudos", value=doc_crudos)
    ti.xcom_push(key="bit_crudos", value=bit_crudos)
    ti.xcom_push(key="registros_extraidos", value=len(doc_crudos) + len(bit_crudos))
    ti.xcom_push(key="duracion_bronze_seg", value=dur)
    LOGGER.info("Bronze cumplimiento: %d documentos, %d bitácora en %.2fs", n1, n2, dur)


def _silver_y_cuarentena(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    doc_crudos = ti.xcom_pull(task_ids="extraer", key="doc_crudos")
    bit_crudos = ti.xcom_pull(task_ids="extraer", key="bit_crudos")
    t0 = time.time()

    # Se excluye la propia partición fecha_logica del dedup contra Gold (A3).
    client = medallion.get_client()
    fecha_logica = context["ds"]
    existentes_doc = set(row[0] for row in client.query(
        "SELECT DISTINCT documento_id FROM urbanflet_gold.fact_cumplimiento_documental WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    existentes_bit = set(row[0] for row in client.query(
        "SELECT DISTINCT evento_id FROM urbanflet_gold.fact_integracion_api WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    client.close()

    rechazados = []
    vistos_doc, doc_validos = set(), []
    for d in doc_crudos:
        flag = None
        if not d.get("tipo") or not d.get("propietario_id"):
            flag = "CAMPO_NULO"
        elif d.get("propietario_tipo") not in TIPOS_PROPIETARIO_VALIDOS:
            flag = "TIPO_INVALIDO"
        elif d["documento_id"] in vistos_doc or d["documento_id"] in existentes_doc:
            flag = "DUPLICADO"
        else:
            vistos_doc.add(d["documento_id"])

        if flag is not None:
            rechazados.append({"id_origen": d["documento_id"], "flag": flag, "valores": d})
        else:
            doc_validos.append(d)

    vistos_bit, bit_validos = set(), []
    for b in bit_crudos:
        flag = None
        if not b.get("actor_id") or not b.get("accion"):
            flag = "CAMPO_NULO"
        elif b["evento_id"] in vistos_bit or b["evento_id"] in existentes_bit:
            flag = "DUPLICADO"
        else:
            vistos_bit.add(b["evento_id"])

        if flag is not None:
            rechazados.append({"id_origen": b["evento_id"], "flag": flag, "valores": b})
        else:
            bit_validos.append(b)

    n_cuarentena = medallion.insertar_cuarentena("cumplimiento", rechazados, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="doc_validos", value=doc_validos)
    ti.xcom_push(key="bit_validos", value=bit_validos)
    ti.xcom_push(key="duracion_silver_seg", value=dur)
    ti.xcom_push(key="registros_validos", value=len(doc_validos) + len(bit_validos))
    ti.xcom_push(key="registros_cuarentena", value=n_cuarentena)
    LOGGER.info("Silver cumplimiento: %d válidos, %d en cuarentena en %.2fs",
                len(doc_validos) + len(bit_validos), n_cuarentena, dur)


def _gold(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    doc_validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="doc_validos")
    bit_validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="bit_validos")
    fecha_logica = context["ds"]
    t0 = time.time()

    # fact_cumplimiento_documental no tiene columna fecha_emision (solo
    # fecha_vencimiento) -- se excluye explícitamente, nunca se detectó antes
    # porque doc_validos siempre llegaba vacío (bug de extracción, ver docstring
    # del módulo).
    filas_doc = [{
        "documento_id": d["documento_id"], "tipo": d["tipo"],
        "propietario_tipo": d["propietario_tipo"], "propietario_id": d["propietario_id"],
        "estado": d["estado"], "fecha_vencimiento": d.get("fecha_vencimiento"),
        "fecha": fecha_logica, "lote_id": lote_id,
    } for d in doc_validos]
    filas_bit = [{
        "evento_id": b["evento_id"], "actor_id": b["actor_id"], "endpoint": b["endpoint"],
        "accion": b["accion"], "ts": b.get("ts"), "fecha": fecha_logica, "lote_id": lote_id,
    } for b in bit_validos]

    n1 = medallion.cargar_gold_idempotente("fact_cumplimiento_documental", filas_doc, fecha_logica, lote_id)
    n2 = medallion.cargar_gold_idempotente("fact_integracion_api", filas_bit, fecha_logica, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="duracion_gold_seg", value=dur)
    LOGGER.info("Gold cumplimiento: %d docs, %d eventos api (fecha=%s)", n1, n2, fecha_logica)


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
    description="CU-O15: Bronze->Silver->Gold diario de cumplimiento documental e integraciones API.",
    schedule_interval="0 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cu-o15", "medallion", "cumplimiento"],
) as dag:

    extraer = PythonOperator(task_id="extraer", python_callable=_extraer)
    silver_y_cuarentena = PythonOperator(task_id="silver_y_cuarentena", python_callable=_silver_y_cuarentena)
    gold = PythonOperator(task_id="gold", python_callable=_gold)
    metricas = PythonOperator(task_id="metricas", python_callable=_metricas)
    # CU-O16 P1: dispara dag_publicar_indicadores como corrida propia (ver
    # comentario extenso en dag_finanzas_gold.py -- mismo mecanismo).
    disparar_publicacion = TriggerDagRunOperator(
        task_id="disparar_publicacion_indicadores",
        trigger_dag_id="dag_publicar_indicadores",
        wait_for_completion=False,
    )

    extraer >> silver_y_cuarentena >> gold >> metricas >> disparar_publicacion
