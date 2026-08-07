"""Compartir viaje en tiempo real — Sección 1.2 de `specs/specs-
administrativas/ux_complementaria.md`. Genera un enlace de solo lectura
que un contacto de confianza puede abrir SIN cuenta mientras el viaje está
`EN_CAMINO`/`EN_CURSO`.

Decisión de token (confirmada con el usuario antes de construir, ver
PLAN_UX_COMPLEMENTARIA.md §8): `secrets.token_urlsafe(32)` -- 256 bits de
entropía, mismo generador ya usado en `integraciones/service.py` para el
secreto de credenciales que se muestra una sola vez. El espacio de claves
vuelve la fuerza bruta computacionalmente inviable; el rate limiting de
abajo es una segunda capa contra scripting/scraping, no la defensa
principal contra adivinar un token.
"""

import secrets
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_redis import get_redis
from src.core.exceptions import DomainError
from src.core.tiempo import como_utc
from src.viajes.service import SinViajeActivoError

# Techo de expiración al generar el token: en este momento el viaje todavía
# no tiene `ts_fin` real (sigue en curso), así que se fija un techo generoso
# como respaldo -- la invalidación real ocurre antes, al finalizar/cancelar
# el viaje (ver `service_finalizacion.py`/`service_ejecucion.py`, que limpian
# el token explícitamente en vez de depender solo de este techo).
TECHO_EXPIRACION_HORAS = 4

ESTADOS_COMPARTIBLES = frozenset({"EN_CAMINO", "EN_CURSO"})

# Rate limiting del endpoint público -- aprobado con el usuario: 20 intentos
# fallidos (token inválido/expirado/no encontrado) en 15 minutos por IP.
# Nunca cuenta contra consultas válidas (alguien viendo un viaje real en vivo
# puede refrescar cada pocos segundos sin ser bloqueado). Mismo patrón que
# `_registrar_fallo_login` en `auth/service.py`.
UMBRAL_FALLOS = 20
VENTANA_FALLOS_MINUTOS = 15


class ViajeCompartidoNoEncontradoError(DomainError):
    """Mismo error genérico sin importar la causa (token inexistente,
    expirado, o viaje ya no compartible) -- no se filtra cuál de las tres
    ocurrió, mismo criterio que `InvalidCredentialsError` en el login."""

    def __init__(self) -> None:
        super().__init__(code="VIAJE_COMPARTIDO_NO_ENCONTRADO", message="Enlace no válido o expirado", status_code=404)


class DemasiadosIntentosCompartirError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="TOO_MANY_SHARE_ATTEMPTS",
            message="Demasiados intentos; espera unos minutos antes de volver a intentar",
            status_code=429,
        )


async def generar_token_compartir(db: AsyncIOMotorDatabase, *, pasajero_id: str) -> str:
    viaje = await db.viajes.find_one({"pasajero_id": pasajero_id, "estado": {"$in": list(ESTADOS_COMPARTIBLES)}})
    if viaje is None:
        raise SinViajeActivoError()

    ahora = datetime.now(UTC)
    token_vigente = viaje.get("token_compartir")
    expira_en = viaje.get("token_compartir_expira_en")
    # Idempotente mientras el token previo siga vigente -- evita invalidar un
    # enlace ya compartido con un contacto si el pasajero toca "Compartir"
    # dos veces por accidente.
    if token_vigente and expira_en and como_utc(expira_en) > ahora:
        return token_vigente

    token = secrets.token_urlsafe(32)
    nueva_expiracion = ahora + timedelta(hours=TECHO_EXPIRACION_HORAS)

    await write_audit_event(
        db,
        actor_id=pasajero_id,
        rol="pasajero",
        accion=AccionAuditoria.VIAJE_COMPARTIR_ACTIVADO,
        entidad="viajes",
        entidad_id=viaje["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"expira_en": nueva_expiracion.isoformat()},
    )
    await db.viajes.update_one(
        {"_id": viaje["_id"]},
        {"$set": {"token_compartir": token, "token_compartir_expira_en": nueva_expiracion}},
    )
    return token


async def _leer_posicion_vehiculo(vehiculo_id: str | None) -> dict | None:
    if vehiculo_id is None:
        return None
    redis = get_redis()
    cache = await redis.hgetall(f"pos:{vehiculo_id}")
    if not cache.get("lat"):
        return None
    return {"lat": float(cache["lat"]), "lon": float(cache["lon"])}


async def obtener_viaje_compartido(db: AsyncIOMotorDatabase, *, token: str) -> dict:
    ahora = datetime.now(UTC)
    viaje = await db.viajes.find_one(
        {
            "token_compartir": token,
            "token_compartir_expira_en": {"$gte": ahora},
            "estado": {"$in": list(ESTADOS_COMPARTIBLES)},
        }
    )
    if viaje is None:
        raise ViajeCompartidoNoEncontradoError()

    posicion = await _leer_posicion_vehiculo(viaje.get("vehiculo_id"))
    return {
        "conductor_nombre": viaje.get("conductor_nombre"),
        "conductor_calificacion": viaje.get("conductor_calificacion"),
        "conductor_foto_url": viaje.get("conductor_foto_url"),
        "vehiculo_placa": viaje.get("vehiculo_placa"),
        "estado": viaje["estado"],
        "posicion": posicion,
    }


def _fallos_key(ip: str) -> str:
    return f"compartir:fallos:{ip}"


def _bloqueado_key(ip: str) -> str:
    return f"compartir:bloqueado:{ip}"


async def verificar_no_bloqueado(ip: str) -> None:
    redis = get_redis()
    if await redis.get(_bloqueado_key(ip)):
        raise DemasiadosIntentosCompartirError()


async def registrar_fallo(ip: str) -> None:
    redis = get_redis()
    key = _fallos_key(ip)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, VENTANA_FALLOS_MINUTOS * 60)
    if count >= UMBRAL_FALLOS:
        await redis.set(_bloqueado_key(ip), "1", ex=VENTANA_FALLOS_MINUTOS * 60)
