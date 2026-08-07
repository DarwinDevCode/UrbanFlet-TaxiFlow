from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth import schemas, service
from src.core.db_mongo import get_database
from src.core.rbac import Actor, get_current_actor

router = APIRouter(prefix="/auth", tags=["auth"])


def _ip_y_dispositivo(request: Request) -> tuple[str | None, str | None]:
    # Módulo 1.4 (admin_sistema): metadatos de sesión, solo informativos --
    # nunca se usan para autorización. `X-Forwarded-For` antes que
    # `request.client` porque en despliegue real el backend suele estar
    # detrás de un proxy/reverse-proxy.
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    dispositivo = request.headers.get("user-agent")
    return ip, dispositivo


@router.post("/registro", response_model=schemas.RegistroResponse, status_code=201)
async def registro(body: schemas.RegistroRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    usuario = await service.registrar_usuario(
        db, nombre=body.nombre, telefono=body.telefono, email=body.email, password=body.password
    )
    return schemas.RegistroResponse(
        usuario_id=usuario["_id"], telefono=usuario.get("telefono"), estado=usuario["estado"]
    )


@router.post("/login", response_model=schemas.TokenPair)
async def login(body: schemas.LoginRequest, request: Request, db: AsyncIOMotorDatabase = Depends(get_database)):
    ip, dispositivo = _ip_y_dispositivo(request)
    tokens = await service.login_con_password(
        db, identificador=body.identificador, password=body.password, ip=ip, dispositivo=dispositivo
    )
    return schemas.TokenPair(**tokens)


@router.post("/refresh", response_model=schemas.TokenPair)
async def refresh(body: schemas.RefreshRequest, request: Request, db: AsyncIOMotorDatabase = Depends(get_database)):
    ip, dispositivo = _ip_y_dispositivo(request)
    tokens = await service.refrescar_token(db, refresh_token=body.refresh_token, ip=ip, dispositivo=dispositivo)
    return schemas.TokenPair(**tokens)


@router.post("/cambiar-password", status_code=204)
async def cambiar_password(
    body: schemas.CambiarPasswordRequest,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.cambiar_password(
        db, usuario_id=actor.usuario_id, password_actual=body.password_actual, password_nueva=body.password_nueva
    )
