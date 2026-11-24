"""Viajes — CU-O04 (solicitar viaje). pkg-viajes también cubre CU-O05/O06
(despacho) y CU-O07/O08/O14 (ejecución, tarifa, historial), que se agregan
en slices posteriores de esta misma fase — ver ítem A3 del plan: es un solo
paquete, no dos módulos separados.

Cortes de alcance explícitos en este slice:
- Resolución de zona_origen_id/zona_destino_id: el formato de `geometria` en
  ZONA nunca quedó especificado (ni siquiera si es GeoJSON) — implementar un
  point-in-polygon real sobre un formato no definido sería inventar spec, no
  seguirla. Se deja `zona_origen_id`/`zona_destino_id` en None; alimenta
  reportes tácticos/BI (Fase 5), no el flujo operativo en sí.
"""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.config import get_settings
from src.core.agregacion_estrategica import agrupar, promedio_ponderado, ultimos_periodos, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, fetch_snapshot_history, get_clickhouse_client
from src.core.exceptions import DomainError
from src.core.geo import distancia_km
from src.core.tiempo import como_utc
from src.parametros import service as parametros_service
from src.parametros.service import ParametroNoVigenteError
from src.viajes import schemas, service_dispatch

# Sección 1.5 de ux_complementaria.md: un viaje PROGRAMADO cuenta como
# "activo" (el pasajero no puede tener dos a la vez, aparece en GET
# /viajes/activo, es cancelable) desde el momento en que se crea, no solo
# desde que el auto-despacho lo toma.
ESTADOS_ACTIVOS = frozenset({"PROGRAMADO", "SOLICITADO", "OFERTADO", "ASIGNADO", "EN_CAMINO", "EN_CURSO"})


class ViajeActivoExistenteError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="TRIP_ALREADY_ACTIVE", message="Ya tienes un viaje en curso o en búsqueda", status_code=409
        )


class SinViajeActivoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="SIN_VIAJE_ACTIVO", message="No tienes un viaje activo", status_code=404)


# CU-O04 A4: el pasajero puede cancelar mientras el viaje todavía no tiene un
# conductor confirmado. A partir de ASIGNADO el conductor ya se puso en
# marcha — cancelar esa cola (CU-O07 A2, con eventual compensación por
# distancia recorrida) queda fuera de alcance de este slice a propósito.
# PROGRAMADO se agrega por la Sección 1.5 (D2 ya aprobado): un viaje que
# todavía no disparó su auto-despacho es, con más razón, cancelable.
ESTADOS_CANCELABLES_PASAJERO = frozenset({"PROGRAMADO", "SOLICITADO", "OFERTADO"})


class ViajeNoCancelableError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VIAJE_NO_CANCELABLE",
            message="El viaje ya tiene un conductor asignado y no se puede cancelar desde aquí",
            status_code=409,
        )


# Sección 1.5: ventana válida para "Programar" -- un mínimo razonable para
# que tenga sentido distinto de "Ahora" (y le da margen a la cadencia del DAG
# de disparo, cada 1-2 min, sin que el viaje quede esperando mucho de más) y
# un máximo para no aceptar una fecha absurdamente lejana sin ningún caso de
# uso real detrás.
MARGEN_MINIMO_PROGRAMACION_MINUTOS = 15
MARGEN_MAXIMO_PROGRAMACION_DIAS = 7


class TsProgramadoInvalidoError(DomainError):
    def __init__(self, mensaje: str) -> None:
        super().__init__(code="TS_PROGRAMADO_INVALIDO", message=mensaje, status_code=422)


class ViajeNoProgramadoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="VIAJE_NO_PROGRAMADO", message="El viaje no está en estado PROGRAMADO", status_code=404)


def resolver_franja(ahora_utc: datetime | None = None) -> str:
    settings = get_settings()
    ahora_utc = ahora_utc or datetime.now(UTC)
    hora_local = ahora_utc.astimezone(ZoneInfo(settings.zona_horaria_operacion)).hour
    if settings.franja_diurna_desde_hora <= hora_local < settings.franja_diurna_hasta_hora:
        return "DIURNA"
    return "NOCTURNA"


async def obtener_viaje_activo(db: AsyncIOMotorDatabase, *, pasajero_id: str) -> dict | None:
    viaje = await db.viajes.find_one({"pasajero_id": pasajero_id, "estado": {"$in": list(ESTADOS_ACTIVOS)}})
    if viaje is None:
        return None
    # Avance de despacho bajo demanda (ver corte de alcance A5 en
    # service_dispatch.py): cada poll del pasajero resuelve ofertas vencidas
    # sin necesitar un scheduler en segundo plano.
    if viaje["estado"] in ("SOLICITADO", "OFERTADO"):
        viaje = await service_dispatch.avanzar_despacho(db, viaje)
    return viaje


