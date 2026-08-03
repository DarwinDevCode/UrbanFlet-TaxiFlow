from datetime import datetime, UTC
from typing import Literal

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.parametros import schemas, service

router = APIRouter(prefix="/parametros", tags=["parametros"])

# Solo quienes administran la plataforma o la junta (gerencia) pueden cambiar
# tarifas/comisión — son "reglas de dinero y estado" (línea 123 arquitectura).
_puede_escribir_parametros = require_roles("admin_plataforma", "gerencia")


def _to_out(doc: dict) -> schemas.ParametroOut:
    return schemas.ParametroOut(
        id=doc["_id"],
        tipo=doc["tipo"],
        valores=doc["valores"],
        vigente_desde=doc["vigente_desde"],
        vigente_hasta=doc["vigente_hasta"],
    )


@router.post("/tarifas", response_model=schemas.ParametroOut, status_code=201)
async def crear_tarifa(
    body: schemas.ParametroTarifaCreate,
    actor: Actor = Depends(_puede_escribir_parametros),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_parametro_tarifa(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        franja=body.franja,
        arrancada=body.arrancada,
        costo_km=body.costo_km,
        costo_min_espera=body.costo_min_espera,
        carrera_minima=body.carrera_minima,
        vigente_desde=body.vigente_desde,
    )
    return _to_out(doc)


@router.post("/comisiones", response_model=schemas.ParametroOut, status_code=201)
async def crear_comision(
    body: schemas.ParametroComisionCreate,
    actor: Actor = Depends(_puede_escribir_parametros),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_parametro_comision(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        porcentaje=body.porcentaje,
        vigente_desde=body.vigente_desde,
    )
    return _to_out(doc)


@router.get("/vigente", response_model=schemas.ParametroOut)
async def obtener_vigente(
    tipo: Literal["tarifa", "comision"],
    franja: Literal["DIURNA", "NOCTURNA"] | None = None,
    fecha: datetime | None = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.obtener_vigente(db, tipo=tipo, fecha=fecha or datetime.now(UTC), franja=franja)
    return _to_out(doc)


@router.post("/zonas", response_model=schemas.ZonaOut, status_code=201)
async def crear_zona(
    body: schemas.ZonaCreate,
    actor: Actor = Depends(_puede_escribir_parametros),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_zona(db, nombre=body.nombre, geometria=body.geometria)
    return schemas.ZonaOut(id=doc["_id"], nombre=doc["nombre"], geometria=doc["geometria"])


@router.get("/zonas", response_model=list[schemas.ZonaOut])
async def listar_zonas(db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await service.listar_zonas(db)
    return [schemas.ZonaOut(id=d["_id"], nombre=d["nombre"], geometria=d["geometria"]) for d in docs]
