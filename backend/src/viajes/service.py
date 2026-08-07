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
from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client
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


async def cancelar_viaje_pasajero(db: AsyncIOMotorDatabase, *, pasajero_id: str) -> dict:
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
        datos_posteriores={"estado": "CANCELADO", "motivo_cancelacion": "Cancelado por el pasajero"},
    )
    await db.viajes.update_one(
        {"_id": viaje_id},
        {
            "$set": {
                "estado": "CANCELADO",
                "motivo_cancelacion": "Cancelado por el pasajero",
                "actor_cancelacion": "pasajero",
            }
        },
    )
    viaje["estado"] = "CANCELADO"
    viaje["motivo_cancelacion"] = "Cancelado por el pasajero"
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
    return sorted(filas, key=lambda f: (f["periodo"], f["zona_origen_id"]))
