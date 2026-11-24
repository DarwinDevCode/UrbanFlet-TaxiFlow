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


class MarcaVehiculoNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="MARCA_VEHICULO_NO_ENCONTRADA", message="La marca no existe", status_code=404)


class MarcaVehiculoYaExisteError(DomainError):
    def __init__(self, nombre: str) -> None:
        super().__init__(
            code="MARCA_VEHICULO_YA_EXISTE", message=f"Ya existe una marca llamada '{nombre}'", status_code=409
        )


class ColorVehiculoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="COLOR_VEHICULO_NO_ENCONTRADO", message="El color no existe", status_code=404)


class RepuestoCatalogoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="REPUESTO_CATALOGO_NO_ENCONTRADO", message="El repuesto no existe", status_code=404)


class RepuestoCatalogoYaExisteError(DomainError):
    def __init__(self, nombre: str) -> None:
        super().__init__(
            code="REPUESTO_CATALOGO_YA_EXISTE", message=f"Ya existe un repuesto llamado '{nombre}'", status_code=409
        )


class ColorVehiculoYaExisteError(DomainError):
    def __init__(self, nombre: str) -> None:
        super().__init__(
            code="COLOR_VEHICULO_YA_EXISTE", message=f"Ya existe un color llamado '{nombre}'", status_code=409
        )


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


def _filtro_activo(incluir_inactivos: bool) -> dict:
    """Filtro base compartido por los 6 catálogos. Un solo lugar donde se
    decide qué significa "activo", para que no se escriba a mano 6 veces."""
    return {} if incluir_inactivos else {"activo": True}


async def listar_tipos_documento(db: AsyncIOMotorDatabase, *, incluir_inactivos: bool = False) -> list[dict]:
    """Ronda de personalización/QA: por defecto devuelve SOLO los activos.

    El default es "solo activos" a propósito, no "todos": un consumidor que
    se olvide del filtro termina ocultando una entrada desactivada (el
    comportamiento correcto de negocio) en vez de seguir ofreciéndola. La
    pantalla de Catálogos es el único llamador que pasa
    `incluir_inactivos=True`, porque ahí sí hay que verlos para reactivarlos.
    """
    return await db.tipos_documento.find(_filtro_activo(incluir_inactivos)).sort("nombre", 1).to_list(length=500)


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


async def listar_motivos(
    db: AsyncIOMotorDatabase, *, categoria: str | None = None, incluir_inactivos: bool = False
) -> list[dict]:
    """Ronda de personalización/QA: por defecto devuelve SOLO los activos.

    El default es "solo activos" a propósito, no "todos": un consumidor que
    se olvide del filtro termina ocultando una entrada desactivada (el
    comportamiento correcto de negocio) en vez de seguir ofreciéndola. La
    pantalla de Catálogos es el único llamador que pasa
    `incluir_inactivos=True`, porque ahí sí hay que verlos para reactivarlos.
    """
    filtro = _filtro_activo(incluir_inactivos)
    if categoria:
        filtro["categoria"] = categoria
    return await db.motivos_cancelacion.find(filtro).sort("nombre", 1).to_list(length=500)


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
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    nombre: str,
    direccion: str,
    telefono: str,
    url_maps: str | None,
    activo: bool,
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "direccion": direccion,
        "telefono": telefono,
        "url_maps": url_maps,
        "activo": activo,
    }
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


async def listar_talleres(db: AsyncIOMotorDatabase, *, incluir_inactivos: bool = False) -> list[dict]:
    """Ronda de personalización/QA: por defecto devuelve SOLO los activos.

    El default es "solo activos" a propósito, no "todos": un consumidor que
    se olvide del filtro termina ocultando una entrada desactivada (el
    comportamiento correcto de negocio) en vez de seguir ofreciéndola. La
    pantalla de Catálogos es el único llamador que pasa
    `incluir_inactivos=True`, porque ahí sí hay que verlos para reactivarlos.
    """
    return await db.talleres.find(_filtro_activo(incluir_inactivos)).sort("nombre", 1).to_list(length=500)


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


# ---------------------------------------------------------------------------
# Ronda 1 (Ola 1.5): marcas y colores de vehículo -- mismo patrón CRUD que
# tipos_documento/motivos/talleres arriba (nombre único, solo activo=False
# en vez de DELETE por la misma razón: son texto libre sin FK real en
# `vehiculos`, un rename acá no alcanza los registros históricos).
# ---------------------------------------------------------------------------


async def crear_marca_vehiculo(db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, nombre: str, activo: bool) -> dict:
    doc = {"_id": str(uuid.uuid4()), "nombre": nombre, "activo": activo}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_CREACION,
        entidad="marcas_vehiculo",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre},
    )
    try:
        await db.marcas_vehiculo.insert_one(doc)
    except DuplicateKeyError as exc:
        raise MarcaVehiculoYaExisteError(nombre) from exc
    return doc


