"""CU-O15 -- dag_viajes_core

Diaria 02:00. Dos fuentes independientes de `viajes`:

  - Viajes **finalizados** el día lógico (`ts_fin` dentro de [ds, ds+1),
    `estado=PAGADO`) -> Gold `fact_viaje`, con las reglas Silver completas de
    la spec (DISTANCIA_CERO, FECHAS_INVALIDAS, ERROR_MONTO, ZONA_INVALIDA) --
    sin cambios respecto a versiones anteriores, sigue alimentando finanzas.
  - Viajes **solicitados** el día lógico (`ts_solicitud` dentro de
    [ds, ds+1), **cualquier estado**) -> Gold `fact_ciclo_viaje`, tabla nueva
    para los informes tácticos de despacho
    (specs/nivel-tactico/tactico_operaciones_despacho.md: tiempo de
    asignación, tasa de cancelación). Se separa de `fact_viaje` a propósito:
    aplicarle las mismas reglas Silver (que asumen un viaje completado, con
    km/tarifa/monto_pagado) a un viaje SIN_CONDUCTOR o CANCELADO los
    rechazaría a todos por FECHAS_INVALIDAS/ERROR_MONTO -- exactamente los
    registros que este informe necesita conservar. Validación Silver mínima
    propia: solo CAMPO_NULO + dedup.

ERROR_MONTO: la spec compara `monto_pagado == tarifa_final`. `monto_pagado`
no vive en el propio documento de viaje -- lo registra recaudación en
`pagos.monto` (backend/src/recaudacion/schemas.py: PagoOut.monto), enlazado
por `pagos.viaje_id`. Por eso Bronze hace un join de lectura (dos colecciones
Mongo) antes de aplicar la regla; si no hay pago aún para un viaje finalizado
se trata como ERROR_MONTO (no hay forma de validar integridad financiera sin
el pago).

max_active_runs=1: es la lectura legítima del "sensor de no-concurrencia" de
A4 -- Airflow ya garantiza nativamente que no haya dos dag runs del mismo DAG
ejecutándose a la vez; no se requiere un sensor custom adicional.

dim_zona: no existe catálogo de zonas geográficas en el dominio (backend/src
no tiene un concepto de zona/geocerca, ver grep de "zona|geocerca" -- solo
aparece en config/nombres de servicio, no como catálogo). Se define aquí un
catálogo estático razonable de zonas de Quito (Ecuador, mercado del dominio)
y se resuelve cada viaje a la zona más cercana por distancia euclidiana
lat/lon a su centroide -- suficiente para demo/dev, documentado como
simplificación.
"""
from __future__ import annotations

import logging
import math
import sys
import time
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

sys.path.append("/opt/airflow/plugins")
import medallion  # noqa: E402

LOGGER = logging.getLogger("airflow.task")
DAG_ID = "dag_viajes_core"
DURACION_MAX_MIN = 1440
MONTO_TOLERANCIA = 0.01

# Catálogo estático de zonas (Quito, Ecuador) -- ver docstring del módulo.
ZONAS = [
    {"zona_id": "Z-NORTE", "nombre": "Quito Norte", "ciudad": "Quito", "lat_centro": -0.1500, "lon_centro": -78.4800},
    {"zona_id": "Z-CENTRO", "nombre": "Quito Centro", "ciudad": "Quito", "lat_centro": -0.2200, "lon_centro": -78.5120},
    {"zona_id": "Z-SUR", "nombre": "Quito Sur", "ciudad": "Quito", "lat_centro": -0.2800, "lon_centro": -78.5400},
    {"zona_id": "Z-VALLES", "nombre": "Valles (Cumbayá/Tumbaco)", "ciudad": "Quito", "lat_centro": -0.1950, "lon_centro": -78.4300},
    {"zona_id": "Z-AEROPUERTO", "nombre": "Aeropuerto Tababela", "ciudad": "Quito", "lat_centro": -0.1290, "lon_centro": -78.3580},
]


def _zona_mas_cercana(lat, lon):
    if lat is None or lon is None:
        return None
    mejor, mejor_d = None, float("inf")
    for z in ZONAS:
        d = math.hypot(z["lat_centro"] - lat, z["lon_centro"] - lon)
        if d < mejor_d:
            mejor, mejor_d = z["zona_id"], d
    return mejor


