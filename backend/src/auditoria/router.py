from datetime import datetime

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.auditoria import schemas, service
from src.core.audit import ACCIONES_ADMINISTRATIVAS
from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client
from src.core.db_mongo import get_database
from src.core.rbac import require_roles

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

# Bitácora de solo inserción: esta es la única superficie de lectura; ninguna
# API expone update/delete sobre `bitacora` (diseno_base_datos.md §1.6).
# admin_sistema agregado para el Módulo 6.1 de Administración del Sistema
# (specs/specs-administrativas/admin_sistema.md) -- vista filtrada de esta
# misma bitácora para acciones administrativas, no un segundo almacén.
_puede_leer_bitacora = require_roles("supervisor_cumplimiento", "admin_plataforma", "gerencia", "admin_sistema")


@router.get("/acciones-administrativas", response_model=list[str])
async def listar_acciones_administrativas(_actor=Depends(_puede_leer_bitacora)):
    """Módulo 6.1 de admin_sistema: única fuente de verdad del catálogo de
    acciones administrativas (`core/audit.py::ACCIONES_ADMINISTRATIVAS`) --
    el frontend (`AuditoriaAdmin.tsx`) consume esta lista en vez de
    mantener un mirror hardcodeado, que ya se desincronizó una vez en la
    práctica (Módulo 3 agregó 3 acciones nuevas y el mirror manual no se
    actualizó, dejándolas invisibles en el filtro sin que ningún test lo
    detectara)."""
    return sorted(a.value for a in ACCIONES_ADMINISTRATIVAS)


@router.get("/eventos", response_model=schemas.EventosPage)
async def listar_eventos(
    actor_id: str | None = None,
    entidad: str | None = None,
    # list[str]: además del filtro por una sola acción (uso ya existente),
    # Módulo 6.1 (admin_sistema) necesita filtrar por VARIAS a la vez -- "solo
    # las acciones administrativas" es un conjunto de ~10 valores de
    # AccionAuditoria, no uno. `?accion=A&accion=B` en la query string.
    accion: list[str] | None = Query(default=None),
    resultado: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pagina: int = Query(default=1, ge=1),
    tamanio_pagina: int = Query(default=50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor=Depends(_puede_leer_bitacora),
):
    filtro: dict = {}
    if actor_id:
        filtro["actor_id"] = actor_id
    if entidad:
        filtro["entidad"] = entidad
    if accion:
        filtro["accion"] = accion[0] if len(accion) == 1 else {"$in": accion}
    if resultado:
        filtro["resultado"] = resultado
    if desde or hasta:
        rango: dict = {}
        if desde:
            rango["$gte"] = desde
        if hasta:
            rango["$lte"] = hasta
        filtro["ts"] = rango

    total = await db.bitacora.count_documents(filtro)
    cursor = (
        db.bitacora.find(filtro)
        .sort("evento_id", -1)
        .skip((pagina - 1) * tamanio_pagina)
        .limit(tamanio_pagina)
    )
    items = [schemas.EventoAuditoriaOut(**doc) async for doc in cursor]
    return schemas.EventosPage(items=items, total=total, pagina=pagina, tamanio_pagina=tamanio_pagina)


@router.get("/panel-tactico/uso-integraciones", response_model=list[schemas.UsoIntegracionOut])
async def obtener_uso_integraciones(
    _actor=Depends(_puede_leer_bitacora),
):
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_uso_integraciones")
    finally:
        client.close()
    filas.sort(key=lambda f: f["conteo"], reverse=True)
    return [schemas.UsoIntegracionOut(**f) for f in filas]


# Nivel estratégico — Panel de Gobernanza de Datos y Seguridad (OE6b/CU-E05,
# nivel_estrategico.md §3.6.b). La spec lo declara **exclusivo de
# `gerencia`**: deliberadamente NO se comparte con `admin_sistema`, que ya
# tiene su propia vista operativa de la misma bitácora en Administración
# (Módulo 6.1) -- de ahí que este gate sea distinto de `_puede_leer_bitacora`
# aunque lea la misma colección.
_gerencia_estrategico = require_roles("gerencia")


@router.get("/panel-estrategico/gobernanza", response_model=schemas.PanelGobernanzaOut)
async def obtener_panel_gobernanza(
    meses: int = Query(default=6, ge=1, le=36),
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor=Depends(_gerencia_estrategico),
):
    datos = await service.obtener_gobernanza_datos(db, meses=meses)
    return schemas.PanelGobernanzaOut(**datos)