async def obtener_viaje_activo_conductor(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict | None:
    return await db.viajes.find_one(
        {"conductor_id": conductor_id, "estado": {"$in": ["ASIGNADO", "EN_CAMINO", "EN_CURSO"]}}
    )


async def solicitar_viaje(db: AsyncIOMotorDatabase, *, pasajero_id: str, body: schemas.SolicitarViajeRequest) -> dict:
    # A3: el pasajero no puede tener más de un viaje activo a la vez (ya
    # incluye PROGRAMADO, ver ESTADOS_ACTIVOS arriba).
    if await obtener_viaje_activo(db, pasajero_id=pasajero_id) is not None:
        raise ViajeActivoExistenteError()

    ahora = datetime.now(UTC)

    ts_programado = None
    if body.ts_programado is not None:
        ts_programado = como_utc(body.ts_programado)
        if ts_programado < ahora + timedelta(minutes=MARGEN_MINIMO_PROGRAMACION_MINUTOS):
            raise TsProgramadoInvalidoError(
                f"La hora programada debe ser al menos {MARGEN_MINIMO_PROGRAMACION_MINUTOS} minutos en el futuro"
            )
        if ts_programado > ahora + timedelta(days=MARGEN_MAXIMO_PROGRAMACION_DIAS):
            raise TsProgramadoInvalidoError(
                f"La hora programada no puede ser más de {MARGEN_MAXIMO_PROGRAMACION_DIAS} días en el futuro"
            )

    # La franja/tarifa de vista previa se resuelve sobre la hora en que el
    # viaje realmente va a despacharse (la programada, si aplica) — no sobre
    # el momento en que el pasajero arma la solicitud. La tarifa final se
    # vuelve a calcular igual al finalizar (service_finalizacion.py), esto es
    # solo la vista previa.
    franja = resolver_franja(ts_programado or ahora)

    tarifa_estimada = None
    tarifa_version_id = None
    if body.destino_lat is not None and body.destino_lon is not None:
        try:
            tarifa = await parametros_service.obtener_vigente(
                db, tipo="tarifa", fecha=ts_programado or ahora, franja=franja
            )
        except ParametroNoVigenteError:
            tarifa = None
        if tarifa is not None:
            km_estimados = distancia_km(body.origen_lat, body.origen_lon, body.destino_lat, body.destino_lon)
            valores = tarifa["valores"]
            estimado = valores["arrancada"] + valores["costo_km"] * km_estimados
            tarifa_estimada = round(max(estimado, valores["carrera_minima"]), 2)
            tarifa_version_id = tarifa["_id"]

    viaje_id = str(uuid.uuid4())
    estado_inicial = "PROGRAMADO" if ts_programado is not None else "SOLICITADO"
    viaje = {
        "_id": viaje_id,
        "pasajero_id": pasajero_id,
        "conductor_id": None,
        "vehiculo_id": None,
        "estado": estado_inicial,
        "origen_lat": body.origen_lat,
        "origen_lon": body.origen_lon,
        "origen_direccion": body.origen_direccion,
        "destino_lat": body.destino_lat,
        "destino_lon": body.destino_lon,
        "destino_direccion": body.destino_direccion,
        "zona_origen_id": None,
        "zona_destino_id": None,
        "franja": franja,
        "tarifa_version_id": tarifa_version_id,
        "ts_programado": ts_programado,
        "ts_solicitud": ahora,
        "ts_asignacion": None,
        "ts_llegada_origen": None,
        "ts_inicio": None,
        "ts_fin": None,
        "km_recorridos": None,
        "min_espera": None,
        "tarifa_estimada": tarifa_estimada,
        "tarifa_final": None,
        "tarifa_version_id_final": None,
        "calificacion_pasajero_a_conductor": None,
        "calificacion_conductor_a_pasajero": None,
        "motivo_cancelacion": None,
        "actor_cancelacion": None,
        "revision_tarifa": False,
        "tarifa_parcial": False,
        "traza": [],
        "conductor_ofertado_id": None,
        "ts_oferta_emitida": None,
        "radio_actual_m": None,
        "radio_idx": 0,
        "ofertas_totales": 0,
        "conductores_descartados": [],
        "conductor_nombre": None,
        "conductor_calificacion": None,
        "vehiculo_placa": None,
        "vehiculo_marca": None,
        "vehiculo_color": None,
    }

    # Write-ahead (CU-O17): "trip state transitions" está en el catálogo
    # mínimo de eventos sensibles — se audita antes de persistir el viaje.
    await write_audit_event(
        db,
        actor_id=pasajero_id,
        rol="pasajero",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id=viaje_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={
            "estado": estado_inicial,
            "ts_programado": ts_programado.isoformat() if ts_programado else None,
        },
    )
    await db.viajes.insert_one(viaje)

    # CU-O04 paso 5 / CU-O05: dispara el auto-despacho inmediatamente después
    # de crear el viaje. No se envuelve junto con la inserción del viaje en la
    # misma transacción: SOLICITADO sin oferta todavía es un estado válido de
    # la propia máquina de estados (no un estado parcial inválido), así que si
    # el despacho no encuentra candidatos ahora, el próximo poll lo reintenta.
    # Sección 1.5: un viaje PROGRAMADO NO dispara despacho ahora — eso ocurre
    # más tarde, vía disparar_viaje_programado() (llamado por el DAG cerca de
    # ts_programado), que reutiliza este mismo avanzar_despacho.
    if estado_inicial == "SOLICITADO":
        viaje = await service_dispatch.avanzar_despacho(db, viaje)

    return viaje


async def disparar_viaje_programado(db: AsyncIOMotorDatabase, *, viaje_id: str) -> dict:
    """Sección 1.5: punto de entrada llamado por `dag_disparar_viajes_
    programados` (Airflow) cerca de `ts_programado` -- transiciona
    PROGRAMADO -> SOLICITADO y entra por el mismo punto de entrada de
    siempre (`avanzar_despacho`, CU-O05), sin reimplementar nada de lógica
    de despacho acá. `ts_solicitud` se actualiza a AHORA (no al momento de
    creación del registro PROGRAMADO): es el instante real en que el viaje
    entra a la cola de despacho, mismo significado que tiene ese campo para
    cualquier otro viaje del sistema -- necesario para que
    `rpt_tiempo_asignacion`/`rpt_tasa_cancelacion` (que particionan
    fact_ciclo_viaje por ts_solicitud) no mezclen "cuándo se programó" con
    "cuándo entró realmente a buscar conductor". `ts_programado` se
    conserva tal cual, como registro de la hora que pidió el pasajero."""
    viaje = await db.viajes.find_one({"_id": viaje_id, "estado": "PROGRAMADO"})
    if viaje is None:
        raise ViajeNoProgramadoError()

    ahora = datetime.now(UTC)
    await write_audit_event(
        db,
        actor_id=None,
        rol=None,
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id=viaje_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "PROGRAMADO"},
        datos_posteriores={"estado": "SOLICITADO", "disparado_por": "dag_disparar_viajes_programados"},
    )
    await db.viajes.update_one({"_id": viaje_id}, {"$set": {"estado": "SOLICITADO", "ts_solicitud": ahora}})
    viaje["estado"] = "SOLICITADO"
    viaje["ts_solicitud"] = ahora

    return await service_dispatch.avanzar_despacho(db, viaje)


