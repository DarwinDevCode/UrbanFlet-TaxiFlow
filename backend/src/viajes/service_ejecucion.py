"""CU-O07 — Ejecutar el viaje: ASIGNADO -> EN_CAMINO -> (llegada) -> EN_CURSO,
con traza GPS, km recorridos y minutos de espera acumulados sobre la marcha.

Cortes de alcance explícitos en este slice (dependen de infraestructura o de
flujos alternos que ameritan su propio slice — no son huecos de la spec):
- A1 (pasajero ausente tras 5 min, CANCELADO/NO_SHOW_PASAJERO) y A2
  (cancelación con conductor en camino, con distancia ya recorrida como
  insumo de una futura política de compensación — decisión ya confirmada de
  no calcular esa compensación): se difieren a un slice posterior de cierre
  de viaje; A3 (cancelación del conductor) sí se implementa aquí porque sin
  ella no hay forma de liberar un viaje ASIGNADO/EN_CAMINO en las pruebas.
- A4 (incidencia en ruta -> notificar a "Coordinador de Operaciones"): ese
  rol no está cableado con un canal de notificación propio todavía.
- A5 (buffer offline de traza en IndexedDB): ya diferido desde el shell de
  turno de Fase 2 (flota/App.tsx); sigue diferido aquí.
- A6 (recálculo de ruta si el desvío supera 2 km): requiere un motor de
  ruteo que no existe en el stack (mismo corte que la distancia en línea
  recta usada en CU-O04/O05).
- Chat/llamada (flujo principal paso 2): sin CU propio ni entidad de datos
  definida en diseno_base_datos.md — no hay MENSAJE/CHAT ahí.
"""

from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_mongo import get_mongo_client
from src.core.db_redis import get_redis
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.core.geo import distancia_km
from src.core.tiempo import como_utc

DISTANCIA_MAX_INICIO_M = 150.0
VELOCIDAD_ESPERA_UMBRAL_KMH = 10.0
# Traza acotada (diseno_base_datos.md §2.1: "< ~17 000 puntos" para un viaje
# de 24h a 5s/punto) — se aplica un tope defensivo al insertar.
TRAZA_MAX_PUNTOS = 20000


class TransicionInvalidaError(DomainError):
    def __init__(self, esperado: str) -> None:
        super().__init__(
            code="TRANSICION_INVALIDA", message=f"El viaje debe estar en estado {esperado}", status_code=409
        )


class FueraDeRangoOrigenError(DomainError):
    def __init__(self, distancia_m: float) -> None:
        super().__init__(
            code="FUERA_DE_RANGO_ORIGEN",
            message=f"El vehículo está a {distancia_m:.0f} m del origen (máx. {DISTANCIA_MAX_INICIO_M:.0f} m)",
            status_code=409,
        )


