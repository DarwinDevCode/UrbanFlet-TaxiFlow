"""CU-O15 / A5 -- dag_historico_nyc

Carga bajo demanda (schedule_interval=None) del dataset crudo NYC Yellow
Taxi **2021 real, ~1.36M filas** (`data/nyc_taxi/yellow_tripdata.csv`,
montado en `/opt/airflow/nyc_data/` -- ver `docker-compose.yml`) a
`fact_viaje_historico`, patrón Medallion Bronze -> Silver/Cuarentena -> Gold.

Reescrito en esta sesión para el dataset real (antes leía un CSV de
muestra 2015 de ~4000 filas, ya preprocesado con columnas que el archivo
crudo real no tiene -- `id_origen`, lat/lon, ISO-8601 -- ver CLAUDE.md,
cambio de arquitectura NYC). Dos cambios de fondo, no cosméticos:

1. **Columnas reales del TLC** (`VendorID`, `tpep_pickup_datetime`,
   `PULocationID`/`DOLocationID` en vez de lat/lon, sin `id_origen`),
   separador decimal **coma** (`"2,34"`) y fecha `MM/DD/YYYY hh:mm:ss AM/PM`.
   `id_origen` se genera determinista por posición de fila (`nyc{n:09d}`,
   mismo esquema que `analytics/scripts/load_raw_trips_pocketbase.py`, para
   que ambas cargas -- esta y la de PocketBase -- sean trazables al mismo
   número de fila del CSV fuente).
2. **Procesamiento en chunks, nunca el archivo completo en memoria ni en
   XCom.** La versión anterior leía todo el CSV a una lista y la pasaba
   completa entre tasks vía XCom (viable con 4000 filas, HUBIERA REVENTADO
   con 1.36M -- XCom serializa a la base de metadatos de Airflow). Un solo
   task (`procesar`) hace streaming del CSV con `csv.DictReader` y procesa
   de a `CHUNK_SIZE` filas: Bronze + Silver/Cuarentena + Gold por chunk,
   liberando cada chunk de memoria antes de leer el siguiente. Gold usa
   `medallion.borrar_particion_gold` UNA sola vez al inicio (no
   `cargar_gold_idempotente` por chunk, que borraría la partición en cada
   llamada -- ver docstring de esa función) + `insertar_gold_chunk` por
   cada chunk, sin volver a borrar. La idempotencia de "reejecutar la misma
   fecha_logica da el mismo resultado" se mantiene igual.

Reglas Silver (adaptadas a las columnas reales):
  - DISTANCIA_CERO: trip_distance <= 0
  - FECHAS_INVALIDAS: dropoff <= pickup, o duración >= 1440 min
  - ERROR_MONTO: se acepta si total_amount coincide (±0.01) con la suma de
    componentes SIN congestion_surcharge, O con la suma SÍ incluyéndolo.
    El dataset real 2021 es inconsistente en esto -- muchas filas seguidas
    excluyen el recargo de congestión ($2.50) de total_amount y otras lo
    incluyen, confirmado inspeccionando filas reales rechazadas en la
    prueba de 500 filas (117/500 fallaban por exactamente esa diferencia).
    No es corrupción de datos, es una inconsistencia real del origen --
    exigir una sola fórmula marcaría como corruptas decenas de miles de
    filas válidas.
  - Dedup: por construcción no hace falta consultar Gold -- `id_origen` es
    determinista por posición de fila, nunca se repite dentro del mismo
    archivo. Se conserva un chequeo defensivo dentro de cada chunk (no
    contra Gold completo, sería releer 1.36M ids por nada).
  - ZONA_INVALIDA no aplica: no hay catálogo de zonas para PULocationID/
    DOLocationID en este dominio (se documentó igual en la versión previa).
"""
from __future__ import annotations

import csv
import logging
import os
import sys
import time
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.append("/opt/airflow/plugins")
import medallion  # noqa: E402

LOGGER = logging.getLogger("airflow.task")

# Override solo para pruebas locales de este DAG (lote chico antes del
# archivo completo) -- en producción/CU-O15 real siempre usa el default.
NYC_CSV_PATH = os.environ.get("NYC_CSV_PATH", "/opt/airflow/nyc_data/yellow_tripdata.csv")
DAG_ID = "dag_historico_nyc"