async def cancelar_viaje_pasajero(db: AsyncIOMotorDatabase, *, pasajero_id: str, motivo: str) -> dict:
    """CU-O04 A4: cancelación temprana por el pasajero, sobre SU viaje activo
    (no toma un viaje_id de la URL — evita cualquier ambigüedad de ownership,
    y de paso evita chocar en el ruteo con /viajes/conductor/cancelar de
    service_ejecucion, que es un endpoint totalmente distinto). Solo válida
    antes de que haya un conductor confirmado (ver
    ESTADOS_CANCELABLES_PASAJERO) — la cancelación con un conductor ya en
    camino es CU-O07 A2, deliberadamente fuera de alcance de este slice.

    A propósito NO reutiliza `obtener_viaje_activo` (que avanza el despacho
    bajo demanda antes de devolver el viaje): cancelar es una intención del
    pasajero sobre el estado que él vio en su última consulta, no debe
    disparar como efecto secundario un redespacho que podría, por ejemplo,
    convertir un SOLICITADO cancelable en un SIN_CONDUCTOR (que ya no
    aparecería como activo en absoluto)."""
    viaje = await db.viajes.find_one({"pasajero_id": pasajero_id, "estado": {"$in": list(ESTADOS_ACTIVOS)}})
    if viaje is None:
        raise SinViajeActivoError()
    if viaje["estado"] not in ESTADOS_CANCELABLES_PASAJERO:
        raise ViajeNoCancelableError()

    viaje_id = viaje["_id"]
    await write_audit_event(
        db,
        actor_id=pasajero_id,
        rol="pasajero",
        accion=AccionAuditoria.VIAJE_CANCELADO_PASAJERO,
        entidad="viajes",
        entidad_id=viaje_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": viaje["estado"]},
        datos_posteriores={"estado": "CANCELADO", "motivo_cancelacion": motivo},
    )
    await db.viajes.update_one(
        {"_id": viaje_id},
        {
            "$set": {
                "estado": "CANCELADO",
                "motivo_cancelacion": motivo,
                "actor_cancelacion": "pasajero",
            }
        },
    )
    viaje["estado"] = "CANCELADO"
    viaje["motivo_cancelacion"] = motivo
    viaje["actor_cancelacion"] = "pasajero"
    return viaje


def _decodificar_polilinea(encoded: str) -> list[tuple[float, float]]:
    """Algoritmo estándar de polilíneas de Google — mismo que el decoder a
    mano en rutas.ts del frontend (Directions API no tiene SDK server-side
    oficial en Python, y no vale la pena una dependencia extra por esto)."""
    puntos: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    largo = len(encoded)

    while index < largo:
        resultado = 0
        shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            resultado |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lat += ~(resultado >> 1) if resultado & 1 else (resultado >> 1)

        resultado = 0
        shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            resultado |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lon += ~(resultado >> 1) if resultado & 1 else (resultado >> 1)

        puntos.append((lat / 1e5, lon / 1e5))
    return puntos


def _ruta_linea_recta(
    origen_lat: float, origen_lon: float, destino_lat: float, destino_lon: float
) -> schemas.EstimacionRutaOut:
    km = distancia_km(origen_lat, origen_lon, destino_lat, destino_lon)
    return schemas.EstimacionRutaOut(
        ruta=[(origen_lat, origen_lon), (destino_lat, destino_lon)],
        distancia_km=km,
        # Estimación gruesa a ~25 km/h promedio urbano — mismo criterio que
        # el fallback que ya existía en el cliente (rutas.ts), ahora también
        # aquí para cuando Directions falla del lado del servidor.
        duracion_min=(km / 25) * 60,
        origen_directions=False,
    )


