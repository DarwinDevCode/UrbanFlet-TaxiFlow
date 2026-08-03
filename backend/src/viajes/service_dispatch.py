"""Despacho — CU-O05 (auto-asignación) y CU-O06 (ofrecer viaje al conductor).

Cortes de alcance explícitos en este slice (dependen de piezas que no existen
todavía en el stack, no son huecos de la spec):
- "Distancia en ruta" (CU-O05 paso 2, 1er criterio de orden) y "ruta óptima
  conductor → origen" (CU-O05 paso 4): no hay motor de ruteo en el stack
  (ni OSRM, ni Google Directions, nada declarado en arquitectura_software.md).
  Se usa distancia en línea recta (haversine, core/geo.py) como proxy — el
  mismo proxy que ya usa el cálculo de tarifa estimada (CU-O04).
- "Tiempo desde su último viaje finalizado" (2º criterio de orden) y
  "calificación promedio" (3er criterio): ambos campos existen en el modelo
  (viajes.estado=FINALIZADO, conductor.calificacion_promedio) pero todavía no
  hay datos poblándolos porque CU-O08 (finalizar viaje, con calificaciones)
  es un slice posterior de esta misma fase. El criterio se aplica igual —
  simplemente no discrimina todavía entre candidatos porque no hay historial.
- A5 (conductor asignado se desconecta antes de llegar → reabrir asignación a
  los 180s): requiere un scheduler en segundo plano, que no existe en el stack
  todavía (mismo corte que "push proactivo SIN_SEÑAL" en flota/service.py).
  En su lugar, el avance de despacho (ofertas expiradas, próximo candidato)
  se calcula bajo demanda: cada poll de `GET /viajes/activo` (pasajero) o
  `GET /viajes/oferta-actual` (conductor) invoca `avanzar_despacho`, que
  resuelve cualquier oferta vencida antes de responder.
"""

import uuid
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_mongo import get_mongo_client
from src.core.db_redis import get_redis
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.core.geo import distancia_km
from src.core.tiempo import como_utc

RADIOS_M = (300, 600, 1000)
OFERTA_EXPIRA_SEGUNDOS = 20
MAX_OFERTAS_TOTALES = 10
POSICION_MAX_ANTIGUEDAD_SEGUNDOS = 60


class SinOfertaActivaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="SIN_OFERTA_ACTIVA", message="No tienes una oferta de viaje pendiente", status_code=404)


class OfertaNoDisponibleError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="OFFER_NO_LONGER_AVAILABLE", message="La oferta ya no está disponible", status_code=409
        )


async def _candidato_valido(
    db: AsyncIOMotorDatabase, usuario: dict, *, origen_lat: float, origen_lon: float, radio_m: int
) -> dict | None:
    conductor = usuario.get("conductor") or {}
    if conductor.get("cumplimiento_ok", True) is False:
        return None

    vehiculo = await db.vehiculos.find_one({"propietario_id": usuario["_id"]})
    if vehiculo is None:
        return None
    if vehiculo.get("estado_habilitacion") != "HABILITADO":
        return None
    if vehiculo.get("cumplimiento_ok", True) is False:
        return None

    redis = get_redis()
    cache = await redis.hgetall(f"pos:{vehiculo['_id']}")
    if not cache.get("ts_servidor"):
        return None
    ts_servidor = datetime.fromisoformat(cache["ts_servidor"])
    if (datetime.now(UTC) - ts_servidor).total_seconds() > POSICION_MAX_ANTIGUEDAD_SEGUNDOS:
        return None

    distancia_km_valor = distancia_km(origen_lat, origen_lon, float(cache["lat"]), float(cache["lon"]))
    if distancia_km_valor * 1000 > radio_m:
        return None

    ultimo_viaje = await db.viajes.find_one(
        {"conductor_id": usuario["_id"], "estado": "FINALIZADO"}, sort=[("ts_fin", -1)]
    )
    ts_ultimo_viaje = como_utc(ultimo_viaje["ts_fin"]) if ultimo_viaje else datetime.min.replace(tzinfo=UTC)

    return {
        "usuario": usuario,
        "vehiculo": vehiculo,
        "distancia_km": distancia_km_valor,
        "ts_ultimo_viaje": ts_ultimo_viaje,
        "calificacion_promedio": conductor.get("calificacion_promedio") or 0.0,
    }


