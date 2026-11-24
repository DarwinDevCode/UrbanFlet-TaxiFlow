from datetime import datetime, UTC
from typing import Literal

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.core.tiempo import como_utc
from src.parametros import schemas, service

router = APIRouter(prefix="/parametros", tags=["parametros"])

# Solo quienes administran la plataforma o la junta (gerencia) pueden cambiar
# tarifas/comisión — son "reglas de dinero y estado" (línea 123 arquitectura).
_puede_escribir_parametros = require_roles("admin_plataforma", "gerencia")

def _to_out(doc: dict) -> schemas.ParametroOut:
    # Bug real encontrado al construir la pantalla de comisión (nunca antes
    # detectado: ningún frontend mostraba `vigente_desde` hasta ahora): Mongo
    # devuelve datetime naive (BSON no guarda tzinfo), y Pydantic serializa
    # un datetime naive SIN sufijo de zona -- el navegador entonces lo
    # interpreta como hora LOCAL, no UTC, y desplaza la fecha mostrada por el
    # offset del usuario. Mismo gotcha ya conocido en el resto del proyecto,
    # mismo helper de siempre (`como_utc`).
    return schemas.ParametroOut(
        id=doc["_id"],
        tipo=doc["tipo"],
        valores=doc["valores"],
        vigente_desde=como_utc(doc["vigente_desde"]),
        vigente_hasta=como_utc(doc["vigente_hasta"]) if doc["vigente_hasta"] is not None else None,
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


# Historial de versiones -- a diferencia de `/vigente` (sin gate, la usa el
# estimador de tarifa del pasajero sin sesión), esto revela cómo cambió un
# parámetro de dinero en el tiempo: mismo criterio de "reglas de dinero y
# estado" que la escritura, gateado a los mismos 2 roles.
@router.get("/historial", response_model=list[schemas.ParametroOut])
async def listar_historial(
    tipo: Literal["tarifa", "comision"],
    franja: Literal["DIURNA", "NOCTURNA"] | None = None,
    actor: Actor = Depends(_puede_escribir_parametros),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    docs = await service.listar_historial(db, tipo=tipo, franja=franja)
    return [_to_out(d) for d in docs]


