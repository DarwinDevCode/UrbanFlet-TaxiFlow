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

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core import sessions as core_sessions
from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.exceptions import InvalidCredentialsError
from src.core.security import verify_password
from src.usuarios import service as usuarios_service


async def obtener_perfil(db: AsyncIOMotorDatabase, usuario_id: str) -> dict:
    return await usuarios_service.obtener_usuario(db, usuario_id)


def _remapear_foto_url(cambios: dict, roles: list[str]) -> dict:
    """`foto_url` vive en `usuarios.conductor.foto_url` (mismo sub-documento
    que `cedula`/`calificacion_promedio`), no como campo top-level -- y solo
    tiene sentido para una cuenta con rol `conductor` (Sección 2.2 de la
    spec). Se ignora en silencio para cualquier otro rol en vez de rechazar
    la petición completa por un campo que ese rol no necesita."""
    if "foto_url" not in cambios:
        return cambios
    foto_url = cambios.pop("foto_url")
    if "conductor" in roles:
        cambios["conductor.foto_url"] = foto_url
    return cambios


async def editar_perfil(
    db: AsyncIOMotorDatabase, *, usuario_id: str, roles: list[str], cambios: dict, password_actual: str
) -> dict:
    usuario = await usuarios_service.obtener_usuario(db, usuario_id)
    if not verify_password(password_actual, usuario.get("hash_password", "")):
        raise InvalidCredentialsError("La contraseña actual no coincide")

    cambios = _remapear_foto_url(dict(cambios), roles)
    return await usuarios_service.editar_usuario(
        db,
        actor_id=usuario_id,
        actor_rol=",".join(roles),
        usuario_id=usuario_id,
        cambios=cambios,
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