async def estimar_ruta(
    db: AsyncIOMotorDatabase, *, origen_lat: float, origen_lon: float, destino_lat: float, destino_lon: float
) -> schemas.EstimacionRutaOut:
    """CU-O04 P3, corregido tras hallazgo en pruebas reales: Directions API
    de Google no envía cabeceras CORS (a diferencia de Geocoding, que sí) —
    llamarla directo desde el navegador falla siempre, silenciosamente, y el
    cliente caía al respaldo de línea recta sin que nadie lo supiera. Ahora
    se pide siempre desde aquí, con la key server-side (nunca en el bundle
    del cliente).

    Módulo 4.2 de admin_sistema: la key se lee vía
    `integraciones.service.obtener_google_maps_api_key` (override en Mongo
    si se rotó desde el panel, si no cae a `Settings`) -- no directo de
    `Settings`, para que una rotación tenga efecto sin reiniciar el backend.
    """
    from src.integraciones.service import obtener_google_maps_api_key

    api_key = await obtener_google_maps_api_key(db)
    if not api_key:
        return _ruta_linea_recta(origen_lat, origen_lon, destino_lat, destino_lon)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params={
                    "origin": f"{origen_lat},{origen_lon}",
                    "destination": f"{destino_lat},{destino_lon}",
                    "key": api_key,
                },
            )
        data = resp.json()
        ruta = (data.get("routes") or [None])[0]
        tramo = (ruta.get("legs") or [None])[0] if ruta else None
        if data.get("status") == "OK" and ruta and tramo:
            return schemas.EstimacionRutaOut(
                ruta=_decodificar_polilinea(ruta["overview_polyline"]["points"]),
                distancia_km=tramo["distance"]["value"] / 1000,
                duracion_min=tramo["duration"]["value"] / 60,
                origen_directions=True,
            )
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        # Directions es opcional por diseño (cuota, red, sin ruta entre los
        # puntos) — nunca debe romper la vista previa de tarifa del pasajero.
        pass

    return _ruta_linea_recta(origen_lat, origen_lon, destino_lat, destino_lon)


# ---------------------------------------------------------------------------
# Panel táctico de Despacho -- CU-T07/T08 (specs/nivel-tactico/tactico_operaciones_despacho.md)
# ---------------------------------------------------------------------------

# Nombre deliberadamente distinto del ESTADOS_ACTIVOS de arriba (línea 35):
# antes de la Sección 1.5 este archivo redefinía el mismo nombre acá con un
# valor idéntico (bug de sombra real, aunque inofensivo hasta ahora, porque
# como es una reasignación a nivel de módulo, TODAS las funciones que
# referencian "ESTADOS_ACTIVOS" resuelven contra esta segunda definición al
# ejecutarse, no la primera) -- se corrige acá porque agregar PROGRAMADO
# solo arriba, sin renombrar esta, lo habría dejado sin efecto en
# obtener_viaje_activo/cancelar_viaje_pasajero. Este segundo conjunto es
# intencionalmente SIN PROGRAMADO: un viaje programado que todavía no
# disparó su despacho no es "un viaje en curso ahora" para este panel.
ESTADOS_ACTIVOS_PANEL = ("SOLICITADO", "OFERTADO", "ASIGNADO", "EN_CAMINO", "EN_CURSO")


async def listar_viajes_activos(db: AsyncIOMotorDatabase) -> list[dict]:
    """Informe simple (MongoDB) -- viajes en curso ahora, cualquier estado activo."""
    cursor = db.viajes.find({"estado": {"$in": list(ESTADOS_ACTIVOS_PANEL)}}).sort("ts_solicitud", -1)
    return await cursor.to_list(length=500)


async def listar_sin_conductor_y_cancelados_hoy(db: AsyncIOMotorDatabase) -> list[dict]:
    """Informe simple (MongoDB) -- SIN_CONDUCTOR/CANCELADO solicitados hoy."""
    inicio_dia = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = db.viajes.find(
        {"estado": {"$in": ["SIN_CONDUCTOR", "CANCELADO"]}, "ts_solicitud": {"$gte": inicio_dia}}
    ).sort("ts_solicitud", -1)
    return await cursor.to_list(length=500)


def obtener_tiempo_asignacion() -> list[dict]:
    """Informe compuesto (ClickHouse) -- `rpt_tiempo_asignacion` (CU-T07/OT4.1)."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_tiempo_asignacion")
    finally:
        client.close()
    return sorted(filas, key=lambda f: (f["zona_origen_id"], f["franja"]))


def obtener_tasa_cancelacion() -> list[dict]:
    """Informe compuesto (ClickHouse) -- `rpt_tasa_cancelacion` (CU-T08/OT4.2)."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_tasa_cancelacion")
    finally:
        client.close()
    # Periodo más reciente primero (auditoría exhaustiva de orden de tablas).
    # Dentro del mismo periodo, la zona ascendente: ahí no hay cronología, es
    # una comparación entre zonas.
    filas = sorted(filas, key=lambda f: f["zona_origen_id"])
    return sorted(filas, key=lambda f: f["periodo"], reverse=True)


