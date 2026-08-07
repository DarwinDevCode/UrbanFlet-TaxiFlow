"""Gestión de cuentas, roles y sesiones — Módulo 1 de admin_sistema
(specs/specs-administrativas/admin_sistema.md, IAM). Toda acción de este
módulo pasa por `write_audit_event` (regla transversal de la spec) y por
`seguridad.service` para la política de contraseña vigente.

Nota sobre "suspender invalida la sesión de inmediato" (§1.1 de la spec):
no hace falta un mecanismo aparte para eso -- `rbac.get_current_actor` ya
relee `usuarios.estado` de Mongo en CADA petición (CU-O18 A3, para que un
cambio de rol o una revocación apliquen sin esperar a que el token expire).
Poner `estado` en `SUSPENDIDO`/`BAJA` (cualquier valor distinto de
`ACTIVO`) ya lo bloquea en la siguiente petición, igual que ya bloquea el
login (`auth/service.py::login_con_password`). El registro de sesiones
activas (Módulo 1.4, `core/sessions.py`) es para el caso más fino de cerrar
UNA sesión puntual sin tocar el resto de la cuenta.
"""

import uuid
from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from src.auth.service import EmailAlreadyRegisteredError, PhoneAlreadyRegisteredError
from src.core import sessions as core_sessions
from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.exceptions import DomainError, WeakPasswordError
from src.core.rbac import ROLES
from src.core.security import hash_password
from src.seguridad.service import obtener_politica_vigente

# CU-O01/CU-O02: pasajero/conductor se autorregistran -- este módulo es
# exclusivamente para "personal interno" (spec §1.1). admin_sistema no
# puede usarlo para fabricar cuentas de pasajero/conductor por este canal.
ROLES_STAFF = frozenset(ROLES - {"pasajero", "conductor"})

_ESTADOS_REACTIVABLES = {"SUSPENDIDO"}


class UsuarioNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="USUARIO_NO_ENCONTRADO", message="El usuario no existe", status_code=404)


class RolInvalidoError(DomainError):
    def __init__(self, roles_invalidos: set[str]) -> None:
        super().__init__(
            code="ROL_INVALIDO",
            message=f"Rol(es) no permitidos para cuentas de personal interno: {', '.join(sorted(roles_invalidos))}",
            status_code=422,
        )


class EstadoInvalidoError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(code="ESTADO_INVALIDO", message=message, status_code=409)


def _valor_anidado(doc: dict, clave: str):
    """Soporta claves con notación de punto (ej. `conductor.foto_url`, usada
    por `perfil/service.py` para el sub-documento `usuarios.conductor`) --
    `dict.get()` plano no resuelve rutas anidadas, así que sin esto el
    "antes" de la auditoría quedaría siempre `None` para esos campos."""
    valor = doc
    for parte in clave.split("."):
        if not isinstance(valor, dict):
            return None
        valor = valor.get(parte)
    return valor


def _validar_roles_staff(roles: list[str]) -> None:
    invalidos = set(roles) - ROLES_STAFF
    if invalidos:
        raise RolInvalidoError(invalidos)


async def crear_cuenta_staff(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    nombre: str,
    telefono: str | None,
    email: str | None,
    password: str,
    roles: list[str],
) -> dict:
    _validar_roles_staff(roles)
    politica = await obtener_politica_vigente(db)
    if len(password) < politica["longitud_minima_password"]:
        raise WeakPasswordError(politica["longitud_minima_password"])

    ahora = datetime.now(UTC)
    usuario: dict = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "hash_password": hash_password(password),
        "roles": roles,
        "estado": "ACTIVO",
        "fecha_registro": ahora,
        "forzar_cambio_password": True,
        "password_actualizada_en": ahora,
    }
    if telefono:
        usuario["telefono"] = telefono
    if email:
        usuario["email"] = email

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_CREACION,
        entidad="usuarios",
        entidad_id=usuario["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre, "roles": roles},
    )

    try:
        await db.usuarios.insert_one(usuario)
    except DuplicateKeyError as exc:
        campo_en_conflicto = next(iter(exc.details.get("keyPattern", {})), None) if exc.details else None
        if campo_en_conflicto == "email":
            raise EmailAlreadyRegisteredError() from exc
        raise PhoneAlreadyRegisteredError() from exc

    return usuario