MONTO_TOLERANCIA = 0.01
DURACION_MAX_MIN = 1440
CHUNK_SIZE = 20000
LOG_EVERY_N_CHUNKS = 5


def _num(v: str, default: float = 0.0) -> float:
    """El CSV real usa coma decimal ("2,34") -- normaliza antes de float()."""
    v = (v or "").strip()
    if not v:
        return default
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return default


def _parse_dt(v: str) -> datetime | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None


def _fila_a_dict(numero_fila: int, r: dict) -> dict:
    return {
        "id_origen": f"nyc{numero_fila:09d}",
        "vendor_id": r.get("VendorID") or "",
        "pickup_datetime": _parse_dt(r.get("tpep_pickup_datetime", "")),
        "dropoff_datetime": _parse_dt(r.get("tpep_dropoff_datetime", "")),
        "passenger_count": int(_num(r.get("passenger_count"), 0)),
        "trip_distance": _num(r.get("trip_distance")),
        # El dataset real no trae lat/lon (usa zonas PULocationID/DOLocationID) --
        # se guardan en 0.0, documentado igual que ZONA_INVALIDA arriba: no hay
        # catálogo de zonas TLC en este dominio para resolverlas a coordenadas.
        "pickup_longitude": 0.0,
        "pickup_latitude": 0.0,
        "dropoff_longitude": 0.0,
        "dropoff_latitude": 0.0,
        "fare_amount": _num(r.get("fare_amount")),
        "extra": _num(r.get("extra")),
        "mta_tax": _num(r.get("mta_tax")),
        "tip_amount": _num(r.get("tip_amount")),
        "tolls_amount": _num(r.get("tolls_amount")),
        "imp_surcharge": _num(r.get("improvement_surcharge")),
        "total_amount": _num(r.get("total_amount")),
        "payment_type": r.get("payment_type") or "",
        "congestion_surcharge": _num(r.get("congestion_surcharge")),
    }


def _validar(r: dict, vistos_en_chunk: set[str]) -> str | None:
    if r["trip_distance"] <= 0:
        return "DISTANCIA_CERO"

    pickup, dropoff = r["pickup_datetime"], r["dropoff_datetime"]
    if pickup is None or dropoff is None:
        return "FECHAS_INVALIDAS"
    dur_min = (dropoff - pickup).total_seconds() / 60.0
    if dropoff <= pickup or dur_min >= DURACION_MAX_MIN:
        return "FECHAS_INVALIDAS"

    base = (
        r["fare_amount"] + r["extra"] + r["mta_tax"] + r["tip_amount"]
        + r["tolls_amount"] + r["imp_surcharge"]
    )
    # El dataset real 2021 es inconsistente: en unas filas total_amount SÍ
    # incluye congestion_surcharge, en otras NO (confirmado inspeccionando
    # filas reales rechazadas -- el mismo patrón de discrepancia de $2.50
    # aparece en decenas de filas seguidas, no es ruido aislado). Se acepta
    # cualquiera de las dos combinaciones dentro de tolerancia, para no
    # castigar una inconsistencia real del origen de datos como si fuera
    # corrupción.
    con_congestion = base + r["congestion_surcharge"]
    if (
        abs(r["total_amount"] - base) > MONTO_TOLERANCIA
        and abs(r["total_amount"] - con_congestion) > MONTO_TOLERANCIA
    ):
        return "ERROR_MONTO"

    if r["id_origen"] in vistos_en_chunk:
        return "DUPLICADO"
    vistos_en_chunk.add(r["id_origen"])
    return None


