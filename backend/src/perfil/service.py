"""Autoservicio de cuenta propia — Sección 1.3/2.2/3.1 de
`specs/specs-administrativas/ux_complementaria.md`. Separado de `usuarios/`
(exclusivamente administrativo, Módulo 1 de admin_sistema) y de `auth/`
(tokens/credenciales) -- este dominio es "lo que cualquier cuenta puede
hacer sobre sí misma", sin importar el rol.

Decisión D1 del plan (ver PLAN_UX_COMPLEMENTARIA.md): sin OTP disponible en
el sistema (el login migró a usuario+contraseña, `CLAUDE.md` §4) y sin
infraestructura de envío de SMS/correo, editar el propio contacto exige la
contraseña actual en vez de una reverificación por OTP -- mismo nivel de
exigencia que ya tiene `POST /auth/cambiar-password`.
"""

from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.archivos import service as archivos_service
from src.core import sessions as core_sessions
from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.exceptions import DomainError, InvalidCredentialsError
from src.core.security import verify_password
from src.usuarios import service as usuarios_service


class ArchivoNoValidoParaFotoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="ARCHIVO_NO_VALIDO_PARA_FOTO",
            message="El archivo no existe, no te pertenece, o no se subió como foto de perfil",
            status_code=422,
        )


async def obtener_perfil(db: AsyncIOMotorDatabase, usuario_id: str) -> dict:
    return await usuarios_service.obtener_usuario(db, usuario_id)


async def editar_perfil(
    db: AsyncIOMotorDatabase, *, usuario_id: str, roles: list[str], cambios: dict, password_actual: str
) -> dict:
    usuario = await usuarios_service.obtener_usuario(db, usuario_id)
    if not verify_password(password_actual, usuario.get("hash_password", "")):
        raise InvalidCredentialsError("La contraseña actual no coincide")

    return await usuarios_service.editar_usuario(
        db,
        actor_id=usuario_id,
        actor_rol=",".join(roles),
        usuario_id=usuario_id,
        cambios=dict(cambios),
        accion=AccionAuditoria.PERFIL_EDICION,
    )


async def editar_foto_perfil(
    db: AsyncIOMotorDatabase, *, usuario_id: str, roles: list[str], archivo_id: str | None
) -> dict:
    """Separado de `editar_perfil` a propósito -- no exige `password_actual`
    (ver docstring de `PerfilFotoEditar`). `archivo_id=None` limpia
    `foto_url` (vuelve al avatar por defecto, resuelto en el frontend).

    Cuando SÍ viene un `archivo_id`, se valida contra `archivos` en vez de
    confiar ciegamente en lo que mande el cliente -- de otro modo cualquier
    usuario podría "robar" como propia la foto de otro (pegando un id ajeno)
    o fijar como foto de perfil un archivo subido para otro propósito (ej.
    evidencia de una falla, contexto `reporte_falla`)."""
    if archivo_id is not None:
        archivo = await archivos_service.obtener_archivo(db, archivo_id=archivo_id)
        if archivo["propietario_id"] != usuario_id or archivo["contexto"] != "foto_perfil":
            raise ArchivoNoValidoParaFotoError()

    return await usuarios_service.editar_usuario(
        db,
        actor_id=usuario_id,
        actor_rol=",".join(roles),
        usuario_id=usuario_id,
        cambios={"foto_url": archivo_id},
        accion=AccionAuditoria.PERFIL_EDICION,
    )


async def listar_sesiones_propias(usuario_id: str) -> list[dict]:
    return await core_sessions.listar_sesiones(usuario_id)


async def revocar_sesion_propia(
    db: AsyncIOMotorDatabase, *, usuario_id: str, roles: list[str], jti: str
) -> bool:
    # Write-ahead (CU-O17), mismo patrón que `usuarios/service.py::revocar_sesion`
    # -- el intento en sí queda trazado aunque el jti ya hubiera vencido solo.
    await write_audit_event(
        db,
        actor_id=usuario_id,
        rol=",".join(roles),
        accion=AccionAuditoria.SESION_CIERRE_REMOTO,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"jti": jti, "origen": "autoservicio"},
    )
    return await core_sessions.revocar_sesion(db, usuario_id, jti)