async def listar_marcas_vehiculo(db: AsyncIOMotorDatabase, *, incluir_inactivos: bool = False) -> list[dict]:
    """Ronda de personalización/QA: por defecto devuelve SOLO los activos.

    El default es "solo activos" a propósito, no "todos": un consumidor que
    se olvide del filtro termina ocultando una entrada desactivada (el
    comportamiento correcto de negocio) en vez de seguir ofreciéndola. La
    pantalla de Catálogos es el único llamador que pasa
    `incluir_inactivos=True`, porque ahí sí hay que verlos para reactivarlos.
    """
    return await db.marcas_vehiculo.find(_filtro_activo(incluir_inactivos)).sort("nombre", 1).to_list(length=500)


async def editar_marca_vehiculo(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, marca_id: str, cambios: dict
) -> dict:
    anterior = await db.marcas_vehiculo.find_one({"_id": marca_id})
    if anterior is None:
        raise MarcaVehiculoNoEncontradaError()
    if not cambios:
        return anterior

    antes = {k: anterior.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_EDICION,
        entidad="marcas_vehiculo",
        entidad_id=marca_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.marcas_vehiculo.update_one({"_id": marca_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        raise MarcaVehiculoYaExisteError(cambios.get("nombre", "")) from exc
    return await db.marcas_vehiculo.find_one({"_id": marca_id})


async def crear_color_vehiculo(db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, nombre: str, activo: bool) -> dict:
    doc = {"_id": str(uuid.uuid4()), "nombre": nombre, "activo": activo}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_CREACION,
        entidad="colores_vehiculo",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre},
    )
    try:
        await db.colores_vehiculo.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ColorVehiculoYaExisteError(nombre) from exc
    return doc


async def listar_colores_vehiculo(db: AsyncIOMotorDatabase, *, incluir_inactivos: bool = False) -> list[dict]:
    """Ronda de personalización/QA: por defecto devuelve SOLO los activos.

    El default es "solo activos" a propósito, no "todos": un consumidor que
    se olvide del filtro termina ocultando una entrada desactivada (el
    comportamiento correcto de negocio) en vez de seguir ofreciéndola. La
    pantalla de Catálogos es el único llamador que pasa
    `incluir_inactivos=True`, porque ahí sí hay que verlos para reactivarlos.
    """
    return await db.colores_vehiculo.find(_filtro_activo(incluir_inactivos)).sort("nombre", 1).to_list(length=500)


async def editar_color_vehiculo(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, color_id: str, cambios: dict
) -> dict:
    anterior = await db.colores_vehiculo.find_one({"_id": color_id})
    if anterior is None:
        raise ColorVehiculoNoEncontradoError()
    if not cambios:
        return anterior

    antes = {k: anterior.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_EDICION,
        entidad="colores_vehiculo",
        entidad_id=color_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.colores_vehiculo.update_one({"_id": color_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        raise ColorVehiculoYaExisteError(cambios.get("nombre", "")) from exc
    return await db.colores_vehiculo.find_one({"_id": color_id})


# ---------------------------------------------------------------------------
# Ola 3 de PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md (§3.2): repuestos --
# mismo patrón CRUD (nombre único, solo activo=False en vez de DELETE) que
# el resto del módulo.
# ---------------------------------------------------------------------------


async def crear_repuesto(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    nombre: str,
    categoria: str,
    precio_referencial: float,
    unidad: str,
    activo: bool,
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "categoria": categoria,
        "precio_referencial": precio_referencial,
        "unidad": unidad,
        "activo": activo,
    }
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_CREACION,
        entidad="repuestos",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre, "categoria": categoria},
    )
    try:
        await db.repuestos.insert_one(doc)
    except DuplicateKeyError as exc:
        raise RepuestoCatalogoYaExisteError(nombre) from exc
    return doc


async def listar_repuestos(db: AsyncIOMotorDatabase, *, incluir_inactivos: bool = False) -> list[dict]:
    """Ronda de personalización/QA: por defecto devuelve SOLO los activos.

    El default es "solo activos" a propósito, no "todos": un consumidor que
    se olvide del filtro termina ocultando una entrada desactivada (el
    comportamiento correcto de negocio) en vez de seguir ofreciéndola. La
    pantalla de Catálogos es el único llamador que pasa
    `incluir_inactivos=True`, porque ahí sí hay que verlos para reactivarlos.
    """
    return await db.repuestos.find(_filtro_activo(incluir_inactivos)).sort("nombre", 1).to_list(length=500)


async def editar_repuesto(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, repuesto_id: str, cambios: dict
) -> dict:
    anterior = await db.repuestos.find_one({"_id": repuesto_id})
    if anterior is None:
        raise RepuestoCatalogoNoEncontradoError()
    if not cambios:
        return anterior

    antes = {k: anterior.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.CATALOGO_EDICION,
        entidad="repuestos",
        entidad_id=repuesto_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.repuestos.update_one({"_id": repuesto_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        raise RepuestoCatalogoYaExisteError(cambios.get("nombre", "")) from exc
    return await db.repuestos.find_one({"_id": repuesto_id})
