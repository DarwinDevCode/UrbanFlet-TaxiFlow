"""Flota — CU-O19 (reportar la posición y el estado del vehículo).

Alcance de esta fase: turno (iniciar/terminar) con las dos banderas
(cumplimiento + mantenimiento) exigidas por CU-O19 paso 1, reporte de
posición con caché en Redis (TTL 60s, línea 47 arquitectura), descarte de
saltos imposibles (A4, GPS spoofing) y contador de precisión baja (A3).

Deliberadamente fuera de esta fase — dependen de módulos que no existen
todavía, no son huecos de la spec:
- A2 (sin señal con viaje activo): depende de CU-O07/CU-O05 de Fase 3.
- Push proactivo de SIN_SEÑAL a los 60s: requiere un job en segundo plano
  (scheduler), no un efecto de este endpoint. Lo que sí se construye es el
  cálculo bajo demanda (`listar_estado_flota`), que un dashboard puede
  refrescar por polling — la fuente de verdad (último ts_servidor) ya queda
  correctamente registrada para cuando ese scheduler se construya.

Fase 3 (Slice 4) completa lo que aquí quedaba comentado como pendiente: el
bloqueo de "terminar turno" con viaje activo, y la acumulación de traza GPS
(CU-O07) se dispara desde `reportar_posicion` — no expone su propio
endpoint, es un efecto secundario del mismo reporte de posición que ya
existía. La escritura real de la traza vive en `viajes.service_ejecucion`
(dueño de la colección `viajes`); este módulo solo la invoca, igual que ya
hace con otras llamadas de servicio entre paquetes (línea 71 arquitectura:
"servicios internos", nunca acceso directo a colecciones ajenas para
escribir en ellas).
"""

from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client
from src.core.db_redis import get_redis
from src.core.exceptions import DomainError
from src.core.geo import distancia_km
from src.flota import schemas
from src.viajes import service_ejecucion

_SALTO_IMPOSIBLE_KM = 3.0
_PRECISION_BAJA_UMBRAL_M = 50.0
_PRECISION_BAJA_CONSECUTIVOS = 3
_POS_CACHE_TTL_SEGUNDOS = 60
_SIN_SENAL_SEGUNDOS = 60


class ConductorSinVehiculoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="CONDUCTOR_SIN_VEHICULO", message="El conductor no tiene un vehículo asociado", status_code=409
        )


class TurnoBloqueadoError(DomainError):
    def __init__(self, motivos: list[str]) -> None:
        self.motivos = motivos
        super().__init__(
            code="TURNO_BLOQUEADO", message="No se puede iniciar turno: " + "; ".join(motivos), status_code=409
        )


class TurnoNoIniciadoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="TURNO_NO_INICIADO", message="No se puede reportar posición sin un turno activo", status_code=409
        )


class TurnoConViajeActivoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="TURNO_CON_VIAJE_ACTIVO",
            message="No se puede terminar turno con un viaje en curso",
            status_code=409,
        )


class PosicionConductorNoAutorizadaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="POSICION_CONDUCTOR_NO_AUTORIZADA",
            message="No tienes autorización para consultar la posición de este conductor",
            status_code=403,
        )


class PosicionConductorNoDisponibleError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="POSICION_CONDUCTOR_NO_DISPONIBLE",
            message="Todavía no hay una posición reportada para este conductor",
            status_code=404,
        )


async def _vehiculo_del_conductor(db: AsyncIOMotorDatabase, conductor_id: str) -> dict | None:
    return await db.vehiculos.find_one({"propietario_id": conductor_id})


