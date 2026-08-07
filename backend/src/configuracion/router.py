from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.configuracion import schemas, service
from src.core import feature_flags
from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles

router = APIRouter(prefix="/configuracion", tags=["configuracion"])

# Módulo 2 es de alto privilegio -- exclusivo de admin_sistema, sin roles
# combinados (misma disciplina que Módulo 1).
_admin_sistema = require_roles("admin_sistema")


def _parametro_to_out(doc: dict) -> schemas.ParametroSistemaOut:
    v = doc["valores"]
    return schemas.ParametroSistemaOut(
        id=doc.get("_id"),
        idioma=v["idioma"],
        zona_horaria=v["zona_horaria"],
        radios_despacho_m=v["radios_despacho_m"],
        oferta_expira_segundos=v["oferta_expira_segundos"],
        vigente_desde=doc["vigente_desde"],
        vigente_hasta=doc["vigente_hasta"],
    )


def _flag_to_out(doc: dict) -> schemas.FlagOut:
    return schemas.FlagOut(
        id=doc["_id"],
        nombre=doc["nombre"],
        activo=doc["activo"],
        porcentaje=doc.get("porcentaje"),
        roles=doc.get("roles") or [],
        creado_en=doc["creado_en"],
        actualizado_en=doc["actualizado_en"],
    )


@router.get("/parametros-sistema", response_model=schemas.ParametroSistemaOut)
async def obtener_parametros_sistema(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await service.obtener_parametro_sistema_documento(db)
    return _parametro_to_out(doc)


@router.post("/parametros-sistema", response_model=schemas.ParametroSistemaOut, status_code=201)
async def crear_parametros_sistema(
    body: schemas.ParametroSistemaCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_parametro_sistema(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        idioma=body.idioma,
        zona_horaria=body.zona_horaria,
        radios_despacho_m=body.radios_despacho_m,
        oferta_expira_segundos=body.oferta_expira_segundos,
        vigente_desde=body.vigente_desde,
    )
    return _parametro_to_out(doc)


@router.get("/flags", response_model=list[schemas.FlagOut])
async def listar_flags(actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)):
    docs = await feature_flags.listar_flags(db)
    return [_flag_to_out(d) for d in docs]


@router.post("/flags", response_model=schemas.FlagOut, status_code=201)
async def crear_flag(
    body: schemas.FlagCreate, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await feature_flags.crear_flag(
        db, nombre=body.nombre, activo=body.activo, porcentaje=body.porcentaje, roles=body.roles
    )
    await write_audit_event(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        accion=AccionAuditoria.FLAG_CREACION,
        entidad="feature_flags",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": doc["nombre"], "activo": doc["activo"]},
    )
    return _flag_to_out(doc)


@router.patch("/flags/{nombre}", response_model=schemas.FlagOut)
async def actualizar_flag(
    nombre: str,
    body: schemas.FlagActualizar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cambios = body.model_dump(exclude_unset=True)
    anterior = await feature_flags.listar_flags(db)
    antes = next((f for f in anterior if f["nombre"] == nombre), None)
    doc = await feature_flags.actualizar_flag(db, nombre=nombre, cambios=cambios)
    await write_audit_event(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        accion=AccionAuditoria.FLAG_MODIFICACION,
        entidad="feature_flags",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_previos={"activo": antes["activo"]} if antes else None,
        datos_posteriores=cambios,
    )
    return _flag_to_out(doc)