async def _buscar_candidatos(
    db: AsyncIOMotorDatabase, *, origen_lat: float, origen_lon: float, radio_m: int, excluir: list[str]
) -> list[dict]:
    candidatos: list[dict] = []
    async for usuario in db.usuarios.find(
        {"roles": "conductor", "conductor.estado_servicio": "DISPONIBLE", "_id": {"$nin": excluir}}
    ):
        candidato = await _candidato_valido(db, usuario, origen_lat=origen_lat, origen_lon=origen_lon, radio_m=radio_m)
        if candidato is not None:
            candidatos.append(candidato)

    # Orden CU-O05 paso 2: (1) distancia asc, (2) tiempo desde último viaje
    # finalizado desc — más tiempo ocioso primero, reparte trabajo — (3)
    # calificación promedio desc.
    candidatos.sort(key=lambda c: (c["distancia_km"], -c["ts_ultimo_viaje"].timestamp(), -c["calificacion_promedio"]))
    return candidatos


async def _marcar_sin_conductor(db: AsyncIOMotorDatabase, viaje: dict) -> dict:
    async def _en_transaccion(session):
        await write_audit_event(
            db,
            actor_id=None,
            rol=None,
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=viaje["_id"],
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": viaje["estado"]},
            datos_posteriores={"estado": "SIN_CONDUCTOR"},
            session=session,
        )
        await db.viajes.update_one(
            {"_id": viaje["_id"]}, {"$set": {"estado": "SIN_CONDUCTOR"}}, session=session
        )
        return session

    await with_transaction(get_mongo_client(), _en_transaccion)
    viaje["estado"] = "SIN_CONDUCTOR"
    return viaje


async def _emitir_oferta(db: AsyncIOMotorDatabase, viaje: dict, candidato: dict, *, radio_m: int) -> dict:
    conductor_id = candidato["usuario"]["_id"]
    ahora = datetime.now(UTC)
    oferta_id = str(uuid.uuid4())

    async def _en_transaccion(session):
        await write_audit_event(
            db,
            actor_id=None,
            rol=None,
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=viaje["_id"],
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": viaje["estado"]},
            datos_posteriores={"estado": "OFERTADO", "conductor_ofertado_id": conductor_id},
            session=session,
        )
        await db.ofertas.insert_one(
            {
                "_id": oferta_id,
                "viaje_id": viaje["_id"],
                "conductor_id": conductor_id,
                "ts_emision": ahora,
                "ts_respuesta": None,
                "resultado": None,
                "radio_m": radio_m,
            },
            session=session,
        )
        await db.viajes.update_one(
            {"_id": viaje["_id"]},
            {
                "$set": {
                    "estado": "OFERTADO",
                    "conductor_ofertado_id": conductor_id,
                    "ts_oferta_emitida": ahora,
                    "radio_actual_m": radio_m,
                },
                "$inc": {"ofertas_totales": 1},
                "$addToSet": {"conductores_descartados": conductor_id},
            },
            session=session,
        )
        return session

    await with_transaction(get_mongo_client(), _en_transaccion)

    viaje["estado"] = "OFERTADO"
    viaje["conductor_ofertado_id"] = conductor_id
    viaje["ts_oferta_emitida"] = ahora
    viaje["radio_actual_m"] = radio_m
    viaje["ofertas_totales"] = viaje.get("ofertas_totales", 0) + 1
    return viaje


async def _intentar_emitir_siguiente(db: AsyncIOMotorDatabase, viaje: dict) -> dict:
    descartados = viaje.get("conductores_descartados", [])
    radio_idx = viaje.get("radio_idx", 0)

    while radio_idx < len(RADIOS_M):
        if viaje.get("ofertas_totales", 0) >= MAX_OFERTAS_TOTALES:
            return await _marcar_sin_conductor(db, viaje)

        radio_m = RADIOS_M[radio_idx]
        candidatos = await _buscar_candidatos(
            db, origen_lat=viaje["origen_lat"], origen_lon=viaje["origen_lon"], radio_m=radio_m, excluir=descartados
        )
        if candidatos:
            return await _emitir_oferta(db, viaje, candidatos[0], radio_m=radio_m)

        radio_idx += 1
        await db.viajes.update_one({"_id": viaje["_id"]}, {"$set": {"radio_idx": radio_idx}})
        viaje["radio_idx"] = radio_idx

    return await _marcar_sin_conductor(db, viaje)


