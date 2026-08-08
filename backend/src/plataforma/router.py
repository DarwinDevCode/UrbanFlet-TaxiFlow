from datetime import date

from fastapi import APIRouter, Depends, Query

from src.core.rbac import Actor, require_roles
from src.plataforma import schemas, service

router = APIRouter(prefix="/plataforma", tags=["plataforma"])

_consumidor_indicadores = require_roles("gerencia", "responsable_plataforma", "admin_plataforma")


@router.get("/indicadores", response_model=schemas.CatalogoIndicadoresOut)
async def obtener_indicadores(actor: Actor = Depends(_consumidor_indicadores)):
    informes = service.obtener_catalogo_indicadores()
    return schemas.CatalogoIndicadoresOut(informes=[schemas.InformeOut(**i) for i in informes])


@router.get("/panel-tactico/corridas", response_model=list[schemas.CorridaOut])
async def listar_corridas(
    dominio: str | None = Query(default=None),
    fecha_logica: date | None = Query(default=None),
    _actor: Actor = Depends(_consumidor_indicadores),
):
    filas = service.listar_corridas(dominio=dominio, fecha_logica=fecha_logica)
    return [schemas.CorridaOut(**f) for f in filas]


@router.get("/panel-tactico/cuarentena-dominio", response_model=list[schemas.CuarentenaDominioOut])
async def obtener_cuarentena_dominio(
    _actor: Actor = Depends(_consumidor_indicadores),
):
    filas = service.obtener_cuarentena_dominio()
    return [schemas.CuarentenaDominioOut(**f) for f in filas]


# Nivel estratégico — Panel de Capacidades y Plataforma (OE3,
# nivel_estrategico.md §3.3). La spec lo asigna a `gerencia` +
# `responsable_plataforma` (lectura) -- ambos ya están en
# `_consumidor_indicadores`, pero se declara un gate propio para no acoplar
# el acceso estratégico al del catálogo de indicadores (CU-O16), que además
# incluye `admin_plataforma`.
_capacidades_estrategico = require_roles("gerencia", "responsable_plataforma")


@router.get("/panel-estrategico/capacidades", response_model=schemas.PanelCapacidadesOut)
async def obtener_panel_capacidades(
    cortes: int = Query(default=12, ge=1, le=60),
    _actor: Actor = Depends(_capacidades_estrategico),
):
    return schemas.PanelCapacidadesOut(**service.obtener_panel_capacidades(cortes=cortes))
