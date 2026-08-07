from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.sistema import schemas, service

router = APIRouter(prefix="/sistema", tags=["sistema"])

# "Esta información no debe ser pública fuera del rol administrativo --
# revela detalles de la pila tecnológica útiles para un atacante" (nota de
# seguridad de la spec, Módulo 8.1).
_admin_sistema = require_roles("admin_sistema")


def _despliegue_to_out(doc: dict) -> schemas.DespliegueOut:
    return schemas.DespliegueOut(
        id=doc["_id"], componente=doc["componente"], version=doc["version"],
        notas=doc.get("notas", ""), desplegado_en=doc["desplegado_en"], desplegado_por=doc.get("desplegado_por"),
    )


@router.get("/version", response_model=schemas.VersionOut)
async def obtener_version(actor: Actor = Depends(_admin_sistema)):
    return schemas.VersionOut(**service.obtener_version())


@router.get("/despliegues", response_model=list[schemas.DespliegueOut])
async def listar_despliegues(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await service.listar_despliegues(db)
    return [_despliegue_to_out(d) for d in docs]


@router.post("/despliegues", response_model=schemas.DespliegueOut, status_code=201)
async def registrar_despliegue(
    body: schemas.DespliegueCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.registrar_despliegue(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles),
        componente=body.componente, version=body.version, notas=body.notas,
    )
    return _despliegue_to_out(doc)


@router.get("/salud", response_model=list[schemas.SaludComponenteOut])
async def obtener_salud(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    resultados = await service.obtener_salud(db)
    return [schemas.SaludComponenteOut(**r) for r in resultados]


@router.get("/umbrales-monitoreo", response_model=list[schemas.UmbralOut])
async def listar_umbrales(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    umbrales = await service.obtener_umbrales(db)
    return [schemas.UmbralOut(componente=c, **v) for c, v in umbrales.items()]


@router.put("/umbrales-monitoreo/{componente}", response_model=schemas.UmbralOut)
async def actualizar_umbral(
    componente: schemas.ComponenteMonitoreo,
    body: schemas.UmbralActualizar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    resultado = await service.actualizar_umbral(
        db, actor_id=actor.usuario_id, rol=",".join(actor.roles), componente=componente,
        latencia_advertencia_ms=body.latencia_advertencia_ms, latencia_critica_ms=body.latencia_critica_ms,
    )
    return schemas.UmbralOut(**resultado)


@router.get("/politica-retencion", response_model=list[schemas.PoliticaRetencionItem])
async def obtener_politica_retencion(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    items = await service.obtener_politica_retencion(db)
    return [schemas.PoliticaRetencionItem(**i) for i in items]


@router.get("/indicadores", response_model=schemas.IndicadoresOut)
async def obtener_indicadores(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    resultado = await service.obtener_indicadores(db)
    return schemas.IndicadoresOut(**resultado)


@router.get("/historial-latencia", response_model=list[schemas.HistorialLatenciaPunto])
async def obtener_historial_latencia(
    horas: int = Query(default=24, ge=1, le=168),
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    puntos = await service.obtener_historial_latencia(db, horas=horas)
    return [schemas.HistorialLatenciaPunto(**p) for p in puntos]
