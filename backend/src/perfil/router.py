from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, get_current_actor
from src.perfil import schemas, service

router = APIRouter(prefix="/perfil", tags=["perfil"])


def _to_out(u: dict) -> schemas.PerfilOut:
    return schemas.PerfilOut(
        id=u["_id"],
        nombre=u["nombre"],
        telefono=u.get("telefono"),
        email=u.get("email"),
        roles=u.get("roles", []),
        fecha_registro=u["fecha_registro"],
        foto_url=(u.get("conductor") or {}).get("foto_url"),
    )


@router.get("", response_model=schemas.PerfilOut)
async def obtener(actor: Actor = Depends(get_current_actor), db: AsyncIOMotorDatabase = Depends(get_database)):
    usuario = await service.obtener_perfil(db, actor.usuario_id)
    return _to_out(usuario)


@router.patch("", response_model=schemas.PerfilOut)
async def editar(
    body: schemas.PerfilEditar,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True, exclude={"password_actual"})
    usuario = await service.editar_perfil(
        db, usuario_id=actor.usuario_id, roles=actor.roles, cambios=cambios, password_actual=body.password_actual
    )
    return _to_out(usuario)


@router.get("/sesiones", response_model=list[schemas.SesionOut])
async def sesiones(actor: Actor = Depends(get_current_actor)):
    activas = await service.listar_sesiones_propias(actor.usuario_id)
    return [schemas.SesionOut(**s) for s in activas]


@router.delete("/sesiones/{jti}", status_code=204)
async def cerrar_sesion(
    jti: str, actor: Actor = Depends(get_current_actor), db: AsyncIOMotorDatabase = Depends(get_database)
):
    await service.revocar_sesion_propia(db, usuario_id=actor.usuario_id, roles=actor.roles, jti=jti)
