from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.catalogos import schemas, service
from src.core.db_mongo import get_database
from src.core.rbac import Actor, get_current_actor, require_roles

router = APIRouter(prefix="/catalogos", tags=["catalogos"])

# Escritura sigue siendo alto privilegio, exclusiva de admin_sistema (misma
# disciplina que Módulos 1 y 2) -- sin cambios respecto a como estaba.
_admin_sistema = require_roles("admin_sistema")

# Ronda 1 de catálogos (Ola 0.1): lectura abierta a cualquier actor
# autenticado -- antes los 6 endpoints, incluidos los GET, estaban
# gateados en exclusiva a admin_sistema, así que ni siquiera
# jefe_mantenimiento podía leer la lista de talleres (403 real, confirmado
# en la auditoría). Un catálogo de referencia (nombres de talleres, tipos
# de documento, motivos) no es información sensible -- mismo criterio que
# ya usa GET /parametros/zonas (parametros/router.py), que tampoco exige
# rol. No se abre sin autenticar del todo acá porque estos 3 catálogos
# solo los consumen pantallas ya logueadas (a diferencia de
# marcas_vehiculo/colores_vehiculo, ver abajo, que sí necesitan ser
# públicos para el formulario de postulación sin sesión).
_cualquier_actor = get_current_actor


def _tipo_to_out(doc: dict) -> schemas.TipoDocumentoOut:
    return schemas.TipoDocumentoOut(
        id=doc["_id"], nombre=doc["nombre"], descripcion=doc.get("descripcion", ""),
        aplica_a=doc["aplica_a"], activo=doc["activo"],
    )


def _motivo_to_out(doc: dict) -> schemas.MotivoOut:
    return schemas.MotivoOut(
        id=doc["_id"], nombre=doc["nombre"], descripcion=doc.get("descripcion", ""),
        categoria=doc["categoria"], activo=doc["activo"],
    )


def _taller_to_out(doc: dict) -> schemas.TallerOut:
    return schemas.TallerOut(
        id=doc["_id"], nombre=doc["nombre"], direccion=doc.get("direccion", ""),
        telefono=doc.get("telefono", ""), url_maps=doc.get("url_maps"), activo=doc["activo"],
    )


def _marca_to_out(doc: dict) -> schemas.MarcaVehiculoOut:
    return schemas.MarcaVehiculoOut(id=doc["_id"], nombre=doc["nombre"], activo=doc["activo"])


def _color_to_out(doc: dict) -> schemas.ColorVehiculoOut:
    return schemas.ColorVehiculoOut(id=doc["_id"], nombre=doc["nombre"], activo=doc["activo"])


def _repuesto_to_out(doc: dict) -> schemas.RepuestoCatalogoOut:
    return schemas.RepuestoCatalogoOut(
        id=doc["_id"],
        nombre=doc["nombre"],
        categoria=doc["categoria"],
        precio_referencial=doc["precio_referencial"],
        unidad=doc["unidad"],
        activo=doc["activo"],
    )


