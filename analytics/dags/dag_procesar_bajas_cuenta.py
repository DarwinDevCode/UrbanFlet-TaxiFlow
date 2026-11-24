"""Autoservicio de baja de cuenta -- vencimiento del periodo de gracia.

Cuando un usuario solicita cerrar su propia cuenta desde Ajustes, la cuenta
queda ACTIVA durante 30 días (puede cancelar en cualquier momento). Este DAG
es el que hace efectivo el vencimiento: una vez al día busca las cuentas cuyo
plazo ya pasó sin cancelarse y le pide al backend que les aplique la baja
lógica.

Mismo patrón que `dag_disparar_viajes_programados` -- el otro job operativo
del proyecto -- y NO un scheduler nuevo en paralelo: Airflow llama a un
endpoint interno del backend protegido por `INTERNAL_API_TOKEN`, y toda la
lógica de negocio (incluido el guard de "no cortar el acceso con un viaje en
curso") vive del lado del backend, nunca reimplementada acá.

A diferencia de los 7 DAGs de `analytics/dags/` que son pipelines
Bronze->Silver->Gold, este no toca ClickHouse ni registra una "corrida" en el
Módulo de Plataforma.

Cadencia diaria a las 06:00, la misma hora que la spec ya define para el
control de vigencia documental -- son los 2 trabajos diarios de
mantenimiento de datos del sistema, no hay razón para que corran en momentos
distintos.

El endpoint es idempotente (filtra por `estado: ACTIVO`), así que un
reintento de Airflow no puede dar de baja dos veces la misma cuenta ni
revertir una cancelación.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

LOGGER = logging.getLogger("airflow.task")
DAG_ID = "dag_procesar_bajas_cuenta"

TIMEOUT_HTTP_SEGUNDOS = 30


def _procesar(**context) -> None:
    backend_url = os.environ["BACKEND_URL"]
    token = os.environ["INTERNAL_API_TOKEN"]

    resp = requests.post(
        f"{backend_url}/usuarios/procesar-bajas-vencidas",
        headers={"X-Internal-Token": token},
        timeout=TIMEOUT_HTTP_SEGUNDOS,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"El backend rechazó el procesamiento de bajas: HTTP {resp.status_code} {resp.text}")

    datos = resp.json()
    LOGGER.info(
        "%s: %d baja(s) aplicada(s), %d omitida(s) por viaje activo, %d revisada(s).",
        DAG_ID,
        datos.get("aplicadas", 0),
        datos.get("omitidas_por_viaje_activo", 0),
        datos.get("revisadas", 0),
    )


default_args = {
    "owner": "plataforma",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id=DAG_ID,
    description="Aplica la baja lógica a las cuentas cuyo periodo de gracia de 30 días venció sin cancelarse.",
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cuentas", "baja", "job-diario"],
) as dag:
    PythonOperator(task_id="procesar", python_callable=_procesar)
