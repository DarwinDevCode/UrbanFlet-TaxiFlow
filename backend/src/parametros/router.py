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

# Módulo 3.1 de admin_sistema (specs/specs-administrativas/admin_sistema.md):
# gestión de catálogos -- zonas ya vivía en este router (creado antes de que
# existiera el paquete de Administración del Sistema), así que se extiende
# el acceso de escritura a `admin_sistema` en vez de duplicar un segundo
# CRUD de zonas en otro módulo. Deliberadamente separado de
# `_puede_escribir_parametros` (tarifa/comisión) -- admin_sistema no debe
# poder tocar reglas de dinero, solo el catálogo de zonas.
_puede_gestionar_zonas = require_roles("admin_plataforma", "gerencia", "admin_sistema")


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


def _zona_to_out(doc: dict) -> schemas.ZonaOut:
    return schemas.ZonaOut(id=doc["_id"], nombre=doc["nombre"], geometria=doc["geometria"])


@router.post("/zonas", response_model=schemas.ZonaOut, status_code=201)
async def crear_zona(
    body: schemas.ZonaCreate,
    actor: Actor = Depends(_puede_gestionar_zonas),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_zona(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), nombre=body.nombre, geometria=body.geometria
    )
    return _zona_to_out(doc)


@router.get("/zonas", response_model=list[schemas.ZonaOut])
async def listar_zonas(db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await service.listar_zonas(db)
    return [_zona_to_out(d) for d in docs]


@router.patch("/zonas/{zona_id}", response_model=schemas.ZonaOut)
async def editar_zona(
    zona_id: str,
    body: schemas.ZonaCreate,
    actor: Actor = Depends(_puede_gestionar_zonas),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.editar_zona(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        zona_id=zona_id,
        nombre=body.nombre,
        geometria=body.geometria,
    )
    return _zona_to_out(doc)


@router.delete("/zonas/{zona_id}", status_code=204)
async def eliminar_zona(
    zona_id: str,
    actor: Actor = Depends(_puede_gestionar_zonas),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await service.eliminar_zona(db, actor_id=actor.usuario_id, rol=",".join(actor.roles), zona_id=zona_id)
