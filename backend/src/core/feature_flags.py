"""Feature flags — Módulo 2.2 de admin_sistema (specs/specs-administrativas/
admin_sistema.md). Formaliza el patrón de "backlog consciente" que el
proyecto ya usa (pago electrónico, chat, OTP...) como una capacidad real:
activar una función para un subconjunto de usuarios sin desplegar código
nuevo. Colección `feature_flags`, no versionada (a diferencia de
`parametros`) -- un flag es un interruptor, no una regla de negocio con
vigencia histórica.

**Alcance real (ver PLAN_ADMIN_SISTEMA.md, nota de 2.2)**: se construye el
mecanismo genérico completo (crear/activar/desactivar/consultar por rol o
porcentaje) pero no se conecta a ninguna función de negocio existente --
no hay backlog real (pago electrónico, etc.) que este módulo académico deba
cablear. `is_enabled()` es el helper listo para que un futuro módulo lo
use.
"""

import hashlib
import uuid
from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.exceptions import DomainError


class FlagNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="FLAG_NO_ENCONTRADO", message="El feature flag no existe", status_code=404)


class FlagYaExisteError(DomainError):
    def __init__(self, nombre: str) -> None:
        super().__init__(code="FLAG_YA_EXISTE", message=f"Ya existe un flag llamado '{nombre}'", status_code=409)


async def crear_flag(
    db: AsyncIOMotorDatabase, *, nombre: str, activo: bool, porcentaje: int | None, roles: list[str] | None
) -> dict:
    existente = await db.feature_flags.find_one({"nombre": nombre})
    if existente is not None:
        raise FlagYaExisteError(nombre)
    ahora = datetime.now(UTC)
    doc = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "activo": activo,
        "porcentaje": porcentaje,
        "roles": roles or [],
        "creado_en": ahora,
        "actualizado_en": ahora,
    }
    await db.feature_flags.insert_one(doc)
    return doc


async def listar_flags(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.feature_flags.find().sort("nombre", 1).to_list(length=500)


async def actualizar_flag(db: AsyncIOMotorDatabase, *, nombre: str, cambios: dict) -> dict:
    doc = await db.feature_flags.find_one({"nombre": nombre})
    if doc is None:
        raise FlagNoEncontradoError()
    cambios_con_ts = {**cambios, "actualizado_en": datetime.now(UTC)}
    await db.feature_flags.update_one({"nombre": nombre}, {"$set": cambios_con_ts})
    return await db.feature_flags.find_one({"nombre": nombre})


def _en_porcentaje(nombre: str, actor_id: str, porcentaje: int) -> bool:
    # Hash determinista actor+flag -> bucket estable 0-99, mismo patrón que
    # ya usa el proyecto para fracciones deterministas (ver
    # analytics/scripts/seed_viajes_nyc.py: "estado ~93% PAGADO... fracción
    # determinista por hash de fila") -- el mismo actor siempre cae del
    # mismo lado del corte para un flag dado, no es aleatorio por petición.
    clave = f"{nombre}:{actor_id}".encode()
    bucket = int(hashlib.sha256(clave).hexdigest(), 16) % 100
    return bucket < porcentaje


async def is_enabled(
    db: AsyncIOMotorDatabase, nombre: str, *, actor_id: str | None = None, roles: list[str] | None = None
) -> bool:
    """Consulta genérica para que un módulo de negocio futuro decida si una
    función está habilitada para este actor. Nunca lanza -- un flag
    inexistente o inactivo se trata como deshabilitado (fail-closed), nunca
    como error. Los flags nunca deben usarse como mecanismo de autorización
    (nota de seguridad de la spec) -- solo gobiernan visibilidad de
    funcionalidad, `require_roles` sigue siendo el único gate de permisos."""
    doc = await db.feature_flags.find_one({"nombre": nombre})
    if doc is None or not doc.get("activo"):
        return False
    flag_roles = doc.get("roles") or []
    if flag_roles and not (set(roles or []) & set(flag_roles)):
        return False
    porcentaje = doc.get("porcentaje")
    if porcentaje is not None and porcentaje < 100:
        if actor_id is None:
            return False
        return _en_porcentaje(nombre, actor_id, porcentaje)
    return True