@router.get("/tipos-documento", response_model=list[schemas.TipoDocumentoOut])
async def listar_tipos_documento(
    incluir_inactivos: bool = False,
    actor: Actor = Depends(_cualquier_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    docs = await service.listar_tipos_documento(db, incluir_inactivos=incluir_inactivos)
    return [_tipo_to_out(d) for d in docs]


@router.post("/tipos-documento", response_model=schemas.TipoDocumentoOut, status_code=201)
async def crear_tipo_documento(
    body: schemas.TipoDocumentoCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_tipo_documento(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre,
        descripcion=body.descripcion, aplica_a=body.aplica_a, activo=body.activo,
    )
    return _tipo_to_out(doc)


@router.patch("/tipos-documento/{tipo_id}", response_model=schemas.TipoDocumentoOut)
async def editar_tipo_documento(
    tipo_id: str,
    body: schemas.TipoDocumentoEditar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    doc = await service.editar_tipo_documento(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), tipo_id=tipo_id, cambios=cambios
    )
    return _tipo_to_out(doc)


@router.get("/motivos", response_model=list[schemas.MotivoOut])
async def listar_motivos(
    categoria: str | None = None,
    incluir_inactivos: bool = False,
    actor: Actor = Depends(_cualquier_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # `categoria` filtra en servidor (no solo en el cliente) -- lo consumen
    # tanto la pantalla de administración (sin filtro, ve las 2 categorías)
    # como los selectores de cancelación de conductor/pasajero (Ola 1.3/1.4,
    # que solo necesitan `categoria=cancelacion`).
    docs = await service.listar_motivos(db, categoria=categoria, incluir_inactivos=incluir_inactivos)
    return [_motivo_to_out(d) for d in docs]


@router.post("/motivos", response_model=schemas.MotivoOut, status_code=201)
async def crear_motivo(
    body: schemas.MotivoCreate, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await service.crear_motivo(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre,
        descripcion=body.descripcion, categoria=body.categoria, activo=body.activo,
    )
    return _motivo_to_out(doc)


@router.patch("/motivos/{motivo_id}", response_model=schemas.MotivoOut)
async def editar_motivo(
    motivo_id: str,
    body: schemas.MotivoEditar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    doc = await service.editar_motivo(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), motivo_id=motivo_id, cambios=cambios
    )
    return _motivo_to_out(doc)


@router.get("/talleres", response_model=list[schemas.TallerOut])
async def listar_talleres(
    incluir_inactivos: bool = False,
    actor: Actor = Depends(_cualquier_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    docs = await service.listar_talleres(db, incluir_inactivos=incluir_inactivos)
    return [_taller_to_out(d) for d in docs]


@router.post("/talleres", response_model=schemas.TallerOut, status_code=201)
async def crear_taller(
    body: schemas.TallerCreate, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await service.crear_taller(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre,
        direccion=body.direccion, telefono=body.telefono, url_maps=body.url_maps, activo=body.activo,
    )
    return _taller_to_out(doc)


@router.patch("/talleres/{taller_id}", response_model=schemas.TallerOut)
async def editar_taller(
    taller_id: str,
    body: schemas.TallerEditar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    doc = await service.editar_taller(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), taller_id=taller_id, cambios=cambios
    )
    return _taller_to_out(doc)


# ---------------------------------------------------------------------------
# Ronda 1 (Ola 1.5): marcas/colores de vehículo. GET público (sin Depends de
# actor) -- a diferencia de los 3 catálogos de arriba, el único consumidor
# real es el formulario de postulación de web-conductor, que es público
# (sin sesión, CU-O01). Mismo criterio que GET /parametros/zonas.
# ---------------------------------------------------------------------------


@router.get("/marcas-vehiculo", response_model=list[schemas.MarcaVehiculoOut])
async def listar_marcas_vehiculo(
    incluir_inactivos: bool = False, db: AsyncIOMotorDatabase = Depends(get_database)
):
    docs = await service.listar_marcas_vehiculo(db, incluir_inactivos=incluir_inactivos)
    return [_marca_to_out(d) for d in docs]


@router.post("/marcas-vehiculo", response_model=schemas.MarcaVehiculoOut, status_code=201)
async def crear_marca_vehiculo(
    body: schemas.MarcaVehiculoCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_marca_vehiculo(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre, activo=body.activo
    )
    return _marca_to_out(doc)


@router.patch("/marcas-vehiculo/{marca_id}", response_model=schemas.MarcaVehiculoOut)
async def editar_marca_vehiculo(
    marca_id: str,
    body: schemas.MarcaVehiculoEditar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    doc = await service.editar_marca_vehiculo(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), marca_id=marca_id, cambios=cambios
    )
    return _marca_to_out(doc)


@router.get("/colores-vehiculo", response_model=list[schemas.ColorVehiculoOut])
async def listar_colores_vehiculo(
    incluir_inactivos: bool = False, db: AsyncIOMotorDatabase = Depends(get_database)
):
    docs = await service.listar_colores_vehiculo(db, incluir_inactivos=incluir_inactivos)
    return [_color_to_out(d) for d in docs]


@router.post("/colores-vehiculo", response_model=schemas.ColorVehiculoOut, status_code=201)
async def crear_color_vehiculo(
    body: schemas.ColorVehiculoCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_color_vehiculo(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre, activo=body.activo
    )
    return _color_to_out(doc)


@router.patch("/colores-vehiculo/{color_id}", response_model=schemas.ColorVehiculoOut)
async def editar_color_vehiculo(
    color_id: str,
    body: schemas.ColorVehiculoEditar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    doc = await service.editar_color_vehiculo(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), color_id=color_id, cambios=cambios
    )
    return _color_to_out(doc)


# ---------------------------------------------------------------------------
# Ola 3 de PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md (§3.2): repuestos --
# lectura abierta a cualquier actor autenticado (mismo criterio que
# talleres/tipos_documento/motivos, no público como marca/color: el único
# consumidor es Mantenimiento.tsx, una pantalla ya logueada).
# ---------------------------------------------------------------------------


@router.get("/repuestos", response_model=list[schemas.RepuestoCatalogoOut])
async def listar_repuestos(
    incluir_inactivos: bool = False,
    actor: Actor = Depends(_cualquier_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    docs = await service.listar_repuestos(db, incluir_inactivos=incluir_inactivos)
    return [_repuesto_to_out(d) for d in docs]


@router.post("/repuestos", response_model=schemas.RepuestoCatalogoOut, status_code=201)
async def crear_repuesto(
    body: schemas.RepuestoCatalogoCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_repuesto(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        nombre=body.nombre,
        categoria=body.categoria,
        precio_referencial=body.precio_referencial,
        unidad=body.unidad,
        activo=body.activo,
    )
    return _repuesto_to_out(doc)


@router.patch("/repuestos/{repuesto_id}", response_model=schemas.RepuestoCatalogoOut)
async def editar_repuesto(
    repuesto_id: str,
    body: schemas.RepuestoCatalogoEditar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    doc = await service.editar_repuesto(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), repuesto_id=repuesto_id, cambios=cambios
    )
    return _repuesto_to_out(doc)
