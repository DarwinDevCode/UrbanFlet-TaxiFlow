"""Sección 1.5 de `specs/specs-administrativas/ux_complementaria.md` --
"Programar un viaje" (D2, aprobado explícitamente por el usuario antes de
construir, ver PLAN_UX_COMPLEMENTARIA.md §9).

A diferencia de los otros 7 DAGs de `analytics/dags/`, este NO es un
pipeline Bronze->Silver->Gold -- no toca `medallion.py`/`indicadores.py`,
no escribe en ClickHouse, no registra una "corrida" en el sentido del
Módulo de Plataforma. Es un disparador operativo puro: cada 2 minutos,
busca viajes `PROGRAMADO` cuya hora ya llegó y le pide al backend que los
transicione a `SOLICITADO` -- el mismo punto de entrada de siempre del
auto-despacho (CU-O05). El DAG nunca reimplementa lógica de despacho, solo
dispara `POST /viajes/{id}/disparar-programado` (protegido por
`INTERNAL_API_TOKEN`, ver `viajes/router_trips.py::_verificar_token_interno`)
sobre la misma red interna de docker-compose.

Riesgo aceptado explícitamente (D2): si a la hora programada no hay ningún
conductor disponible, el viaje cae en `SIN_CONDUCTOR` -- mismo
comportamiento que ya existe hoy para cualquier viaje sin candidatos, sin
mecanismo de reintento especial (CU-O05 A3 sigue en el backlog general del
proyecto).

Cadencia de 2 minutos (no más fino): Airflow no está pensado para
granularidad de segundos -- se acepta esa ventana de margen, documentada
también en el propio D2.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

LOGGER = logging.getLogger("airflow.task")
DAG_ID = "dag_disparar_viajes_programados"

TIMEOUT_HTTP_SEGUNDOS = 10


def _disparar(**context) -> None:
    from pymongo import MongoClient

    backend_url = os.environ["BACKEND_URL"]
    token = os.environ["INTERNAL_API_TOKEN"]

    cliente = MongoClient(os.environ["MONGO_URI"])
    db = cliente[os.environ.get("MONGO_DB_NAME", "urbanflet")]
    try:
        ahora = datetime.utcnow()
        pendientes = list(db.viajes.find({"estado": "PROGRAMADO", "ts_programado": {"$lte": ahora}}, {"_id": 1}))
    finally:
        cliente.close()

    if not pendientes:
        LOGGER.info("Sin viajes PROGRAMADO vencidos en esta corrida.")
        return

    disparados, fallidos = 0, 0
    for doc in pendientes:
        viaje_id = doc["_id"]
        try:
            resp = requests.post(
                f"{backend_url}/viajes/{viaje_id}/disparar-programado",
                headers={"X-Internal-Token": token},
                timeout=TIMEOUT_HTTP_SEGUNDOS,
            )
            # 404 (VIAJE_NO_PROGRAMADO) es un resultado esperado en un
            # reintento -- otra corrida ya lo disparó entre la consulta de
            # arriba y este POST -- no cuenta como fallo real.
            if resp.status_code == 200:
                disparados += 1
            elif resp.status_code == 404:
                LOGGER.info("Viaje %s ya no estaba PROGRAMADO (disparado por otra corrida) -- se omite.", viaje_id)
            else:
                fallidos += 1
                LOGGER.error("Fallo al disparar viaje %s: HTTP %s %s", viaje_id, resp.status_code, resp.text)
        except requests.RequestException as exc:
            fallidos += 1
            LOGGER.error("Error de red disparando viaje %s: %s", viaje_id, exc)

    LOGGER.info("dag_disparar_viajes_programados: %d disparados, %d fallidos, %d candidatos", disparados, fallidos, len(pendientes))
    if fallidos:
        # Deja que Airflow reintente la corrida completa (default_args.retries)
        # -- el endpoint es seguro de reintentar (un viaje ya disparado
        # responde 404, no un doble-despacho).
        raise RuntimeError(f"{fallidos} viaje(s) programado(s) no se pudieron disparar")


default_args = {
    "owner": "operaciones",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id=DAG_ID,
    description="Sección 1.5 ux_complementaria.md: dispara el auto-despacho de viajes PROGRAMADO cuya hora ya llegó.",
    schedule_interval="*/2 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["ux-complementaria", "viajes", "programado"],
) as dag:
    PythonOperator(task_id="disparar", python_callable=_disparar)
