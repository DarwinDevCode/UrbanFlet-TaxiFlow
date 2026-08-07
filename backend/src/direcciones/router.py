from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.direcciones import schemas, service

router = APIRouter(prefix="/direcciones", tags=["direcciones"])

_pasajero = require_roles("pasajero")


def _to_out(doc: dict) -> schemas.DireccionOut:
    return schemas.DireccionOut(
        id=doc["_id"], etiqueta=doc["etiqueta"], direccion=doc["direccion"], lat=doc["lat"], lon=doc["lon"]
    )


@router.get("", response_model=list[schemas.DireccionOut])
async def listar(actor: Actor = Depends(_pasajero), db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await service.listar_direcciones(db, actor.usuario_id)
    return [_to_out(d) for d in docs]


@router.post("", response_model=schemas.DireccionOut, status_code=201)
async def crear(
    body: schemas.DireccionCreate, actor: Actor = Depends(_pasajero), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await service.crear_direccion(
        db, usuario_id=actor.usuario_id, etiqueta=body.etiqueta, direccion=body.direccion, lat=body.lat, lon=body.lon
    )
    return _to_out(doc)


@router.delete("/{direccion_id}", status_code=204)
async def eliminar(
    direccion_id: str, actor: Actor = Depends(_pasajero), db: AsyncIOMotorDatabase = Depends(get_database)
):
    await service.eliminar_direccion(db, usuario_id=actor.usuario_id, direccion_id=direccion_id)
