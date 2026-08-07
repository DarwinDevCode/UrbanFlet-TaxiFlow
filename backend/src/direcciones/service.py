"""Direcciones favoritas — Sección 1.1 de `specs/specs-administrativas/
ux_complementaria.md`. Exclusivo `pasajero`: elimina la fricción de escribir
la misma dirección (casa, trabajo) en cada solicitud de viaje. Datos
personales de ubicación -- por eso `usuarios/service.py::anonimizar_usuario`
también las purga (Módulo 8.2, gobernanza de datos).
"""

import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.exceptions import DomainError

# Límite razonable para evitar abuso (spam de filas) sin bloquear el caso de
# uso real -- nadie necesita más de un puñado de direcciones guardadas.
LIMITE_DIRECCIONES = 10


class LimiteDireccionesError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="LIMITE_DIRECCIONES_ALCANZADO",
            message=f"Ya guardaste el máximo de {LIMITE_DIRECCIONES} direcciones favoritas",
            status_code=409,
        )


class DireccionNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="DIRECCION_NO_ENCONTRADA", message="La dirección no existe", status_code=404)


async def listar_direcciones(db: AsyncIOMotorDatabase, usuario_id: str) -> list[dict]:
    cursor = db.direcciones_favoritas.find({"usuario_id": usuario_id}).sort("etiqueta", 1)
    return await cursor.to_list(length=LIMITE_DIRECCIONES)


async def crear_direccion(
    db: AsyncIOMotorDatabase, *, usuario_id: str, etiqueta: str, direccion: str, lat: float, lon: float
) -> dict:
    total = await db.direcciones_favoritas.count_documents({"usuario_id": usuario_id})
    if total >= LIMITE_DIRECCIONES:
        raise LimiteDireccionesError()

    doc = {
        "_id": str(uuid.uuid4()),
        "usuario_id": usuario_id,
        "etiqueta": etiqueta,
        "direccion": direccion,
        "lat": lat,
        "lon": lon,
    }
    await db.direcciones_favoritas.insert_one(doc)
    return doc


async def eliminar_direccion(db: AsyncIOMotorDatabase, *, usuario_id: str, direccion_id: str) -> None:
    resultado = await db.direcciones_favoritas.delete_one({"_id": direccion_id, "usuario_id": usuario_id})
    if resultado.deleted_count == 0:
        raise DireccionNoEncontradaError()