async def avanzar_despacho(db: AsyncIOMotorDatabase, viaje: dict) -> dict:
    """Punto de entrada único del motor de despacho (CU-O05). Se llama tras
    crear un viaje SOLICITADO y, de ahí en más, bajo demanda desde cualquier
    poll de pasajero o conductor — ver corte de alcance A5 arriba."""
    if viaje["estado"] == "SOLICITADO":
        return await _intentar_emitir_siguiente(db, viaje)

    if viaje["estado"] == "OFERTADO":
        expira = como_utc(viaje["ts_oferta_emitida"]) + timedelta(seconds=OFERTA_EXPIRA_SEGUNDOS)
        if datetime.now(UTC) < expira:
            return viaje

        # A1: expiración — cuenta como rechazo pasivo, se registra en `ofertas`.
        await db.ofertas.update_one(
            {"viaje_id": viaje["_id"], "conductor_id": viaje["conductor_ofertado_id"], "resultado": None},
            {"$set": {"resultado": "EXPIRADA", "ts_respuesta": datetime.now(UTC)}},
        )
        viaje["estado"] = "SOLICITADO"
        viaje["conductor_ofertado_id"] = None
        return await _intentar_emitir_siguiente(db, viaje)

    return viaje


async def obtener_oferta_actual(db: AsyncIOMotorDatabase, *, conductor_id: str) -> tuple[dict, dict] | None:
    viaje = await db.viajes.find_one({"conductor_ofertado_id": conductor_id, "estado": "OFERTADO"})
    if viaje is None:
        return None
    viaje = await avanzar_despacho(db, viaje)
    if viaje["estado"] != "OFERTADO" or viaje.get("conductor_ofertado_id") != conductor_id:
        return None
    oferta = await db.ofertas.find_one(
        {"viaje_id": viaje["_id"], "conductor_id": conductor_id, "resultado": None}
    )
    return viaje, oferta


def _nombre_de_pila(nombre: str) -> str:
    return nombre.strip().split(" ")[0]


async def construir_oferta_out(db: AsyncIOMotorDatabase, viaje: dict, conductor_id: str) -> dict:
    pasajero = await db.usuarios.find_one({"_id": viaje["pasajero_id"]})
    vehiculo = await db.vehiculos.find_one({"propietario_id": conductor_id})

    distancia = None
    if vehiculo is not None:
        redis = get_redis()
        cache = await redis.hgetall(f"pos:{vehiculo['_id']}")
        if cache.get("lat"):
            distancia = distancia_km(viaje["origen_lat"], viaje["origen_lon"], float(cache["lat"]), float(cache["lon"]))

    expira = como_utc(viaje["ts_oferta_emitida"]) + timedelta(seconds=OFERTA_EXPIRA_SEGUNDOS)
    segundos_restantes = max(0, int((expira - datetime.now(UTC)).total_seconds()))

    return {
        "viaje_id": viaje["_id"],
        "pasajero_nombre": _nombre_de_pila(pasajero["nombre"]) if pasajero else "Pasajero",
        "pasajero_calificacion": (pasajero.get("pasajero") or {}).get("calificacion_promedio") if pasajero else None,
        "origen_lat": viaje["origen_lat"],
        "origen_lon": viaje["origen_lon"],
        "distancia_km": round(distancia, 2) if distancia is not None else None,
        "tiene_destino": viaje.get("destino_lat") is not None,
        "segundos_restantes": segundos_restantes,
    }


class _OfertaYaNoDisponible(Exception):
    """Señal interna para abortar la transacción cuando la CAS (A4) no
    encuentra coincidencia — nunca escapa de `responder_oferta`."""