async def iniciar_turno(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict:
    usuario = await db.usuarios.find_one({"_id": conductor_id})
    vehiculo = await _vehiculo_del_conductor(db, conductor_id)
    if vehiculo is None:
        raise ConductorSinVehiculoError()

    motivos: list[str] = []
    if vehiculo.get("estado_habilitacion") != "HABILITADO":
        motivos.append("vehículo retirado de servicio (mantenimiento)")
    if vehiculo.get("cumplimiento_ok", True) is False:
        motivos.append(f"documentación del vehículo vencida: {vehiculo.get('cumplimiento_motivo')}")
    if (usuario.get("conductor") or {}).get("cumplimiento_ok", True) is False:
        motivos.append(f"documentación del conductor vencida: {usuario['conductor'].get('cumplimiento_motivo')}")

    if motivos:
        raise TurnoBloqueadoError(motivos)

    await db.usuarios.update_one({"_id": conductor_id}, {"$set": {"conductor.estado_servicio": "DISPONIBLE"}})
    return {"estado_servicio": "DISPONIBLE"}


async def terminar_turno(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict:
    # CU-O19: "No se permite terminar turno con un viaje activo." Lectura
    # directa de `viajes` (no una escritura) — mismo patrón ya tolerado para
    # `usuarios`/`vehiculos` entre módulos; solo las escrituras sobre la
    # colección de otro paquete pasan por su capa de servicio.
    viaje_activo = await db.viajes.find_one(
        {"conductor_id": conductor_id, "estado": {"$in": ["ASIGNADO", "EN_CAMINO", "EN_CURSO"]}}
    )
    if viaje_activo is not None:
        raise TurnoConViajeActivoError()

    await db.usuarios.update_one({"_id": conductor_id}, {"$set": {"conductor.estado_servicio": "FUERA_DE_LINEA"}})
    redis = get_redis()
    vehiculo = await _vehiculo_del_conductor(db, conductor_id)
    if vehiculo:
        await redis.delete(f"pos:{vehiculo['_id']}")
    return {"estado_servicio": "FUERA_DE_LINEA"}


async def reportar_posicion(
    db: AsyncIOMotorDatabase, *, conductor_id: str, body: schemas.PosicionReportarRequest
) -> schemas.PosicionReportarResponse:
    usuario = await db.usuarios.find_one({"_id": conductor_id})
    estado_servicio = (usuario.get("conductor") or {}).get("estado_servicio", "FUERA_DE_LINEA")
    if estado_servicio not in ("DISPONIBLE", "OCUPADO"):
        raise TurnoNoIniciadoError()

    vehiculo = await _vehiculo_del_conductor(db, conductor_id)
    if vehiculo is None:
        raise ConductorSinVehiculoError()
    vehiculo_id = vehiculo["_id"]

    redis = get_redis()
    ts_servidor = datetime.now(UTC)

    cache_key = f"pos:{vehiculo_id}"
    anterior_raw = await redis.hgetall(cache_key)

    # A4: salto imposible entre reportes consecutivos — se descarta el
    # reporte (se conserva la posición anterior) y se audita como posible
    # GPS spoofing; es uno de los eventos de seguridad explícitos del
    # catálogo mínimo de CU-O17.
    if anterior_raw:
        distancia = distancia_km(float(anterior_raw["lat"]), float(anterior_raw["lon"]), body.lat, body.lon)
        if distancia > _SALTO_IMPOSIBLE_KM:
            await write_audit_event(
                db,
                actor_id=conductor_id,
                rol="conductor",
                accion=AccionAuditoria.POSIBLE_GPS_SPOOFING,
                entidad="vehiculos",
                entidad_id=vehiculo_id,
                resultado=ResultadoAuditoria.DENEGADO,
                datos_previos={"lat": float(anterior_raw["lat"]), "lon": float(anterior_raw["lon"])},
                datos_posteriores={"lat": body.lat, "lon": body.lon, "distancia_km": round(distancia, 2)},
            )
            return schemas.PosicionReportarResponse(
                aceptada=False, motivo_descarte=f"salto de {distancia:.1f} km entre reportes consecutivos"
            )

    await db.posiciones.insert_one(
        {
            "vehiculo_id": vehiculo_id,
            "conductor_id": conductor_id,
            "lat": body.lat,
            "lon": body.lon,
            "precision_m": body.precision_m,
            "velocidad": body.velocidad,
            "rumbo": body.rumbo,
            "ts_dispositivo": body.ts_dispositivo,
            "ts_servidor": ts_servidor,
        }
    )

    precision_baja = body.precision_m > _PRECISION_BAJA_UMBRAL_M
    contador_key = f"precision_baja:{vehiculo_id}"
    if precision_baja:
        await redis.incr(contador_key)
        await redis.expire(contador_key, _POS_CACHE_TTL_SEGUNDOS * 5)
    else:
        await redis.delete(contador_key)

    await redis.hset(
        cache_key,
        mapping={
            "lat": body.lat,
            "lon": body.lon,
            "ts_servidor": ts_servidor.isoformat(),
            "estado_servicio": estado_servicio,
        },
    )
    await redis.expire(cache_key, _POS_CACHE_TTL_SEGUNDOS)

    # CU-O07 paso 4/5: si este conductor tiene un viaje EN_CURSO, este mismo
    # reporte de posición también alimenta su traza GPS (km recorridos,
    # minutos de espera) — no hace nada si no hay viaje EN_CURSO.
    await service_ejecucion.registrar_punto_traza(
        db, conductor_id=conductor_id, lat=body.lat, lon=body.lon, velocidad=body.velocidad, ts_servidor=ts_servidor
    )

    return schemas.PosicionReportarResponse(aceptada=True, precision_baja=precision_baja)


async def listar_vehiculos_cercanos(
    db: AsyncIOMotorDatabase, *, lat: float, lon: float, radio_m: float
) -> list[dict]:
    """CU-O04 P1: posiciones anonimizadas de vehículos DISPONIBLE dentro de
    un radio, para pintar íconos anónimos en el mapa del pasajero — nunca
    expone conductor_id/vehiculo_id/placa. Sin índice geoespacial (no
    justificado por el volumen actual, ver docstring del módulo): recorre los
    conductores DISPONIBLE y filtra por haversine, igual que
    `listar_estado_flota`."""
    redis = get_redis()
    radio_km = radio_m / 1000
    resultado: list[dict] = []
    async for usuario in db.usuarios.find({"roles": "conductor", "conductor.estado_servicio": "DISPONIBLE"}):
        vehiculo = await _vehiculo_del_conductor(db, usuario["_id"])
        if vehiculo is None:
            continue
        cache = await redis.hgetall(f"pos:{vehiculo['_id']}")
        if not cache.get("lat"):
            continue
        veh_lat, veh_lon = float(cache["lat"]), float(cache["lon"])
        if distancia_km(lat, lon, veh_lat, veh_lon) <= radio_km:
            resultado.append({"lat": veh_lat, "lon": veh_lon})
    return resultado


_ESTADOS_VIAJE_CON_CONDUCTOR_VISIBLE = ["ASIGNADO", "EN_CAMINO", "EN_CURSO"]


async def obtener_posicion_conductor(db: AsyncIOMotorDatabase, *, actor_id: str, conductor_id: str) -> dict:
    """Posición puntual de UN conductor conocido — a diferencia de
    `listar_vehiculos_cercanos` (anónimo, para el radio de búsqueda antes de
    asignar), esto identifica al conductor por su id y solo se entrega a
    quien tiene autorización explícita para verlo:

    - el propio conductor consultando su posición, o
    - el pasajero de un viaje que ese conductor tiene asignado ahora mismo
      (ASIGNADO/EN_CAMINO/EN_CURSO) — se verifica contra `viajes`, nunca se
      confía en un conductor_id que el cliente afirme sin más.

    Cualquier otro actor (otro pasajero, un conductor distinto) recibe
    PosicionConductorNoAutorizadaError, no un simple filtrado silencioso —
    consultar la posición de un conductor ajeno es justo el tipo de acceso
    que CU-O17/CU-O18 quieren que se rechace explícitamente, no que se
    devuelva vacío como si el dato no existiera.
    """
    autorizado = actor_id == conductor_id
    if not autorizado:
        viaje_del_pasajero = await db.viajes.find_one(
            {
                "pasajero_id": actor_id,
                "conductor_id": conductor_id,
                "estado": {"$in": _ESTADOS_VIAJE_CON_CONDUCTOR_VISIBLE},
            }
        )
        autorizado = viaje_del_pasajero is not None

    if not autorizado:
        raise PosicionConductorNoAutorizadaError()

    vehiculo = await _vehiculo_del_conductor(db, conductor_id)
    if vehiculo is None:
        raise PosicionConductorNoDisponibleError()

    redis = get_redis()
    cache = await redis.hgetall(f"pos:{vehiculo['_id']}")
    if not cache.get("lat"):
        raise PosicionConductorNoDisponibleError()

    return {
        "lat": float(cache["lat"]),
        "lon": float(cache["lon"]),
        "ts_servidor": datetime.fromisoformat(cache["ts_servidor"]),
    }


async def listar_estado_flota(db: AsyncIOMotorDatabase) -> list[dict]:
    redis = get_redis()
    resultado: list[dict] = []
    async for usuario in db.usuarios.find({"roles": "conductor"}):
        conductor = usuario.get("conductor") or {}
        if conductor.get("estado_servicio", "FUERA_DE_LINEA") == "FUERA_DE_LINEA":
            continue
        vehiculo = await _vehiculo_del_conductor(db, usuario["_id"])
        if vehiculo is None:
            continue
        cache = await redis.hgetall(f"pos:{vehiculo['_id']}")
        ts_servidor = datetime.fromisoformat(cache["ts_servidor"]) if cache.get("ts_servidor") else None
        sin_senal = ts_servidor is None or (datetime.now(UTC) - ts_servidor).total_seconds() > _SIN_SENAL_SEGUNDOS
        resultado.append(
            {
                "vehiculo_id": vehiculo["_id"],
                "vehiculo_placa": vehiculo.get("placa"),
                "conductor_id": usuario["_id"],
                "conductor_nombre": usuario.get("nombre"),
                "estado_servicio": "SIN_SEÑAL" if sin_senal else conductor.get("estado_servicio"),
                "lat": float(cache["lat"]) if cache.get("lat") else None,
                "lon": float(cache["lon"]) if cache.get("lon") else None,
                "ts_servidor": ts_servidor,
                "sin_senal": sin_senal,
            }
        )
    return resultado


def obtener_flota_activa_franja() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico de Flota -- CU-T05/OT3.2.

    Lee el último snapshot publicado de `rpt_flota_activa_franja` (corrida
    horaria de `dag_flota_gold`). Nunca calcula el % en vivo -- ese es el rol
    de `listar_estado_flota` (informe simple); este es estrictamente el dato
    ya agregado y publicado (CU-O16 paso 3)."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_flota_activa_franja")
    finally:
        client.close()
    return sorted(filas, key=lambda f: f["franja"])