async def obtener_panel_desempeno_conductores(
    db: AsyncIOMotorDatabase, *, meses: int = 3, historico_completo: bool = False, incluir_inactivos: bool = False
) -> dict:
    """Panel táctico "Rendimiento de Conductores" -- Punto 3 de la ronda de
    mejoras de claridad y profundidad analítica (agosto 2026, ver CLAUDE.md
    §17.4). Combina `rpt_desempeno_conductor` + `rpt_ingreso_conductor` (2
    tablas, grano de periodo distinto en origen -- ver el docstring en
    `analytics/plugins/indicadores.py::refrescar_desempeno_conductor`).

    `historico_completo=False` (default) es la ventana reciente pedida
    explícitamente: los 1.3M viajes NYC sembrados (CLAUDE.md §7/§8.5) están
    repartidos por round-robin entre solo 5 conductores reales, así que
    cualquier comparación sobre el histórico completo mostraría 5 socios casi
    idénticos con ~270K viajes cada uno -- sin varianza real entre ellos. Con
    la ventana reciente (los `meses` periodos más recientes con dato
    publicado) la comparación sí refleja despacho real casi siempre -- PERO
    hay un caso real donde la ventana reciente sola no basta, encontrado con
    verificación real en navegador (no solo en teoría): este entorno de
    desarrollo tiene un salto de 5 años sin ningún dato entre el rango NYC
    (2021-01/02) y la operación real (2026-07+) -- con `meses=3` sobre un
    dataset que solo tiene 3 periodos distintos EN TOTAL, "los 3 más
    recientes" son los 3 únicos que existen, incluidos los 2 de NYC. Por eso
    la advertencia de concentración NO depende solo de `historico_completo`
    (ver más abajo): se enciende también si algún socio en el resultado ya
    filtrado supera `UMBRAL_CONCENTRACION_NYC` viajes en un solo periodo --
    señal real del patrón de siembra, no una fecha de corte arbitraria (que
    dejaría de ser cierta el día que la operación real acumule más historia).
    """
    UMBRAL_CONCENTRACION_NYC = 1000

    client = get_clickhouse_client()
    try:
        desempeno = fetch_latest_snapshot(client, "rpt_desempeno_conductor")
        ingreso = fetch_latest_snapshot(client, "rpt_ingreso_conductor")
    finally:
        client.close()

    periodos_filtro: set[str] | None = None
    if not historico_completo:
        periodos_filtro = set(ultimos_periodos((f["periodo"] for f in desempeno), meses))
        desempeno = [f for f in desempeno if f["periodo"] in periodos_filtro]
        ingreso = [f for f in ingreso if f["periodo"] in periodos_filtro]

    concentracion_detectada = any(f["viajes_completados"] > UMBRAL_CONCENTRACION_NYC for f in desempeno)

    # Parte 3 (ronda de diagnóstico y nuevos indicadores, agosto 2026):
    # kilómetros recorridos y distribución de calificaciones -- ninguno de
    # los dos vive en una `rpt_*` (habría exigido tocar el DAG/Airflow para
    # un solo panel), así que se leen directo de `fact_viaje` con la misma
    # ventana de periodo ya resuelta arriba. Consulta liviana (GROUP BY
    # simple sobre columnas ya existentes, sin el patrón de deduplicación
    # que causó el problema real de memoria documentado en CLAUDE.md §8.6b)
    # -- deliberadamente NO se reintenta ese patrón acá.
    km_por_socio: list[dict] = []
    histograma_calificaciones: list[dict] = []
    client_directo = get_clickhouse_client()
    try:
        condicion_periodo = ""
        parametros: dict = {}
        if periodos_filtro is not None:
            condicion_periodo = "AND formatDateTime(ts_fin, '%Y-%m') IN {periodos:Array(String)}"
            parametros["periodos"] = list(periodos_filtro)

        km_rows = client_directo.query(
            f"""
            SELECT conductor_id, sum(km_recorridos) AS km_total
            FROM urbanflet_gold.fact_viaje
            WHERE conductor_id != '' {condicion_periodo}
            GROUP BY conductor_id
            """,
            parameters=parametros,
        ).result_rows
        km_por_socio = [{"conductor_id": cid, "km_total": round(km, 1)} for cid, km in km_rows]

        calif_rows = client_directo.query(
            f"""
            SELECT calificacion_puntaje, count() AS viajes
            FROM urbanflet_gold.fact_viaje
            WHERE calificacion_puntaje IS NOT NULL {condicion_periodo}
            GROUP BY calificacion_puntaje
            ORDER BY calificacion_puntaje
            """,
            parameters=parametros,
        ).result_rows
        histograma_calificaciones = [
            {"estrellas": int(estrellas), "viajes": viajes} for estrellas, viajes in calif_rows
        ]
    except Exception:  # noqa: BLE001 -- ClickHouse caído/tabla ausente: el panel se sirve sin estos 2 extras, nunca 500
        pass
    finally:
        client_directo.close()

    ingreso_por_clave = {(f["conductor_id"], f["periodo"]): f for f in ingreso}
    conductor_ids = {f["conductor_id"] for f in desempeno} | {f["conductor_id"] for f in ingreso}

    ids_inactivos: set[str] = set()
    if incluir_inactivos:
        # Roster completo de conductores activos, cruzado contra quienes YA
        # tienen alguna fila en la ventana -- la diferencia son los socios sin
        # ningún viaje completado/cancelado, informativo para un jefe de área
        # que quiere ver también quién no está produciendo, no solo quién sí
        # (Parte 3 de la ronda de diagnóstico, agosto 2026). Roster acotado a
        # `estado: ACTIVO` -- un conductor suspendido o dado de baja no debería
        # aparecer como "sin actividad", ya está fuera de operación por otra
        # razón documentada en su propia ficha.
        todos_conductores = await db.usuarios.find(
            {"roles": "conductor", "estado": "ACTIVO"}, {"_id": 1}
        ).to_list(length=1000)
        ids_inactivos = {u["_id"] for u in todos_conductores} - conductor_ids

    nombres = await _resolver_nombres_conductores(
        db, conductor_ids | ids_inactivos | {f["conductor_id"] for f in km_por_socio}
    )

    filas = []
    for f in desempeno:
        ing = ingreso_por_clave.get((f["conductor_id"], f["periodo"]))
        filas.append({
            "conductor_id": f["conductor_id"],
            "conductor_nombre": nombres.get(f["conductor_id"]),
            "periodo": f["periodo"],
            "viajes_completados": f["viajes_completados"],
            "viajes_cancelados": f["viajes_cancelados"],
            "pct_exito": f["pct_exito"],
            "calificacion_promedio": f.get("calificacion_promedio"),
            "bruto": ing["bruto"] if ing else None,
            "comisiones": ing["comisiones"] if ing else None,
            "neto": ing["neto"] if ing else None,
            "sin_actividad": False,
        })
    # Periodo más reciente primero (auditoría exhaustiva de orden de tablas):
    # el periodo es un string "YYYY-MM", así que ordena bien lexicográficamente.
    # Dentro de un mismo periodo se mantiene el nombre del socio ascendente --
    # ahí no hay "más reciente" que valga, es una lista de comparación.
    filas.sort(key=lambda f: f["conductor_id"])
    filas.sort(key=lambda f: f["periodo"], reverse=True)

    filas_inactivas = [
        {
            "conductor_id": cid,
            "conductor_nombre": nombres.get(cid),
            "periodo": "Sin actividad en la ventana",
            "viajes_completados": 0,
            "viajes_cancelados": 0,
            "pct_exito": 0.0,
            "calificacion_promedio": None,
            "bruto": None,
            "comisiones": None,
            "neto": None,
            "sin_actividad": True,
        }
        for cid in sorted(ids_inactivos, key=lambda cid: nombres.get(cid, cid))
    ]

    km_por_socio_out = [
        {
            "conductor_id": f["conductor_id"],
            "conductor_nombre": nombres.get(f["conductor_id"]),
            "km_total": f["km_total"],
        }
        for f in km_por_socio
    ]
    km_por_socio_out.sort(key=lambda f: f["km_total"], reverse=True)

    return {
        "filas": filas + filas_inactivas,
        "km_por_socio": km_por_socio_out,
        "histograma_calificaciones": histograma_calificaciones,
        "metadata": {
            "historico_completo": historico_completo,
            "ventana_meses": None if historico_completo else meses,
            "advertencia_concentracion_historica": historico_completo or concentracion_detectada,
            "incluir_inactivos": incluir_inactivos,
            "conductores_sin_actividad": len(ids_inactivos),
        },
    }


