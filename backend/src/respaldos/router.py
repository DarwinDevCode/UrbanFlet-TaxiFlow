from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.respaldos import schemas, service

router = APIRouter(prefix="/respaldos", tags=["respaldos"])

# 7.1 (respaldos técnicos): exclusivo admin_sistema, mismo criterio que el
# resto del módulo de administración del sistema.
_admin_sistema = require_roles("admin_sistema")
# 7.2 (plan de continuidad): la spec pide explícitamente que gerencia
# también pueda verlo/gestionarlo -- único OR-gate real de todo el bloque
# de admin_sistema hasta ahora (nota de seguridad de la spec: "revela
# puntos únicos de falla").
_admin_o_gerencia = require_roles("admin_sistema", "gerencia")


@router.post("", response_model=list[schemas.RespaldoOut], status_code=202)
async def disparar_respaldo(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    docs = await service.disparar_respaldo(db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles))
    for doc in docs:
        if doc["motor"] == "mongo":
            service.lanzar_en_fondo(service.ejecutar_respaldo_mongo(doc["_id"]))
        else:
            service.lanzar_en_fondo(service.ejecutar_respaldo_clickhouse(doc["_id"]))
    return [schemas.RespaldoOut(**service.respaldo_a_salida(d)) for d in docs]


@router.get("", response_model=list[schemas.RespaldoOut])
async def listar_respaldos(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    items = await service.listar_respaldos(db)
    return [schemas.RespaldoOut(**i) for i in items]


@router.post("/{respaldo_id}/verificar", response_model=schemas.VerificacionOut)
async def verificar_respaldo(
    respaldo_id: str, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    resultado = await service.verificar_respaldo(db, respaldo_id)
    return schemas.VerificacionOut(**resultado)


@router.post("/{respaldo_id}/restaurar", response_model=schemas.RestauracionOut, status_code=202)
async def restaurar_respaldo(
    respaldo_id: str, actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await service.restaurar_respaldo(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), respaldo_id=respaldo_id
    )
    respaldo = await db.respaldos.find_one({"_id": respaldo_id})
    if doc["motor"] == "mongo":
        service.lanzar_en_fondo(service.ejecutar_restauracion_mongo(doc["_id"], respaldo["ruta_archivo"]))
    else:
        service.lanzar_en_fondo(service.ejecutar_restauracion_clickhouse(doc["_id"], respaldo["ruta_archivo"]))
    return schemas.RestauracionOut(**service.restauracion_a_salida(doc))


@router.get("/restauraciones", response_model=list[schemas.RestauracionOut])
async def listar_restauraciones(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    items = await service.listar_restauraciones(db)
    return [schemas.RestauracionOut(**i) for i in items]


@router.get("/plan-dr", response_model=list[schemas.PlanDrItem])
async def listar_plan_dr(actor: Actor = Depends(_admin_o_gerencia), db: AsyncIOMotorDatabase = Depends(get_database)):
    items = await service.listar_plan_dr(db)
    return [schemas.PlanDrItem(**i) for i in items]


@router.put("/plan-dr/{dominio}", response_model=schemas.PlanDrItem)
async def actualizar_plan_dr(
    dominio: schemas.DominioDr,
    body: schemas.PlanDrActualizar,
    actor: Actor = Depends(_admin_o_gerencia),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    resultado = await service.actualizar_plan_dr(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles),
        dominio=dominio, rto=body.rto, rpo=body.rpo, notas=body.notas,
    )
    return schemas.PlanDrItem(**resultado)


@router.get("/simulacros", response_model=list[schemas.SimulacroOut])
async def listar_simulacros(
    actor: Actor = Depends(_admin_o_gerencia), db: AsyncIOMotorDatabase = Depends(get_database)
):
    docs = await service.listar_simulacros(db)
    return [schemas.SimulacroOut(id=d["_id"], **{k: v for k, v in d.items() if k != "_id"}) for d in docs]


@router.post("/simulacros", response_model=schemas.SimulacroOut, status_code=201)
async def registrar_simulacro(
    body: schemas.SimulacroCreate,
    actor: Actor = Depends(_admin_o_gerencia),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.registrar_simulacro(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles),
        fecha=body.fecha, resultado=body.resultado, notas=body.notas,
    )
    return schemas.SimulacroOut(id=doc["_id"], **{k: v for k, v in doc.items() if k != "_id"})
