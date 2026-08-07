from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.seguridad import schemas, service

router = APIRouter(prefix="/seguridad", tags=["seguridad"])

# Alto privilegio (nota de seguridad de la spec, §1.3): solo admin_sistema
# puede tocar las reglas de bloqueo/complejidad de contraseña de todo el
# sistema.
_admin_sistema = require_roles("admin_sistema")


def _to_out(doc: dict) -> schemas.PoliticaAuthOut:
    v = doc["valores"]
    return schemas.PoliticaAuthOut(
        id=doc.get("_id"),
        longitud_minima_password=v["longitud_minima_password"],
        umbral_intentos_fallidos=v["umbral_intentos_fallidos"],
        ventana_minutos=v["ventana_minutos"],
        bloqueo_minutos=v["bloqueo_minutos"],
        vencimiento_dias_alto_privilegio=v.get("vencimiento_dias_alto_privilegio"),
        vigente_desde=doc["vigente_desde"],
        vigente_hasta=doc["vigente_hasta"],
    )


@router.get("/politica-auth", response_model=schemas.PoliticaAuthOut)
async def obtener_politica_auth(
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.obtener_politica_documento(db)
    return _to_out(doc)


@router.post("/politica-auth", response_model=schemas.PoliticaAuthOut, status_code=201)
async def crear_politica_auth(
    body: schemas.PoliticaAuthCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_politica_auth(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        longitud_minima_password=body.longitud_minima_password,
        umbral_intentos_fallidos=body.umbral_intentos_fallidos,
        ventana_minutos=body.ventana_minutos,
        bloqueo_minutos=body.bloqueo_minutos,
        vencimiento_dias_alto_privilegio=body.vencimiento_dias_alto_privilegio,
        vigente_desde=body.vigente_desde,
    )
    return _to_out(doc)


def _to_out_seguridad(doc: dict) -> schemas.PoliticaSeguridadOut:
    v = doc["valores"]
    return schemas.PoliticaSeguridadOut(
        id=doc.get("_id"),
        access_token_minutos=v["access_token_minutos"],
        refresh_token_dias=v["refresh_token_dias"],
        refresh_umbral_fallos=v["refresh_umbral_fallos"],
        refresh_ventana_minutos=v["refresh_ventana_minutos"],
        rbac_umbral_denegaciones=v["rbac_umbral_denegaciones"],
        rbac_ventana_minutos=v["rbac_ventana_minutos"],
        rbac_suspension_minutos=v["rbac_suspension_minutos"],
        vigente_desde=doc["vigente_desde"],
        vigente_hasta=doc["vigente_hasta"],
    )


@router.get("/politica-seguridad", response_model=schemas.PoliticaSeguridadOut)
async def obtener_politica_seguridad(
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.obtener_politica_seguridad_documento(db)
    return _to_out_seguridad(doc)


@router.post("/politica-seguridad", response_model=schemas.PoliticaSeguridadOut, status_code=201)
async def crear_politica_seguridad(
    body: schemas.PoliticaSeguridadCreate,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.crear_politica_seguridad(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        access_token_minutos=body.access_token_minutos,
        refresh_token_dias=body.refresh_token_dias,
        refresh_umbral_fallos=body.refresh_umbral_fallos,
        refresh_ventana_minutos=body.refresh_ventana_minutos,
        rbac_umbral_denegaciones=body.rbac_umbral_denegaciones,
        rbac_ventana_minutos=body.rbac_ventana_minutos,
        rbac_suspension_minutos=body.rbac_suspension_minutos,
        vigente_desde=body.vigente_desde,
    )
    return _to_out_seguridad(doc)
