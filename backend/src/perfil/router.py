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
        foto_url=u.get("foto_url"),
        baja_solicitada_en=u.get("baja_solicitada_en"),
        baja_efectiva_en=u.get("baja_efectiva_en"),
        dias_restantes_baja=service.dias_restantes_de_baja(u),
        vehiculos_a_retirar=u.get("vehiculos_a_retirar", []),
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


@router.patch("/foto", response_model=schemas.PerfilOut)
async def editar_foto(
    body: schemas.PerfilFotoEditar,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    usuario = await service.editar_foto_perfil(
        db, usuario_id=actor.usuario_id, roles=actor.roles, archivo_id=body.archivo_id
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


# ---------------------------------------------------------------------------
# Autoservicio de baja de cuenta (periodo de gracia de 30 días).
# ---------------------------------------------------------------------------


@router.post("/baja-cuenta", response_model=schemas.PerfilOut)
async def solicitar_baja_cuenta(
    body: schemas.SolicitarBajaCuentaRequest,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Inicia el cierre voluntario de la PROPIA cuenta. `actor.usuario_id`
    siempre -- nunca un id que venga del cliente: nadie puede solicitar la
    baja de la cuenta de otra persona por este canal (para eso está la baja
    administrativa del Módulo 1, con su propio gate de rol)."""
    usuario = await service.solicitar_baja_cuenta(db, usuario_id=actor.usuario_id, motivo=body.motivo)
    return _to_out(usuario)


@router.delete("/baja-cuenta", response_model=schemas.PerfilOut)
async def cancelar_baja_cuenta(
    actor: Actor = Depends(get_current_actor), db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Cancela la baja en curso. Sin cuerpo ni confirmación extra: el titular
    ya confirmó al solicitarla, arrepentirse no debe costar más que un clic."""
    usuario = await service.cancelar_baja_cuenta(db, usuario_id=actor.usuario_id)
    return _to_out(usuario)