async def _resolver_nombres_conductores(db: AsyncIOMotorDatabase, conductor_ids: set[str]) -> dict[str, str]:
    conductor_ids = {c for c in conductor_ids if c}
    if not conductor_ids:
        return {}
    usuarios = await db.usuarios.find({"_id": {"$in": list(conductor_ids)}}).to_list(length=len(conductor_ids))
    return {u["_id"]: u["nombre"] for u in usuarios}


def _periodo_a_trimestre(periodo: str) -> str:
    anio, mes = periodo.split("-")[0], int(periodo.split("-")[1])
    return f"{anio}-T{(mes - 1) // 3 + 1}"


# ---------------------------------------------------------------------------
# Nivel estratégico -- Panel de Desempeño de Conductores (N6 rediseñado)
# ---------------------------------------------------------------------------
# Cierre del pendiente 1.1 (Tier 1/Tier 2): la primera versión de este panel
# reusaba `obtener_panel_desempeno_conductores` TAL CUAL -- misma
# granularidad mensual por conductor que ve `coordinador_operaciones` en el
# panel táctico, sin ninguna segunda capa de agregación propia. Eso rompía
# el patrón de los otros 9 paneles estratégicos (todos agregan sobre `rpt_*`,
# no re-exponen el dato táctico intacto).
#
# Evaluación de costo (pedida explícitamente antes de decidir): las 2
# fuentes (`rpt_desempeno_conductor`/`rpt_ingreso_conductor`) YA son un
# agregado por conductorxmes, no una tabla operativa fila por fila -- así que
# no hay "más crudo" que agregar hacia arriba salvo el propio grano temporal.
# Agrupar por TRIMESTRE en vez de por mes resultó de costo bajo: reusa el
# mismo patrón de bucketing ya escrito en
# `estrategico/service.py::obtener_panel_rentabilidad`
# (trimestre = año + (mes-1)//3 + 1) -- una vista genuinamente más gruesa que
# la operativa, no una re-exposición. Se implementa acá en vez de
# documentar una excepción, porque el esfuerzo real resultó bajo y hay
# margen real para una capa distinta.
UMBRAL_CONCENTRACION_NYC_TRIMESTRE = 3000  # 3x el umbral mensual del panel táctico