def _extraer(**context):
    medallion.ensure_schema()
    ti = context["ti"]
    lote_id = medallion.registrar_inicio_corrida(DAG_ID, context["ds"])
    ti.xcom_push(key="lote_id", value=lote_id)
    ti.xcom_push(key="iniciado_en", value=datetime.utcnow().isoformat())
    t0 = time.time()

    from pymongo import MongoClient
    import os

    cliente = MongoClient(os.environ["MONGO_URI"])
    db = cliente[os.environ.get("MONGO_DB_NAME", "urbanflet")]

    ds = context["ds"]
    inicio = datetime.fromisoformat(ds)
    fin = inicio + timedelta(days=1)

    viajes = list(db.viajes.find({
        "estado": "PAGADO",
        "ts_fin": {"$gte": inicio, "$lt": fin},
    }))
    viaje_ids = [str(v["_id"]) for v in viajes]
    pagos_por_viaje = {p["viaje_id"]: p for p in db.pagos.find({"viaje_id": {"$in": viaje_ids}})} if viaje_ids else {}

    ciclo_viajes = list(db.viajes.find({"ts_solicitud": {"$gte": inicio, "$lt": fin}}))
    cliente.close()

    crudos = []
    for v in viajes:
        vid = str(v.get("_id"))
        pago = pagos_por_viaje.get(vid)
        crudos.append({
            "viaje_id": vid,
            "pasajero_id": str(v.get("pasajero_id")),
            "conductor_id": str(v.get("conductor_id")) if v.get("conductor_id") else "",
            "vehiculo_id": str(v.get("vehiculo_id")) if v.get("vehiculo_id") else "",
            "estado": v.get("estado"),
            "origen_lat": v.get("origen_lat"),
            "origen_lon": v.get("origen_lon"),
            "destino_lat": v.get("destino_lat"),
            "destino_lon": v.get("destino_lon"),
            "franja": v.get("franja"),
            "ts_solicitud": v.get("ts_solicitud"),
            "ts_inicio": v.get("ts_inicio"),
            "ts_fin": v.get("ts_fin"),
            "km_recorridos": v.get("km_recorridos"),
            "tarifa_final": v.get("tarifa_final"),
            "monto_pagado": pago.get("monto") if pago else None,
        })

    crudos_ciclo = [{
        "viaje_id": str(v.get("_id")),
        "estado": v.get("estado"),
        "zona_origen_id": _zona_mas_cercana(v.get("origen_lat"), v.get("origen_lon")),
        "franja": v.get("franja") or "",
        "ts_solicitud": v.get("ts_solicitud"),
        "ts_asignacion": v.get("ts_asignacion"),
        "motivo_cancelacion": v.get("motivo_cancelacion"),
        "actor_cancelacion": v.get("actor_cancelacion"),
    } for v in ciclo_viajes]

    n = medallion.insertar_bronze("bronze_viajes", crudos, lote_id)
    n_ciclo = medallion.insertar_bronze("bronze_ciclo_viaje", crudos_ciclo, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="crudos", value=crudos)
    ti.xcom_push(key="crudos_ciclo", value=crudos_ciclo)
    ti.xcom_push(key="registros_extraidos", value=len(crudos) + len(crudos_ciclo))
    ti.xcom_push(key="duracion_bronze_seg", value=dur)
    LOGGER.info(
        "Bronze viajes: %d finalizados + %d ciclo-completo extraídos/insertados en %.2fs", n, n_ciclo, dur
    )


