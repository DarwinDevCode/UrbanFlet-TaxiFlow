"""Sección 1.2 de `specs/specs-administrativas/ux_complementaria.md`.

Primer endpoint del proyecto sin `Depends(get_current_actor)` fuera de
`/auth/registro`/`/auth/login` -- documentado explícitamente porque es un
patrón nuevo, no un descuido. La autorización aquí es el propio token
(256 bits de entropía, ver `service_compartir.py`), no una sesión.
"""

from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.viajes import schemas, service_compartir

router = APIRouter(prefix="/publico", tags=["publico"])


def _ip_cliente(request: Request) -> str:
    # Mismo criterio que `auth/router.py::_ip_y_dispositivo`: en despliegue
    # real el backend suele estar detrás de un proxy/reverse-proxy.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


@router.get("/viajes-compartidos/{token}", response_model=schemas.ViajeCompartidoOut)
async def obtener_viaje_compartido(
    token: str, request: Request, db: AsyncIOMotorDatabase = Depends(get_database)
):
    ip = _ip_cliente(request)
    await service_compartir.verificar_no_bloqueado(ip)

    try:
        datos = await service_compartir.obtener_viaje_compartido(db, token=token)
    except service_compartir.ViajeCompartidoNoEncontradoError:
        await service_compartir.registrar_fallo(ip)
        raise

    return schemas.ViajeCompartidoOut(**datos)
