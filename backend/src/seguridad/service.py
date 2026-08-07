"""Políticas de autenticación configurables — Módulo 1.3 de admin_sistema
(specs/specs-administrativas/admin_sistema.md). Antes de este módulo, la
longitud mínima de contraseña y el umbral de bloqueo por intentos fallidos
estaban fijos en `auth/service.py` (8 caracteres, 5 fallos/15min → bloqueo
15min, CU-O18 A4). Reutiliza el patrón versionado ya probado en
`parametros/service.py::_crear_version` (mismo tipo de dato: valor +
vigencia, nunca retroactivo) en vez de crear un mecanismo paralelo.

Los valores de hoy (`DEFAULTS`) son el fallback cuando nunca se configuró
una política -- así el comportamiento no cambia para el sistema hasta que
un admin_sistema publique la primera versión.
"""

from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.parametros.service import ParametroNoVigenteError, _crear_version, obtener_vigente

_TIPO = "politica_auth"

DEFAULTS = {
    "longitud_minima_password": 8,
    "umbral_intentos_fallidos": 5,
    "ventana_minutos": 15,
    "bloqueo_minutos": 15,
    "vencimiento_dias_alto_privilegio": None,
}

# Roles a los que aplica el vencimiento periódico de contraseña, si la
# política lo configura -- los de mayor privilegio del catálogo (CU-O18).
ROLES_ALTO_PRIVILEGIO = frozenset({"admin_sistema", "admin_plataforma", "gerencia"})


async def crear_politica_auth(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    longitud_minima_password: int,
    umbral_intentos_fallidos: int,
    ventana_minutos: int,
    bloqueo_minutos: int,
    vencimiento_dias_alto_privilegio: int | None,
    vigente_desde: datetime,
) -> dict:
    from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event

    anterior = await obtener_politica_vigente(db)

    # Write-ahead con antes/después -- lo que el dashboard de Auditoría
    # (Módulo 6.1) necesita para "comparación antes/después" sin requerir un
    # campo nuevo en EVENTO_AUDITORIA (datos_previos/datos_posteriores ya
    # existen para esto).
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.POLITICA_AUTH_CAMBIO,
        entidad="politica_auth",
        entidad_id=None,
        resultado=ResultadoAuditoria.OK,
        datos_previos=anterior,
        datos_posteriores={
            "longitud_minima_password": longitud_minima_password,
            "umbral_intentos_fallidos": umbral_intentos_fallidos,
            "ventana_minutos": ventana_minutos,
            "bloqueo_minutos": bloqueo_minutos,
            "vencimiento_dias_alto_privilegio": vencimiento_dias_alto_privilegio,
            "vigente_desde": vigente_desde.isoformat(),
        },
    )

    valores = {
        "longitud_minima_password": longitud_minima_password,
        "umbral_intentos_fallidos": umbral_intentos_fallidos,
        "ventana_minutos": ventana_minutos,
        "bloqueo_minutos": bloqueo_minutos,
        "vencimiento_dias_alto_privilegio": vencimiento_dias_alto_privilegio,
    }
    return await _crear_version(
        db, actor_id=actor_id, rol=rol, tipo=_TIPO, valores=valores, vigente_desde=vigente_desde, filtro_serie={}
    )


async def obtener_politica_vigente(db: AsyncIOMotorDatabase, *, fecha: datetime | None = None) -> dict:
    """Nunca lanza -- si no hay política publicada todavía, cae a `DEFAULTS`
    (los valores que ya regían antes de que este módulo existiera)."""
    try:
        doc = await obtener_vigente(db, tipo=_TIPO, fecha=fecha or datetime.now(UTC))
        return dict(doc["valores"])
    except ParametroNoVigenteError:
        return dict(DEFAULTS)


async def obtener_politica_documento(db: AsyncIOMotorDatabase, *, fecha: datetime | None = None) -> dict:
    """Para el endpoint GET -- igual que `obtener_politica_vigente` pero
    conserva id/vigencia; sintetiza un documento "default" (id=None,
    vigente_desde=None) cuando nunca se publicó una versión real."""
    try:
        return await obtener_vigente(db, tipo=_TIPO, fecha=fecha or datetime.now(UTC))
    except ParametroNoVigenteError:
        return {"_id": None, "valores": dict(DEFAULTS), "vigente_desde": None, "vigente_hasta": None}


