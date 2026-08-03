"""CU-O15 -- dag_flota_gold

Horaria. Extrae de Mongo `posiciones` (backend/src/core/db_mongo.py índice
[vehiculo_id, ts_servidor], TTL 7 días) las reportadas en la hora lógica de la
corrida y carga fact_ubicacion_flota de forma idempotente.

Reglas Silver (el dominio no tiene reglas propias en la spec -- se usan
validaciones genéricas razonables citadas en la consigna: campos obligatorios
no nulos, enum válido, rango de fecha coherente):
  - CAMPO_NULO: vehiculo_id/lat/lon/ts_servidor ausentes
  - COORD_INVALIDA: lat fuera de [-90,90] o lon fuera de [-180,180]
  - ESTADO_INVALIDO: estado_servicio fuera del enum conocido
  - Dedup por (vehiculo_id, ts_servidor) dentro del lote y contra Gold.
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
DAG_ID = "dag_flota_gold"
ESTADOS_VALIDOS = {"FUERA_DE_LINEA", "DISPONIBLE", "OCUPADO", "SIN_SEÑAL"}


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
    posiciones = list(db.posiciones.find({"ts_servidor": {"$gte": inicio, "$lt": fin}}))

    # `posiciones` (backend/src/flota/service.py::reportar_posicion) NUNCA
    # guarda `estado_servicio` en el propio documento -- ese campo vive en
    # `usuarios.conductor.estado_servicio` (el estado de turno del socio,
    # no de la posición puntual). Bug encontrado en auditoría: este DAG
    # asumía que venía en `posiciones` y quedaba `None` el 100% de las
    # veces, reventando el INSERT a Bronze (columna NOT NULL). Se resuelve
    # con un join de lectura por conductor_id, mismo patrón que el join
    # pagos/viajes de dag_viajes_core -- se usa el estado ACTUAL del
    # conductor como mejor aproximación disponible (no existe historial de
    # cambios de estado_servicio en ningún lado para reconstruir "cuál era
    # su estado exactamente en ese ts_servidor").
    conductor_ids = {str(p["conductor_id"]) for p in posiciones if p.get("conductor_id")}
    estado_por_conductor = {
        u["_id"]: (u.get("conductor") or {}).get("estado_servicio")
        for u in db.usuarios.find({"_id": {"$in": list(conductor_ids)}}, {"conductor.estado_servicio": 1})
    } if conductor_ids else {}
    cliente.close()

    crudos = [{
        "vehiculo_id": str(p.get("vehiculo_id")) if p.get("vehiculo_id") else None,
        "conductor_id": str(p.get("conductor_id")) if p.get("conductor_id") else "",
        "lat": p.get("lat"), "lon": p.get("lon"),
        "estado_servicio": estado_por_conductor.get(str(p.get("conductor_id"))),
        "ts_servidor": p.get("ts_servidor"),
    } for p in posiciones]

    n = medallion.insertar_bronze("bronze_flota_posiciones", crudos, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="crudos", value=crudos)
    ti.xcom_push(key="registros_extraidos", value=len(crudos))
    ti.xcom_push(key="duracion_bronze_seg", value=dur)
    LOGGER.info("Bronze flota: %d extraídos en %.2fs", n, dur)


def _silver_y_cuarentena(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    crudos = ti.xcom_pull(task_ids="extraer", key="crudos")
    t0 = time.time()

    # Se excluye la propia partición fecha_logica: se reemplaza por la carga
    # idempotente (A3) y no debe contar como duplicado contra sí misma.
    client = medallion.get_client()
    fecha_logica = context["ds"]
    existentes = set(
        (row[0], row[1]) for row in
        client.query(
            "SELECT vehiculo_id, ts_servidor FROM urbanflet_gold.fact_ubicacion_flota WHERE fecha != {fecha:Date}",
            parameters={"fecha": fecha_logica},
        ).result_rows
    )
    client.close()

    vistos = set()
    validos, rechazados = [], []
    for i, r in enumerate(crudos):
        flag = None
        if not r.get("vehiculo_id") or r.get("lat") is None or r.get("lon") is None or not r.get("ts_servidor"):
            flag = "CAMPO_NULO"
        elif not (-90 <= r["lat"] <= 90) or not (-180 <= r["lon"] <= 180):
            flag = "COORD_INVALIDA"
        elif r.get("estado_servicio") not in ESTADOS_VALIDOS:
            flag = "ESTADO_INVALIDO"
        else:
            clave = (r["vehiculo_id"], r["ts_servidor"])
            if clave in vistos or clave in existentes:
                flag = "DUPLICADO"
            else:
                vistos.add(clave)

        if flag is not None:
            rechazados.append({"id_origen": f"{r.get('vehiculo_id')}_{i}", "flag": flag, "valores": r})
        else:
            validos.append(r)

    n_cuarentena = medallion.insertar_cuarentena("flota", rechazados, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="validos", value=validos)
    ti.xcom_push(key="duracion_silver_seg", value=dur)
    ti.xcom_push(key="registros_validos", value=len(validos))
    ti.xcom_push(key="registros_cuarentena", value=n_cuarentena)
    LOGGER.info("Silver flota: %d válidos, %d en cuarentena en %.2fs", len(validos), n_cuarentena, dur)


def _gold(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="validos")
    fecha_logica = context["ds"]
    t0 = time.time()
    filas = [{**r, "fecha": fecha_logica, "lote_id": lote_id} for r in validos]
    n = medallion.cargar_gold_idempotente("fact_ubicacion_flota", filas, fecha_logica, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="duracion_gold_seg", value=dur)
    LOGGER.info("Gold flota: %d filas en fact_ubicacion_flota (fecha=%s)", n, fecha_logica)


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
    description="CU-O15: Bronze->Silver->Gold horario de posiciones de flota (fact_ubicacion_flota).",
    schedule_interval="@hourly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cu-o15", "medallion", "flota"],
) as dag:

    extraer = PythonOperator(task_id="extraer", python_callable=_extraer)
    silver_y_cuarentena = PythonOperator(task_id="silver_y_cuarentena", python_callable=_silver_y_cuarentena)
    gold = PythonOperator(task_id="gold", python_callable=_gold)
    metricas = PythonOperator(task_id="metricas", python_callable=_metricas)
    # CU-O16 P1: dispara dag_publicar_indicadores como corrida propia (ver
    # comentario extenso en dag_finanzas_gold.py -- mismo mecanismo). Al ser
    # horaria, esta es la única fuente que dispara la publicación varias
    # veces al día en vez de una -- exactamente lo que pide la spec para el
    # informe de flota activa (refrescarse en cada corrida, no solo diario).
    disparar_publicacion = TriggerDagRunOperator(
        task_id="disparar_publicacion_indicadores",
        trigger_dag_id="dag_publicar_indicadores",
        wait_for_completion=False,
    )

    extraer >> silver_y_cuarentena >> gold >> metricas >> disparar_publicacion
