from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, get_current_actor
from src.preferencias import schemas, service

router = APIRouter(prefix="/preferencias", tags=["preferencias"])


@router.get("", response_model=schemas.PreferenciasOut)
async def obtener(actor: Actor = Depends(get_current_actor), db: AsyncIOMotorDatabase = Depends(get_database)):
    datos = await service.obtener_preferencias(db, actor.usuario_id)
    return schemas.PreferenciasOut(**datos)


@router.patch("", response_model=schemas.PreferenciasOut)
async def editar(
    body: schemas.PreferenciasEditar,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    datos = await service.actualizar_preferencias(db, usuario_id=actor.usuario_id, cambios=cambios)
    return schemas.PreferenciasOut(**datos)
