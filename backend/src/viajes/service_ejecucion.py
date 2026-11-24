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
- A6 (recálculo de ruta si el desvío supera 2 km): el recálculo en sí ocurre
  del lado del cliente (web-pasajero desde CU-O04 P3, web-conductor desde el
  bloque de "navegación óptima" — ver UMBRAL_DESVIO_RUTA_KM en
  apps/shared-ui/src/api/rutas.ts). Lo que SÍ vive acá es el registro en
  bitácora que la spec exige ("...el sistema recalcula la ruta y lo
  registra... el dato queda para auditoría") — ver
  `registrar_recalculo_ruta_por_desvio` más abajo y
  `POST /viajes/conductor/recalculo-ruta` en router_ejecucion.py. Antes de
  esta función no había ningún rastro server-side del recálculo — el
  cliente llamaba GET /viajes/estimacion-ruta (el mismo endpoint genérico
  que usa cualquier cálculo de ruta, incluida la primera estimación de
  tarifa) sin que el backend tuviera forma de distinguir "esto fue un
  desvío real" de "esto es solo la ruta inicial".
- Chat/llamada (flujo principal paso 2): sin CU propio ni entidad de datos
  definida en diseno_base_datos.md — no hay MENSAJE/CHAT ahí.
"""

import re
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


# Bitácora de revisión (2026-08-26, hallazgo #7): `esperado` venía como
# enum(s) crudo(s) (ej. "ASIGNADO, EN_CAMINO o EN_CURSO") incrustado en un
# mensaje que de resto está en español -- el frontend ya traduce el estado
# que SÍ tiene el viaje (`ETIQUETA_ESTADO_VIAJE`), pero no traducía el que
# el backend dice que DEBERÍA tener. Reemplazo por token, no por frase
# completa, porque `esperado` puede traer 1, 2 o 3 estados unidos por
# ", "/" o " -- cualquier token que no esté en el diccionario se deja tal
# cual (nunca rompe el mensaje, solo no lo mejora).
_ETIQUETA_ESTADO = {
    "PROGRAMADO": "Programado",
    "SOLICITADO": "Solicitado",
    "OFERTADO": "Ofertado",
    "ASIGNADO": "Asignado",
    "EN_CAMINO": "En camino",
    "EN_CURSO": "En curso",
    "FINALIZADO": "Finalizado",
    "PAGADO": "Pagado",
    "CANCELADO": "Cancelado",
    "SIN_CONDUCTOR": "Sin conductor",
}


def _traducir_estados(texto: str) -> str:
    return re.sub(r"[A-Z][A-Z_]*", lambda m: _ETIQUETA_ESTADO.get(m.group(0), m.group(0)), texto)


class TransicionInvalidaError(DomainError):
    def __init__(self, esperado: str) -> None:
        super().__init__(
            code="TRANSICION_INVALIDA",
            message=f"El viaje debe estar en estado {_traducir_estados(esperado)}",
            status_code=409,
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
                },
                # Sección 1.2: el viaje vuelve al pool de despacho y puede
                # terminar EN_CAMINO de nuevo con OTRO conductor -- un token
                # ya compartido no debe seguir mostrando esa posición nueva
                # sin que el pasajero lo vuelva a pedir explícitamente.
                "$unset": {"token_compartir": "", "token_compartir_expira_en": ""},
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


async def cancelar_por_incidencia(db: AsyncIOMotorDatabase, *, conductor_id: str, viaje_id: str) -> dict:
    """Ronda 2 del flujo de fallas (Fase C), CU-O07 A4: reporte de falla con
    `impide_continuar=true` mientras el viaje está EN_CURSO.

    A diferencia de A3 (`cancelar_por_conductor` arriba, que solo permite
    ASIGNADO/EN_CAMINO y hace volver el MISMO documento a SOLICITADO para
    redespacharlo), el texto de la propuesta describe una "nueva solicitud
    automática para el pasajero desde esa posición" -- no un redespacho del
    mismo viaje. Tiene sentido: un viaje EN_CURSO ya acumuló traza/
    km_recorridos/min_espera reales de un tramo que no se completó, mezclar
    eso con un viaje que arranca de cero (con otro conductor, quizás otro
    vehículo) sería un dato contaminado. Por eso esta función solo cancela
    -- la creación de la nueva solicitud vive en
    `reportes_falla/service.py`, que reutiliza
    `viajes.service.solicitar_viaje` tal cual, sin duplicar la lógica de
    despacho."""
    viaje = await db.viajes.find_one({"_id": viaje_id, "conductor_id": conductor_id, "estado": "EN_CURSO"})
    if viaje is None:
        raise TransicionInvalidaError("EN_CURSO")

    await write_audit_event(
        db,
        actor_id=conductor_id,
        rol="conductor",
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id=viaje["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "EN_CURSO"},
        datos_posteriores={"estado": "CANCELADO", "motivo_cancelacion": "INCIDENCIA"},
    )
    await db.viajes.update_one(
        {"_id": viaje["_id"]},
        {
            "$set": {"estado": "CANCELADO", "motivo_cancelacion": "INCIDENCIA", "actor_cancelacion": "conductor"},
            # Mismo criterio de higiene que cancelar_por_conductor: un token
            # de "compartir viaje" ya emitido no debe seguir vivo sobre un
            # viaje que quedó cancelado.
            "$unset": {"token_compartir": "", "token_compartir_expira_en": ""},
        },
    )
    await db.usuarios.update_one({"_id": conductor_id}, {"$set": {"conductor.estado_servicio": "DISPONIBLE"}})

    viaje["estado"] = "CANCELADO"
    viaje["motivo_cancelacion"] = "INCIDENCIA"
    viaje["actor_cancelacion"] = "conductor"
    return viaje


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


async def registrar_recalculo_ruta_por_desvio(
    db: AsyncIOMotorDatabase,
    *,
    conductor_id: str,
    lat: float,
    lon: float,
    distancia_desvio_km: float,
    ruta_anterior: list[tuple[float, float]],
    ruta_nueva: list[tuple[float, float]],
) -> None:
    """CU-O07 A6: "si la posición se aleja más de 2 km de la ruta prevista
    sin recálculo, el sistema recalcula la ruta y lo registra... el dato
    queda para auditoría". El recálculo ya ocurrió en el cliente (ver
    UMBRAL_DESVIO_RUTA_KM en apps/shared-ui/src/api/rutas.ts) contra el
    mismo GET /viajes/estimacion-ruta que usa cualquier cálculo de ruta —
    esta función es exclusivamente el registro en bitácora que faltaba, con
    el mismo mecanismo write-ahead que el resto de eventos de este archivo
    (VIAJE_TRANSICION_ESTADO arriba). No hay ningún efecto de negocio que
    mutar aparte del propio registro -- a diferencia de
    marcar_en_camino/llegue/iniciar, acá el evento de auditoría ES el
    efecto completo (mismo patrón que POSIBLE_GPS_SPOOFING en
    flota/service.py, que tampoco muta la entidad además de auditar).

    Se aplica a cualquier tramo activo del viaje (ASIGNADO/EN_CAMINO yendo
    hacia el origen, EN_CURSO yendo hacia el destino) -- A6 no distingue
    tramo, y restringirlo a uno solo dejaría el otro sin rastro.
    """
    viaje = await db.viajes.find_one(
        {"conductor_id": conductor_id, "estado": {"$in": ["ASIGNADO", "EN_CAMINO", "EN_CURSO"]}}
    )
    if viaje is None:
        raise TransicionInvalidaError("ASIGNADO, EN_CAMINO o EN_CURSO")

    await write_audit_event(
        db,
        actor_id=conductor_id,
        rol="conductor",
        accion=AccionAuditoria.VIAJE_RECALCULO_RUTA,
        entidad="viajes",
        entidad_id=viaje["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_previos={"ruta": ruta_anterior},
        datos_posteriores={
            "lat": lat,
            "lon": lon,
            "distancia_desvio_km": round(distancia_desvio_km, 3),
            "ruta": ruta_nueva,
        },
    )
