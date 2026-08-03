"""Control de acceso por rol — CU-O18 (operativo_cumplimiento.md).

Catálogo de roles y resolución de permisos tal como los describe el CU: la
autorización se resuelve por consulta de perfil en cada petición (nunca por lo
que diga el JWT), para que una baja de rol o una revocación apliquen de
inmediato sin esperar a que expire el token (CU-O18 A3).
"""

from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_mongo import get_database
from src.core.db_redis import get_redis
from src.core.exceptions import DomainError, InsufficientRoleError, SessionSuspendedError
from src.core.security import TokenType, decode_token

# Catálogo de roles verbatim de CU-O18 (precondición).
ROLES = frozenset(
    {
        "pasajero",
        "conductor",
        "admin_captacion",
        "coordinador_operaciones",
        "coordinador_flota",
        "jefe_mantenimiento",
        "admin_financiero",
        "supervisor_cumplimiento",
        "responsable_plataforma",
        "gerencia",
        "integracion_externa",
        "admin_plataforma",
    }
)

_DENIAL_WINDOW_SECONDS = 10 * 60
_DENIAL_THRESHOLD = 5
_SUSPENSION_SECONDS = 30 * 60

_bearer_scheme = HTTPBearer(auto_error=False)


class InvalidTokenError(DomainError):
    def __init__(self, message: str = "Token inválido o expirado") -> None:
        super().__init__(code="INVALID_TOKEN", message=message, status_code=401)


@dataclass
class Actor:
    usuario_id: str
    roles: list[str] = field(default_factory=list)
    estado: str = "ACTIVO"

    def has_any_role(self, required: set[str]) -> bool:
        return bool(required.intersection(self.roles))


async def _is_session_suspended(usuario_id: str) -> bool:
    redis = get_redis()
    return bool(await redis.get(f"rbac:suspended:{usuario_id}"))


async def get_current_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Actor:
    if credentials is None:
        raise InvalidTokenError("No se proporcionó token de sesión")

    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise InvalidTokenError("El token no es un access token")

    usuario_id: str = payload["sub"]

    if await _is_session_suspended(usuario_id):
        raise SessionSuspendedError()

    # Resolución de rol "por petición": se ignoran los roles del token y se
    # consultan en Mongo, tal como exige CU-O18 A3.
    usuario = await db.usuarios.find_one({"_id": usuario_id})
    if usuario is None or usuario.get("estado") != "ACTIVO":
        raise InvalidTokenError("Usuario inexistente o inactivo")

    actor = Actor(usuario_id=usuario_id, roles=usuario.get("roles", []), estado=usuario["estado"])
    request.state.actor = actor
    return actor


async def _alertar_supervisores_cumplimiento(request: Request, db: AsyncIOMotorDatabase, motivo: str) -> None:
    dispatcher = getattr(request.app.state, "notification_dispatcher", None)
    if dispatcher is None:
        return
    async for supervisor in db.usuarios.find({"roles": "supervisor_cumplimiento"}):
        await dispatcher.notify_user(supervisor["_id"], "ALERTA_SEGURIDAD", {"motivo": motivo})


async def _register_denial_and_maybe_suspend(
    request: Request, db: AsyncIOMotorDatabase, actor: Actor, entidad: str
) -> None:
    redis = get_redis()
    key = f"rbac:denials:{actor.usuario_id}"

    # Write-ahead (CU-O17): "role-denied attempts" está en el catálogo mínimo
    # de eventos sensibles. El evento se escribe antes de cualquier efecto
    # (contador de denegaciones, suspensión de sesión).
    await write_audit_event(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        accion=AccionAuditoria.ACCESO_DENEGADO,
        entidad=entidad,
        entidad_id=None,
        resultado=ResultadoAuditoria.DENEGADO,
    )

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _DENIAL_WINDOW_SECONDS)

    if count >= _DENIAL_THRESHOLD:
        await redis.set(f"rbac:suspended:{actor.usuario_id}", "1", ex=_SUSPENSION_SECONDS)
        # CU-O18 A4: "cinco denegaciones del mismo actor en 10 minutos:
        # el sistema suspende la sesión y alerta al Supervisor de Cumplimiento."
        await _alertar_supervisores_cumplimiento(
            request, db, motivo=f"Sesión de {actor.usuario_id} suspendida por accesos denegados repetidos"
        )


def require_roles(*roles: str):
    required = set(roles)
    if not required.issubset(ROLES):
        raise ValueError(f"Roles desconocidos en require_roles: {required - ROLES}")

    async def _dependency(
        request: Request,
        actor: Actor = Depends(get_current_actor),
        db: AsyncIOMotorDatabase = Depends(get_database),
    ) -> Actor:
        if not actor.has_any_role(required):
            await _register_denial_and_maybe_suspend(request, db, actor, entidad=request.url.path)
            raise InsufficientRoleError()
        return actor

    return _dependency
