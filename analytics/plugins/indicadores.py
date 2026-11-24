"""CU-O16 -- Publicar los indicadores para los informes de las areas.

Snapshot tables (no ClickHouse VIEWs) para los 6 informes tacticos del
catalogo (spec paso 1). Cada refresh_* calcula el agregado actual desde Gold
y hace UN SOLO `client.insert(...)` con todas las filas del informe,
etiquetadas con `fecha_datos` (fecha logica de los datos que representa el
snapshot) y `actualizado_en` (momento del refresco).

Por que esto resuelve A1/A3 sin lógica extra:

  - Un `INSERT` a ClickHouse en una sola llamada se hace visible a los
    lectores como bloque atomico (todas sus filas aparecen juntas o ninguna:
    no hay INSERT parcial visible para SELECT concurrentes). Esa propiedad
    ES el "swap atomico" de A3 -- no se necesita tabla temporal + rename.
  - Los lectores SIEMPRE consultan
        SELECT ... FROM rpt_x WHERE fecha_datos = (SELECT max(fecha_datos) FROM rpt_x)
    Nunca ven una mezcla de dos refrescos porque toman el conjunto de filas
    de UN solo fecha_datos (el mas reciente insertado).
  - Si la corrida Gold del dominio de HOY fallo (o no ha corrido), la funcion
    de refresco de ese informe se salta el INSERT de hoy por completo. La
    consulta de "max(fecha_datos)" entonces sigue devolviendo el snapshot
    del ultimo dia bueno automaticamente -- sin ninguna rama especial en el
    lector. Eso es A1 ("los informes siguen sirviendo la ultima version
    buena, marcada datos al dia anterior") gratis.
  - A2 (regenerar sin re-ejecutar el DAG): cada refresh_* es una funcion
    independiente que solo LEE Gold y escribe el snapshot; se puede invocar
    en cualquier momento (dag_publicar_indicadores) sin volver a extraer de
    las fuentes transaccionales.

Cada tabla rpt_* es MergeTree simple (no ReplacingMergeTree): se conservan
todos los refrescos historicos (auditable), el lector siempre filtra por el
fecha_datos maximo.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import medallion

LOGGER = logging.getLogger("airflow.task")


# ---------------------------------------------------------------------------
# DDL idempotente de las tablas de snapshot (rpt_*)
# ---------------------------------------------------------------------------

def ensure_schema_indicadores() -> None:
    client = medallion.get_client()
    ddls = [
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_flota_activa_franja
        (
            franja String, pct_disponible Float64, total_registros UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, franja)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_tasa_discrepancias
        (
            fecha_periodo Date, metodo String, pct_discrepancia Float64, pct_conciliado Float64,
            total_registros UInt32, fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, fecha_periodo, metodo)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_margen_comision
        (
            periodo String, margen Float64, bruto_total Float64, comisiones_total Float64,
            horas_hasta_pago_promedio Nullable(Float64), fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, periodo)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_conversion_onboarding
        (
            tipo String, canal String, pct_activo Float64, total_registros UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, tipo, canal)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_documentacion_vigente
        (
            tipo String, pct_vigente Float64, total_registros UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, tipo)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_uso_integraciones
        (
            endpoint String, conteo UInt32, total_global UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, endpoint)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_cumplimiento_plan_preventivo
        (
            periodo String, pct_cumplimiento Float64, total_ordenes UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, periodo)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_costo_mantenimiento_vehiculo
        (
            vehiculo_id String, periodo String, costo_total Float64, total_ordenes UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, vehiculo_id, periodo)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_conversion_captacion
        (
            periodo String, canal String, pct_conversion Float64,
            dias_aprobacion_promedio Nullable(Float64), total_solicitudes UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, periodo, canal)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_altas_retencion_canal
        (
            periodo String, canal String, altas UInt32,
            pct_retencion Float64, fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, periodo, canal)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_tiempo_asignacion
        (
            zona_origen_id String, franja String, segundos_promedio Float64,
            segundos_p95 Float64, total_registros UInt32,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, zona_origen_id, franja)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_tasa_cancelacion
        (
            periodo String, zona_origen_id String, motivo String, actor String,
            cancelados UInt32, solicitados UInt32, tasa_cancelacion Float64,
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, periodo, zona_origen_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_cuarentena_dominio
        (
            dag_id String, pct_cuarentena Float64, registros_extraidos UInt32,
            registros_cuarentena UInt32, fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, dag_id)
        """,
        # Punto 3 de la ronda de mejoras de claridad y profundidad analítica
        # (agosto 2026) -- nuevo dashboard táctico "Rendimiento de Conductores".
        # Ver refrescar_desempeno_conductor()/refrescar_ingreso_conductor() para
        # el porqué de 2 tablas separadas (fuentes Gold con grano de periodo
        # distinto: fact_viaje/fact_ciclo_viaje son por viaje, fact_liquidacion
        # es por ciclo de liquidación semanal -- ambas se bucketan a mes acá).
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_desempeno_conductor
        (
            conductor_id String, periodo String, viajes_completados UInt32,
            viajes_cancelados UInt32, pct_exito Float64, calificacion_promedio Nullable(Float64),
            fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, periodo, conductor_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS urbanflet_gold.rpt_ingreso_conductor
        (
            conductor_id String, periodo String, bruto Float64, comisiones Float64,
            neto Float64, fecha_datos Date, actualizado_en DateTime
        )
        ENGINE = MergeTree ORDER BY (fecha_datos, periodo, conductor_id)
        """,
    ]
    for ddl in ddls:
        client.command(ddl)
    client.close()
    LOGGER.info("indicadores.ensure_schema_indicadores: tablas rpt_* verificadas/creadas.")


# ---------------------------------------------------------------------------
# Precondicion CU-O16: "corrida Gold del dominio finalizada OK o WARN"
# ---------------------------------------------------------------------------

def _ultima_corrida_ok_o_warn(client, dag_id: str) -> bool:
    """True si la corrida MAS RECIENTE de `dag_id` (cualquier fecha_logica)
    quedo OK o WARN. Si la ultima quedo FAILED, o no hay corridas todavia,
    devuelve False -- el refresco de hoy se salta (A1)."""
    filas = client.query(
        "SELECT estado FROM urbanflet_gold.corridas WHERE dag_id = {dag_id:String} "
        "ORDER BY iniciado_en DESC LIMIT 1",
        parameters={"dag_id": dag_id},
    ).result_rows
    if not filas:
        return False
    return filas[0][0] in ("OK", "WARN")


# ---------------------------------------------------------------------------
# Informe 1 -- % de flota activa por franja (dag_flota_gold)
# ---------------------------------------------------------------------------
# Simplificacion documentada: la spec pide "por franja y zona", pero
# fact_ubicacion_flota no tiene zona_id (solo lat/lon crudos, sin join a
# dim_zona -- ese join no existe para flota en el modelo actual). Se reporta
# solo por franja horaria (bucket de 6h derivado de la hora de ts_servidor);
# agregar zona requeriria un nearest-neighbor geoespacial contra dim_zona que
# no esta implementado en esta iteracion.

def refrescar_flota_activa() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_flota_gold"):
            LOGGER.warning("rpt_flota_activa_franja: ultima corrida de dag_flota_gold no OK/WARN, se omite el refresco de hoy.")
            return False

        filas = client.query(
            """
            SELECT
                multiIf(
                    toHour(ts_servidor) < 6, '00-06',
                    toHour(ts_servidor) < 12, '06-12',
                    toHour(ts_servidor) < 18, '12-18',
                    '18-24'
                ) AS franja,
                countIf(estado_servicio = 'DISPONIBLE') / count() AS pct_disponible,
                count() AS total_registros
            FROM urbanflet_gold.fact_ubicacion_flota
            GROUP BY franja
            ORDER BY franja
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[f, pct, total, hoy, ahora] for f, pct, total in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_flota_activa_franja",
                registros,
                column_names=["franja", "pct_disponible", "total_registros", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info("rpt_flota_activa_franja: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 2 -- Tasa de discrepancias (dag_finanzas_gold, fact_recaudacion)
# ---------------------------------------------------------------------------

def refrescar_tasa_discrepancias() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_finanzas_gold"):
            LOGGER.warning("rpt_tasa_discrepancias: ultima corrida de dag_finanzas_gold no OK/WARN, se omite el refresco de hoy.")
            return False

        filas = client.query(
            """
            SELECT
                toStartOfMonth(fecha) AS fecha_periodo,
                metodo,
                countIf(estado = 'DISCREPANCIA' OR abs(diferencia) > 0.01) / count() AS pct_discrepancia,
                sumIf(monto, estado = 'VALIDADO') / nullif(sum(monto), 0) AS pct_conciliado,
                count() AS total_registros
            FROM urbanflet_gold.fact_recaudacion
            GROUP BY fecha_periodo, metodo
            ORDER BY fecha_periodo, metodo
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [
            [fp, m, pct, (conc if conc is not None else 0.0), total, hoy, ahora]
            for fp, m, pct, conc, total in filas
        ]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_tasa_discrepancias",
                registros,
                column_names=[
                    "fecha_periodo", "metodo", "pct_discrepancia", "pct_conciliado",
                    "total_registros", "fecha_datos", "actualizado_en",
                ],
            )
        LOGGER.info("rpt_tasa_discrepancias: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 3 -- Margen de comision (dag_finanzas_gold, fact_liquidacion)
# ---------------------------------------------------------------------------

def refrescar_margen_comision() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_finanzas_gold"):
            LOGGER.warning("rpt_margen_comision: ultima corrida de dag_finanzas_gold no OK/WARN, se omite el refresco de hoy.")
            return False

        filas = client.query(
            """
            SELECT
                formatDateTime(periodo_inicio, '%Y-%m') AS periodo,
                sum(comisiones) / nullif(sum(bruto), 0) AS margen,
                sum(bruto) AS bruto_total,
                sum(comisiones) AS comisiones_total,
                avgIf(dateDiff('hour', ts_emision, ts_pago), ts_pago IS NOT NULL) AS horas_hasta_pago_promedio
            FROM urbanflet_gold.fact_liquidacion
            GROUP BY periodo
            ORDER BY periodo
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[p, (m if m is not None else 0.0), bt, ct, hhp, hoy, ahora] for p, m, bt, ct, hhp in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_margen_comision",
                registros,
                column_names=[
                    "periodo", "margen", "bruto_total", "comisiones_total",
                    "horas_hasta_pago_promedio", "fecha_datos", "actualizado_en",
                ],
            )
        LOGGER.info("rpt_margen_comision: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 4 -- Conversion de onboarding (dag_captacion_gold, fact_registro_usuario)
# ---------------------------------------------------------------------------

def refrescar_conversion_onboarding() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_captacion_gold"):
            LOGGER.warning("rpt_conversion_onboarding: ultima corrida de dag_captacion_gold no OK/WARN, se omite el refresco de hoy.")
            return False

        filas = client.query(
            """
            SELECT
                tipo, canal,
                countIf(estado = 'ACTIVO') / count() AS pct_activo,
                count() AS total_registros
            FROM urbanflet_gold.fact_registro_usuario
            GROUP BY tipo, canal
            ORDER BY tipo, canal
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[t, c, pct, total, hoy, ahora] for t, c, pct, total in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_conversion_onboarding",
                registros,
                column_names=["tipo", "canal", "pct_activo", "total_registros", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info("rpt_conversion_onboarding: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 5 -- Documentacion vigente por tipo (dag_cumplimiento_gold, fact_cumplimiento_documental)
# ---------------------------------------------------------------------------

def refrescar_documentacion_vigente() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_cumplimiento_gold"):
            LOGGER.warning("rpt_documentacion_vigente: ultima corrida de dag_cumplimiento_gold no OK/WARN, se omite el refresco de hoy.")
            return False

        filas = client.query(
            """
            SELECT
                tipo,
                countIf(fecha_vencimiento >= today()) / count() AS pct_vigente,
                count() AS total_registros
            FROM urbanflet_gold.fact_cumplimiento_documental
            GROUP BY tipo
            ORDER BY tipo
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[t, pct, total, hoy, ahora] for t, pct, total in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_documentacion_vigente",
                registros,
                column_names=["tipo", "pct_vigente", "total_registros", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info("rpt_documentacion_vigente: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 6 -- Uso de integraciones por endpoint (dag_cumplimiento_gold, fact_integracion_api)
# ---------------------------------------------------------------------------
# fact_integracion_api se carga hoy exclusivamente desde dag_cumplimiento_gold
# (ver ese DAG: bronze_bitacora -> fact_integracion_api, "aproximado desde
# bitacora"). No existe otro DAG que la pueble, asi que este informe tambien
# se gatea con la corrida de dag_cumplimiento_gold.

def refrescar_uso_integraciones() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_cumplimiento_gold"):
            LOGGER.warning("rpt_uso_integraciones: ultima corrida de dag_cumplimiento_gold no OK/WARN, se omite el refresco de hoy.")
            return False

        filas = client.query(
            """
            SELECT endpoint, count() AS conteo
            FROM urbanflet_gold.fact_integracion_api
            GROUP BY endpoint
            ORDER BY conteo DESC
            """
        ).result_rows
        total_global = sum(c for _, c in filas)

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[e, c, total_global, hoy, ahora] for e, c in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_uso_integraciones",
                registros,
                column_names=["endpoint", "conteo", "total_global", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info("rpt_uso_integraciones: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 7 -- Cumplimiento del plan preventivo por mes (dag_mantenimiento_gold, fact_orden_mantenimiento)
# ---------------------------------------------------------------------------
# No hay spec de nivel tactico en este repo que defina esta agregacion (ver
# docstring de dag_mantenimiento_gold.py) -- se interpreta "cumplimiento"
# como el % de ordenes PREVENTIVA que cerraron en o antes de su
# fecha_programada (columna `cumple_plazo`, calculada en el DAG fuente).

def refrescar_cumplimiento_plan_preventivo() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_mantenimiento_gold"):
            LOGGER.warning(
                "rpt_cumplimiento_plan_preventivo: ultima corrida de dag_mantenimiento_gold no OK/WARN, se omite el refresco de hoy."
            )
            return False

        filas = client.query(
            """
            SELECT
                substring(toString(fecha_programada), 1, 7) AS periodo,
                countIf(cumple_plazo = 1) / count() AS pct_cumplimiento,
                count() AS total_ordenes
            FROM urbanflet_gold.fact_orden_mantenimiento
            WHERE tipo = 'PREVENTIVA'
            GROUP BY periodo
            ORDER BY periodo
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[p, pct, total, hoy, ahora] for p, pct, total in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_cumplimiento_plan_preventivo",
                registros,
                column_names=["periodo", "pct_cumplimiento", "total_ordenes", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info(
            "rpt_cumplimiento_plan_preventivo: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy
        )
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 8 -- Costo de mantenimiento por vehiculo y periodo (dag_mantenimiento_gold, fact_orden_mantenimiento)
# ---------------------------------------------------------------------------

def refrescar_costo_mantenimiento_vehiculo() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_mantenimiento_gold"):
            LOGGER.warning(
                "rpt_costo_mantenimiento_vehiculo: ultima corrida de dag_mantenimiento_gold no OK/WARN, se omite el refresco de hoy."
            )
            return False

        # El alias de salida `costo_total` colisiona con la columna fuente del
        # mismo nombre si el filtro va en un WHERE al mismo nivel (ClickHouse
        # intenta resolver "costo_total" del WHERE contra el alias agregado
        # -> ILLEGAL_AGGREGATION). Se filtra en una subquery para que el
        # WHERE vea la columna cruda, sin ambigüedad con el alias de arriba.
        filas = client.query(
            """
            SELECT
                vehiculo_id,
                substring(toString(fecha), 1, 7) AS periodo,
                sum(costo_total) AS costo_total,
                count() AS total_ordenes
            FROM (
                SELECT vehiculo_id, fecha, costo_total
                FROM urbanflet_gold.fact_orden_mantenimiento
                WHERE costo_total IS NOT NULL
            )
            GROUP BY vehiculo_id, periodo
            ORDER BY vehiculo_id, periodo
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[v, p, costo, total, hoy, ahora] for v, p, costo, total in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_costo_mantenimiento_vehiculo",
                registros,
                column_names=["vehiculo_id", "periodo", "costo_total", "total_ordenes", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info(
            "rpt_costo_mantenimiento_vehiculo: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy
        )
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 9 -- Conversion y tiempo de aprobacion por mes/canal
# (dag_captacion_gold, fact_solicitud_captacion) -- CU-T01/OT1.1
# ---------------------------------------------------------------------------

def refrescar_conversion_captacion() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_captacion_gold"):
            LOGGER.warning(
                "rpt_conversion_captacion: ultima corrida de dag_captacion_gold no OK/WARN, se omite el refresco de hoy."
            )
            return False

        filas = client.query(
            """
            SELECT
                substring(toString(fecha_envio), 1, 7) AS periodo,
                canal,
                countIf(estado = 'APROBADA') / countIf(estado IN ('APROBADA', 'RECHAZADA')) AS pct_conversion,
                avgIf(dias_aprobacion, dias_aprobacion IS NOT NULL) AS dias_aprobacion_promedio,
                count() AS total_solicitudes
            FROM urbanflet_gold.fact_solicitud_captacion
            GROUP BY periodo, canal
            HAVING countIf(estado IN ('APROBADA', 'RECHAZADA')) > 0
            ORDER BY periodo, canal
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[p, c, pct, dias, total, hoy, ahora] for p, c, pct, dias, total in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_conversion_captacion",
                registros,
                column_names=[
                    "periodo", "canal", "pct_conversion", "dias_aprobacion_promedio",
                    "total_solicitudes", "fecha_datos", "actualizado_en",
                ],
            )
        LOGGER.info("rpt_conversion_captacion: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 10 -- Altas y retencion por canal/mes
# (dag_captacion_gold, fact_registro_usuario) -- CU-T02/OT1.2
# ---------------------------------------------------------------------------
# Simplificacion documentada: "retencion" en el sentido estricto de la spec
# (actividad a 90 dias del alta) necesitaria un re-chequeo periodico del
# estado del usuario -- no existe ningun job que reobserve usuarios 90 dias
# despues de su alta. Se aproxima con el `estado` que trae el snapshot de
# Gold para altas de hace >=90 dias (proxy: sigue ACTIVO), no una medicion de
# actividad real (viajes/conexiones). Documentado aqui en vez de fabricar una
# metrica de actividad que el sistema no rastrea todavia.

def refrescar_altas_retencion_canal() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_captacion_gold"):
            LOGGER.warning(
                "rpt_altas_retencion_canal: ultima corrida de dag_captacion_gold no OK/WARN, se omite el refresco de hoy."
            )
            return False

        filas = client.query(
            """
            SELECT
                substring(toString(ts_creacion), 1, 7) AS periodo,
                canal,
                count() AS altas,
                countIf(estado = 'ACTIVO' AND ts_creacion <= now() - INTERVAL 90 DAY)
                    / greatest(countIf(ts_creacion <= now() - INTERVAL 90 DAY), 1) AS pct_retencion
            FROM urbanflet_gold.fact_registro_usuario
            GROUP BY periodo, canal
            ORDER BY periodo, canal
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[p, c, altas, pct, hoy, ahora] for p, c, altas, pct in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_altas_retencion_canal",
                registros,
                column_names=["periodo", "canal", "altas", "pct_retencion", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info("rpt_altas_retencion_canal: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 11 -- Tiempo de asignacion por zona/franja
# (dag_viajes_core, fact_ciclo_viaje) -- CU-T07/OT4.1
# ---------------------------------------------------------------------------

def refrescar_tiempo_asignacion() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_viajes_core"):
            LOGGER.warning(
                "rpt_tiempo_asignacion: ultima corrida de dag_viajes_core no OK/WARN, se omite el refresco de hoy."
            )
            return False

        filas = client.query(
            """
            SELECT
                ifNull(zona_origen_id, 'DESCONOCIDA') AS zona_origen_id,
                franja,
                avg(dateDiff('second', ts_solicitud, ts_asignacion)) AS segundos_promedio,
                quantile(0.95)(dateDiff('second', ts_solicitud, ts_asignacion)) AS segundos_p95,
                count() AS total_registros
            FROM urbanflet_gold.fact_ciclo_viaje
            WHERE ts_asignacion IS NOT NULL
            GROUP BY zona_origen_id, franja
            ORDER BY zona_origen_id, franja
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[z, f, prom, p95, total, hoy, ahora] for z, f, prom, p95, total in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_tiempo_asignacion",
                registros,
                column_names=[
                    "zona_origen_id", "franja", "segundos_promedio", "segundos_p95",
                    "total_registros", "fecha_datos", "actualizado_en",
                ],
            )
        LOGGER.info("rpt_tiempo_asignacion: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 12 -- Tasa de cancelacion por motivo/actor/zona/mes
# (dag_viajes_core, fact_ciclo_viaje) -- CU-T08/OT4.2
# ---------------------------------------------------------------------------
# SIN_CONDUCTOR se trata como demanda desatendida (spec): sin motivo/actor
# explicito de cancelacion, se etiqueta motivo='SIN_CONDUCTOR', actor='sistema'.
#
# Defecto corregido (ronda de correcciones, agosto 2026): la version anterior
# calculaba `solicitados` con el MISMO `GROUP BY periodo, zona, motivo, actor`
# que particiona los cancelados -- como cada fila de ese agrupamiento, salvo
# el bucket motivo='N/A' (viajes NO cancelados), contiene EXCLUSIVAMENTE
# viajes cancelados, `solicitados` terminaba siendo un sinonimo de
# `cancelados` en la practica (`HAVING cancelados > 0` descarta el resto), asi
# que `tasa_cancelacion` por fila valia SIEMPRE 1.0 y cualquier consumidor que
# sumara `solicitados` entre filas heredaba ese mismo 100% ficticio -- nunca
# el universo real de viajes solicitados. Confirmado contra el dato real:
# `PanelDespacho.tsx` (tactico) sumaba las filas de este informe sin ningun
# filtro y mostraba 100.0% de forma permanente, sin importar el periodo.
#
# Corregido con un JOIN contra una segunda agregacion (`totales`, sin la
# dimension motivo/actor) que calcula el UNIVERSO real de viajes solicitados
# por (periodo, zona) -- se repite igual en cada fila de desglose de ese
# mismo periodo/zona, por diseno (es el mismo denominador para las N filas de
# motivo/actor que comparten periodo+zona). Un consumidor que sume
# `cancelados` entre filas de un periodo sigue obteniendo el total correcto
# (los buckets de cancelados son disjuntos, sin cambios ahi); uno que quiera
# el `solicitados`/`tasa_cancelacion` agregado del periodo debe deduplicar
# por zona primero (una fila por zona, no una por motivo/actor) antes de
# sumar -- ver `obtener_panel_confiabilidad` (backend) y
# `PanelDespacho.tsx::tasaCancelacionGlobal` (frontend), los 2 unicos
# consumidores reales, ya corregidos con ese mismo criterio.

def refrescar_tasa_cancelacion() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_viajes_core"):
            LOGGER.warning(
                "rpt_tasa_cancelacion: ultima corrida de dag_viajes_core no OK/WARN, se omite el refresco de hoy."
            )
            return False

        filas = client.query(
            """
            SELECT
                desglose.periodo AS periodo,
                desglose.zona_origen_id AS zona_origen_id,
                desglose.motivo AS motivo,
                desglose.actor AS actor,
                desglose.cancelados AS cancelados,
                totales.solicitados AS solicitados,
                desglose.cancelados / totales.solicitados AS tasa_cancelacion
            FROM (
                SELECT
                    substring(toString(ts_solicitud), 1, 7) AS periodo,
                    ifNull(zona_origen_id, 'DESCONOCIDA') AS zona_origen_id,
                    multiIf(estado = 'SIN_CONDUCTOR', 'SIN_CONDUCTOR', motivo_cancelacion IS NOT NULL, motivo_cancelacion, 'N/A') AS motivo,
                    ifNull(actor_cancelacion, 'sistema') AS actor,
                    countIf(estado IN ('CANCELADO', 'SIN_CONDUCTOR')) AS cancelados
                FROM urbanflet_gold.fact_ciclo_viaje
                GROUP BY periodo, zona_origen_id, motivo, actor
                HAVING cancelados > 0
            ) AS desglose
            INNER JOIN (
                SELECT
                    substring(toString(ts_solicitud), 1, 7) AS periodo,
                    ifNull(zona_origen_id, 'DESCONOCIDA') AS zona_origen_id,
                    count() AS solicitados
                FROM urbanflet_gold.fact_ciclo_viaje
                GROUP BY periodo, zona_origen_id
            ) AS totales
            ON desglose.periodo = totales.periodo AND desglose.zona_origen_id = totales.zona_origen_id
            ORDER BY periodo, zona_origen_id
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[p, z, m, a, canc, sol, tasa, hoy, ahora] for p, z, m, a, canc, sol, tasa in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_tasa_cancelacion",
                registros,
                column_names=[
                    "periodo", "zona_origen_id", "motivo", "actor", "cancelados",
                    "solicitados", "tasa_cancelacion", "fecha_datos", "actualizado_en",
                ],
            )
        LOGGER.info("rpt_tasa_cancelacion: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 13 -- % de cuarentena por dominio (tabla `corridas`, todos los DAGs)
# -- CU-T14/OT8.1
# ---------------------------------------------------------------------------
# A diferencia del resto de refrescar_*, este no depende de un solo dominio
# (es meta: agrega la corrida MAS RECIENTE de cada DAG) -- no hay gate
# _ultima_corrida_ok_o_warn de un dominio único que aplicar aquí.

def refrescar_cuarentena_dominio() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        filas = client.query(
            """
            SELECT
                dag_id,
                argMax(registros_extraidos, iniciado_en) AS registros_extraidos,
                argMax(registros_cuarentena, iniciado_en) AS registros_cuarentena
            FROM urbanflet_gold.corridas
            GROUP BY dag_id
            ORDER BY dag_id
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [
            [d, (rc / re if re > 0 else 0.0), re, rc, hoy, ahora] for d, re, rc in filas
        ]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_cuarentena_dominio",
                registros,
                column_names=[
                    "dag_id", "pct_cuarentena", "registros_extraidos",
                    "registros_cuarentena", "fecha_datos", "actualizado_en",
                ],
            )
        LOGGER.info("rpt_cuarentena_dominio: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Informe 14/15 -- Rendimiento de conductores (dag_viajes_core/dag_finanzas_gold)
# Punto 3 de la ronda de mejoras de claridad y profundidad analítica (agosto
# 2026). Ver CLAUDE.md §17.4 para la justificación de negocio de cada campo.
# ---------------------------------------------------------------------------
# 2 tablas, no 1: fact_viaje/fact_ciclo_viaje (grano = un viaje) y
# fact_liquidacion (grano = un ciclo de liquidación semanal, ya bucketado a
# mes acá para que comparta la misma clave `periodo` que la primera) tienen
# grano de tiempo distinto -- combinarlas en una sola consulta ClickHouse
# obligaría a un FULL OUTER JOIN de dos agregaciones ya resueltas, que
# ClickHouse soporta pero complica la lectura sin ganar nada: el endpoint que
# las consume (viajes/service.py::obtener_panel_desempeno_conductores) ya las
# combina por clave (conductor_id, periodo) en Python, mismo patrón que usa
# `dag_flota_gold` para resolver `estado_servicio` con un join de lectura.

def refrescar_desempeno_conductor() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_viajes_core"):
            LOGGER.warning(
                "rpt_desempeno_conductor: ultima corrida de dag_viajes_core no OK/WARN, se omite el refresco de hoy."
            )
            return False

        completados = {
            (cid, periodo): (n, calif)
            for cid, periodo, n, calif in client.query(
                """
                SELECT
                    conductor_id,
                    formatDateTime(ts_fin, '%Y-%m') AS periodo,
                    count() AS viajes_completados,
                    avgIf(calificacion_puntaje, calificacion_puntaje IS NOT NULL) AS calificacion_promedio
                FROM urbanflet_gold.fact_viaje
                WHERE conductor_id != ''
                GROUP BY conductor_id, periodo
                """
            ).result_rows
        }
        cancelados = {
            (cid, periodo): n
            for cid, periodo, n in client.query(
                """
                SELECT
                    conductor_id,
                    formatDateTime(ts_solicitud, '%Y-%m') AS periodo,
                    countIf(estado = 'CANCELADO') AS viajes_cancelados
                FROM urbanflet_gold.fact_ciclo_viaje
                WHERE conductor_id IS NOT NULL AND conductor_id != ''
                GROUP BY conductor_id, periodo
                HAVING viajes_cancelados > 0
                """
            ).result_rows
        }

        claves = set(completados) | set(cancelados)
        hoy = date.today()
        ahora = datetime.utcnow()
        registros = []
        for cid, periodo in claves:
            n_completados, calificacion = completados.get((cid, periodo), (0, None))
            n_cancelados = cancelados.get((cid, periodo), 0)
            total = n_completados + n_cancelados
            pct_exito = (n_completados / total) if total > 0 else 0.0
            registros.append([
                cid, periodo, n_completados, n_cancelados, pct_exito, calificacion, hoy, ahora,
            ])

        if registros:
            client.insert(
                "urbanflet_gold.rpt_desempeno_conductor",
                registros,
                column_names=[
                    "conductor_id", "periodo", "viajes_completados", "viajes_cancelados",
                    "pct_exito", "calificacion_promedio", "fecha_datos", "actualizado_en",
                ],
            )
        LOGGER.info("rpt_desempeno_conductor: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


def refrescar_ingreso_conductor() -> bool:
    ensure_schema_indicadores()
    client = medallion.get_client()
    try:
        if not _ultima_corrida_ok_o_warn(client, "dag_finanzas_gold"):
            LOGGER.warning(
                "rpt_ingreso_conductor: ultima corrida de dag_finanzas_gold no OK/WARN, se omite el refresco de hoy."
            )
            return False

        filas = client.query(
            """
            SELECT
                conductor_id,
                formatDateTime(periodo_inicio, '%Y-%m') AS periodo,
                sum(bruto) AS bruto, sum(comisiones) AS comisiones, sum(neto) AS neto
            FROM urbanflet_gold.fact_liquidacion
            GROUP BY conductor_id, periodo
            """
        ).result_rows

        hoy = date.today()
        ahora = datetime.utcnow()
        registros = [[cid, periodo, bruto, comisiones, neto, hoy, ahora] for cid, periodo, bruto, comisiones, neto in filas]
        if registros:
            client.insert(
                "urbanflet_gold.rpt_ingreso_conductor",
                registros,
                column_names=["conductor_id", "periodo", "bruto", "comisiones", "neto", "fecha_datos", "actualizado_en"],
            )
        LOGGER.info("rpt_ingreso_conductor: %d filas de snapshot insertadas (fecha_datos=%s).", len(registros), hoy)
        return True
    finally:
        client.close()


REFRESCOS = {
    "flota_activa_franja": refrescar_flota_activa,
    "tasa_discrepancias": refrescar_tasa_discrepancias,
    "margen_comision": refrescar_margen_comision,
    "conversion_onboarding": refrescar_conversion_onboarding,
    "documentacion_vigente": refrescar_documentacion_vigente,
    "uso_integraciones": refrescar_uso_integraciones,
    "cumplimiento_plan_preventivo": refrescar_cumplimiento_plan_preventivo,
    "costo_mantenimiento_vehiculo": refrescar_costo_mantenimiento_vehiculo,
    "conversion_captacion": refrescar_conversion_captacion,
    "altas_retencion_canal": refrescar_altas_retencion_canal,
    "tiempo_asignacion": refrescar_tiempo_asignacion,
    "tasa_cancelacion": refrescar_tasa_cancelacion,
    "cuarentena_dominio": refrescar_cuarentena_dominio,
    "desempeno_conductor": refrescar_desempeno_conductor,
    "ingreso_conductor": refrescar_ingreso_conductor,
}