# ---------------------------------------------------------------------------
# Autoservicio de baja de cuenta con periodo de gracia de 30 días.
#
# Deliberadamente SEPARADO de la anonimización de CU-O17 A2 (Gobernanza de
# Datos, `usuarios.service.anonimizar_usuario`): esa es una acción legal,
# irreversible y ejecutada por un administrador sobre los datos personales;
# esto es un cierre de cuenta voluntario, iniciado por el propio titular, y
# reversible durante todo el periodo de gracia. Cerrar la cuenta NO dispara
# la anonimización -- si el titular además quiere que se borren sus datos
# personales, eso sigue siendo una solicitud aparte que un administrador
# atiende por el otro camino.
# ---------------------------------------------------------------------------

DIAS_PERIODO_GRACIA = 30


class BajaYaSolicitadaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="BAJA_YA_SOLICITADA",
            message="Ya hay una baja de cuenta en curso. Puedes cancelarla desde Ajustes.",
            status_code=409,
        )


class SinBajaEnCursoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="SIN_BAJA_EN_CURSO",
            message="Esta cuenta no tiene ninguna baja pendiente que cancelar",
            status_code=409,
        )


def dias_restantes_de_baja(usuario: dict) -> int | None:
    """Días que faltan para que la baja se haga efectiva, o `None` si la
    cuenta no tiene una baja en curso. Nunca negativo: si el plazo ya venció
    pero el job todavía no corrió, se informa 0 (no "-2 días")."""
    efectiva = usuario.get("baja_efectiva_en")
    if not efectiva:
        return None
    if efectiva.tzinfo is None:
        efectiva = efectiva.replace(tzinfo=UTC)
    restantes = (efectiva - datetime.now(UTC)).days
    return max(restantes, 0)


async def solicitar_baja_cuenta(db: AsyncIOMotorDatabase, *, usuario_id: str, motivo: str | None) -> dict:
    """Inicia el cierre voluntario. La cuenta sigue ACTIVA y con acceso
    normal durante los 30 días -- solo se marcan las 2 fechas."""
    usuario = await usuarios_service.obtener_usuario(db, usuario_id)
    if usuario.get("baja_efectiva_en"):
        raise BajaYaSolicitadaError()

    # Mismo guard que la baja administrativa, importado, no duplicado: no se
    # puede iniciar el cierre con un viaje vivo de por medio.
    await usuarios_service.verificar_sin_viaje_activo(db, usuario_id)

    # Caso borde 2 (advertencia, no bloqueo -- mismo criterio que la baja
    # administrativa): si el titular tiene un vehículo habilitado a su
    # nombre, ese vehículo saldrá de la flota cuando venza el plazo. Se
    # reusa el helper ya extraído en `usuarios_service`, no una consulta
    # nueva, y se devuelve para que la UI pueda decirlo ANTES de confirmar.
    placas = await usuarios_service.listar_vehiculos_habilitados_de(db, usuario_id)

    ahora = datetime.now(UTC)
    efectiva = ahora + timedelta(days=DIAS_PERIODO_GRACIA)

    await write_audit_event(
        db,
        actor_id=usuario_id,
        rol=",".join(usuario.get("roles", [])) or "sin_rol",
        accion=AccionAuditoria.CUENTA_BAJA_SOLICITADA,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={
            "baja_solicitada_en": ahora.isoformat(),
            "baja_efectiva_en": efectiva.isoformat(),
            "motivo": motivo,
        },
    )
    await db.usuarios.update_one(
        {"_id": usuario_id},
        {"$set": {"baja_solicitada_en": ahora, "baja_efectiva_en": efectiva, "baja_motivo": motivo}},
    )
    actualizado = await usuarios_service.obtener_usuario(db, usuario_id)
    actualizado["vehiculos_a_retirar"] = placas
    return actualizado


async def cancelar_baja_cuenta(db: AsyncIOMotorDatabase, *, usuario_id: str) -> dict:
    """Arrepentimiento: un solo paso, sin confirmación adicional. La cuenta
    vuelve exactamente a su estado anterior, sin rastro del aviso."""
    usuario = await usuarios_service.obtener_usuario(db, usuario_id)
    if not usuario.get("baja_efectiva_en"):
        raise SinBajaEnCursoError()

    await write_audit_event(
        db,
        actor_id=usuario_id,
        rol=",".join(usuario.get("roles", [])) or "sin_rol",
        accion=AccionAuditoria.CUENTA_BAJA_CANCELADA,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"baja_efectiva_en": str(usuario.get("baja_efectiva_en"))},
        datos_posteriores={"baja_efectiva_en": None},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id},
        {"$unset": {"baja_solicitada_en": "", "baja_efectiva_en": "", "baja_motivo": ""}},
    )
    return await usuarios_service.obtener_usuario(db, usuario_id)
