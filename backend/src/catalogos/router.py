from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.catalogos import schemas, service
from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles

router = APIRouter(prefix="/catalogos", tags=["catalogos"])

# Módulo 3 es de alto privilegio -- exclusivo de admin_sistema, sin roles
# combinados (misma disciplina que Módulos 1 y 2).
_admin_sistema = require_roles("admin_sistema")


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
        telefono=doc.get("telefono", ""), activo=doc["activo"],
    )


@router.get("/tipos-documento", response_model=list[schemas.TipoDocumentoOut])
async def listar_tipos_documento(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    docs = await service.listar_tipos_documento(db)
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
async def listar_motivos(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await service.listar_motivos(db)
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
async def listar_talleres(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await service.listar_talleres(db)
    return [_taller_to_out(d) for d in docs]


@router.post("/talleres", response_model=schemas.TallerOut, status_code=201)
async def crear_taller(
    body: schemas.TallerCreate, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await service.crear_taller(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre,
        direccion=body.direccion, telefono=body.telefono, activo=body.activo,
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