def _silver_y_cuarentena(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    crudos = ti.xcom_pull(task_ids="extraer", key="crudos")
    t0 = time.time()

    # Se excluye la propia partición fecha_logica del chequeo de dedup contra
    # Gold: esa partición se reemplaza por la carga idempotente (paso Gold),
    # así que reprocesar la MISMA fecha lógica (A3) no debe marcarse como
    # duplicado -- solo interesa detectar duplicados de OTRA fecha lógica.
    client = medallion.get_client()
    fecha_logica = context["ds"]
    existentes = set(row[0] for row in client.query(
        "SELECT DISTINCT viaje_id FROM urbanflet_gold.fact_viaje WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    existentes_ciclo = set(row[0] for row in client.query(
        "SELECT DISTINCT viaje_id FROM urbanflet_gold.fact_ciclo_viaje WHERE fecha != {fecha:Date}",
        parameters={"fecha": fecha_logica},
    ).result_rows)
    client.close()

    vistos = set()
    validos, rechazados = [], []

    for r in crudos:
        flag = None
        km = r.get("km_recorridos") or 0
        if km <= 0:
            flag = "DISTANCIA_CERO"

        if flag is None:
            inicio, fin = r.get("ts_inicio"), r.get("ts_fin")
            if not inicio or not fin:
                flag = "FECHAS_INVALIDAS"
            else:
                dur_min = (fin - inicio).total_seconds() / 60.0
                if fin <= inicio or dur_min >= DURACION_MAX_MIN:
                    flag = "FECHAS_INVALIDAS"

        if flag is None:
            monto_pagado = r.get("monto_pagado")
            tarifa_final = r.get("tarifa_final")
            if monto_pagado is None or tarifa_final is None or abs(monto_pagado - tarifa_final) > MONTO_TOLERANCIA:
                flag = "ERROR_MONTO"

        if flag is None:
            zona_o = _zona_mas_cercana(r.get("origen_lat"), r.get("origen_lon"))
            zona_d = _zona_mas_cercana(r.get("destino_lat"), r.get("destino_lon"))
            if zona_o is None or zona_d is None:
                flag = "ZONA_INVALIDA"
            else:
                r["_zona_origen"] = zona_o
                r["_zona_destino"] = zona_d

        if flag is None:
            if r["viaje_id"] in vistos or r["viaje_id"] in existentes:
                flag = "DUPLICADO"
            else:
                vistos.add(r["viaje_id"])

        if flag is not None:
            rechazados.append({"id_origen": r["viaje_id"], "flag": flag, "valores": r})
        else:
            validos.append(r)

    crudos_ciclo = ti.xcom_pull(task_ids="extraer", key="crudos_ciclo")
    vistos_ciclo = set()
    validos_ciclo = []
    for r in crudos_ciclo:
        flag = None
        if not r.get("viaje_id") or not r.get("estado") or not r.get("ts_solicitud"):
            flag = "CAMPO_NULO"
        elif r["viaje_id"] in vistos_ciclo or r["viaje_id"] in existentes_ciclo:
            flag = "DUPLICADO"
        else:
            vistos_ciclo.add(r["viaje_id"])

        if flag is not None:
            rechazados.append({"id_origen": f"ciclo:{r['viaje_id']}", "flag": flag, "valores": r})
        else:
            validos_ciclo.append(r)

    n_cuarentena = medallion.insertar_cuarentena("viajes", rechazados, lote_id)
    dur = time.time() - t0
    ti.xcom_push(key="validos", value=validos)
    ti.xcom_push(key="validos_ciclo", value=validos_ciclo)
    ti.xcom_push(key="duracion_silver_seg", value=dur)
    ti.xcom_push(key="registros_validos", value=len(validos) + len(validos_ciclo))
    ti.xcom_push(key="registros_cuarentena", value=n_cuarentena)
    LOGGER.info(
        "Silver viajes: %d/%d válidos, %d en cuarentena en %.2fs", len(validos), len(validos_ciclo), n_cuarentena, dur
    )


def _gold(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    validos = ti.xcom_pull(task_ids="silver_y_cuarentena", key="validos")
    fecha_logica = context["ds"]
    t0 = time.time()

    filas_viaje = []
    for r in validos:
        km = r.get("km_recorridos") or 0
        dur_min = (r["ts_fin"] - r["ts_inicio"]).total_seconds() / 60.0 if r.get("ts_inicio") and r.get("ts_fin") else 0
        filas_viaje.append({
            "viaje_id": r["viaje_id"], "pasajero_id": r["pasajero_id"], "conductor_id": r["conductor_id"],
            "vehiculo_id": r["vehiculo_id"], "zona_origen_id": r.get("_zona_origen") or "",
            "zona_destino_id": r.get("_zona_destino") or "", "franja": r.get("franja") or "",
            "km_recorridos": km, "duracion_min": dur_min, "tarifa_final": r.get("tarifa_final") or 0,
            "ts_solicitud": r.get("ts_solicitud"), "ts_fin": r.get("ts_fin"),
            "fecha": fecha_logica, "lote_id": lote_id,
        })

    n_viaje = medallion.cargar_gold_idempotente("fact_viaje", filas_viaje, fecha_logica, lote_id)

    validos_ciclo = ti.xcom_pull(task_ids="silver_y_cuarentena", key="validos_ciclo")
    filas_ciclo = [{
        "viaje_id": r["viaje_id"], "estado": r["estado"], "zona_origen_id": r.get("zona_origen_id"),
        "franja": r.get("franja") or "", "ts_solicitud": r["ts_solicitud"], "ts_asignacion": r.get("ts_asignacion"),
        "motivo_cancelacion": r.get("motivo_cancelacion"), "actor_cancelacion": r.get("actor_cancelacion"),
        "fecha": fecha_logica, "lote_id": lote_id,
    } for r in validos_ciclo]
    n_ciclo = medallion.cargar_gold_idempotente("fact_ciclo_viaje", filas_ciclo, fecha_logica, lote_id)
    LOGGER.info("Gold viajes: %d filas en fact_ciclo_viaje (fecha=%s)", n_ciclo, fecha_logica)

    # dim_zona: catálogo completo (ReplacingMergeTree, sin partición por fecha -- se repuebla siempre).
    client = medallion.get_client()
    client.insert("urbanflet_gold.dim_zona", [
        [z["zona_id"], z["nombre"], z["ciudad"], z["lat_centro"], z["lon_centro"]] for z in ZONAS
    ], column_names=["zona_id", "nombre", "ciudad", "lat_centro", "lon_centro"])

    # dim_tiempo: una fila por la fecha lógica de esta corrida (ReplacingMergeTree dedup por fecha).
    d = datetime.fromisoformat(fecha_logica).date()
    client.insert("urbanflet_gold.dim_tiempo", [[
        d, d.year, d.month, d.day, d.isoweekday(), 1 if d.isoweekday() >= 6 else 0,
    ]], column_names=["fecha", "anio", "mes", "dia", "dia_semana", "es_fin_de_semana"])
    client.close()

    dur = time.time() - t0
    ti.xcom_push(key="duracion_gold_seg", value=dur)
    LOGGER.info("Gold viajes: %d filas en fact_viaje (fecha=%s)", n_viaje, fecha_logica)


def _metricas(**context):
    ti = context["ti"]
    lote_id = ti.xcom_pull(task_ids="extraer", key="lote_id")
    iniciado_en = datetime.fromisoformat(ti.xcom_pull(task_ids="extraer", key="iniciado_en"))
    estado = medallion.finalizar_corrida(
        dag_id=DAG_ID,
        fecha_logica=context["ds"],
        lote_id=lote_id,
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
    description="CU-O15: Bronze->Silver->Gold diario de viajes finalizados (fact_viaje, dim_zona, dim_tiempo).",
    schedule_interval="0 2 * * *",
    # start_date bajado a 2020 (antes 2024) para permitir backfill manual de
    # fechas históricas (ej. siembra NYC 2021, ver CLAUDE.md cambio de
    # arquitectura) -- con catchup=False esto NO dispara una avalancha de
    # corridas retroactivas, solo habilita que `airflow dags trigger -e
    # <fecha>` con una fecha vieja cree TaskInstances reales en vez de un
    # DagRun con 0 tareas marcado "success" trivialmente (el bug real que
    # esto corrige: execution_date < start_date hacía que el scheduler
    # nunca creara TaskInstances, pero igual cerraba el DagRun como éxito).
    start_date=datetime(2020, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["cu-o15", "medallion", "viajes"],
) as dag:

    extraer = PythonOperator(task_id="extraer", python_callable=_extraer)
    silver_y_cuarentena = PythonOperator(task_id="silver_y_cuarentena", python_callable=_silver_y_cuarentena)
    gold = PythonOperator(task_id="gold", python_callable=_gold)
    metricas = PythonOperator(task_id="metricas", python_callable=_metricas)
    # CU-O16 P1: dispara dag_publicar_indicadores como corrida propia (ver
    # comentario extenso en dag_finanzas_gold.py -- mismo mecanismo). Hoy
    # ningún informe rpt_* depende todavía de dag_viajes_core
    # específicamente (ver indicadores._ultima_corrida_ok_o_warn en cada
    # refrescar_*), pero se dispara igual: es uno de los DAGs de dominio que
    # alimentan Gold, y cualquier informe futuro que dependa de fact_viaje
    # quedará automáticamente encadenado sin tocar este archivo de nuevo.
    disparar_publicacion = TriggerDagRunOperator(
        task_id="disparar_publicacion_indicadores",
        trigger_dag_id="dag_publicar_indicadores",
        wait_for_completion=False,
    )

    extraer >> silver_y_cuarentena >> gold >> metricas >> disparar_publicacion