def _procesar(**context):
    medallion.ensure_schema()
    ti = context["ti"]
    fecha_logica = context["ds"]
    lote_id = medallion.registrar_inicio_corrida(DAG_ID, fecha_logica)
    iniciado_en = datetime.utcnow()
    t0 = time.time()

    # Idempotencia (paso 5): se limpia la partición UNA sola vez al
    # principio, después cada chunk se inserta sin volver a borrar (ver
    # docstring de medallion.borrar_particion_gold).
    medallion.borrar_particion_gold("fact_viaje_historico", fecha_logica)

    total_extraidos = 0
    total_validos = 0
    total_cuarentena = 0
    chunk_num = 0

    def _flush(chunk_crudos: list[dict]) -> None:
        nonlocal total_extraidos, total_validos, total_cuarentena, chunk_num
        chunk_num += 1
        vistos: set[str] = set()
        validos: list[dict] = []
        rechazados: list[dict] = []
        for r in chunk_crudos:
            flag = _validar(r, vistos)
            if flag is not None:
                rechazados.append({"id_origen": r["id_origen"], "flag": flag, "valores": r})
            else:
                validos.append(r)

        medallion.insertar_bronze("bronze_viaje_historico_nyc", chunk_crudos, lote_id)
        medallion.insertar_cuarentena("historico_nyc", rechazados, lote_id)
        # insertar_gold_chunk agrega `fecha`/`lote_id` -- `validos` va tal cual.
        medallion.insertar_gold_chunk("fact_viaje_historico", validos, fecha_logica, lote_id)

        total_extraidos += len(chunk_crudos)
        total_validos += len(validos)
        total_cuarentena += len(rechazados)

        if chunk_num % LOG_EVERY_N_CHUNKS == 0:
            transcurrido = time.time() - t0
            velocidad = total_extraidos / transcurrido if transcurrido > 0 else 0
            LOGGER.info(
                "[chunk %d] %s leídos, %s válidos, %s en cuarentena -- %.0fs transcurridos, %.0f filas/s",
                chunk_num, f"{total_extraidos:,}", f"{total_validos:,}", f"{total_cuarentena:,}",
                transcurrido, velocidad,
            )

    with open(NYC_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        chunk: list[dict] = []
        for numero_fila, r in enumerate(reader, start=1):
            chunk.append(_fila_a_dict(numero_fila, r))
            if len(chunk) >= CHUNK_SIZE:
                _flush(chunk)
                chunk = []
        if chunk:
            _flush(chunk)

    dur = time.time() - t0
    LOGGER.info(
        "Terminado: %s extraídos, %s válidos, %s en cuarentena, %d chunks, %.0fs totales (%.0f filas/s)",
        f"{total_extraidos:,}", f"{total_validos:,}", f"{total_cuarentena:,}", chunk_num, dur,
        total_extraidos / dur if dur > 0 else 0,
    )

    ti.xcom_push(key="lote_id", value=lote_id)
    ti.xcom_push(key="iniciado_en", value=iniciado_en.isoformat())
    ti.xcom_push(key="registros_extraidos", value=total_extraidos)
    ti.xcom_push(key="registros_validos", value=total_validos)
    ti.xcom_push(key="registros_cuarentena", value=total_cuarentena)
    ti.xcom_push(key="duracion_total_seg", value=dur)


def _metricas(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="procesar", key="lote_id")
    iniciado_en = datetime.fromisoformat(ti.xcom_pull(task_ids="procesar", key="iniciado_en"))
    estado = medallion.finalizar_corrida(
        dag_id=DAG_ID,
        fecha_logica=context["ds"],
        lote_id=lote_id,
        registros_extraidos=ti.xcom_pull(task_ids="procesar", key="registros_extraidos"),
        registros_validos=ti.xcom_pull(task_ids="procesar", key="registros_validos"),
        registros_cuarentena=ti.xcom_pull(task_ids="procesar", key="registros_cuarentena"),
        duracion_bronze_seg=ti.xcom_pull(task_ids="procesar", key="duracion_total_seg"),
        duracion_silver_seg=0.0,
        duracion_gold_seg=0.0,
        iniciado_en=iniciado_en,
    )
    LOGGER.info("Corrida %s finalizada con estado=%s", lote_id, estado)


default_args = {
    "owner": "plataforma-bi",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": medallion.on_failure_callback_factory(DAG_ID),
}

with DAG(
    dag_id=DAG_ID,
    description="CU-O15/A5: carga bajo demanda del dataset histórico NYC 2021 real (~1.36M filas) a fact_viaje_historico.",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cu-o15", "medallion", "historico"],
) as dag:

    procesar = PythonOperator(task_id="procesar", python_callable=_procesar, execution_timeout=timedelta(hours=2))
    metricas = PythonOperator(task_id="metricas", python_callable=_metricas)

    procesar >> metricas