async def listar_usuarios(
    db: AsyncIOMotorDatabase,
    *,
    rol: str | None = None,
    estado: str | None = None,
    texto: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filtro: dict = {}
    if rol:
        filtro["roles"] = rol
    if estado:
        filtro["estado"] = estado
    if texto:
        filtro["$or"] = [
            {"nombre": {"$regex": texto, "$options": "i"}},
            {"telefono": {"$regex": texto, "$options": "i"}},
            {"email": {"$regex": texto, "$options": "i"}},
        ]
    total = await db.usuarios.count_documents(filtro)
    cursor = db.usuarios.find(filtro).sort("fecha_registro", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return items, total


async def obtener_usuario(db: AsyncIOMotorDatabase, usuario_id: str) -> dict:
    usuario = await db.usuarios.find_one({"_id": usuario_id})
    if usuario is None:
        raise UsuarioNoEncontradoError()
    return usuario


async def editar_usuario(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    usuario_id: str,
    cambios: dict,
    accion: AccionAuditoria = AccionAuditoria.USUARIO_EDICION,
) -> dict:
    """`accion` por defecto es `USUARIO_EDICION` (Módulo 1.1, un admin_sistema
    editando la cuenta de un tercero). `perfil/service.py` reutiliza esta
    misma función para autoservicio, pasando `AccionAuditoria.PERFIL_EDICION`
    -- para que el filtro administrativo de Auditoría distinga "un admin
    editó a otro" de "alguien editó lo suyo", sin duplicar el resto de la
    lógica (chequeo de unicidad de teléfono/correo incluido)."""
    usuario = await obtener_usuario(db, usuario_id)
    if not cambios:
        return usuario

    antes = {k: _valor_anidado(usuario, k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=accion,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.usuarios.update_one({"_id": usuario_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        campo_en_conflicto = next(iter(exc.details.get("keyPattern", {})), None) if exc.details else None
        if campo_en_conflicto == "email":
            raise EmailAlreadyRegisteredError() from exc
        raise PhoneAlreadyRegisteredError() from exc
    return await obtener_usuario(db, usuario_id)


async def asignar_roles(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, roles: list[str]
) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    roles_previos = usuario.get("roles", [])
    # Si la cuenta ya es de pasajero/conductor (autorregistro), no se le
    # puede reasignar a un rol de personal interno por este canal ni
    # viceversa -- evita mezclar el ciclo de vida de las dos apps externas
    # con el de `web-interno`.
    era_staff = not (set(roles_previos) & {"pasajero", "conductor"})
    if era_staff:
        _validar_roles_staff(roles)
    elif set(roles) - set(roles_previos):
        raise RolInvalidoError(set(roles) - set(roles_previos))

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ROL_MODIFICACION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"roles": roles_previos},
        datos_posteriores={"roles": roles},
    )
    await db.usuarios.update_one({"_id": usuario_id}, {"$set": {"roles": roles}})
    return await obtener_usuario(db, usuario_id)


async def suspender_usuario(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, motivo: str
) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    if usuario["estado"] != "ACTIVO":
        raise EstadoInvalidoError(f"Solo se puede suspender una cuenta ACTIVA (estado actual: {usuario['estado']})")

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_SUSPENSION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "ACTIVO"},
        datos_posteriores={"estado": "SUSPENDIDO", "motivo": motivo},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id}, {"$set": {"estado": "SUSPENDIDO", "motivo_suspension": motivo}}
    )
    return await obtener_usuario(db, usuario_id)


async def reactivar_usuario(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    if usuario["estado"] not in _ESTADOS_REACTIVABLES:
        raise EstadoInvalidoError(
            f"Solo una cuenta SUSPENDIDA se puede reactivar (estado actual: {usuario['estado']})"
        )

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_REACTIVACION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "SUSPENDIDO"},
        datos_posteriores={"estado": "ACTIVO"},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id}, {"$set": {"estado": "ACTIVO", "motivo_suspension": None}}
    )
    return await obtener_usuario(db, usuario_id)


