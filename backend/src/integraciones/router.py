from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.integraciones import schemas, service

router = APIRouter(prefix="/integraciones", tags=["integraciones"])

# Módulo 4 es de alto privilegio -- exclusivo de admin_sistema, sin roles
# combinados (misma disciplina que el resto de módulos de admin_sistema).
_admin_sistema = require_roles("admin_sistema")


def _credencial_to_out(doc: dict) -> schemas.CredencialOut:
    return schemas.CredencialOut(
        id=doc["_id"], nombre=doc["nombre"], alcance=doc.get("alcance", ""),
        vigente_desde=doc["vigente_desde"], vigente_hasta=doc["vigente_hasta"],
        revocada=doc["revocada"], usos_registrados=doc.get("usos_registrados", 0),
    )


@router.post("/credenciales", response_model=schemas.CredencialCreadaOut, status_code=201)
async def crear_credencial(
    body: schemas.CredencialCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc, secreto = await service.crear_credencial(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre, alcance=body.alcance
    )
    return schemas.CredencialCreadaOut(
        id=doc["_id"], nombre=doc["nombre"], secreto=secreto, alcance=doc["alcance"], vigente_desde=doc["vigente_desde"]
    )


@router.get("/credenciales", response_model=list[schemas.CredencialOut])
async def listar_credenciales(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await service.listar_credenciales(db)
    return [_credencial_to_out(d) for d in docs]


@router.post("/credenciales/{credencial_id}/revocar", response_model=schemas.CredencialOut)
async def revocar_credencial(
    credencial_id: str,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.revocar_credencial(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), credencial_id=credencial_id
    )
    return _credencial_to_out(doc)


@router.get("/servicios-externos", response_model=list[schemas.ServicioExternoOut])
async def listar_servicios_externos(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await service.listar_servicios_externos(db)


@router.post("/servicios-externos/google_maps/rotar", response_model=schemas.ServicioExternoOut)
async def rotar_google_maps_key(
    body: schemas.RotarKeyRequest,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await service.rotar_google_maps_key(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), api_key=body.api_key
    )
