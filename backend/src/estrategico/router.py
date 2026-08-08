from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.estrategico import schemas, service

# Los otros 7 dashboards estratégicos exponen `GET /<dominio>/panel-estrategico/...`
# dentro del router de su dominio (mismo patrón descentralizado del nivel
# táctico). Estos 2 no tienen dominio dueño -- ver el docstring de
# `estrategico/service.py` -- así que su prefijo ya es "estratégico" y no
# repiten el segmento `/panel-estrategico/`.
router = APIRouter(prefix="/estrategico", tags=["estrategico"])

# La spec asigna ambos a `gerencia` + `junta_socios`. **Decisión aprobada:
# `junta_socios` NO se crea como rol** (no existe en `core/rbac.py::ROLES`, y
# un rol sin cuenta ni pantalla propias repetiría el patrón muerto de
# `integracion_externa`) -- quedan bajo `gerencia`, el otro rol que la propia
# spec ya lista para los dos. Mismo criterio que en `mantenimiento/router.py`
# (OE2b) y `recaudacion/router.py` (OE5).
_gerencia = require_roles("gerencia")


@router.get("/rentabilidad-demanda", response_model=schemas.PanelRentabilidadOut)
async def obtener_panel_rentabilidad(
    meses: int = Query(default=12, ge=1, le=60),
    _actor: Actor = Depends(_gerencia),
):
    return schemas.PanelRentabilidadOut(**service.obtener_panel_rentabilidad(meses=meses))


@router.get("/tablero-ejecutivo", response_model=schemas.TableroEjecutivoOut)
async def obtener_tablero_ejecutivo(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_gerencia),
):
    return schemas.TableroEjecutivoOut(**await service.obtener_tablero_ejecutivo(db))