async def dar_de_baja_usuario(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, motivo: str
) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    if usuario["estado"] == "BAJA":
        raise EstadoInvalidoError("La cuenta ya está dada de baja")

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_BAJA,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": usuario["estado"]},
        datos_posteriores={"estado": "BAJA", "motivo": motivo},
    )
    await db.usuarios.update_one({"_id": usuario_id}, {"$set": {"estado": "BAJA", "motivo_baja": motivo}})
    return await obtener_usuario(db, usuario_id)


async def anonimizar_usuario(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str) -> dict:
    """Módulo 8.2 (Gobernanza de datos) -- CU-O17 A2 / derechos ARCO (LOPDP):
    "los datos personales se anonimizan en las entidades de negocio, pero
    los eventos de bitácora se conservan con el identificador seudonimizado;
    la propia anonimización queda registrada como evento".

    Irreversible: no hay operación inversa, ni en este service ni expuesta
    por ningún endpoint. `actor_id` en la bitácora (pasada y futura) sigue
    siendo el mismo UUID opaco que siempre fue -- nunca fue el dato
    personal en sí, así que no hace falta (ni se debe) tocar ningún evento
    ya escrito para "seudonimizarlo" ahí. Lo que sí se seudonimiza es la
    entidad `usuarios`: de ahí en adelante, cualquier pantalla que resuelva
    este `usuario_id` a un nombre para mostrar ve el seudónimo, nunca el
    dato real (que ya no existe en ningún documento vivo del sistema).
    """
    usuario = await obtener_usuario(db, usuario_id)
    if usuario.get("anonimizado"):
        raise EstadoInvalidoError("La cuenta ya fue anonimizada")

    seudonimo = f"Usuario Anonimizado {usuario_id[:8]}"
    ahora = datetime.now(UTC)

    # A propósito, `datos_previos`/`datos_posteriores` NO llevan el
    # nombre/teléfono/correo real: `bitacora` es insert-only, y grabar el
    # dato que se está purgando en un evento permanente derrotaría el
    # propósito de la anonimización. El evento documenta que ocurrió, con
    # el seudónimo nuevo (que no es información personal) -- no el detalle
    # de qué se borró.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_ANONIMIZACION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"anonimizado": False},
        datos_posteriores={"anonimizado": True, "nombre_seudonimo": seudonimo},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id},
        {
            "$set": {"nombre": seudonimo, "anonimizado": True, "anonimizado_en": ahora},
            "$unset": {"telefono": "", "email": ""},
        },
    )
    # Sección 1.1 de ux_complementaria.md: las direcciones favoritas son
    # datos personales de ubicación -- se purgan junto con el resto de la
    # cuenta, no quedan huérfanas apuntando a un usuario ya anonimizado.
    await db.direcciones_favoritas.delete_many({"usuario_id": usuario_id})
    return await obtener_usuario(db, usuario_id)


async def listar_accesos(db: AsyncIOMotorDatabase, usuario_id: str, *, limit: int = 50) -> list[dict]:
    """Historial de accesos (§1.1) e intentos fallidos (§1.4) en un único
    listado -- ambos ya son eventos de la misma bitácora (CU-O17),
    distinguibles por `resultado`."""
    acciones = [AccionAuditoria.SESION_INICIO.value, AccionAuditoria.LOGIN_FALLIDO_CONSECUTIVO.value]
    cursor = (
        db.bitacora.find({"entidad_id": usuario_id, "accion": {"$in": acciones}})
        .sort("ts", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def listar_sesiones(usuario_id: str) -> list[dict]:
    return await core_sessions.listar_sesiones(usuario_id)


async def revocar_sesion(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, jti: str
) -> bool:
    # Write-ahead (CU-O17): se registra el intento antes del efecto, igual
    # que el resto del módulo -- incluso si el jti ya no existía (sesión
    # vencida sola), el intento de un admin de cerrarla es en sí mismo un
    # evento de seguridad que vale la pena dejar trazado.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.SESION_CIERRE_REMOTO,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"jti": jti},
    )
    return await core_sessions.revocar_sesion(db, usuario_id, jti)
