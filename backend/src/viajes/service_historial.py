"""CU-O14 — Consultar el historial de viajes.

Cortes de alcance explícitos en este slice:
- Paso 3 ("mapa con la ruta recorrida"): no hay componente de mapa en el
  stack todavía. El detalle expone la traza cruda (lat/lon/ts por punto, ya
  acumulada por CU-O07) para que un mapa futuro la consuma, pero no la
  renderiza — mismo corte que la ausencia de motor de ruteo en CU-O04/O05.
- Paso 4 (comprobante en PDF con folio secuencial y "datos fiscales de la
  cooperativa"): depende estructuralmente de un viaje en estado PAGADO, que
  todavía no existe — CU-O09 (registrar pago, Fase 4/Control Financiero) es
  quien produce esa transición; construir el comprobante ahora sería para un
  estado inalcanzable con el código actual. Además, los "datos fiscales de
  la cooperativa" (RUC, razón social, dirección) no están definidos en
  ningún documento de specs/ — no es un hueco de implementación menor, es un
  dato de negocio real que falta y debe confirmarse antes de construir el
  comprobante, no inventarse. Se difiere a Fase 4 junto con CU-O09/O10/O11.
"""

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

# Historial = viajes ya cerrados, nunca los activos (esos viven en
# GET /viajes/activo y /viajes/conductor/activo).
ESTADOS_HISTORIAL = frozenset({"FINALIZADO", "PAGADO", "CANCELADO", "SIN_CONDUCTOR"})
ESTADOS_HISTORIAL_FILTRABLES = frozenset({"FINALIZADO", "CANCELADO"})


def _nombre_de_pila(nombre: str) -> str:
    return nombre.strip().split(" ")[0]


async def enriquecer_con_pasajero(db: AsyncIOMotorDatabase, viaje: dict) -> dict:
    """CU-O14 A2: el conductor solo ve nombre de pila y calificación del
    pasajero — nunca teléfono ni historial de ubicaciones (que ni siquiera se
    consulta aquí). Se usa tanto en el detalle (GET /viajes/{id}) como en la
    lista, para que ambos muestren la misma "contraparte limitada"."""
    pasajero = await db.usuarios.find_one({"_id": viaje["pasajero_id"]})
    if pasajero is None:
        return viaje
    return {
        **viaje,
        "pasajero_nombre": _nombre_de_pila(pasajero["nombre"]),
        "pasajero_calificacion": (pasajero.get("pasajero") or {}).get("calificacion_promedio"),
    }


async def listar_historial_global(
    db: AsyncIOMotorDatabase,
    *,
    texto: str | None,
    estado: str | None,
    desde: datetime | None,
    hasta: datetime | None,
    pagina: int,
    limite: int,
) -> tuple[list[dict], int]:
    """Sección 3.3 de `specs/specs-administrativas/ux_complementaria.md` —
    historial navegable de TODOS los viajes de la cooperativa (no solo los
    propios), para roles con visibilidad autorizada. `texto` busca por
    nombre de pasajero (resuelto vía `usuarios`, ya que `pasajero_nombre`
    no vive en el propio documento del viaje -- a diferencia de
    `conductor_nombre`, que sí se snapshotea al asignar) o por nombre de
    conductor (directo sobre el snapshot). Filtro por zona: **gap
    conocido, no implementado** -- `viajes.zona_origen_id`/`zona_destino_id`
    existen en el schema pero nunca se resuelven (mismo límite ya
    documentado para el panel táctico de Flota), así que no se ofrece un
    parámetro que prometería un filtro que no funciona.
    """
    filtro: dict = {"estado": {"$in": list(ESTADOS_HISTORIAL)}}
    if estado:
        filtro["estado"] = estado
    if desde or hasta:
        rango: dict = {}
        if desde:
            rango["$gte"] = desde
        if hasta:
            rango["$lte"] = hasta
        filtro["ts_solicitud"] = rango
    if texto:
        pasajero_ids = [
            u["_id"] async for u in db.usuarios.find({"nombre": {"$regex": texto, "$options": "i"}}, {"_id": 1})
        ]
        filtro["$or"] = [
            {"pasajero_id": {"$in": pasajero_ids}},
            {"conductor_nombre": {"$regex": texto, "$options": "i"}},
        ]

    total = await db.viajes.count_documents(filtro)
    cursor = db.viajes.find(filtro).sort("ts_solicitud", -1).skip((pagina - 1) * limite).limit(limite)
    viajes = await cursor.to_list(length=limite)

    # Mismo enriquecimiento "contraparte limitada" que ya usa CU-O14 A2
    # (nombre de pila + calificación del pasajero, nunca teléfono) -- ni
    # siquiera un rol administrativo con este acceso necesita el contacto
    # completo del pasajero para consultar el historial (mismo principio de
    # mínimo privilegio ya aplicado en Administración).
    return [await enriquecer_con_pasajero(db, v) for v in viajes], total


async def listar_historial(
    db: AsyncIOMotorDatabase,
    *,
    usuario_id: str,
    rol: str,
    estado: str | None,
    desde: datetime | None,
    hasta: datetime | None,
    pagina: int,
    limite: int,
) -> tuple[list[dict], int]:
    campo_actor = "pasajero_id" if rol == "pasajero" else "conductor_id"
    filtro: dict = {campo_actor: usuario_id, "estado": {"$in": list(ESTADOS_HISTORIAL)}}
    if estado:
        filtro["estado"] = estado
    if desde or hasta:
        rango: dict = {}
        if desde:
            rango["$gte"] = desde
        if hasta:
            rango["$lte"] = hasta
        filtro["ts_solicitud"] = rango

    total = await db.viajes.count_documents(filtro)
    cursor = db.viajes.find(filtro).sort("ts_solicitud", -1).skip((pagina - 1) * limite).limit(limite)
    viajes = await cursor.to_list(length=limite)

    if rol == "conductor":
        viajes = [await enriquecer_con_pasajero(db, v) for v in viajes]

    return viajes, total
