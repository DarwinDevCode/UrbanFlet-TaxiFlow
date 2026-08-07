"""Registro de sesiones activas en Redis — Módulo 1.4 de admin_sistema
(specs/specs-administrativas/admin_sistema.md). No existía antes: JWT es
stateless por diseño (core/security.py), así que "listar quién tiene una
sesión abierta ahora" y "cerrarla remotamente" necesitan un registro aparte.

Solo se registra el jti del ACCESS token (es el único que valida
`rbac.get_current_actor` en cada petición) -- el refresh token no se
trackea como "sesión" propia. TTL igual a la vida configurada del access
token: el registro se limpia solo, sin job de limpieza aparte.

`sesion:revocada:{jti}` es el blocklist puntual que `rbac.get_current_actor`
consulta -- cerrar una sesión no toca `rbac:suspended:{usuario_id}` (eso
suspende TODA la cuenta, ver core/rbac.py), solo invalida ese jti concreto.
"""

import json
from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_redis import get_redis


def _set_key(usuario_id: str) -> str:
    return f"usuario:{usuario_id}:sesiones"


def _sesion_key(jti: str) -> str:
    return f"sesion:{jti}"


def _revocada_key(jti: str) -> str:
    return f"sesion:revocada:{jti}"


async def _ttls_vigentes(db: AsyncIOMotorDatabase) -> tuple[int, int]:
    """(ttl access en segundos, ttl refresh en segundos) -- Módulo 6.2: el
    TTL de sesión debe seguir al TTL de token configurado (política de
    seguridad), no a un valor fijo de `Settings` que puede haber quedado
    desactualizado si se publicó una política distinta."""
    from src.seguridad.service import obtener_politica_seguridad_vigente

    politica = await obtener_politica_seguridad_vigente(db)
    return politica["access_token_minutos"] * 60, politica["refresh_token_dias"] * 24 * 60 * 60


async def registrar_sesion(
    db: AsyncIOMotorDatabase, usuario_id: str, jti: str, *, ip: str | None, dispositivo: str | None
) -> None:
    redis = get_redis()
    ttl_access, ttl_refresh = await _ttls_vigentes(db)
    datos = {"usuario_id": usuario_id, "ip": ip, "dispositivo": dispositivo, "ts_inicio": datetime.now(UTC).isoformat()}
    valor = json.dumps(datos)
    await redis.set(_sesion_key(jti), valor, ex=ttl_access)
    # El set de jtis por usuario puede acumular entradas de sesiones ya
    # expiradas (su TTL individual ya venció) -- listar_sesiones() las poda
    # de forma perezosa al leer, no hace falta limpiar el set aquí.
    await redis.sadd(_set_key(usuario_id), jti)
    await redis.expire(_set_key(usuario_id), ttl_refresh)


async def listar_sesiones(usuario_id: str) -> list[dict]:
    redis = get_redis()
    jtis = await redis.smembers(_set_key(usuario_id))
    sesiones = []
    vencidos = []
    for jti in jtis:
        crudo = await redis.get(_sesion_key(jti))
        if crudo is None:
            vencidos.append(jti)
            continue
        datos = json.loads(crudo)
        sesiones.append({
            "jti": jti,
            "ip": datos.get("ip"),
            "dispositivo": datos.get("dispositivo"),
            "ts_inicio": datos.get("ts_inicio"),
        })
    if vencidos:
        await redis.srem(_set_key(usuario_id), *vencidos)
    sesiones.sort(key=lambda s: s["ts_inicio"] or "", reverse=True)
    return sesiones


async def revocar_sesion(db: AsyncIOMotorDatabase, usuario_id: str, jti: str) -> bool:
    """True si el jti pertenecía a una sesión registrada de ese usuario."""
    redis = get_redis()
    existia = await redis.sismember(_set_key(usuario_id), jti)
    if not existia:
        return False
    await redis.delete(_sesion_key(jti))
    await redis.srem(_set_key(usuario_id), jti)
    ttl_access, _ttl_refresh = await _ttls_vigentes(db)
    await redis.set(_revocada_key(jti), "1", ex=ttl_access)
    return True
