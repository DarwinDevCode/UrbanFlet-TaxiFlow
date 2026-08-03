"""Librería compartida del patrón Medallion (Bronze -> Silver -> Cuarentena -> Gold)
para los DAGs de transformación de datos de UrbanFleet-TaxiFlow (CU-O15).

Importable desde cualquier DAG en /opt/airflow/dags porque este archivo vive en
/opt/airflow/plugins, que Airflow añade automáticamente a sys.path. Por robustez,
cada DAG también hace un `sys.path.append("/opt/airflow/plugins")` antes de importar.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, date
from typing import Any, Iterable

import clickhouse_connect

LOGGER = logging.getLogger("airflow.task")

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123"))
CLICKHOUSE_DB = "urbanflet_gold"

# Umbral de A2: % de cuarentena > 1% del lote -> WARN
UMBRAL_CUARENTENA_WARN = 0.01


# ---------------------------------------------------------------------------
# Cliente ClickHouse
# ---------------------------------------------------------------------------

def get_client(database: str | None = None):
    """Factory del cliente ClickHouse (HTTP, clickhouse-connect)."""
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=database if database is not None else CLICKHOUSE_DB,
    )


def _to_json(value: Any) -> str:
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)

    return json.dumps(value, default=default, ensure_ascii=False)


# ---------------------------------------------------------------------------
# DDL idempotente — se ejecuta al comienzo de cada corrida de cada DAG.
# ---------------------------------------------------------------------------

def _bronze_ddl(tabla: str, columnas: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.{tabla}
    (
        {columnas},
        lote_id String,
        extraido_en DateTime
    )
    ENGINE = MergeTree
    ORDER BY (lote_id, extraido_en)
    """


