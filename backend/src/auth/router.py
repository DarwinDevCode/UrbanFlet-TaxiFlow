from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auth import schemas, service
from src.core.db_mongo import get_database

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registro", response_model=schemas.RegistroResponse, status_code=201)
async def registro(body: schemas.RegistroRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    usuario = await service.registrar_usuario(
        db, nombre=body.nombre, telefono=body.telefono, email=body.email, password=body.password
    )
    return schemas.RegistroResponse(
        usuario_id=usuario["_id"], telefono=usuario.get("telefono"), estado=usuario["estado"]
    )


@router.post("/login", response_model=schemas.TokenPair)
async def login(body: schemas.LoginRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    tokens = await service.login_con_password(db, identificador=body.identificador, password=body.password)
    return schemas.TokenPair(**tokens)


@router.post("/refresh", response_model=schemas.TokenPair)
async def refresh(body: schemas.RefreshRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    tokens = await service.refrescar_token(db, refresh_token=body.refresh_token)
    return schemas.TokenPair(**tokens)
