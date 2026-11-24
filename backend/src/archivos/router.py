from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.archivos import schemas, service
from src.core.db_mongo import get_database
from src.core.exceptions import DomainError
from src.core.rbac import Actor, get_current_actor, get_current_actor_opcional

router = APIRouter(prefix="/archivos", tags=["archivos"])


class AccesoDenegadoArchivoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="ACCESO_DENEGADO_ARCHIVO", message="No tienes permiso para ver este archivo", status_code=403
        )


@router.post("", response_model=schemas.ArchivoOut, status_code=201)
async def subir_archivo(
    contexto: str = Form(...),
    file: UploadFile = File(...),
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.guardar_archivo(db, actor_id=actor.usuario_id, contexto=contexto, upload=file)
    return service.archivo_a_salida(doc)


@router.get("/{archivo_id}/meta", response_model=schemas.ArchivoOut)
async def obtener_metadata(
    archivo_id: str, actor: Actor = Depends(get_current_actor), db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = await service.obtener_archivo(db, archivo_id=archivo_id)
    if not service.puede_ver(doc, actor_id=actor.usuario_id, roles=actor.roles):
        raise AccesoDenegadoArchivoError()
    return service.archivo_a_salida(doc)


@router.get("/{archivo_id}")
async def descargar_archivo(
    archivo_id: str,
    actor: Actor | None = Depends(get_current_actor_opcional),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Actor opcional: la mayoría de los contextos siguen exigiendo un
    # propietario/rol permitido de verdad (`puede_ver` lo hace cumplir
    # igual), pero `foto_perfil` (lectura pública, ver `archivos/service.py`)
    # necesita poder servirse a un visitante sin sesión -- la vista pública
    # de "Compartir viaje" es la primera consumidora real.
    doc = await service.obtener_archivo(db, archivo_id=archivo_id)
    actor_id = actor.usuario_id if actor else None
    roles = actor.roles if actor else []
    if not service.puede_ver(doc, actor_id=actor_id, roles=roles):
        raise AccesoDenegadoArchivoError()
    return FileResponse(
        doc["ruta_disco"], media_type=doc["content_type"], filename=doc["nombre_original"]
    )
