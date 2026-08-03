"""Backend único en Python (arquitectura_software.md línea 5): un solo
proceso FastAPI que monta el router de cada módulo de dominio. Monolito
modular — ver ítem D12 del plan: no hay broker de mensajería porque los
módulos se llaman entre sí en proceso, nunca acceden a colecciones ajenas.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.auditoria.router import router as auditoria_router
from src.auth.router import router as auth_router
from src.captacion.router import router as captacion_router
from src.core.config import get_settings
from src.core.db_mongo import close_mongo_client, ensure_indexes
from src.core.db_redis import close_redis
from src.core.exceptions import DomainError
from src.core.idempotency import IdempotencyMiddleware
from src.cumplimiento.router import router as cumplimiento_router
from src.flota.router import router as flota_router
from src.mantenimiento.router import router as mantenimiento_router
from src.notificaciones.router import router as notificaciones_router
from src.notificaciones.service import NotificationService
from src.parametros.router import router as parametros_router
from src.plataforma.router import router as plataforma_router
from src.recaudacion.router import router as recaudacion_router
from src.recaudacion.router import router_liquidaciones
from src.viajes.router_dispatch import router as viajes_dispatch_router
from src.viajes.router_ejecucion import router as viajes_ejecucion_router
from src.viajes.router_finalizacion import router as viajes_finalizacion_router
from src.viajes.router_trips import router as viajes_trips_router


# Sin esto, logger.info()/warning() en cualquier módulo (p. ej.
# notificaciones/webpush.py) cae al vacío: el logger raíz no tiene handler
# propio salvo que algo lo configure, y uvicorn solo configura SUS PROPIOS
# loggers ("uvicorn", "uvicorn.access"), no el resto de la app.
logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    app.state.notification_dispatcher = NotificationService()
    yield
    await close_mongo_client()
    await close_redis()


app = FastAPI(title="UrbanFleet-TaxiFlow API", version="0.1.0", lifespan=lifespan)

app.add_middleware(IdempotencyMiddleware)

# Los 3 clientes web corren en orígenes distintos al backend (línea 5
# arquitectura: "tres clientes web"). allow_credentials=False porque la
# sesión viaja como Bearer token en el header Authorization, no como cookie
# — no hay necesidad de exponer credenciales de navegador entre orígenes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})


app.include_router(auth_router)
app.include_router(captacion_router)
app.include_router(cumplimiento_router)
app.include_router(mantenimiento_router)
app.include_router(flota_router)
app.include_router(viajes_trips_router)
app.include_router(viajes_dispatch_router)
app.include_router(viajes_ejecucion_router)
app.include_router(viajes_finalizacion_router)
app.include_router(recaudacion_router)
app.include_router(router_liquidaciones)
app.include_router(parametros_router)
app.include_router(notificaciones_router)
app.include_router(auditoria_router)
app.include_router(plataforma_router)


@app.get("/salud")
async def salud():
    return {"estado": "OK"}