async def marcar_en_camino(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict:
    viaje = await db.viajes.find_one({"conductor_id": conductor_id, "estado": "ASIGNADO"})
    if viaje is None:
        raise TransicionInvalidaError("ASIGNADO")

    await write_audit_event(
        db,
        actor_id=conductor_id,
        rol="conductor",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id=viaje["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "ASIGNADO"},
        datos_posteriores={"estado": "EN_CAMINO"},
    )
    await db.viajes.update_one({"_id": viaje["_id"]}, {"$set": {"estado": "EN_CAMINO"}})
    viaje["estado"] = "EN_CAMINO"
    return viaje


async def marcar_llegada(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict:
    viaje = await db.viajes.find_one({"conductor_id": conductor_id, "estado": "EN_CAMINO"})
    if viaje is None:
        raise TransicionInvalidaError("EN_CAMINO")

    ahora = datetime.now(UTC)
    # No cambia `estado` (no es una transición de la máquina de estados),
    # pero sí persiste un hecho de negocio -> mismo contrato de write-ahead.
    await write_audit_event(
        db,
        actor_id=conductor_id,
        rol="conductor",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id=viaje["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"evento": "LLEGADA_ORIGEN"},
    )
    await db.viajes.update_one({"_id": viaje["_id"]}, {"$set": {"ts_llegada_origen": ahora}})
    viaje["ts_llegada_origen"] = ahora
    return viaje


async def iniciar_viaje(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict:
    viaje = await db.viajes.find_one({"conductor_id": conductor_id, "estado": "EN_CAMINO"})
    if viaje is None:
        raise TransicionInvalidaError("EN_CAMINO")

    redis = get_redis()
    cache = await redis.hgetall(f"pos:{viaje['vehiculo_id']}")
    if not cache.get("lat"):
        raise FueraDeRangoOrigenError(float("inf"))

    distancia_m = (
        distancia_km(viaje["origen_lat"], viaje["origen_lon"], float(cache["lat"]), float(cache["lon"])) * 1000
    )
    if distancia_m > DISTANCIA_MAX_INICIO_M:
        raise FueraDeRangoOrigenError(distancia_m)

    ahora = datetime.now(UTC)
    await write_audit_event(
        db,
        actor_id=conductor_id,
        rol="conductor",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id=viaje["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "EN_CAMINO"},
        datos_posteriores={"estado": "EN_CURSO"},
    )
    await db.viajes.update_one(
        {"_id": viaje["_id"]},
        {"$set": {"estado": "EN_CURSO", "ts_inicio": ahora, "km_recorridos": 0.0, "min_espera": 0.0}},
    )
    viaje["estado"] = "EN_CURSO"
    viaje["ts_inicio"] = ahora
    viaje["km_recorridos"] = 0.0
    viaje["min_espera"] = 0.0
    return viaje


async def cancelar_por_conductor(db: AsyncIOMotorDatabase, *, conductor_id: str, motivo: str) -> dict:
    """A3: permitido solo antes de EN_CURSO. El viaje vuelve a SOLICITADO y
    se redespacha (CU-O05) sin que el pasajero repita la solicitud."""
    viaje = await db.viajes.find_one({"conductor_id": conductor_id, "estado": {"$in": ["ASIGNADO", "EN_CAMINO"]}})
    if viaje is None:
        raise TransicionInvalidaError("ASIGNADO o EN_CAMINO")

    descartados = list({*viaje.get("conductores_descartados", []), conductor_id})

    async def _en_transaccion(session):
        await write_audit_event(
            db,
            actor_id=conductor_id,
            rol="conductor",
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=viaje["_id"],
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": viaje["estado"]},
            datos_posteriores={"estado": "SOLICITADO", "motivo_cancelacion_conductor": motivo},
            session=session,
        )
        await db.viajes.update_one(
            {"_id": viaje["_id"]},
            {
                "$set": {
                    "estado": "SOLICITADO",
                    "conductor_id": None,
                    "vehiculo_id": None,
                    "conductor_ofertado_id": None,
                    "conductor_nombre": None,
                    "conductor_calificacion": None,
                    "vehiculo_placa": None,
                    "vehiculo_marca": None,
                    "vehiculo_color": None,
                    "ts_asignacion": None,
                    "conductores_descartados": descartados,
                }
            },
            session=session,
        )
        await db.usuarios.update_one(
            {"_id": conductor_id}, {"$set": {"conductor.estado_servicio": "DISPONIBLE"}}, session=session
        )
        return session

    await with_transaction(get_mongo_client(), _en_transaccion)

    viaje["estado"] = "SOLICITADO"
    viaje["conductor_id"] = None
    viaje["conductor_ofertado_id"] = None
    viaje["conductores_descartados"] = descartados

    # Import diferido: service_dispatch importa desde este mismo paquete
    # (viajes/) y no hay necesidad de acoplar el módulo entero a nivel de
    # import de archivo — solo esta función necesita redespachar.
    from src.viajes import service_dispatch

    return await service_dispatch.avanzar_despacho(db, viaje)


async def registrar_punto_traza(
    db: AsyncIOMotorDatabase,
    *,
    conductor_id: str,
    lat: float,
    lon: float,
    velocidad: float | None,
    ts_servidor: datetime,
) -> None:
    """Se llama desde flota.service.reportar_posicion (CU-O19) en cada
    reporte de posición — no directamente desde un endpoint propio. Si el
    conductor no tiene un viaje EN_CURSO, no hace nada (la mayoría de los
    reportes de posición ocurren fuera de un viaje)."""
    viaje = await db.viajes.find_one({"conductor_id": conductor_id, "estado": "EN_CURSO"})
    if viaje is None:
        return

    traza = viaje.get("traza") or []
    km_recorridos = viaje.get("km_recorridos") or 0.0
    min_espera = viaje.get("min_espera") or 0.0

    if traza:
        anterior = traza[-1]
        km_recorridos += distancia_km(anterior["lat"], anterior["lon"], lat, lon)
        segundos_transcurridos = (ts_servidor - como_utc(anterior["ts"])).total_seconds()
        if velocidad is not None and velocidad < VELOCIDAD_ESPERA_UMBRAL_KMH and segundos_transcurridos > 0:
            min_espera += segundos_transcurridos / 60

    punto = {"lat": lat, "lon": lon, "ts": ts_servidor, "velocidad": velocidad}
    await db.viajes.update_one(
        {"_id": viaje["_id"]},
        {
            "$push": {"traza": {"$each": [punto], "$slice": -TRAZA_MAX_PUNTOS}},
            "$set": {"km_recorridos": round(km_recorridos, 3), "min_espera": round(min_espera, 2)},
        },
    )