async def responder_oferta(db: AsyncIOMotorDatabase, *, conductor_id: str, aceptar: bool) -> dict:
    resultado = await obtener_oferta_actual(db, conductor_id=conductor_id)
    if resultado is None:
        raise SinOfertaActivaError()
    viaje, _oferta = resultado

    ahora = datetime.now(UTC)

    if aceptar:
        usuario = await db.usuarios.find_one({"_id": conductor_id})
        vehiculo = await db.vehiculos.find_one({"propietario_id": conductor_id})

        async def _en_transaccion(session):
            # Write-ahead (CU-O17) primero, como en cualquier otra transición
            # de viaje. La CAS de abajo (A4: protección contra doble
            # asignación) puede no encontrar coincidencia si el conductor ya
            # no está ofertado — en ese caso se aborta la transacción entera
            # (con Mongo real esto también descarta este mismo evento de
            # auditoría, para que la bitácora nunca declare un efecto que no
            # ocurrió; ver la nota equivalente sobre el fallback sin sesión en
            # tests/captacion/test_write_ahead.py).
            await write_audit_event(
                db,
                actor_id=conductor_id,
                rol="conductor",
                accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
                entidad="viajes",
                entidad_id=viaje["_id"],
                resultado=ResultadoAuditoria.OK,
                datos_posteriores={"estado": "ASIGNADO"},
                session=session,
            )

            # A4: aceptación condicional sobre estado + conductor_ofertado_id
            # — protege contra doble asignación si dos respuestas llegan casi
            # simultáneas (el conductor y una expiración concurrente, p. ej.).
            actualizado = await db.viajes.find_one_and_update(
                {"_id": viaje["_id"], "estado": "OFERTADO", "conductor_ofertado_id": conductor_id},
                {
                    "$set": {
                        "estado": "ASIGNADO",
                        "conductor_id": conductor_id,
                        "vehiculo_id": vehiculo["_id"],
                        "ts_asignacion": ahora,
                        "conductor_nombre": usuario["nombre"],
                        "conductor_calificacion": (usuario.get("conductor") or {}).get("calificacion_promedio"),
                        "vehiculo_placa": vehiculo["placa"],
                        "vehiculo_marca": vehiculo["marca"],
                        "vehiculo_color": vehiculo["color"],
                    }
                },
                session=session,
                return_document=ReturnDocument.AFTER,
            )
            if actualizado is None:
                raise _OfertaYaNoDisponible()

            await db.ofertas.update_one(
                {"viaje_id": viaje["_id"], "conductor_id": conductor_id, "resultado": None},
                {"$set": {"resultado": "ACEPTADA", "ts_respuesta": ahora}},
                session=session,
            )
            await db.usuarios.update_one(
                {"_id": conductor_id}, {"$set": {"conductor.estado_servicio": "OCUPADO"}}, session=session
            )
            return actualizado

        try:
            return await with_transaction(get_mongo_client(), _en_transaccion)
        except _OfertaYaNoDisponible:
            raise OfertaNoDisponibleError() from None

    # Rechazo explícito: también es una transición de viaje (OFERTADO →
    # SOLICITADO) — misma regla de write-ahead antes del efecto.
    async def _en_transaccion_rechazo(session):
        await write_audit_event(
            db,
            actor_id=conductor_id,
            rol="conductor",
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=viaje["_id"],
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"estado": "SOLICITADO"},
            session=session,
        )
        actualizado = await db.viajes.find_one_and_update(
            {"_id": viaje["_id"], "estado": "OFERTADO", "conductor_ofertado_id": conductor_id},
            {"$set": {"estado": "SOLICITADO", "conductor_ofertado_id": None}},
            session=session,
            return_document=ReturnDocument.AFTER,
        )
        if actualizado is None:
            raise _OfertaYaNoDisponible()

        await db.ofertas.update_one(
            {"viaje_id": viaje["_id"], "conductor_id": conductor_id, "resultado": None},
            {"$set": {"resultado": "RECHAZADA", "ts_respuesta": ahora}},
            session=session,
        )
        return actualizado

    try:
        actualizado = await with_transaction(get_mongo_client(), _en_transaccion_rechazo)
    except _OfertaYaNoDisponible:
        raise OfertaNoDisponibleError() from None
    return await avanzar_despacho(db, actualizado)