async def obtener_panel_estrategico_desempeno_conductores(
    db: AsyncIOMotorDatabase, *, trimestres: int = 4, historico_completo: bool = False
) -> dict:
    """Panel estratégico de Desempeño de Conductores -- filas por
    conductorxTRIMESTRE (no por conductorxmes como el panel táctico), sin
    KPI de concentración (decisión de negocio ya cerrada) y con la misma
    advertencia PERMANENTE (no condicional) sobre la concentración
    artificial del dataset NYC sembrado (CLAUDE.md §8.5/§17.4)."""
    client = get_clickhouse_client()
    try:
        desempeno = fetch_latest_snapshot(client, "rpt_desempeno_conductor")
        ingreso = fetch_latest_snapshot(client, "rpt_ingreso_conductor")
    finally:
        client.close()

    if not historico_completo:
        periodos_recientes = set(ultimos_periodos((f["periodo"] for f in desempeno), trimestres * 3))
        desempeno = [f for f in desempeno if f["periodo"] in periodos_recientes]
        ingreso = [f for f in ingreso if f["periodo"] in periodos_recientes]

    ingreso_por_clave = {(f["conductor_id"], f["periodo"]): f for f in ingreso}

    acumulado: dict[tuple[str, str], dict] = {}
    for f in desempeno:
        trimestre = _periodo_a_trimestre(f["periodo"])
        clave = (f["conductor_id"], trimestre)
        acc = acumulado.setdefault(
            clave,
            {
                "conductor_id": f["conductor_id"],
                "trimestre": trimestre,
                "viajes_completados": 0,
                "viajes_cancelados": 0,
                "_peso_calificacion": 0.0,
                "_suma_calificacion": 0.0,
                "bruto": 0.0,
                "comisiones": 0.0,
                "neto": 0.0,
            },
        )
        acc["viajes_completados"] += f["viajes_completados"]
        acc["viajes_cancelados"] += f["viajes_cancelados"]
        if f.get("calificacion_promedio") is not None:
            acc["_suma_calificacion"] += f["calificacion_promedio"] * f["viajes_completados"]
            acc["_peso_calificacion"] += f["viajes_completados"]
        ing = ingreso_por_clave.get((f["conductor_id"], f["periodo"]))
        if ing:
            acc["bruto"] += ing["bruto"]
            acc["comisiones"] += ing["comisiones"]
            acc["neto"] += ing["neto"]

    concentracion_detectada = any(
        acc["viajes_completados"] > UMBRAL_CONCENTRACION_NYC_TRIMESTRE for acc in acumulado.values()
    )

    conductor_ids = {conductor_id for conductor_id, _ in acumulado}
    nombres = await _resolver_nombres_conductores(db, conductor_ids)

    filas = []
    for (conductor_id, trimestre), acc in acumulado.items():
        total = acc["viajes_completados"] + acc["viajes_cancelados"]
        filas.append(
            {
                "conductor_id": conductor_id,
                "conductor_nombre": nombres.get(conductor_id),
                "trimestre": trimestre,
                "viajes_completados": acc["viajes_completados"],
                "viajes_cancelados": acc["viajes_cancelados"],
                "pct_exito": round(acc["viajes_completados"] / total, 4) if total else None,
                "calificacion_promedio": (
                    round(acc["_suma_calificacion"] / acc["_peso_calificacion"], 2)
                    if acc["_peso_calificacion"]
                    else None
                ),
                "bruto": round(acc["bruto"], 2),
                "comisiones": round(acc["comisiones"], 2),
                "neto": round(acc["neto"], 2),
            }
        )
    # Trimestre más reciente primero (mismo criterio que el panel táctico
    # equivalente). "YYYY-Qn" ordena bien lexicográficamente.
    filas.sort(key=lambda f: f["conductor_id"])
    filas.sort(key=lambda f: f["trimestre"], reverse=True)

    return {
        "filas": filas,
        "metadata": {
            "historico_completo": historico_completo,
            "ventana_trimestres": None if historico_completo else trimestres,
            "advertencia_concentracion_historica": historico_completo or concentracion_detectada,
        },
    }


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Confiabilidad y Disponibilidad del Servicio
# (OE2a, nivel_estrategico.md §3.2.a, patrón Z)
# ---------------------------------------------------------------------------


