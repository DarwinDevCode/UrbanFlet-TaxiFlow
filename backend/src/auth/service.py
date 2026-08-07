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

Módulo de Administración del Sistema (specs/specs-administrativas/
admin_sistema.md, Módulo 1.3): la longitud mínima de contraseña y los
umbrales de bloqueo por intentos fallidos ya no son constantes fijas -- se
leen de `seguridad.service.obtener_politica_vigente()` en cada llamada
(fallback a los valores que regían antes, ver `seguridad/service.py::DEFAULTS`,
si nunca se publicó una política). Módulo 1.4: cada access token emitido
registra una "sesión" consultable/revocable en Redis (`core/sessions.py`).
"""

import secrets
import uuid
from datetime import datetime, UTC

import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from src.core import sessions as core_sessions
from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_redis import get_redis
from src.core.exceptions import DomainError, InvalidCredentialsError, TooManyLoginAttemptsError, WeakPasswordError
from src.core.security import TokenType, create_token, decode_token, hash_password, verify_password
from src.seguridad.service import ROLES_ALTO_PRIVILEGIO, obtener_politica_seguridad_vigente, obtener_politica_vigente


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
    politica = await obtener_politica_vigente(db)
    if len(password) < politica["longitud_minima_password"]:
        raise WeakPasswordError(politica["longitud_minima_password"])

    ahora = datetime.now(UTC)
    usuario: dict = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "hash_password": hash_password(password),
        "roles": [],
        # Sin un paso de verificación externo (ya no hay OTP ni Firebase),
        # tener una contraseña válida ES la prueba de identidad — la cuenta
        # queda utilizable de inmediato.
        "estado": "ACTIVO",
        "fecha_registro": ahora,
        # Módulo 1.1/1.3: soporte de "forzar cambio de contraseña" (admin) y
        # de vencimiento periódico para roles de alto privilegio.
        "forzar_cambio_password": False,
        "password_actualizada_en": ahora,
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


def _password_vencida(usuario: dict, politica: dict) -> bool:
    dias = politica.get("vencimiento_dias_alto_privilegio")
    if not dias:
        return False
    if not set(usuario.get("roles", [])) & ROLES_ALTO_PRIVILEGIO:
        return False
    actualizada_en = usuario.get("password_actualizada_en")
    if actualizada_en is None:
        return False
    if actualizada_en.tzinfo is None:
        actualizada_en = actualizada_en.replace(tzinfo=UTC)
    return (datetime.now(UTC) - actualizada_en).days >= dias


async def _emitir_tokens(
    db: AsyncIOMotorDatabase, usuario: dict, *, ip: str | None = None, dispositivo: str | None = None
) -> dict:
    # `nombre` viaja como extra_claim (mismo mecanismo que `roles`, ver
    # comentario en create_token) solo para mostrar un nombre legible en la
    # UI en vez del usuario_id crudo -- nunca se usa para autorización.
    extra = {"nombre": usuario.get("nombre")}
    access_jti = secrets.token_hex(16)
    roles = usuario.get("roles", [])
    # Módulo 6.2: TTL configurable en vez de las constantes fijas de Settings.
    politica_seguridad = await obtener_politica_seguridad_vigente(db)
    access = create_token(
        usuario["_id"], roles, TokenType.ACCESS, extra_claims=extra, jti=access_jti,
        access_ttl_minutos=politica_seguridad["access_token_minutos"],
    )
    refresh = create_token(
        usuario["_id"], roles, TokenType.REFRESH, extra_claims=extra,
        refresh_ttl_dias=politica_seguridad["refresh_token_dias"],
    )
    # Módulo 1.4: registra la sesión del access token recién emitido -- es el
    # único que `rbac.get_current_actor` valida en cada petición, así que es
    # el único que hace falta trackear para "listar/cerrar sesiones activas".
    await core_sessions.registrar_sesion(db, usuario["_id"], access_jti, ip=ip, dispositivo=dispositivo)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


async def login_con_password(
    db: AsyncIOMotorDatabase,
    *,
    identificador: str,
    password: str,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> dict:
    """`identificador` es el teléfono o el correo — el que el usuario haya
    elegido al registrarse; se busca por cualquiera de los dos. Mismo mensaje
    de error (`InvalidCredentialsError`) sin importar si el identificador no
    existe o la contraseña no coincide, para no filtrar cuáles cuentas
    existen."""
    redis = get_redis()
    politica = await obtener_politica_vigente(db)
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
        await _registrar_fallo_login(db, redis, failure_key, lock_key, identificador, usuario, politica)
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

    tokens = await _emitir_tokens(db, usuario, ip=ip, dispositivo=dispositivo)
    forzado = bool(usuario.get("forzar_cambio_password"))
    tokens["debe_cambiar_password"] = forzado or _password_vencida(usuario, politica)
    return tokens


async def _registrar_fallo_login(
    db: AsyncIOMotorDatabase,
    redis,
    failure_key: str,
    lock_key: str,
    identificador: str,
    usuario: dict | None,
    politica: dict,
) -> None:
    """Cuenta intentos fallidos por `identificador` (no por usuario_id: la
    cuenta puede no existir todavía, y no queremos filtrar esa diferencia).
    Al llegar al umbral, se bloquea el identificador durante la ventana de
    bloqueo — mismo patrón que `_register_denial_and_maybe_suspend` en
    `core/rbac.py`. Umbral/ventana/duración configurables desde Módulo 1.3
    (antes eran constantes fijas: 5 fallos/15min → bloqueo 15min)."""
    count = await redis.incr(failure_key)
    if count == 1:
        await redis.expire(failure_key, politica["ventana_minutos"] * 60)

    if count >= politica["umbral_intentos_fallidos"]:
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
        await redis.set(lock_key, "1", ex=politica["bloqueo_minutos"] * 60)
        await redis.delete(failure_key)


async def refrescar_token(
    db: AsyncIOMotorDatabase, *, refresh_token: str, ip: str | None = None, dispositivo: str | None = None
) -> dict:
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
        politica_seguridad = await obtener_politica_seguridad_vigente(db)
        await _registrar_fallo_refresh(redis, failure_key, usuario_id, politica_seguridad)
        raise InvalidCredentialsError()

    await redis.delete(failure_key)
    # roles se releen de Mongo (no del refresh token) por el mismo motivo que
    # get_current_actor: un cambio de rol debe aplicar de inmediato.
    return await _emitir_tokens(db, usuario, ip=ip, dispositivo=dispositivo)


async def _registrar_fallo_refresh(redis, failure_key: str, usuario_id: str, politica_seguridad: dict) -> None:
    """Umbral/ventana configurables desde Módulo 6.2 (antes constantes fijas:
    3 fallos/15min)."""
    ventana_segundos = politica_seguridad["refresh_ventana_minutos"] * 60
    count = await redis.incr(failure_key)
    if count == 1:
        await redis.expire(failure_key, ventana_segundos)
    if count >= politica_seguridad["refresh_umbral_fallos"]:
        await redis.set(f"rbac:suspended:{usuario_id}", "1", ex=ventana_segundos)


async def cambiar_password(
    db: AsyncIOMotorDatabase, *, usuario_id: str, password_actual: str, password_nueva: str
) -> None:
    """Cierra el ciclo de `forzar_cambio_password` (Módulo 1.1) y del
    vencimiento periódico (Módulo 1.3): requiere la contraseña actual (no
    basta con estar autenticado) para no permitir que una sesión robada
    cambie la contraseña sin conocerla."""
    usuario = await db.usuarios.find_one({"_id": usuario_id})
    if usuario is None or not verify_password(password_actual, usuario.get("hash_password", "")):
        raise InvalidCredentialsError("La contraseña actual no coincide")

    politica = await obtener_politica_vigente(db)
    if len(password_nueva) < politica["longitud_minima_password"]:
        raise WeakPasswordError(politica["longitud_minima_password"])

    ahora = datetime.now(UTC)
    await write_audit_event(
        db,
        actor_id=usuario_id,
        rol=",".join(usuario.get("roles", [])),
        accion=AccionAuditoria.PASSWORD_CAMBIO,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
    )
    cambios = {
        "hash_password": hash_password(password_nueva),
        "forzar_cambio_password": False,
        "password_actualizada_en": ahora,
    }
    await db.usuarios.update_one({"_id": usuario_id}, {"$set": cambios})