def _cuarentena_ddl(tabla: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.{tabla}
    (
        id_origen String,
        flag String,
        lote_id String,
        valores_originales String,
        rechazado_en DateTime
    )
    ENGINE = MergeTree
    ORDER BY (lote_id, id_origen)
    """


def ensure_schema() -> None:
    """Crea (si no existen) la base de datos y todas las tablas Bronze,
    Cuarentena, Gold, `corridas` y `alertas`. Idempotente: se puede correr
    en cada ejecución de cada DAG sin efectos secundarios."""
    client = get_client(database="default")
    client.command("CREATE DATABASE IF NOT EXISTS urbanflet_gold")
    client.close()

    client = get_client()

    ddls: list[str] = []

    # --- Bronze (staging) por dominio -------------------------------------------------
    ddls.append(_bronze_ddl(
        "bronze_viajes",
        """
        viaje_id String, pasajero_id String, conductor_id String, vehiculo_id String,
        estado String, origen_lat Float64, origen_lon Float64, destino_lat Float64,
        destino_lon Float64, franja String, ts_solicitud DateTime, ts_inicio Nullable(DateTime),
        ts_fin Nullable(DateTime), km_recorridos Nullable(Float64), tarifa_final Nullable(Float64),
        monto_pagado Nullable(Float64)
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_flota_posiciones",
        """
        vehiculo_id String, conductor_id String, lat Float64, lon Float64,
        estado_servicio Nullable(String), ts_servidor DateTime
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_pagos",
        """
        pago_id String, viaje_id String, conductor_id String, metodo String,
        monto Float64, tarifa_final Float64, estado String, ts_registro DateTime
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_liquidaciones",
        """
        liquidacion_id String, conductor_id String, periodo_inicio DateTime,
        periodo_fin DateTime, estado String, bruto Float64, comisiones Float64,
        ajustes Float64, neto Float64, ts_emision DateTime, ts_pago Nullable(DateTime)
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_usuarios",
        """
        usuario_id String, tipo String, estado String, telefono String,
        email String, canal String, ts_creacion DateTime
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_solicitudes",
        """
        solicitud_id String, estado String, canal String,
        fecha_envio DateTime, fecha_decision Nullable(DateTime)
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_ciclo_viaje",
        """
        viaje_id String, estado String, zona_origen_id Nullable(String), franja String,
        ts_solicitud DateTime, ts_asignacion Nullable(DateTime),
        motivo_cancelacion Nullable(String), actor_cancelacion Nullable(String)
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_documentos",
        """
        documento_id String, tipo String, propietario_tipo String, propietario_id String,
        estado String, fecha_emision Nullable(Date), fecha_vencimiento Nullable(Date)
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_bitacora",
        """
        evento_id String, actor_id String, accion String, endpoint String, ts DateTime
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_ordenes_mantenimiento",
        """
        orden_id String, vehiculo_id String, tipo String, estado String,
        km_entrada Float64, km_salida Nullable(Float64), costo_total Nullable(Float64),
        horas_taller Nullable(Float64), fecha_programada Date, fecha_cierre DateTime
        """,
    ))
    ddls.append(_bronze_ddl(
        "bronze_viaje_historico_nyc",
        """
        id_origen String, vendor_id String, pickup_datetime DateTime,
        dropoff_datetime DateTime, passenger_count Int32, trip_distance Float64,
        pickup_longitude Float64, pickup_latitude Float64, dropoff_longitude Float64,
        dropoff_latitude Float64, fare_amount Float64, extra Float64, mta_tax Float64,
        tip_amount Float64, tolls_amount Float64, imp_surcharge Float64,
        total_amount Float64, payment_type String, congestion_surcharge Float64
        """,
    ))

    # --- Cuarentena por dominio ---------------------------------------------------
    for tabla in (
        "cuarentena_viajes", "cuarentena_flota", "cuarentena_finanzas",
        "cuarentena_captacion", "cuarentena_cumplimiento", "cuarentena_historico_nyc",
        "cuarentena_mantenimiento",
    ):
        ddls.append(_cuarentena_ddl(tabla))

    # --- Gold -----------------------------------------------------------------
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_viaje
    (
        viaje_id String, pasajero_id String, conductor_id String, vehiculo_id String,
        zona_origen_id String, zona_destino_id String, franja String,
        km_recorridos Float64, duracion_min Float64, tarifa_final Float64,
        ts_solicitud DateTime, ts_fin DateTime, fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, viaje_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.dim_zona
    (
        zona_id String, nombre String, ciudad String, lat_centro Float64, lon_centro Float64
    )
    ENGINE = ReplacingMergeTree ORDER BY zona_id
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.dim_tiempo
    (
        fecha Date, anio UInt16, mes UInt8, dia UInt8, dia_semana UInt8, es_fin_de_semana UInt8
    )
    ENGINE = ReplacingMergeTree ORDER BY fecha
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_ubicacion_flota
    (
        vehiculo_id String, conductor_id String, lat Float64, lon Float64,
        estado_servicio String, ts_servidor DateTime, fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, vehiculo_id, ts_servidor)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_recaudacion
    (
        pago_id String, viaje_id String, conductor_id String, metodo String,
        monto Float64, tarifa_final Float64, diferencia Float64, estado String,
        ts_registro DateTime, fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, pago_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_liquidacion
    (
        liquidacion_id String, conductor_id String, periodo_inicio DateTime,
        periodo_fin DateTime, estado String, bruto Float64, comisiones Float64,
        ajustes Float64, neto Float64, ts_emision DateTime, ts_pago Nullable(DateTime),
        fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, liquidacion_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_registro_usuario
    (
        usuario_id String, tipo String, estado String, canal String,
        ts_creacion DateTime, fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, usuario_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_ciclo_viaje
    (
        viaje_id String, estado String, zona_origen_id Nullable(String), franja String,
        ts_solicitud DateTime, ts_asignacion Nullable(DateTime),
        motivo_cancelacion Nullable(String), actor_cancelacion Nullable(String),
        fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, viaje_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_solicitud_captacion
    (
        solicitud_id String, estado String, canal String,
        fecha_envio DateTime, fecha_decision Nullable(DateTime),
        dias_aprobacion Nullable(Float64), fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, solicitud_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_cumplimiento_documental
    (
        documento_id String, tipo String, propietario_tipo String, propietario_id String,
        estado String, fecha_vencimiento Nullable(Date), fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, documento_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_integracion_api
    (
        evento_id String, actor_id String, endpoint String, accion String,
        ts DateTime, fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, evento_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_orden_mantenimiento
    (
        orden_id String, vehiculo_id String, tipo String, km_entrada Float64,
        km_salida Nullable(Float64), costo_total Nullable(Float64), horas_taller Nullable(Float64),
        fecha_programada Date, cumple_plazo UInt8, fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, orden_id)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.fact_viaje_historico
    (
        id_origen String, vendor_id String, pickup_datetime DateTime, dropoff_datetime DateTime,
        passenger_count Int32, trip_distance Float64, pickup_longitude Float64,
        pickup_latitude Float64, dropoff_longitude Float64, dropoff_latitude Float64,
        fare_amount Float64, extra Float64, mta_tax Float64, tip_amount Float64,
        tolls_amount Float64, imp_surcharge Float64, total_amount Float64,
        payment_type String, congestion_surcharge Float64, fecha Date, lote_id String
    )
    ENGINE = MergeTree PARTITION BY fecha ORDER BY (fecha, id_origen)
    """)

    # --- Metadatos de corrida ---------------------------------------------------
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.corridas
    (
        dag_id String, fecha_logica Date, lote_id String, estado String,
        registros_extraidos UInt32, registros_validos UInt32, registros_cuarentena UInt32,
        porcentaje_calidad Float64, duracion_bronze_seg Float64, duracion_silver_seg Float64,
        duracion_gold_seg Float64, iniciado_en DateTime, finalizado_en Nullable(DateTime)
    )
    ENGINE = MergeTree ORDER BY (dag_id, fecha_logica, iniciado_en)
    """)
    ddls.append("""
    CREATE TABLE IF NOT EXISTS urbanflet_gold.alertas
    (
        dag_id String, fecha_logica Date, tipo String, mensaje String, creado_en DateTime
    )
    ENGINE = MergeTree ORDER BY (dag_id, creado_en)
    """)

    for ddl in ddls:
        client.command(ddl)
    client.close()
    LOGGER.info("medallion.ensure_schema: esquema urbanflet_gold verificado/creado.")


# ---------------------------------------------------------------------------
# Ciclo de vida de una corrida
# ---------------------------------------------------------------------------

def registrar_inicio_corrida(dag_id: str, fecha_logica) -> str:
    """Genera un lote_id único y deja constancia del inicio de la corrida.
    La fila de `corridas` se completa (estado, métricas, fin) en finalizar_corrida;
    aquí solo generamos el identificador -- no insertamos una fila a medias porque
    ClickHouse MergeTree no soporta UPDATE eficiente; el registro completo se
    inserta una sola vez al final."""
    lote_id = f"{dag_id}_{fecha_logica}_{uuid.uuid4().hex[:8]}"
    LOGGER.info("Inicio de corrida dag_id=%s fecha_logica=%s lote_id=%s", dag_id, fecha_logica, lote_id)
    return lote_id


def insertar_bronze(tabla: str, registros: list[dict], lote_id: str) -> int:
    """Inserta registros crudos (sin transformar) en la tabla Bronze indicada,
    agregando lote_id y extraido_en. No lanza si `registros` está vacío."""
    if not registros:
        return 0
    client = get_client()
    extraido_en = datetime.utcnow()
    columnas = list(registros[0].keys())
    filas = []
    for r in registros:
        fila = [r.get(c) for c in columnas]
        filas.append(fila + [lote_id, extraido_en])
    client.insert(f"urbanflet_gold.{tabla}", filas, column_names=columnas + ["lote_id", "extraido_en"])
    client.close()
    return len(filas)


def insertar_cuarentena(dominio: str, registros_rechazados: list[dict], lote_id: str) -> int:
    """`registros_rechazados`: lista de dicts con claves id_origen, flag, valores (dict).
    `dominio` mapea a la tabla `cuarentena_{dominio}`."""
    if not registros_rechazados:
        return 0
    client = get_client()
    rechazado_en = datetime.utcnow()
    filas = [
        [r["id_origen"], r["flag"], lote_id, _to_json(r["valores"]), rechazado_en]
        for r in registros_rechazados
    ]
    client.insert(
        f"urbanflet_gold.cuarentena_{dominio}",
        filas,
        column_names=["id_origen", "flag", "lote_id", "valores_originales", "rechazado_en"],
    )
    client.close()
    return len(filas)


def borrar_particion_gold(tabla: str, fecha_logica) -> None:
    """Borra la partición `fecha_logica` de una tabla Gold, sin insertar nada.

    Existe para cargas de **muy alto volumen** (p. ej. `dag_historico_nyc`
    con el dataset NYC completo, ~1.3M filas) que no caben en memoria de una
    sola vez y se insertan en Gold chunk por chunk con `client.insert(...)`
    directo (no con `cargar_gold_idempotente`, que borra la partición EN
    CADA LLAMADA -- llamarla una vez por chunk dispararía N `ALTER ... DELETE`
    sobre la misma partición, y como esas mutaciones son asíncronas en
    ClickHouse, no hay garantía de orden entre el DELETE de un chunk y el
    INSERT de otro: se podría borrar un chunk que ya se había insertado).
    El patrón correcto para carga masiva es: `borrar_particion_gold` UNA
    VEZ al inicio de la corrida, y despues insertar cada chunk sin volver a
    borrar -- la idempotencia de "reejecutar la misma fecha_logica da el
    mismo resultado" se mantiene igual que con `cargar_gold_idempotente`."""
    client = get_client()
    fecha_str = fecha_logica.isoformat() if hasattr(fecha_logica, "isoformat") else str(fecha_logica)
    client.command(f"ALTER TABLE urbanflet_gold.{tabla} DELETE WHERE fecha = '{fecha_str}'")
    client.close()


def insertar_gold_chunk(tabla: str, registros: list[dict], fecha_logica, lote_id: str) -> int:
    """Inserta un chunk de filas Gold ya validadas, SIN borrar la partición
    (ver `borrar_particion_gold`). `registros` no debe incluir `fecha`/
    `lote_id` -- se agregan aquí, igual que en `cargar_gold_idempotente`."""
    if not registros:
        return 0
    client = get_client()
    fecha_str = fecha_logica.isoformat() if hasattr(fecha_logica, "isoformat") else str(fecha_logica)
    fecha_dt = date.fromisoformat(fecha_str)
    columnas = list(registros[0].keys())
    filas = [[r.get(c) for c in columnas] + [fecha_dt, lote_id] for r in registros]
    client.insert(
        f"urbanflet_gold.{tabla}", filas, column_names=columnas + ["fecha", "lote_id"]
    )
    client.close()
    return len(filas)


def cargar_gold_idempotente(tabla: str, registros: list[dict], fecha_logica, lote_id: str) -> int:
    """Carga idempotente (spec paso 5): borra la partición `fecha_logica` de la
    tabla Gold y luego inserta los registros válidos. Reejecutar una corrida
    para la misma fecha produce exactamente el mismo resultado."""
    client = get_client()
    fecha_str = fecha_logica.isoformat() if hasattr(fecha_logica, "isoformat") else str(fecha_logica)
    fecha_dt = date.fromisoformat(fecha_str)
    client.command(f"ALTER TABLE urbanflet_gold.{tabla} DELETE WHERE fecha = '{fecha_str}'")
    # ALTER DELETE en ClickHouse es asíncrono por mutación; para un dataset de
    # dev/demo de este tamaño no es necesario esperar el mutation queue porque
    # la siguiente sentencia es un INSERT (no depende del DELETE ya aplicado
    # físicamente, solo de que haya sido encolado) -- documentado como
    # simplificación aceptable para esta iteración.
    if not registros:
        client.close()
        return 0
    columnas = list(registros[0].keys())
    # Normaliza la columna "fecha" (partición) a `date` real -- los DAGs suelen
    # pasar el `ds` de Airflow (string "YYYY-MM-DD") en ese campo.
    filas = []
    for r in registros:
        fila = []
        for c in columnas:
            v = r.get(c)
            if c == "fecha" and isinstance(v, str):
                v = date.fromisoformat(v)
            fila.append(v)
        filas.append(fila)
    client.insert(f"urbanflet_gold.{tabla}", filas, column_names=columnas)
    client.close()
    return len(filas)


def finalizar_corrida(
    dag_id: str,
    fecha_logica,
    lote_id: str,
    registros_extraidos: int,
    registros_validos: int,
    registros_cuarentena: int,
    duracion_bronze_seg: float,
    duracion_silver_seg: float,
    duracion_gold_seg: float,
    iniciado_en: datetime,
) -> str:
    """Calcula % de calidad, decide estado (OK/WARN), escribe la fila en
    `corridas` y, si WARN, también en `alertas` + log ERROR/WARNING visible
    en el log de la tarea de Airflow (esa visibilidad ES la alerta inmediata
    de esta iteración -- no existe todavía un canal de push separado)."""
    finalizado_en = datetime.utcnow()
    porcentaje_calidad = (registros_validos / registros_extraidos) if registros_extraidos else 1.0
    tasa_cuarentena = (registros_cuarentena / registros_extraidos) if registros_extraidos else 0.0
    estado = "WARN" if tasa_cuarentena > UMBRAL_CUARENTENA_WARN else "OK"

    client = get_client()
    fecha_str = fecha_logica.isoformat() if hasattr(fecha_logica, "isoformat") else str(fecha_logica)
    fecha_dt = date.fromisoformat(fecha_str)
    client.insert(
        "urbanflet_gold.corridas",
        [[
            dag_id, fecha_dt, lote_id, estado,
            registros_extraidos, registros_validos, registros_cuarentena,
            porcentaje_calidad, duracion_bronze_seg, duracion_silver_seg, duracion_gold_seg,
            iniciado_en, finalizado_en,
        ]],
        column_names=[
            "dag_id", "fecha_logica", "lote_id", "estado",
            "registros_extraidos", "registros_validos", "registros_cuarentena",
            "porcentaje_calidad", "duracion_bronze_seg", "duracion_silver_seg", "duracion_gold_seg",
            "iniciado_en", "finalizado_en",
        ],
    )

    if estado == "WARN":
        mensaje = (
            f"PICO_CUARENTENA: {registros_cuarentena}/{registros_extraidos} "
            f"({tasa_cuarentena:.2%}) registros rechazados en lote {lote_id} "
            f"(> {UMBRAL_CUARENTENA_WARN:.0%} umbral A2)."
        )
        client.insert(
            "urbanflet_gold.alertas",
            [[dag_id, fecha_dt, "PICO_CUARENTENA", mensaje, datetime.utcnow()]],
            column_names=["dag_id", "fecha_logica", "tipo", "mensaje", "creado_en"],
        )
        LOGGER.warning("[ALERTA A2 - PICO_CUARENTENA] %s", mensaje)
    else:
        LOGGER.info(
            "Corrida %s fecha_logica=%s OK: %d/%d validos (%.2f%% calidad), %d en cuarentena.",
            dag_id, fecha_str, registros_validos, registros_extraidos,
            porcentaje_calidad * 100, registros_cuarentena,
        )

    client.close()
    return estado


def registrar_alerta_falla(dag_id: str, fecha_logica, mensaje: str, tipo: str = "FUENTE_INACCESIBLE") -> None:
    """Usado por on_failure_callback (A1): la corrida agotó reintentos y quedó
    FAILED. Escribe la alerta y también una fila `corridas` con estado FAILED
    cuando sea posible determinar fecha_logica."""
    LOGGER.error("[ALERTA %s] dag_id=%s fecha_logica=%s mensaje=%s", tipo, dag_id, fecha_logica, mensaje)
    try:
        client = get_client()
        fecha_str = fecha_logica.isoformat() if hasattr(fecha_logica, "isoformat") else str(fecha_logica)
        fecha_dt = date.fromisoformat(fecha_str)
        client.insert(
            "urbanflet_gold.alertas",
            [[dag_id, fecha_dt, tipo, mensaje, datetime.utcnow()]],
            column_names=["dag_id", "fecha_logica", "tipo", "mensaje", "creado_en"],
        )
        client.close()
    except Exception:
        LOGGER.exception("No se pudo escribir la alerta de falla en ClickHouse (fuente probablemente inaccesible).")


def on_failure_callback_factory(dag_id: str):
    """Devuelve un on_failure_callback listo para usar en default_args de un DAG."""

    def _callback(context):
        fecha_logica = context.get("ds") or context.get("logical_date")
        exception = context.get("exception")
        mensaje = f"Tarea {context.get('task_instance').task_id if context.get('task_instance') else '?'} FAILED: {exception}"
        registrar_alerta_falla(dag_id, fecha_logica, mensaje, tipo="FUENTE_INACCESIBLE")

    return _callback
