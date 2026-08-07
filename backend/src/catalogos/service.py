"""Catálogos de tipos de documento y motivos de cancelación/incidencia —
Módulo 3.2/3.3 de admin_sistema (specs/specs-administrativas/
admin_sistema.md). Ambos son taxonomías de referencia puras hoy:
`documentos.tipo` (captacion/cumplimiento) y `viajes.motivo_cancelacion`
son texto libre sin FK, así que este CRUD gestiona el catálogo, no migra
los datos ya existentes a claves foráneas (confirmado explícitamente en
PLAN_ADMIN_SISTEMA.md antes de construir esto).

Sin DELETE: a diferencia de zonas (que sí tiene DELETE con guardia de "en
uso"), estos dos catálogos solo se desactivan (`activo=False`) -- no hay
forma de saber con certeza si un nombre histórico en `documentos.tipo` o
`viajes.motivo_cancelacion` sigue "en uso" (son texto libre, un rename acá
no los alcanza), así que desactivar es la única operación segura y
reversible.
"""

import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.exceptions import DomainError


class TipoDocumentoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="TIPO_DOCUMENTO_NO_ENCONTRADO", message="El tipo de documento no existe", status_code=404)


class TipoDocumentoYaExisteError(DomainError):
    def __init__(self, nombre: str) -> None:
        mensaje = f"Ya existe un tipo de documento llamado '{nombre}'"
        super().__init__(code="TIPO_DOCUMENTO_YA_EXISTE", message=mensaje, status_code=409)


class MotivoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="MOTIVO_NO_ENCONTRADO", message="El motivo no existe", status_code=404)


class MotivoYaExisteError(DomainError):
    def __init__(self, nombre: str) -> None:
        super().__init__(code="MOTIVO_YA_EXISTE", message=f"Ya existe un motivo llamado '{nombre}'", status_code=409)


class TallerNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="TALLER_NO_ENCONTRADO", message="El taller no existe", status_code=404)


class TallerYaExisteError(DomainError):
    def __init__(self, nombre: str) -> None:
        super().__init__(code="TALLER_YA_EXISTE", message=f"Ya existe un taller llamado '{nombre}'", status_code=409)


async def crear_tipo_documento(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, nombre: str, descripcion: str, aplica_a: str, activo: bool
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()), "nombre": nombre, "descripcion": descripcion, "aplica_a": aplica_a, "activo": activo
    }
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_CREACION,
        entidad="tipos_documento",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre, "aplica_a": aplica_a},
    )
    try:
        await db.tipos_documento.insert_one(doc)
    except DuplicateKeyError as exc:
        raise TipoDocumentoYaExisteError(nombre) from exc
    return doc


async def listar_tipos_documento(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.tipos_documento.find().sort("nombre", 1).to_list(length=500)


async def editar_tipo_documento(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, tipo_id: str, cambios: dict
) -> dict:
    anterior = await db.tipos_documento.find_one({"_id": tipo_id})
    if anterior is None:
        raise TipoDocumentoNoEncontradoError()
    if not cambios:
        return anterior

    antes = {k: anterior.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_EDICION,
        entidad="tipos_documento",
        entidad_id=tipo_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.tipos_documento.update_one({"_id": tipo_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        raise TipoDocumentoYaExisteError(cambios.get("nombre", "")) from exc
    return await db.tipos_documento.find_one({"_id": tipo_id})


async def crear_motivo(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, nombre: str, descripcion: str, categoria: str, activo: bool
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()), "nombre": nombre, "descripcion": descripcion, "categoria": categoria, "activo": activo
    }
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_CREACION,
        entidad="motivos_cancelacion",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre, "categoria": categoria},
    )
    try:
        await db.motivos_cancelacion.insert_one(doc)
    except DuplicateKeyError as exc:
        raise MotivoYaExisteError(nombre) from exc
    return doc


async def listar_motivos(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.motivos_cancelacion.find().sort("nombre", 1).to_list(length=500)


async def editar_motivo(db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, motivo_id: str, cambios: dict) -> dict:
    anterior = await db.motivos_cancelacion.find_one({"_id": motivo_id})
    if anterior is None:
        raise MotivoNoEncontradoError()
    if not cambios:
        return anterior

    antes = {k: anterior.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_EDICION,
        entidad="motivos_cancelacion",
        entidad_id=motivo_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.motivos_cancelacion.update_one({"_id": motivo_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        raise MotivoYaExisteError(cambios.get("nombre", "")) from exc
    return await db.motivos_cancelacion.find_one({"_id": motivo_id})


async def crear_taller(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, nombre: str, direccion: str, telefono: str, activo: bool
) -> dict:
    doc = {"_id": str(uuid.uuid4()), "nombre": nombre, "direccion": direccion, "telefono": telefono, "activo": activo}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_CREACION,
        entidad="talleres",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre},
    )
    try:
        await db.talleres.insert_one(doc)
    except DuplicateKeyError as exc:
        raise TallerYaExisteError(nombre) from exc
    return doc


async def listar_talleres(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.talleres.find().sort("nombre", 1).to_list(length=500)


async def editar_taller(db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, taller_id: str, cambios: dict) -> dict:
    anterior = await db.talleres.find_one({"_id": taller_id})
    if anterior is None:
        raise TallerNoEncontradoError()
    if not cambios:
        return anterior

    antes = {k: anterior.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_EDICION,
        entidad="talleres",
        entidad_id=taller_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.talleres.update_one({"_id": taller_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        raise TallerYaExisteError(cambios.get("nombre", "")) from exc
    return await db.talleres.find_one({"_id": taller_id})