def obtener_panel_confiabilidad(*, meses: int = 6, cortes: int = 12) -> dict:
    """Segunda capa de agregación sobre 3 `rpt_*` tácticos, sin tabla nueva.

    Fuentes (nivel_estrategico.md §3.2.a): `rpt_tiempo_asignacion` +
    `rpt_tasa_cancelacion` (Despacho) + `rpt_flota_activa_franja` (Flota).
    Este endpoint vive en el router de `viajes` y no en uno central porque
    2 de las 3 fuentes son de Despacho -- se aplica el mismo criterio
    descentralizado que ya usa el nivel táctico (cada dominio expone lo suyo);
    leer la tabla `rpt_*` de Flota desde acá es una lectura de solo lectura a
    ClickHouse, no un acoplamiento de dominio.

    Tendencia: `rpt_tasa_cancelacion` ya trae `periodo` (mes) en el propio
    snapshot; `rpt_tiempo_asignacion` y `rpt_flota_activa_franja` no, así que
    su tendencia sale del historial de `fecha_datos` (`fetch_snapshot_history`).

    **Una limitación real de las fuentes tácticas, verificada contra los
    datos, que este endpoint declara en vez de disimular:**

    1. La dimensión "franja" no usa el mismo vocabulario en las dos tablas:
       `rpt_flota_activa_franja` publica `00-06/06-12/12-18/18-24` y
       `rpt_tiempo_asignacion` publica `DIURNA/NOCTURNA`. No se cruzan por
       franja (un join daría 100% de nulos); se devuelven como dos listas
       separadas, cada una con su propia taxonomía.

    (Hasta la ronda de correcciones de agosto 2026, `rpt_tasa_cancelacion.
    tasa_cancelacion` no era una tasa consolidable -- `solicitados` se
    calculaba con el mismo `GROUP BY` que particiona por motivo/actor, así
    que siempre valía 1.0. Corregido de raíz en
    `indicadores.refrescar_tasa_cancelacion` con un JOIN contra el universo
    real de viajes solicitados por periodo/zona -- ver el docstring de esa
    función. Como `solicitados` ahora se repite igual en cada fila de
    desglose que comparte periodo+zona, sumarlo tal cual entre filas de
    motivo/actor distintos seguiría multiplicando el denominador -- por eso
    abajo se deduplica por zona antes de sumar, no se suma la fila cruda.)
    """
    client = get_clickhouse_client()
    try:
        asignacion = fetch_latest_snapshot(client, "rpt_tiempo_asignacion")
        cancelacion = fetch_latest_snapshot(client, "rpt_tasa_cancelacion")
        flota = fetch_latest_snapshot(client, "rpt_flota_activa_franja")
        asignacion_hist = fetch_snapshot_history(client, "rpt_tiempo_asignacion", limite_dias=cortes)
        flota_hist = fetch_snapshot_history(client, "rpt_flota_activa_franja", limite_dias=cortes)
    finally:
        client.close()

    # --- KPIs del último corte -------------------------------------------
    segundos_promedio = promedio_ponderado(asignacion, "segundos_promedio", "total_registros")
    pct_flota_activa = promedio_ponderado(flota, "pct_disponible", "total_registros")

    por_periodo_cancelacion = agrupar(cancelacion, "periodo")
    periodos = ultimos_periodos(por_periodo_cancelacion.keys(), meses)

    def _solicitados_del_periodo(filas: list[dict]) -> int:
        # `solicitados` viaja repetido en cada fila de desglose que comparte
        # periodo+zona (ver refrescar_tasa_cancelacion) -- deduplicar por
        # zona antes de sumar, o el denominador se multiplica por la
        # cantidad de motivos/actores distintos de esa zona.
        por_zona = {f["zona_origen_id"]: f["solicitados"] for f in filas}
        return sum(por_zona.values())

    tendencia_cancelacion = [
        {
            "periodo": periodo,
            "cancelados": sum(f["cancelados"] for f in por_periodo_cancelacion[periodo]),
            "sin_conductor": sum(
                f["cancelados"] for f in por_periodo_cancelacion[periodo] if f["motivo"] == "SIN_CONDUCTOR"
            ),
            "solicitados": _solicitados_del_periodo(por_periodo_cancelacion[periodo]),
        }
        for periodo in periodos
    ]

    cancelados_actual = tendencia_cancelacion[-1]["cancelados"] if tendencia_cancelacion else None
    cancelados_previo = tendencia_cancelacion[-2]["cancelados"] if len(tendencia_cancelacion) > 1 else None
    solicitados_actual = tendencia_cancelacion[-1]["solicitados"] if tendencia_cancelacion else None
    tasa_cancelacion_actual = (
        cancelados_actual / solicitados_actual if cancelados_actual is not None and solicitados_actual else None
    )

    # --- Tendencia por corte (tablas sin dimensión de periodo propia) ------
    tendencia_asignacion = [
        {
            "periodo": str(fecha),
            "segundos_promedio": promedio_ponderado(filas, "segundos_promedio", "total_registros") or 0.0,
            "total_registros": sum(f["total_registros"] for f in filas),
        }
        for fecha, filas in sorted(agrupar(asignacion_hist, "fecha_datos").items())
    ]
    tendencia_flota = [
        {
            "periodo": str(fecha),
            "pct_disponible": promedio_ponderado(filas, "pct_disponible", "total_registros") or 0.0,
            "total_registros": sum(f["total_registros"] for f in filas),
        }
        for fecha, filas in sorted(agrupar(flota_hist, "fecha_datos").items())
    ]

    # --- Listas: franjas con menor disponibilidad / peor tiempo de asignación
    # (dos taxonomías distintas, ver limitación 2 del docstring -- NO se cruzan)
    franjas = sorted(
        (
            {
                "franja": franja,
                "pct_disponible": promedio_ponderado(filas, "pct_disponible", "total_registros") or 0.0,
                "total_registros": sum(f["total_registros"] for f in filas),
            }
            for franja, filas in agrupar(flota, "franja").items()
        ),
        key=lambda f: f["pct_disponible"],
    )
    franjas_asignacion = sorted(
        (
            {
                "franja": franja,
                "segundos_promedio": promedio_ponderado(filas, "segundos_promedio", "total_registros") or 0.0,
                "total_registros": sum(f["total_registros"] for f in filas),
            }
            for franja, filas in agrupar(asignacion, "franja").items()
        ),
        key=lambda f: f["segundos_promedio"],
        reverse=True,
    )

    # La dimensión zona sigue sin dato real (`viajes.zona_origen_id` nunca se
    # resuelve, ver docstring de este módulo): las filas Gold la traen como
    # cadena vacía / literal "SIN_ZONA". Se declara explícitamente en vez de
    # ofrecer un filtro que no filtraría nada -- mismo criterio que el Panel
    # de Flota táctico ya usa para su propio gap de zona.
    zonas = {str(f.get("zona_origen_id") or "").strip() for f in asignacion}
    zona_disponible = bool(zonas - {"", "SIN_ZONA", "None"})

    return {
        "kpis": {
            "segundos_asignacion_promedio": segundos_promedio,
            "cancelaciones_periodo": cancelados_actual,
            "variacion_cancelaciones_pct": variacion_pct(cancelados_actual, cancelados_previo),
            "tasa_cancelacion": tasa_cancelacion_actual,
            "pct_flota_activa": pct_flota_activa,
            "franja_menor_cobertura": franjas[0]["franja"] if franjas else None,
        },
        "tendencia_asignacion": tendencia_asignacion,
        "tendencia_cancelacion": tendencia_cancelacion,
        "tendencia_flota": tendencia_flota,
        "franjas": franjas,
        "franjas_asignacion": franjas_asignacion,
        "metadata": {
            "meses": meses,
            "zona_disponible": zona_disponible,
            "tasa_cancelacion_disponible": True,
            "fuentes": ["rpt_tiempo_asignacion", "rpt_tasa_cancelacion", "rpt_flota_activa_franja"],
            # Tier 1, punto 6 (H-T5): `cancelados` ya es un conteo, no un
            # promedio ponderado -- el propio `cancelados_previo` es el n real
            # que respalda `variacion_cancelaciones_pct`.
            "registros_previos": {"variacion_cancelaciones_pct": cancelados_previo},
        },
    }
