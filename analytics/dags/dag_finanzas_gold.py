"""CU-O15 -- dag_finanzas_gold

Diaria 03:00. Extrae de Mongo `pagos` y `liquidaciones` (backend/src/recaudacion/schemas.py)
del día lógico y carga fact_recaudacion + fact_liquidacion de forma idempotente.

Reglas Silver genéricas (el dominio no tiene tabla de reglas propia en la spec):
  - CAMPO_NULO: monto/tarifa_final o campos de liquidación ausentes
  - MONTO_NEGATIVO: monto < 0
  - ESTADO_INVALIDO: fuera del enum conocido
  - Dedup por id (pago_id / liquidacion_id) dentro del lote y contra Gold.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

sys.path.append("/opt/airflow/plugins")
import medallion  # noqa: E402

LOGGER = logging.getLogger("airflow.task")
DAG_ID = "dag_finanzas_gold"
ESTADOS_PAGO_VALIDOS = {"VALIDADO", "DISCREPANCIA", "PENDIENTE_CONFIRMACION"}
ESTADOS_LIQ_VALIDOS = {"EMITIDA", "OBSERVADA", "APROBADA", "PAGADA"}


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

    pagos = list(db.pagos.find({"ts_registro": {"$gte": inicio, "$lt": fin}}))
    liquidaciones = list(db.liquidaciones.find({"ts_emision": {"$gte": inicio, "$lt": fin}}))
    cliente.close()

    pagos_crudos = [{
        "pago_id": str(p.get("_id")), "viaje_id": p.get("viaje_id") or "",
        "conductor_id": str(p.get("conductor_id")) if p.get("conductor_id") else "",
        "metodo": p.get("metodo"), "monto": p.get("monto"), "tarifa_final": p.get("tarifa_final"),
        "estado": p.get("estado"), "ts_registro": p.get("ts_registro"),
    } for p in pagos]
    liq_crudos = [{
        "liquidacion_id": str(l.get("_id")), "conductor_id": str(l.get("conductor_id")) if l.get("conductor_id") else "",
        "periodo_inicio": l.get("periodo_inicio"), "periodo_fin": l.get("periodo_fin"),
        "estado": l.get("estado"), "bruto": l.get("bruto"), "comisiones": l.get("comisiones"),
        "ajustes": l.get("ajustes"), "neto": l.get("neto"), "ts_emision": l.get("ts_emision"),
        "ts_pago": l.get("ts_pago"),
    } for l in liquidaciones]

    n1 = medallion.insertar_bronze("bronze_pagos", pagos_crudos, lote_id)
    n2 = medallion.insertar_bronze("bronze_liquidaciones", liq_crudos, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="pagos_crudos", value=pagos_crudos)
    ti.xcom_push(key="liq_crudos", value=liq_crudos)
    ti.xcom_push(key="registros_extraidos", value=len(pagos_crudos) + len(liq_crudos))
    ti.xcom_push(key="duracion_bronze_seg", value=dur)
    LOGGER.info("Bronze finanzas: %d pagos, %d liquidaciones en %.2fs", n1, n2, dur)


def _silver_y_cuarentena(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    pagos_crudos = ti.xcom_pull(task_ids="extraer", key="pagos_crudos")
    liq_crudos = ti.xcom_pull(task_ids="extraer", key="liq_crudos")
    t0 = time.time()

    # Se excluye la propia partición fecha_logica del dedup contra Gold (A3).
    client = medallion.get_client()
    fecha_logica = context["ds"]
    existentes_pagos = set(row[0] for row in client.query(
        "SELECT DISTINCT pago_id FROM urbanflet_gold.fact_recaudacion WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    existentes_liq = set(row[0] for row in client.query(
        "SELECT DISTINCT liquidacion_id FROM urbanflet_gold.fact_liquidacion WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    client.close()

    rechazados = []
    vistos_pagos, pagos_validos = set(), []
    for p in pagos_crudos:
        flag = None
        if p.get("monto") is None or p.get("tarifa_final") is None:
            flag = "CAMPO_NULO"
        elif p["monto"] < 0:
            flag = "MONTO_NEGATIVO"
        elif p.get("estado") not in ESTADOS_PAGO_VALIDOS:
            flag = "ESTADO_INVALIDO"
        elif p["pago_id"] in vistos_pagos or p["pago_id"] in existentes_pagos:
            flag = "DUPLICADO"
        else:
            vistos_pagos.add(p["pago_id"])

        if flag is not None:
            rechazados.append({"id_origen": p["pago_id"], "flag": flag, "valores": p})
        else:
            pagos_validos.append(p)

    vistos_liq, liq_validos = set(), []
    for l in liq_crudos:
        flag = None
        if l.get("bruto") is None or l.get("neto") is None:
            flag = "CAMPO_NULO"
        elif l.get("estado") not in ESTADOS_LIQ_VALIDOS:
            flag = "ESTADO_INVALIDO"
        elif l["liquidacion_id"] in vistos_liq or l["liquidacion_id"] in existentes_liq:
            flag = "DUPLICADO"
        else:
            vistos_liq.add(l["liquidacion_id"])

        if flag is not None:
            rechazados.append({"id_origen": l["liquidacion_id"], "flag": flag, "valores": l})
        else:
            liq_validos.append(l)

    n_cuarentena = medallion.insertar_cuarentena("finanzas", rechazados, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="pagos_validos", value=pagos_validos)
    ti.xcom_push(key="liq_validos", value=liq_validos)
    ti.xcom_push(key="duracion_silver_seg", value=dur)
    ti.xcom_push(key="registros_validos", value=len(pagos_validos) + len(liq_validos))
    ti.xcom_push(key="registros_cuarentena", value=n_cuarentena)
    LOGGER.info("Silver finanzas: %d válidos, %d en cuarentena en %.2fs",
                len(pagos_validos) + len(liq_validos), n_cuarentena, dur)


def _gold(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    pagos_validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="pagos_validos")
    liq_validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="liq_validos")
    fecha_logica = context["ds"]
    t0 = time.time()

    filas_pagos = [{
        "pago_id": p["pago_id"], "viaje_id": p["viaje_id"], "conductor_id": p["conductor_id"],
        "metodo": p.get("metodo") or "", "monto": p["monto"], "tarifa_final": p["tarifa_final"],
        "diferencia": (p["monto"] - p["tarifa_final"]), "estado": p.get("estado") or "",
        "ts_registro": p.get("ts_registro"), "fecha": fecha_logica, "lote_id": lote_id,
    } for p in pagos_validos]
    filas_liq = [{
        "liquidacion_id": l["liquidacion_id"], "conductor_id": l["conductor_id"],
        "periodo_inicio": l.get("periodo_inicio"), "periodo_fin": l.get("periodo_fin"),
        "estado": l.get("estado") or "", "bruto": l["bruto"], "comisiones": l.get("comisiones") or 0,
        "ajustes": l.get("ajustes") or 0, "neto": l["neto"], "ts_emision": l.get("ts_emision"),
        "ts_pago": l.get("ts_pago"), "fecha": fecha_logica, "lote_id": lote_id,
    } for l in liq_validos]

    n1 = medallion.cargar_gold_idempotente("fact_recaudacion", filas_pagos, fecha_logica, lote_id)
    n2 = medallion.cargar_gold_idempotente("fact_liquidacion", filas_liq, fecha_logica, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="duracion_gold_seg", value=dur)
    LOGGER.info("Gold finanzas: %d en fact_recaudacion, %d en fact_liquidacion (fecha=%s)", n1, n2, fecha_logica)


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
    description="CU-O15: Bronze->Silver->Gold diario de recaudación y liquidaciones (fact_recaudacion, fact_liquidacion).",
    schedule_interval="0 3 * * *",
    # start_date bajado a 2020 (antes 2024) -- ver mismo comentario en
    # dag_viajes_core.py: permite backfill manual de fechas históricas sin
    # que el scheduler cierre el DagRun como "success" con 0 TaskInstances.
    start_date=datetime(2020, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cu-o15", "medallion", "finanzas"],
) as dag:

    extraer = PythonOperator(task_id="extraer", python_callable=_extraer)
    silver_y_cuarentena = PythonOperator(task_id="silver_y_cuarentena", python_callable=_silver_y_cuarentena)
    gold = PythonOperator(task_id="gold", python_callable=_gold)
    metricas = PythonOperator(task_id="metricas", python_callable=_metricas)
    # CU-O16 P1: "con la carga Gold confirmada, el sistema refresca las
    # vistas materializadas" -- dispara dag_publicar_indicadores como una
    # corrida propia (auditable en su historial de DagRuns), no una llamada
    # inline. trigger_rule por defecto es "all_success": solo dispara si
    # extraer/silver/gold/metricas terminaron sin excepción, que es
    # exactamente cuando `metricas` ya dejó la corrida en estado OK o WARN
    # (FAILED corta la cadena antes de llegar acá). Cada tarea de
    # dag_publicar_indicadores vuelve a chequear el estado OK/WARN de este
    # dominio por su cuenta (indicadores._ultima_corrida_ok_o_warn), así que
    # el disparo es seguro incluso si algo más lo dispara en paralelo.
    disparar_publicacion = TriggerDagRunOperator(
        task_id="disparar_publicacion_indicadores",
        trigger_dag_id="dag_publicar_indicadores",
        wait_for_completion=False,
    )

    extraer >> silver_y_cuarentena >> gold >> metricas >> disparar_publicacion
