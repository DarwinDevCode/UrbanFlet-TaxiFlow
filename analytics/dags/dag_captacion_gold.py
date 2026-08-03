"""CU-O15 -- dag_captacion_gold

Diaria 03:30. Dos fuentes independientes, ambas necesarias para los
informes tácticos de Captación (specs/nivel-tactico/tactico_captacion.md):

  - `usuarios` (altas del día lógico, por `ts_creacion`) -> Gold
    `fact_registro_usuario` -- alimenta "altas y retención por canal".
  - `solicitudes` (postulaciones enviadas el día lógico, por `fecha_envio`)
    -> Gold `fact_solicitud_captacion` -- alimenta "conversión y tiempo de
    aprobación por canal". Antes de esta versión el DAG solo tocaba
    `usuarios` y el `canal` de Gold estaba HARDCODEADO a "app" (bug real,
    nunca reflejaba el dato real) -- corregido junto con el backfill de
    `canal` en Mongo (`backend/scripts/backfill_canal.py`).

Reglas Silver genéricas:
  - CAMPO_NULO: usuario_id/estado (o solicitud_id/estado/fecha_envio) ausentes
  - SIN_CONTACTO (solo usuarios): ni telefono ni email
  - Dedup por id dentro del lote y contra Gold (ambas fuentes comparten la
    tabla `cuarentena_captacion`, distinguibles por el prefijo de `id_origen`).
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
DAG_ID = "dag_captacion_gold"


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

    # Bug real preexistente corregido acá: este DAG filtraba por `ts_creacion`,
    # un campo que `usuarios` nunca tuvo -- el campo real es `fecha_registro`
    # (ver backend/src/auth/service.py). fact_registro_usuario llevaba desde
    # siempre 0 filas por esto, nunca detectado porque nada dependía todavía
    # de ese dato hasta este dashboard táctico.
    usuarios = list(db.usuarios.find({"fecha_registro": {"$gte": inicio, "$lt": fin}}))
    solicitudes = list(db.solicitudes.find({"fecha_envio": {"$gte": inicio, "$lt": fin}}))
    cliente.close()

    crudos_usuarios = [{
        "usuario_id": str(u.get("_id")),
        "tipo": u.get("tipo") or ("CONDUCTOR" if u.get("conductor") else "PASAJERO"),
        "estado": u.get("estado") or "ACTIVO",
        "telefono": u.get("telefono") or "",
        "email": u.get("email") or "",
        "canal": u.get("canal") or "web",
        "ts_creacion": u.get("fecha_registro"),
    } for u in usuarios]

    crudos_solicitudes = [{
        "solicitud_id": str(s.get("_id")),
        "estado": s.get("estado") or "",
        "canal": s.get("canal") or "web",
        "fecha_envio": s.get("fecha_envio"),
        "fecha_decision": s.get("fecha_decision"),
    } for s in solicitudes]

    n_usuarios = medallion.insertar_bronze("bronze_usuarios", crudos_usuarios, lote_id)
    n_solicitudes = medallion.insertar_bronze("bronze_solicitudes", crudos_solicitudes, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="crudos_usuarios", value=crudos_usuarios)
    ti.xcom_push(key="crudos_solicitudes", value=crudos_solicitudes)
    ti.xcom_push(key="registros_extraidos", value=len(crudos_usuarios) + len(crudos_solicitudes))
    ti.xcom_push(key="duracion_bronze_seg", value=dur)
    LOGGER.info(
        "Bronze captación: %d usuarios + %d solicitudes extraídos en %.2fs", n_usuarios, n_solicitudes, dur
    )


def _silver_y_cuarentena(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    crudos_usuarios = ti.xcom_pull(task_ids="extraer", key="crudos_usuarios")
    crudos_solicitudes = ti.xcom_pull(task_ids="extraer", key="crudos_solicitudes")
    t0 = time.time()
    fecha_logica = context["ds"]

    client = medallion.get_client()
    usuarios_existentes = set(row[0] for row in client.query(
        "SELECT DISTINCT usuario_id FROM urbanflet_gold.fact_registro_usuario WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    solicitudes_existentes = set(row[0] for row in client.query(
        "SELECT DISTINCT solicitud_id FROM urbanflet_gold.fact_solicitud_captacion WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    client.close()

    vistos_usuarios: set[str] = set()
    validos_usuarios, rechazados = [], []
    for r in crudos_usuarios:
        flag = None
        if not r.get("usuario_id") or not r.get("estado"):
            flag = "CAMPO_NULO"
        elif not r.get("telefono") and not r.get("email"):
            flag = "SIN_CONTACTO"
        elif r["usuario_id"] in vistos_usuarios or r["usuario_id"] in usuarios_existentes:
            flag = "DUPLICADO"
        else:
            vistos_usuarios.add(r["usuario_id"])

        if flag is not None:
            rechazados.append({"id_origen": f"usuario:{r['usuario_id']}", "flag": flag, "valores": r})
        else:
            validos_usuarios.append(r)

    vistos_solicitudes: set[str] = set()
    validos_solicitudes = []
    for r in crudos_solicitudes:
        flag = None
        if not r.get("solicitud_id") or not r.get("estado") or not r.get("fecha_envio"):
            flag = "CAMPO_NULO"
        elif r["solicitud_id"] in vistos_solicitudes or r["solicitud_id"] in solicitudes_existentes:
            flag = "DUPLICADO"
        else:
            vistos_solicitudes.add(r["solicitud_id"])

        if flag is not None:
            rechazados.append({"id_origen": f"solicitud:{r['solicitud_id']}", "flag": flag, "valores": r})
        else:
            validos_solicitudes.append(r)

    n_cuarentena = medallion.insertar_cuarentena("captacion", rechazados, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="validos_usuarios", value=validos_usuarios)
    ti.xcom_push(key="validos_solicitudes", value=validos_solicitudes)
    ti.xcom_push(key="duracion_silver_seg", value=dur)
    ti.xcom_push(key="registros_validos", value=len(validos_usuarios) + len(validos_solicitudes))
    ti.xcom_push(key="registros_cuarentena", value=n_cuarentena)
    LOGGER.info(
        "Silver captación: %d/%d válidos, %d en cuarentena en %.2fs",
        len(validos_usuarios), len(validos_solicitudes), n_cuarentena, dur,
    )


def _gold(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    validos_usuarios = ti.xcom_pull(task_ids="silver_y_cuarentena", key="validos_usuarios")
    validos_solicitudes = ti.xcom_pull(task_ids="silver_y_cuarentena", key="validos_solicitudes")
    fecha_logica = context["ds"]
    t0 = time.time()

    filas_usuarios = [{
        "usuario_id": r["usuario_id"], "tipo": r["tipo"], "estado": r["estado"],
        "canal": r["canal"], "ts_creacion": r.get("ts_creacion"),
        "fecha": fecha_logica, "lote_id": lote_id,
    } for r in validos_usuarios]

    filas_solicitudes = []
    for r in validos_solicitudes:
        dias_aprobacion = None
        if r.get("fecha_decision") and r.get("fecha_envio"):
            dias_aprobacion = (r["fecha_decision"] - r["fecha_envio"]).total_seconds() / 86400
        filas_solicitudes.append({
            "solicitud_id": r["solicitud_id"], "estado": r["estado"], "canal": r["canal"],
            "fecha_envio": r["fecha_envio"], "fecha_decision": r.get("fecha_decision"),
            "dias_aprobacion": dias_aprobacion, "fecha": fecha_logica, "lote_id": lote_id,
        })

    n1 = medallion.cargar_gold_idempotente("fact_registro_usuario", filas_usuarios, fecha_logica, lote_id)
    n2 = medallion.cargar_gold_idempotente("fact_solicitud_captacion", filas_solicitudes, fecha_logica, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="duracion_gold_seg", value=dur)
    LOGGER.info(
        "Gold captación: %d filas en fact_registro_usuario, %d en fact_solicitud_captacion (fecha=%s)",
        n1, n2, fecha_logica,
    )


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
    description="CU-O15: Bronze->Silver->Gold diario de captación (fact_registro_usuario + fact_solicitud_captacion).",
    schedule_interval="30 3 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cu-o15", "medallion", "captacion"],
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
