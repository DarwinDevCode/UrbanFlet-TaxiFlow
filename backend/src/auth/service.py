"""Servicio de auth (transversal, sin CU formal — ítem A1 del plan).

`registro` crea únicamente la cuenta base (USUARIO). La creación del perfil de
PASAJERO (CU-O02) o de SOLICITUD_CONDUCTOR (CU-O01) es responsabilidad del
módulo `captacion` en Fase 1, que llama a este servicio como capa inferior —
así se respeta el límite "ningún módulo accede a las colecciones de otro
dominio directamente" (arquitectura_software.md línea 71).

Login autocontenido (teléfono O correo, a elección del usuario, + contraseña)
— mismo mecanismo para los tres roles (pasajero, conductor, personal de
`web-interno`), sin verificación externa de ningún tipo. La posesión de la
contraseña es la única prueba de identidad que este sistema exige; por eso
`estado` pasa a `ACTIVO` en el momento mismo del registro, no después de un
paso de verificación que ya no existe.
"""

import uuid
from datetime import datetime, UTC

import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_redis import get_redis
from src.core.exceptions import DomainError, InvalidCredentialsError, TooManyLoginAttemptsError
from src.core.security import TokenType, create_token, decode_token, hash_password, verify_password

_MAX_REFRESH_FAILURES = 3
_REFRESH_FAILURE_WINDOW_SECONDS = 15 * 60

_MAX_LOGIN_FAILURES = 5
_LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
_LOGIN_LOCKOUT_SECONDS = 15 * 60


class PhoneAlreadyRegisteredError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="PHONE_ALREADY_REGISTERED", message="El teléfono ya está registrado", status_code=409)


class EmailAlreadyRegisteredError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="EMAIL_ALREADY_REGISTERED", message="El correo ya está registrado", status_code=409)


async def registrar_usuario(
    db: AsyncIOMotorDatabase, *, nombre: str, telefono: str | None, email: str | None, password: str
) -> dict:
    """`telefono`/`email` son ambos opcionales a este nivel — cada schema de
    request (auth, pasajero, solicitud de conductor) es responsable de exigir
    al menos uno antes de llegar aquí (validación en la frontera, no
    duplicada en el servicio). `password` sí es requerido siempre: es el
    único mecanismo de autenticación del sistema."""
    usuario: dict = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "hash_password": hash_password(password),
        "roles": [],
        # Sin un paso de verificación externo (ya no hay OTP ni Firebase),
        # tener una contraseña válida ES la prueba de identidad — la cuenta
        # queda utilizable de inmediato.
        "estado": "ACTIVO",
        "fecha_registro": datetime.now(UTC),
    }
    # Se omiten las claves por completo (no se guardan como None) cuando no
    # vienen — así los índices sparse de `telefono`/`email` (core/db_mongo.py)
    # no chocan entre sí cuando muchas cuentas comparten "no tengo email" o
    # "no tengo teléfono", que es justo el caso ahora que cualquiera de los
    # dos alcanza para registrarse.
    if telefono:
        usuario["telefono"] = telefono
    if email:
        usuario["email"] = email

    # Write-ahead (CU-O17): el evento se escribe ANTES del efecto de negocio.
    # Si esto falla, AuditWriteError propaga y el insert de abajo nunca corre.
    await write_audit_event(
        db,
        actor_id=usuario["_id"],
        rol=None,
        accion=AccionAuditoria.CREDENCIAL_CREACION,
        entidad="usuarios",
        entidad_id=usuario["_id"],
        resultado=ResultadoAuditoria.OK,
    )

    try:
        await db.usuarios.insert_one(usuario)
    except DuplicateKeyError as exc:
        # keyPattern indica cuál de los dos índices únicos chocó, para no
        # devolver siempre el mismo error genérico sin importar cuál campo
        # ya estaba en uso.
        campo_en_conflicto = next(iter(exc.details.get("keyPattern", {})), None) if exc.details else None
        if campo_en_conflicto == "email":
            raise EmailAlreadyRegisteredError() from exc
        raise PhoneAlreadyRegisteredError() from exc

    return usuario


def _emitir_tokens(usuario: dict) -> dict:
    # `nombre` viaja como extra_claim (mismo mecanismo que `roles`, ver
    # comentario en create_token) solo para mostrar un nombre legible en la
    # UI en vez del usuario_id crudo -- nunca se usa para autorización.
    extra = {"nombre": usuario.get("nombre")}
    access = create_token(usuario["_id"], usuario.get("roles", []), TokenType.ACCESS, extra_claims=extra)
    refresh = create_token(usuario["_id"], usuario.get("roles", []), TokenType.REFRESH, extra_claims=extra)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