# ---------------------------------------------------------------------------
# Módulo 6.2 -- políticas de seguridad transversales: TTL de tokens +
# umbrales de los 3 mecanismos de rate limiting que YA existen en el
# sistema (login, ver Módulo 1.3 arriba -- ese queda intacto; refresh y
# denegaciones RBAC, antes fijos en `auth/service.py`/`core/rbac.py`).
# Alcance recortado y APROBADO (PLAN_ADMIN_SISTEMA.md, nota de 6.2): no se
# construye un rate-limiter genérico por endpoint, solo se vuelven
# configurables los 3 mecanismos puntuales que ya existían.
# ---------------------------------------------------------------------------

_TIPO_SEGURIDAD = "seguridad"

DEFAULTS_SEGURIDAD = {
    # Antes constantes fijas en core/security.py (Settings.jwt_*).
    "access_token_minutos": 15,
    "refresh_token_dias": 30,
    # Antes constantes fijas en auth/service.py (_MAX_REFRESH_FAILURES,
    # _REFRESH_FAILURE_WINDOW_SECONDS).
    "refresh_umbral_fallos": 3,
    "refresh_ventana_minutos": 15,
    # Antes constantes fijas en core/rbac.py (_DENIAL_THRESHOLD,
    # _DENIAL_WINDOW_SECONDS, _SUSPENSION_SECONDS) -- CU-O18 A4.
    "rbac_umbral_denegaciones": 5,
    "rbac_ventana_minutos": 10,
    "rbac_suspension_minutos": 30,
}


async def crear_politica_seguridad(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    access_token_minutos: int,
    refresh_token_dias: int,
    refresh_umbral_fallos: int,
    refresh_ventana_minutos: int,
    rbac_umbral_denegaciones: int,
    rbac_ventana_minutos: int,
    rbac_suspension_minutos: int,
    vigente_desde: datetime,
) -> dict:
    from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event

    anterior = await obtener_politica_seguridad_vigente(db)

    valores = {
        "access_token_minutos": access_token_minutos,
        "refresh_token_dias": refresh_token_dias,
        "refresh_umbral_fallos": refresh_umbral_fallos,
        "refresh_ventana_minutos": refresh_ventana_minutos,
        "rbac_umbral_denegaciones": rbac_umbral_denegaciones,
        "rbac_ventana_minutos": rbac_ventana_minutos,
        "rbac_suspension_minutos": rbac_suspension_minutos,
    }

    # Write-ahead con antes/después -- "cambios aquí son de alto impacto"
    # (nota de seguridad de la spec §6.2).
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.POLITICA_SEGURIDAD_CAMBIO,
        entidad="politica_seguridad",
        entidad_id=None,
        resultado=ResultadoAuditoria.OK,
        datos_previos=anterior,
        datos_posteriores={**valores, "vigente_desde": vigente_desde.isoformat()},
    )

    return await _crear_version(
        db,
        actor_id=actor_id,
        rol=rol,
        tipo=_TIPO_SEGURIDAD,
        valores=valores,
        vigente_desde=vigente_desde,
        filtro_serie={},
    )


async def obtener_politica_seguridad_vigente(db: AsyncIOMotorDatabase, *, fecha: datetime | None = None) -> dict:
    """Nunca lanza -- sin política publicada cae a `DEFAULTS_SEGURIDAD` (los
    valores que ya regían fijos antes de este módulo)."""
    try:
        doc = await obtener_vigente(db, tipo=_TIPO_SEGURIDAD, fecha=fecha or datetime.now(UTC))
        return dict(doc["valores"])
    except ParametroNoVigenteError:
        return dict(DEFAULTS_SEGURIDAD)


async def obtener_politica_seguridad_documento(db: AsyncIOMotorDatabase, *, fecha: datetime | None = None) -> dict:
    try:
        return await obtener_vigente(db, tipo=_TIPO_SEGURIDAD, fecha=fecha or datetime.now(UTC))
    except ParametroNoVigenteError:
        return {"_id": None, "valores": dict(DEFAULTS_SEGURIDAD), "vigente_desde": None, "vigente_hasta": None}