async def login_con_password(db: AsyncIOMotorDatabase, *, identificador: str, password: str) -> dict:
    """`identificador` es el teléfono o el correo — el que el usuario haya
    elegido al registrarse; se busca por cualquiera de los dos. Mismo mensaje
    de error (`InvalidCredentialsError`) sin importar si el identificador no
    existe o la contraseña no coincide, para no filtrar cuáles cuentas
    existen."""
    redis = get_redis()
    lock_key = f"auth:login_locked:{identificador}"
    failure_key = f"auth:login_failures:{identificador}"

    # Cuenta bloqueada por intentos fallidos previos: se rechaza sin siquiera
    # tocar Mongo, tanto si el identificador existe como si no.
    if await redis.get(lock_key):
        raise TooManyLoginAttemptsError()

    usuario = await db.usuarios.find_one({"$or": [{"telefono": identificador}, {"email": identificador}]})
    credenciales_validas = (
        usuario is not None
        and usuario["estado"] == "ACTIVO"
        and usuario.get("hash_password") is not None
        and verify_password(password, usuario["hash_password"])
    )

    if not credenciales_validas:
        await _registrar_fallo_login(db, redis, failure_key, lock_key, identificador, usuario)
        raise InvalidCredentialsError()

    await redis.delete(failure_key)

    # Write-ahead (CU-O17): igual que registrar_usuario, el evento se
    # registra ANTES de emitir la sesión — si la escritura de auditoría
    # falla, AuditWriteError propaga y ninguna sesión se crea.
    await write_audit_event(
        db,
        actor_id=usuario["_id"],
        rol=None,
        accion=AccionAuditoria.SESION_INICIO,
        entidad="usuarios",
        entidad_id=usuario["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"metodo": "password"},
    )

    return _emitir_tokens(usuario)


async def _registrar_fallo_login(
    db: AsyncIOMotorDatabase, redis, failure_key: str, lock_key: str, identificador: str, usuario: dict | None
) -> None:
    """Cuenta intentos fallidos por `identificador` (no por usuario_id: la
    cuenta puede no existir todavía, y no queremos filtrar esa diferencia).
    Al llegar al umbral, se bloquea el identificador durante la ventana de
    bloqueo — mismo patrón que `_register_denial_and_maybe_suspend` en
    `core/rbac.py`."""
    count = await redis.incr(failure_key)
    if count == 1:
        await redis.expire(failure_key, _LOGIN_FAILURE_WINDOW_SECONDS)

    if count >= _MAX_LOGIN_FAILURES:
        # Write-ahead (CU-O17): el evento se escribe ANTES de aplicar el
        # bloqueo.
        await write_audit_event(
            db,
            actor_id=usuario["_id"] if usuario else identificador,
            rol=None,
            accion=AccionAuditoria.LOGIN_FALLIDO_CONSECUTIVO,
            entidad="usuarios",
            entidad_id=usuario["_id"] if usuario else None,
            resultado=ResultadoAuditoria.DENEGADO,
        )
        await redis.set(lock_key, "1", ex=_LOGIN_LOCKOUT_SECONDS)
        await redis.delete(failure_key)


async def refrescar_token(db: AsyncIOMotorDatabase, *, refresh_token: str) -> dict:
    redis = get_redis()
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != TokenType.REFRESH.value:
            raise InvalidCredentialsError("El token no es un refresh token")
    except jwt.PyJWTError as exc:
        raise InvalidCredentialsError("Refresh token inválido o expirado") from exc

    usuario_id = payload["sub"]
    failure_key = f"auth:refresh_failures:{usuario_id}"

    usuario = await db.usuarios.find_one({"_id": usuario_id})
    if usuario is None or usuario["estado"] != "ACTIVO":
        await _registrar_fallo_refresh(redis, failure_key, usuario_id)
        raise InvalidCredentialsError()

    await redis.delete(failure_key)
    # roles se releen de Mongo (no del refresh token) por el mismo motivo que
    # get_current_actor: un cambio de rol debe aplicar de inmediato.
    return _emitir_tokens(usuario)


async def _registrar_fallo_refresh(redis, failure_key: str, usuario_id: str) -> None:
    count = await redis.incr(failure_key)
    if count == 1:
        await redis.expire(failure_key, _REFRESH_FAILURE_WINDOW_SECONDS)
    if count >= _MAX_REFRESH_FAILURES:
        await redis.set(f"rbac:suspended:{usuario_id}", "1", ex=_REFRESH_FAILURE_WINDOW_SECONDS)
