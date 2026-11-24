"""Mantenimiento — CU-O12 (registrar orden), CU-O13 (cerrar orden y
habilitar el vehículo).

Alcance de esta fase: se cubre el flujo principal de ambos CU y los
alternos con validación bloqueante (A2/A3 de CU-O13) y la anulación (A4 de
CU-O12). Quedan fuera de esta fase — no son huecos de la spec, son
dependencias de módulos que todavía no existen — la pre-orden automática por
umbral de kilometraje (A2 de CU-O12, necesita telemetría de flota agregada)
y la pre-orden por incidencia de viaje (A1 de CU-O12, necesita CU-O07 de
Fase 3).

Cada operación que muta más de una entidad de negocio (orden + vehículo)
está envuelta en `core.db_transaction.with_transaction` — el mismo patrón
introducido en Fase 1 para la cadena de aprobación de Captación.
"""

import re
import uuid
from datetime import date, datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.agregacion_estrategica import agrupar, promedio_ponderado, ultimos_periodos, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client
from src.core.db_mongo import get_mongo_client
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.core.notifications import NotificationDispatcher
from src.mantenimiento import schemas


class VehiculoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="VEHICULO_NO_ENCONTRADO", message="El vehículo no existe", status_code=404)


# Autoservicio del conductor (GET /mantenimiento/vehiculos/mio/ficha) -- caso
# real y alcanzable: una postulación aprobada sin vehículo, o cualquier otra
# situación en la que `vehiculos.propietario_id` nunca llegó a apuntar a esta
# cuenta. Distinto de VehiculoNoEncontradoError (ese es "el id no existe";
# este es "esta cuenta no tiene ningún vehículo propio").
class VehiculoConductorNoAsignadoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VEHICULO_CONDUCTOR_NO_ASIGNADO",
            message="No tenés un vehículo asignado",
            status_code=404,
        )


# --------------------------------------------------------------------------
# Decisión 3 -- baja lógica de vehículos como transición dentro de la máquina
# de estados ya existente (`vehiculos.estado_habilitacion`), NO como un campo
# `activo` aparte: un booleano suelto crearía dos fuentes de verdad que
# pueden desincronizarse (`activo:false` con `estado:HABILITADO` a la vez).
#
# Se agrega un valor NUEVO porque se confirmó que ninguno de los 2 existentes
# sirve:
#   - `HABILITADO`: disponible para despacho.
#   - `RETIRADO_DE_SERVICIO`: fuera de servicio TEMPORALMENTE por una orden de
#     mantenimiento, y **se revierte solo** al cerrar o anular esa orden
#     (`cerrar_orden`/`anular_orden` lo vuelven a HABILITADO). Reusarlo para
#     una baja permanente haría que cerrar una orden resucitara un vehículo
#     que ya salió de la flota.
#   - `DADO_DE_BAJA` (nuevo): salida PERMANENTE de la flota operativa. Ningún
#     flujo automático lo revierte.
#
# Los consumidores que ya filtran por `!= "HABILITADO"` (auto-despacho en
# `viajes/service_dispatch.py`, gate de inicio de turno en `flota/service.py`)
# excluyen el estado nuevo sin ningún cambio -- fallan del lado seguro.
# --------------------------------------------------------------------------
ESTADO_HABILITADO = "HABILITADO"
ESTADO_RETIRADO_DE_SERVICIO = "RETIRADO_DE_SERVICIO"
ESTADO_DADO_DE_BAJA = "DADO_DE_BAJA"

# Una orden en cualquiera de estos 3 estados retiene el vehículo (mismo
# criterio que ya usa `listar_vehiculos_retirados`).
ESTADOS_ORDEN_ABIERTA = ("ABIERTA", "EN_TALLER", "ESPERANDO_REPUESTO")


class VehiculoYaDadoDeBajaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VEHICULO_YA_DADO_DE_BAJA",
            message="El vehículo ya está dado de baja",
            status_code=409,
        )


class BajaVehiculoConOrdenAbiertaError(DomainError):
    """Mismo patrón que `BajaConViajeActivoError` (baja de cuentas): se
    bloquea con un mensaje que dice EXACTAMENTE qué hay que cerrar primero,
    no un error genérico. Es resoluble por el propio Jefe de Mantenimiento:
    cerrar o anular la orden y reintentar."""

    def __init__(self, orden_id: str, estado: str) -> None:
        super().__init__(
            code="BAJA_VEHICULO_CON_ORDEN_ABIERTA",
            message=(
                f"No se puede dar de baja: el vehículo tiene una orden de mantenimiento {estado} "
                f"({orden_id[:8]}…). Ciérrala o anúlala y vuelve a intentarlo."
            ),
            status_code=409,
        )


async def editar_vehiculo(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, vehiculo_id: str, cambios: dict
) -> dict:
    """Corrección de los datos DESCRIPTIVOS de un vehículo (placa, marca,
    modelo, color, año, capacidad) -- cierra la U del CRUD que
    PROPUESTA_CRUD_Y_BAJA_LOGICA.md marcaba como faltante: hasta ahora, una
    placa mal tecleada al aprobar una postulación no tenía ningún camino de
    corrección en todo el sistema.

    Deliberadamente NO acepta `estado_habilitacion` ni `propietario_id`:
    - `estado_habilitacion` es la máquina de estados (la mueven las órdenes
      de mantenimiento y la baja lógica), no un campo de formulario.
    - reasignar un vehículo a otro socio es un flujo propio que quedó
      explícitamente fuera de alcance en la Decisión 2.
    """
    vehiculo = await db.vehiculos.find_one({"_id": vehiculo_id})
    if vehiculo is None:
        raise VehiculoNoEncontradoError()
    if vehiculo.get("estado_habilitacion") == ESTADO_DADO_DE_BAJA:
        raise VehiculoYaDadoDeBajaError()
    if not cambios:
        return vehiculo

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_EDICION,
        entidad="vehiculos",
        entidad_id=vehiculo_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={campo: vehiculo.get(campo) for campo in cambios},
        datos_posteriores=cambios,
    )
    await db.vehiculos.update_one({"_id": vehiculo_id}, {"$set": cambios})
    vehiculo.update(cambios)
    return vehiculo


async def dar_de_baja_vehiculo(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    vehiculo_id: str,
    motivo: str,
    origen: str | None = None,
) -> dict:
    """Saca un vehículo de la flota operativa de forma permanente.

    `origen` deja trazable POR QUÉ salió cuando no fue una acción directa
    sobre el vehículo -- lo usa la Decisión 2 (baja automática al dar de baja
    al socio dueño) para referenciar el evento de baja de la cuenta que la
    originó. En una baja manual va en `None`.

    Write-ahead de auditoría antes del efecto, igual que el resto del sistema.
    """
    vehiculo = await db.vehiculos.find_one({"_id": vehiculo_id})
    if vehiculo is None:
        raise VehiculoNoEncontradoError()
    if vehiculo.get("estado_habilitacion") == ESTADO_DADO_DE_BAJA:
        raise VehiculoYaDadoDeBajaError()

    orden_abierta = await db.ordenes.find_one(
        {"vehiculo_id": vehiculo_id, "estado": {"$in": list(ESTADOS_ORDEN_ABIERTA)}}
    )
    if orden_abierta is not None:
        raise BajaVehiculoConOrdenAbiertaError(orden_abierta["_id"], orden_abierta["estado"])

    datos_posteriores: dict = {"estado_habilitacion": ESTADO_DADO_DE_BAJA, "motivo": motivo}
    if origen:
        datos_posteriores["origen"] = origen

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_BAJA,
        entidad="vehiculos",
        entidad_id=vehiculo_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado_habilitacion": vehiculo.get("estado_habilitacion")},
        datos_posteriores=datos_posteriores,
    )
    await db.vehiculos.update_one(
        {"_id": vehiculo_id},
        {"$set": {"estado_habilitacion": ESTADO_DADO_DE_BAJA, "motivo_baja": motivo}},
    )
    vehiculo["estado_habilitacion"] = ESTADO_DADO_DE_BAJA
    vehiculo["motivo_baja"] = motivo
    return vehiculo


# Ronda 2 (Fase B): ver la nota completa en mantenimiento/schemas.py junto a
# FichaVehiculoOut -- no existe un plan preventivo diferenciado por
# antigüedad en ningún lado del sistema, se usa este umbral global único
# (el mismo valor que la propia spec usa como ejemplo, CU-O12 A2).
UMBRAL_KM_PREVENTIVO = 5000


class OrdenNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="ORDEN_NO_ENCONTRADA", message="La orden no existe", status_code=404)


# Bitácora de revisión (2026-08-26, hallazgo #7): mismo criterio que
# `viajes/service_ejecucion.py::_traducir_estados` -- `esperado`/`estado`
# venían como enum(s) crudo(s) incrustados en un mensaje en español.
_ETIQUETA_ESTADO_ORDEN = {
    "ABIERTA": "Abierta",
    "EN_TALLER": "En taller",
    "ESPERANDO_REPUESTO": "Esperando repuesto",
    "CERRADA": "Cerrada",
    "ANULADA": "Anulada",
}


def _traducir_estados_orden(texto: str) -> str:
    return re.sub(r"[A-Z][A-Z_]*", lambda m: _ETIQUETA_ESTADO_ORDEN.get(m.group(0), m.group(0)), texto)


class OrdenEstadoInvalidoError(DomainError):
    def __init__(self, esperado: str) -> None:
        super().__init__(
            code="ORDEN_ESTADO_INVALIDO",
            message=f"La orden debe estar en estado: {_traducir_estados_orden(esperado)}",
            status_code=409,
        )


class CampoNoCorregibleEnEsteEstadoError(DomainError):
    def __init__(self, campo: str, estado: str) -> None:
        super().__init__(
            code="CAMPO_NO_CORREGIBLE_EN_ESTE_ESTADO",
            message=f"No se puede corregir '{campo}' con la orden en estado {_traducir_estados_orden(estado)}",
            status_code=409,
        )


class KmSalidaMenorError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="KM_SALIDA_MENOR",
            message="El kilometraje de salida es menor al de entrada; marca ajuste_justificado con motivo",
            status_code=400,
        )


async def obtener_placas_vehiculos(db: AsyncIOMotorDatabase, vehiculo_ids: set[str]) -> dict[str, str]:
    """Resuelve `vehiculo_id` -> `placa` en un solo `$in`, para que la
    bandeja de órdenes (CU-O12/CU-O13) no muestre el UUID crudo del
    vehículo. Mismo criterio de batch que
    `captacion.service.enriquecer_con_usuario_nombre`."""
    vehiculo_ids = {v for v in vehiculo_ids if v}
    if not vehiculo_ids:
        return {}
    vehiculos = await db.vehiculos.find({"_id": {"$in": list(vehiculo_ids)}}).to_list(length=len(vehiculo_ids))
    return {v["_id"]: v["placa"] for v in vehiculos}


# Tope de la búsqueda de vehículos. Antes era 10, que alcanzaba para el
# autocompletado por placa pero truncaba en silencio cualquier consulta amplia
# (la flota real de este entorno tiene 93). 200 es un tope real que no
# trunca en la práctica y sigue acotando la respuesta.
LIMITE_BUSQUEDA_VEHICULOS = 200


async def buscar_vehiculo_por_placa(db: AsyncIOMotorDatabase, *, placa: str) -> list[dict]:
    # Búsqueda de apoyo para el formulario de "crear orden" (necesita el
    # vehiculo_id, que el usuario no conoce de memoria, solo la placa).
    # Orden alfabético por placa, no "más reciente primero": `vehiculos` no
    # tiene ningún campo de fecha de alta (ver PROPUESTA_CRUD_Y_BAJA_LOGICA),
    # así que no hay recencia que ordenar. Lo importante acá es que el orden
    # sea DETERMINISTA -- antes era el orden natural de Mongo, que puede
    # devolver los mismos 10 resultados en distinto orden entre llamadas.
    # Decisión 3: un vehículo dado de baja no debe poder elegirse para un
    # proceso NUEVO (crear una orden, sobre todo) -- se excluye acá, en el
    # único buscador que alimenta esos selectores, en vez de esperar que cada
    # pantalla se acuerde de filtrar. Su historial (órdenes pasadas, viajes)
    # no se toca: esto solo acota la búsqueda para procesos nuevos.
    cursor = (
        db.vehiculos.find(
            {
                "placa": {"$regex": placa, "$options": "i"},
                "estado_habilitacion": {"$ne": ESTADO_DADO_DE_BAJA},
            }
        )
        .sort("placa", 1)
        .limit(LIMITE_BUSQUEDA_VEHICULOS)
    )
    return await cursor.to_list(length=LIMITE_BUSQUEDA_VEHICULOS)


async def obtener_ficha_vehiculo(db: AsyncIOMotorDatabase, *, vehiculo_id: str) -> dict:
    """CU-O12 P1 (H6): "kilometraje acumulado... fecha y kilometraje de la
    última intervención, y el plan preventivo aplicable". `km_acumulado` se
    alimenta desde `viajes.km_recorridos` al finalizar cada viaje (ver
    `viajes/service_finalizacion.py::finalizar_viaje`) + el backfill inicial
    (`scripts/backfill_km_acumulado.py`). La "última intervención" es la
    orden `CERRADA` más reciente de este vehículo por `fecha_cierre` (único
    datetime real de cierre que existe en `ordenes`, mismo criterio que ya
    usa `dag_mantenimiento_gold`)."""
    vehiculo = await db.vehiculos.find_one({"_id": vehiculo_id})
    if vehiculo is None:
        raise VehiculoNoEncontradoError()

    ultima = await db.ordenes.find_one({"vehiculo_id": vehiculo_id, "estado": "CERRADA"}, sort=[("fecha_cierre", -1)])
    km_acumulado = vehiculo.get("km_acumulado") or 0.0
    km_ultima = ultima["km_salida"] if ultima else None
    fecha_ultima = ultima.get("fecha_cierre") if ultima else None
    proxima_km = (km_ultima if km_ultima is not None else 0) + UMBRAL_KM_PREVENTIVO

    return {
        "_id": vehiculo["_id"],
        "placa": vehiculo["placa"],
        "marca": vehiculo["marca"],
        "modelo": vehiculo["modelo"],
        "estado_habilitacion": vehiculo["estado_habilitacion"],
        "km_acumulado": km_acumulado,
        "fecha_ultima_intervencion": fecha_ultima,
        "km_ultima_intervencion": km_ultima,
        "proxima_km_preventivo": proxima_km,
        "le_toca_preventivo": km_acumulado >= proxima_km,
        "umbral_km_preventivo": UMBRAL_KM_PREVENTIVO,
    }


async def obtener_ficha_de_mi_vehiculo(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict:
    """Autoservicio del conductor sobre `obtener_ficha_vehiculo`: resuelve el
    vehículo del que el actor es socio propietario (mismo patrón inline ya
    usado en `flota/service.py::_vehiculo_del_conductor` y
    `reportes_falla/service.py`, sin acoplarse a ese módulo) y delega en el
    cálculo real ya existente -- nunca acepta un `vehiculo_id` del cliente,
    así que no hay forma de pedir la ficha de un vehículo ajeno."""
    vehiculo = await db.vehiculos.find_one({"propietario_id": conductor_id})
    if vehiculo is None:
        raise VehiculoConductorNoAsignadoError()
    return await obtener_ficha_vehiculo(db, vehiculo_id=vehiculo["_id"])


def _costo_estimado(mano_obra_estimada: float, repuestos_estimados: list[dict]) -> float:
    """Ronda 2, Fase G (punto 1): proyección de costo, nunca persistida --
    se recalcula siempre desde `mano_obra_estimada` + suma de
    `repuestos_estimados`, igual que `proxima_km_preventivo` se recalcula
    desde `km_salida` en vez de guardarse."""
    total_repuestos = sum(r["cantidad"] * r["costo_unitario"] for r in repuestos_estimados)
    return round(mano_obra_estimada + total_repuestos, 2)


async def crear_orden(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    actor_id: str,
    actor_rol: str,
    vehiculo_id: str,
    tipo: str,
    descripcion: str,
    km_entrada: int,
    taller: str,
    fecha_programada: date,
    retirar_vehiculo: bool,
    repuestos_estimados: list[schemas.RepuestoInput],
    evidencias: list[str] | None = None,
    mano_obra_estimada: float = 0.0,
    orden_madre_id: str | None = None,
) -> dict:
    vehiculo = await db.vehiculos.find_one({"_id": vehiculo_id})
    if vehiculo is None:
        raise VehiculoNoEncontradoError()

    orden_id = str(uuid.uuid4())
    orden = {
        "_id": orden_id,
        "vehiculo_id": vehiculo_id,
        "tipo": tipo,
        "estado": "ABIERTA",
        "descripcion": descripcion,
        "km_entrada": km_entrada,
        "km_salida": None,
        "taller": taller,
        "fecha_programada": fecha_programada.isoformat(),
        "fecha_cierre": None,
        "costo_total": None,
        # Ronda 2, Fase G (punto 2, CU-O13 A1): campo ya existía en el
        # schema desde el inicio del proyecto, nunca se había cableado --
        # ver crear_orden_encadenada más abajo, el único llamador real.
        "orden_madre_id": orden_madre_id,
        "repuestos_estimados": [r.model_dump() for r in repuestos_estimados],
        "repuestos_consumidos": [],
        # Ronda 2, Fase D: solo poblado cuando la orden nace de convertir un
        # reporte de falla (reportes_falla/service.py::convertir_en_orden).
        "evidencias": evidencias or [],
        # Ronda 2, Fase G (punto 1): costo estimado vs. real.
        "mano_obra_estimada": mano_obra_estimada,
    }

    if retirar_vehiculo:
        # La orden y el retiro del vehículo son dos entidades de negocio
        # distintas mutadas por la misma operación — se envuelven en una
        # transacción para que no quede una orden creada con el vehículo
        # todavía HABILITADO (o viceversa) si algo falla a mitad de camino.
        await with_transaction(
            get_mongo_client(),
            lambda session: _crear_orden_con_retiro(db, orden, actor_id=actor_id, actor_rol=actor_rol, session=session),
        )
    else:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_REGISTRO,
            entidad="ordenes",
            entidad_id=orden_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"vehiculo_id": vehiculo_id, "tipo": tipo},
        )
        await db.ordenes.insert_one(orden)

    if vehiculo.get("propietario_id"):
        await dispatcher.notify_user(
            vehiculo["propietario_id"], "ORDEN_MANTENIMIENTO_REGISTRADA", {"orden_id": orden_id, "tipo": tipo}
        )

    return orden


async def _crear_orden_con_retiro(
    db: AsyncIOMotorDatabase, orden: dict, *, actor_id: str, actor_rol: str, session
) -> None:
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_REGISTRO,
        entidad="ordenes",
        entidad_id=orden["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"vehiculo_id": orden["vehiculo_id"], "tipo": orden["tipo"]},
        session=session,
    )
    await db.ordenes.insert_one(orden, session=session)

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_RETIRO,
        entidad="vehiculos",
        entidad_id=orden["vehiculo_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"motivo": f"orden {orden['_id']}"},
        session=session,
    )
    await db.vehiculos.update_one(
        {"_id": orden["vehiculo_id"]},
        {"$set": {"estado_habilitacion": "RETIRADO_DE_SERVICIO"}},
        session=session,
    )


async def marcar_en_taller(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, orden_id: str) -> dict:
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] != "ABIERTA":
        raise OrdenEstadoInvalidoError("ABIERTA")

    # Ronda 2, Fase E/G (H8): esta transición nunca se auditaba, a diferencia
    # de crear/cerrar/anular -- mismo contrato write-ahead que el resto de
    # este archivo, corregido de paso al construir el estado nuevo.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_EN_TALLER,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "ABIERTA"},
        datos_posteriores={"estado": "EN_TALLER"},
    )
    await db.ordenes.update_one({"_id": orden_id}, {"$set": {"estado": "EN_TALLER"}})
    orden["estado"] = "EN_TALLER"
    return orden


async def _resolver_nombre_actor(db: AsyncIOMotorDatabase, actor_id: str) -> str | None:
    usuario = await db.usuarios.find_one({"_id": actor_id}, {"nombre": 1})
    return usuario["nombre"] if usuario else None


async def _registrar_actividad(
    db: AsyncIOMotorDatabase,
    *,
    orden_id: str,
    actor_id: str,
    actor_nombre: str | None,
    rol: str,
    tipo: str,
    detalle: str,
    evidencias: list[str],
) -> dict:
    """Ronda 2, Fase F: bitácora propia de la orden -- insert-only, igual
    que `bitacora` global, pero embebida (`ordenes.actividades`) porque es
    detalle operativo de UNA orden, no un evento de auditoría de sistema.
    No duplica `write_audit_event` -- las transiciones de estado que además
    generan una actividad (ver marcar_esperando_repuesto/reanudar_taller)
    siguen auditándose aparte, esto es la vista legible para quien abre la
    orden."""
    actividad = {
        "ts": datetime.now(UTC),
        "actor_id": actor_id,
        "actor_nombre": actor_nombre,
        "rol": rol,
        "tipo": tipo,
        "detalle": detalle,
        "evidencias": evidencias,
    }
    await db.ordenes.update_one({"_id": orden_id}, {"$push": {"actividades": actividad}})
    return actividad


async def marcar_esperando_repuesto(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, orden_id: str, motivo: str
) -> dict:
    """Ronda 2, Fase E (CU-O12 A3): EN_TALLER -> ESPERANDO_REPUESTO, con
    motivo obligatorio (espera visible, no un limbo silencioso)."""
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] != "EN_TALLER":
        raise OrdenEstadoInvalidoError("EN_TALLER")

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_ESPERA_REPUESTO,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "EN_TALLER"},
        datos_posteriores={"estado": "ESPERANDO_REPUESTO", "motivo_espera": motivo},
    )
    await db.ordenes.update_one(
        {"_id": orden_id}, {"$set": {"estado": "ESPERANDO_REPUESTO", "motivo_espera": motivo}}
    )
    # Fase F: la transición queda además como actividad legible en la
    # cronología de la orden -- automática, no un paso manual aparte.
    actor_nombre = await _resolver_nombre_actor(db, actor_id)
    actividad = await _registrar_actividad(
        db,
        orden_id=orden_id,
        actor_id=actor_id,
        actor_nombre=actor_nombre,
        rol=actor_rol,
        tipo="CAMBIO_ESTADO",
        detalle=f"Pasó a espera de repuesto: {motivo}",
        evidencias=[],
    )
    orden["estado"] = "ESPERANDO_REPUESTO"
    orden["motivo_espera"] = motivo
    orden["actividades"] = [*orden.get("actividades", []), actividad]
    return orden


async def reanudar_taller(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, orden_id: str) -> dict:
    """Ronda 2, Fase E: ESPERANDO_REPUESTO -> EN_TALLER (el repuesto llegó,
    el taller retoma el trabajo). `motivo_espera` se conserva como rastro
    histórico -- no se limpia al volver, ver nota en schemas.py."""
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] != "ESPERANDO_REPUESTO":
        raise OrdenEstadoInvalidoError("ESPERANDO_REPUESTO")

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_REANUDACION,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "ESPERANDO_REPUESTO"},
        datos_posteriores={"estado": "EN_TALLER"},
    )
    await db.ordenes.update_one({"_id": orden_id}, {"$set": {"estado": "EN_TALLER"}})
    actor_nombre = await _resolver_nombre_actor(db, actor_id)
    actividad = await _registrar_actividad(
        db,
        orden_id=orden_id,
        actor_id=actor_id,
        actor_nombre=actor_nombre,
        rol=actor_rol,
        tipo="CAMBIO_ESTADO",
        detalle="Reanudó el trabajo en taller (repuesto disponible)",
        evidencias=[],
    )
    orden["estado"] = "EN_TALLER"
    orden["actividades"] = [*orden.get("actividades", []), actividad]
    return orden


# Ronda "corrección acotada por estado": qué campos son corregibles depende
# de en qué estado está la orden -- ver el docstring de `CorregirOrdenRequest`
# (schemas.py) para el análisis completo. ABIERTA es superset de EN_TALLER/
# ESPERANDO_REPUESTO a propósito (los 2 campos de EN_TALLER también valen
# en ABIERTA, nunca al revés).
_CAMPOS_CORRECCION_ABIERTA = {"descripcion", "taller", "fecha_programada", "repuestos_estimados", "mano_obra_estimada"}
_CAMPOS_CORRECCION_EN_TALLER = {"repuestos_estimados", "mano_obra_estimada"}


async def corregir_orden(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    orden_id: str,
    descripcion: str | None,
    taller: str | None,
    fecha_programada: date | None,
    repuestos_estimados: list[schemas.RepuestoInput] | None,
    mano_obra_estimada: float | None,
    motivo: str,
) -> dict:
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] not in ("ABIERTA", "EN_TALLER", "ESPERANDO_REPUESTO"):
        raise OrdenEstadoInvalidoError("ABIERTA, EN_TALLER o ESPERANDO_REPUESTO")

    campos_permitidos = (
        _CAMPOS_CORRECCION_ABIERTA if orden["estado"] == "ABIERTA" else _CAMPOS_CORRECCION_EN_TALLER
    )

    cambios: dict = {}
    if descripcion is not None:
        if "descripcion" not in campos_permitidos:
            raise CampoNoCorregibleEnEsteEstadoError("descripcion", orden["estado"])
        cambios["descripcion"] = descripcion
    if taller is not None:
        if "taller" not in campos_permitidos:
            raise CampoNoCorregibleEnEsteEstadoError("taller", orden["estado"])
        cambios["taller"] = taller
    if fecha_programada is not None:
        if "fecha_programada" not in campos_permitidos:
            raise CampoNoCorregibleEnEsteEstadoError("fecha_programada", orden["estado"])
        cambios["fecha_programada"] = fecha_programada.isoformat()
    if repuestos_estimados is not None:
        cambios["repuestos_estimados"] = [r.model_dump() for r in repuestos_estimados]
    if mano_obra_estimada is not None:
        cambios["mano_obra_estimada"] = mano_obra_estimada

    if not cambios:
        return orden

    datos_previos = {k: orden.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_CORRECCION,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=datos_previos,
        datos_posteriores={**cambios, "motivo": motivo},
    )
    await db.ordenes.update_one({"_id": orden_id}, {"$set": cambios})
    orden.update(cambios)

    # Además del evento de auditoría formal, queda en la cronología legible
    # de la orden (Fase F) -- mismo criterio ya usado para las transiciones
    # automáticas de ESPERANDO_REPUESTO/REANUDACION.
    etiquetas_campo = {
        "descripcion": "descripción",
        "taller": "taller",
        "fecha_programada": "fecha programada",
        "repuestos_estimados": "repuestos estimados",
        "mano_obra_estimada": "mano de obra estimada",
    }
    campos_txt = ", ".join(etiquetas_campo[c] for c in cambios)
    actor_nombre = await _resolver_nombre_actor(db, actor_id)
    actividad = await _registrar_actividad(
        db,
        orden_id=orden_id,
        actor_id=actor_id,
        actor_nombre=actor_nombre,
        rol=actor_rol,
        tipo="COMENTARIO",
        detalle=f"Corrigió {campos_txt}. Motivo: {motivo}",
        evidencias=[],
    )
    orden["actividades"] = [*orden.get("actividades", []), actividad]
    return orden


async def agregar_actividad(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, orden_id: str, detalle: str, evidencias: list[str]
) -> dict:
    """Ronda 2, Fase F: comentario/avance manual del Jefe de Mantenimiento
    -- solo mientras la orden está activa en taller (EN_TALLER o
    ESPERANDO_REPUESTO); antes de entrar a taller o después de cerrada/
    anulada no hay "avance" que registrar."""
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] not in ("EN_TALLER", "ESPERANDO_REPUESTO"):
        raise OrdenEstadoInvalidoError("EN_TALLER o ESPERANDO_REPUESTO")

    actor_nombre = await _resolver_nombre_actor(db, actor_id)
    actividad = await _registrar_actividad(
        db,
        orden_id=orden_id,
        actor_id=actor_id,
        actor_nombre=actor_nombre,
        rol=actor_rol,
        tipo="COMENTARIO",
        detalle=detalle,
        evidencias=evidencias,
    )
    orden["actividades"] = [*orden.get("actividades", []), actividad]
    return orden


async def listar_ordenes(
    db: AsyncIOMotorDatabase,
    *,
    estado: str | None = None,
    vehiculo_id: str | None = None,
    placa: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filtro: dict = {}
    if estado:
        filtro["estado"] = estado
    if vehiculo_id:
        filtro["vehiculo_id"] = vehiculo_id
    if placa:
        vehiculos = await db.vehiculos.find({"placa": {"$regex": placa, "$options": "i"}}, {"_id": 1}).to_list(
            length=200
        )
        ids = [v["_id"] for v in vehiculos]
        filtro["vehiculo_id"] = {"$in": ids} if ids else "__ninguno__"
    total = await db.ordenes.count_documents(filtro)
    # Más reciente primero (ronda de orden por defecto en tablas). `ordenes`
    # no tiene un campo de fecha de creación propio -- `fecha_programada` es
    # el único disponible, así que es una aproximación (orden programada más
    # adelante primero), no "creada más recientemente primero" en sentido
    # estricto. Agregar una fecha de creación real es un cambio de esquema,
    # fuera de alcance de este ajuste de presentación.
    items = (
        await db.ordenes.find(filtro)
        .sort("fecha_programada", -1)
        .skip(offset)
        .limit(limit)
        .to_list(length=limit)
    )
    return items, total


async def cerrar_orden(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    actor_id: str,
    actor_rol: str,
    orden_id: str,
    body: schemas.OrdenCerrarRequest,
) -> dict:
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    # Ronda 2, Fase E: una orden puede cerrarse tanto desde EN_TALLER como
    # desde ESPERANDO_REPUESTO (el repuesto pudo llegar y el taller cierra
    # de una vez, sin pasar de nuevo por "reanudar").
    if orden["estado"] not in ("EN_TALLER", "ESPERANDO_REPUESTO"):
        raise OrdenEstadoInvalidoError("EN_TALLER o ESPERANDO_REPUESTO")
    # A3: kilometraje de salida menor al de entrada requiere ajuste
    # justificado explícito, registrado en la bitácora (no silencioso).
    if body.km_salida < orden["km_entrada"] and not body.ajuste_justificado:
        raise KmSalidaMenorError()

    ahora = datetime.now(UTC)

    # Ronda 2, Fase G (punto 1): costo estimado vs. real -- calculado ANTES
    # de auditar para que la desviación quede en el MISMO evento
    # ORDEN_MANTENIMIENTO_CIERRE que ya existía, sin un evento nuevo.
    costo_estimado = _costo_estimado(orden.get("mano_obra_estimada", 0.0) or 0.0, orden.get("repuestos_estimados", []))
    desviacion_pct = (
        round((body.costo_total - costo_estimado) / costo_estimado * 100, 2) if costo_estimado > 0 else None
    )

    if body.habilitar_vehiculo:
        orden_actualizada = await with_transaction(
            get_mongo_client(),
            lambda session: _cerrar_orden_con_habilitacion(
                db,
                orden,
                body=body,
                actor_id=actor_id,
                actor_rol=actor_rol,
                ahora=ahora,
                costo_estimado=costo_estimado,
                desviacion_pct=desviacion_pct,
                session=session,
            ),
        )
    else:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_CIERRE,
            entidad="ordenes",
            entidad_id=orden_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={
                "costo_total": body.costo_total,
                "costo_estimado": costo_estimado,
                "desviacion_costo_pct": desviacion_pct,
            },
        )
        await db.ordenes.update_one(
            {"_id": orden_id},
            {
                "$set": {
                    "estado": "CERRADA",
                    "trabajos_realizados": body.trabajos_realizados,
                    "repuestos_consumidos": [r.model_dump() for r in body.repuestos_consumidos],
                    "costo_total": body.costo_total,
                    "horas_taller": body.horas_taller,
                    "km_salida": body.km_salida,
                    "fecha_cierre": ahora,
                }
            },
        )
        orden_actualizada = dict(orden)
        orden_actualizada.update(
            estado="CERRADA",
            trabajos_realizados=body.trabajos_realizados,
            repuestos_consumidos=[r.model_dump() for r in body.repuestos_consumidos],
            costo_total=body.costo_total,
            horas_taller=body.horas_taller,
            km_salida=body.km_salida,
            fecha_cierre=ahora,
        )

    if body.ajuste_justificado and body.km_salida < orden["km_entrada"]:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_CIERRE,
            entidad="vehiculos",
            entidad_id=orden["vehiculo_id"],
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"ajuste_km": body.km_salida, "motivo": body.motivo_ajuste},
        )

    vehiculo = await db.vehiculos.find_one({"_id": orden["vehiculo_id"]})
    if vehiculo and vehiculo.get("propietario_id"):
        await dispatcher.notify_user(
            vehiculo["propietario_id"],
            "ORDEN_MANTENIMIENTO_CERRADA",
            {"orden_id": orden_id, "costo_total": body.costo_total},
        )

    # H9 (CU-O13 P2): "el sistema recalcula la fecha/kilometraje de la
    # próxima intervención preventiva" -- proyección, no un campo persistido
    # (ver nota en schemas.py::OrdenOut.proxima_km_preventivo). Mismo umbral
    # global documentado en obtener_ficha_vehiculo.
    orden_actualizada["proxima_km_preventivo"] = body.km_salida + UMBRAL_KM_PREVENTIVO
    orden_actualizada["costo_estimado"] = costo_estimado
    orden_actualizada["desviacion_costo_pct"] = desviacion_pct

    # Ronda 2, Fase G (punto 2, CU-O13 A1): "abrir correctiva encadenada" al
    # cerrar -- crea la orden hija DESPUÉS de que el cierre ya se confirmó
    # (no envuelta en la misma transacción: el cierre es el hecho de negocio
    # completo por sí solo, la encadenada es una conveniencia que no debe
    # poder revertir un cierre ya válido si algo le falla a ella).
    if body.orden_encadenada is not None:
        hija = await crear_orden(
            db,
            dispatcher,
            actor_id=actor_id,
            actor_rol=actor_rol,
            vehiculo_id=orden["vehiculo_id"],
            tipo="CORRECTIVA",
            descripcion=body.orden_encadenada.descripcion,
            km_entrada=body.km_salida,
            taller=body.orden_encadenada.taller,
            fecha_programada=body.orden_encadenada.fecha_programada,
            retirar_vehiculo=False,
            repuestos_estimados=[],
            orden_madre_id=orden_id,
        )
        orden_actualizada["orden_encadenada_id"] = hija["_id"]

    return orden_actualizada


async def _cerrar_orden_con_habilitacion(
    db: AsyncIOMotorDatabase,
    orden: dict,
    *,
    body: schemas.OrdenCerrarRequest,
    actor_id: str,
    actor_rol: str,
    ahora: datetime,
    costo_estimado: float,
    desviacion_pct: float | None,
    session,
) -> dict:
    orden_id = orden["_id"]

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_CIERRE,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={
            "costo_total": body.costo_total,
            "costo_estimado": costo_estimado,
            "desviacion_costo_pct": desviacion_pct,
        },
        session=session,
    )
    await db.ordenes.update_one(
        {"_id": orden_id},
        {
            "$set": {
                "estado": "CERRADA",
                "trabajos_realizados": body.trabajos_realizados,
                "repuestos_consumidos": [r.model_dump() for r in body.repuestos_consumidos],
                "costo_total": body.costo_total,
                "horas_taller": body.horas_taller,
                "km_salida": body.km_salida,
                "fecha_cierre": ahora,
            }
        },
        session=session,
    )

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_HABILITACION,
        entidad="vehiculos",
        entidad_id=orden["vehiculo_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"orden_id": orden_id},
        session=session,
    )
    # Decisión 3: solo re-habilita si estaba retirado POR MANTENIMIENTO. Sin
    # este filtro, cerrar una orden resucitaría un vehículo `DADO_DE_BAJA`
    # (salida permanente de la flota). `anular_orden` ya tenía este mismo
    # guard; acá faltaba porque hasta ahora no existía un tercer estado.
    await db.vehiculos.update_one(
        {"_id": orden["vehiculo_id"], "estado_habilitacion": ESTADO_RETIRADO_DE_SERVICIO},
        {"$set": {"estado_habilitacion": ESTADO_HABILITADO}},
        session=session,
    )

    resultado = dict(orden)
    resultado.update(
        estado="CERRADA",
        trabajos_realizados=body.trabajos_realizados,
        repuestos_consumidos=[r.model_dump() for r in body.repuestos_consumidos],
        costo_total=body.costo_total,
        horas_taller=body.horas_taller,
        km_salida=body.km_salida,
        fecha_cierre=ahora,
    )
    return resultado


async def anular_orden(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, orden_id: str, motivo: str) -> dict:
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] != "ABIERTA":
        raise OrdenEstadoInvalidoError("ABIERTA")

    vehiculo = await db.vehiculos.find_one({"_id": orden["vehiculo_id"]})
    debe_reabilitar = bool(vehiculo) and vehiculo.get("estado_habilitacion") == "RETIRADO_DE_SERVICIO"

    if debe_reabilitar:
        orden_actualizada = await with_transaction(
            get_mongo_client(),
            lambda session: _anular_orden_con_rehabilitacion(
                db, orden, motivo=motivo, actor_id=actor_id, actor_rol=actor_rol, session=session
            ),
        )
    else:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_ANULACION,
            entidad="ordenes",
            entidad_id=orden_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"motivo": motivo},
        )
        await db.ordenes.update_one({"_id": orden_id}, {"$set": {"estado": "ANULADA", "motivo_anulacion": motivo}})
        orden_actualizada = dict(orden)
        orden_actualizada.update(estado="ANULADA")

    return orden_actualizada


async def _anular_orden_con_rehabilitacion(
    db: AsyncIOMotorDatabase, orden: dict, *, motivo: str, actor_id: str, actor_rol: str, session
) -> dict:
    orden_id = orden["_id"]

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_ANULACION,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"motivo": motivo},
        session=session,
    )
    await db.ordenes.update_one(
        {"_id": orden_id}, {"$set": {"estado": "ANULADA", "motivo_anulacion": motivo}}, session=session
    )

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_HABILITACION,
        entidad="vehiculos",
        entidad_id=orden["vehiculo_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"motivo": f"orden {orden_id} anulada"},
        session=session,
    )
    await db.vehiculos.update_one(
        {"_id": orden["vehiculo_id"]}, {"$set": {"estado_habilitacion": "HABILITADO"}}, session=session
    )

    resultado = dict(orden)
    resultado.update(estado="ANULADA")
    return resultado


async def listar_vehiculos_retirados(db: AsyncIOMotorDatabase) -> list[dict]:
    """Panel táctico -- CU-T04/OT7.1, informe simple (MongoDB):
    vehículos `RETIRADO_DE_SERVICIO` y la orden abierta que los retiene."""
    resultado: list[dict] = []
    async for vehiculo in db.vehiculos.find({"estado_habilitacion": "RETIRADO_DE_SERVICIO"}):
        # Ronda 2, Fase E: ESPERANDO_REPUESTO retiene el vehículo tanto como
        # EN_TALLER -- sin este estado en el filtro, un vehículo esperando
        # repuesto dejaría de aparecer como "retirado por una orden real"
        # (mostraría orden_id=None pese a seguir RETIRADO_DE_SERVICIO).
        orden = await db.ordenes.find_one(
            {"vehiculo_id": vehiculo["_id"], "estado": {"$in": ["ABIERTA", "EN_TALLER", "ESPERANDO_REPUESTO"]}},
            sort=[("fecha_programada", 1)],
        )
        resultado.append(
            {
                "vehiculo_id": vehiculo["_id"],
                "placa": vehiculo["placa"],
                "orden_id": orden["_id"] if orden else None,
                "orden_estado": orden["estado"] if orden else None,
                "fecha_programada": orden["fecha_programada"] if orden else None,
            }
        )
    # Más reciente primero (ronda de orden por defecto en tablas). `vehiculos`
    # no tiene fecha propia, pero la orden que lo retiene sí -- se ordena por
    # esa, que además es el dato que el panel muestra en la fila. Los que no
    # tienen orden asociada (`None`) quedan al final, nunca arriba simulando
    # ser los más recientes.
    resultado.sort(key=lambda v: (v["fecha_programada"] is not None, v["fecha_programada"] or ""), reverse=True)
    return resultado


def obtener_cumplimiento_plan_preventivo() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico -- CU-T04/OT7.1."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_cumplimiento_plan_preventivo")
    finally:
        client.close()
    return sorted(filas, key=lambda f: f["periodo"])


async def obtener_costo_mantenimiento_top(db: AsyncIOMotorDatabase, *, top: int = 5) -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico -- CU-T11/OT7.2.

    El snapshot trae una fila por vehículo x periodo (mes); para el ranking
    del dashboard se acumula por vehículo (todos los periodos publicados) y
    se toman los `top` de mayor costo. `rpt_costo_mantenimiento_vehiculo` no
    tiene la placa (solo `vehiculo_id`, dimensión Gold) -- se resuelve acá
    mismo con un solo `$in` a Mongo, igual patrón que `obtener_placas_vehiculos`."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_costo_mantenimiento_vehiculo")
    finally:
        client.close()

    acumulado: dict[str, dict] = {}
    for fila in filas:
        acc = acumulado.setdefault(
            fila["vehiculo_id"], {"vehiculo_id": fila["vehiculo_id"], "costo_total": 0.0, "total_ordenes": 0}
        )
        acc["costo_total"] += fila["costo_total"]
        acc["total_ordenes"] += fila["total_ordenes"]

    resultado = sorted(acumulado.values(), key=lambda f: f["costo_total"], reverse=True)[:top]
    placas = await obtener_placas_vehiculos(db, {f["vehiculo_id"] for f in resultado})
    for fila in resultado:
        fila["vehiculo_placa"] = placas.get(fila["vehiculo_id"])
        fila["periodo"] = "acumulado"
    return resultado


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Estado y Costo de Flota
# (OE2b, nivel_estrategico.md §3.2.b, patrón Z)
# ---------------------------------------------------------------------------


async def obtener_panel_estado_costo_flota(
    db: AsyncIOMotorDatabase, *, meses: int = 12, top: int = 10
) -> dict:
    """Segunda capa de agregación sobre `rpt_cumplimiento_plan_preventivo` +
    `rpt_costo_mantenimiento_vehiculo`, sin tabla nueva.

    Las 2 fuentes ya traen `periodo` (mes) dentro del último snapshot, así
    que la tendencia extendida sale del propio `fetch_latest_snapshot` sin
    necesitar historial de cortes -- ver `core/agregacion_estrategica`, caso 1.

    **`km_recorridos` va siempre en `None`, a propósito.** La spec pide una
    tabla de "vehículos candidatos a reemplazo (costo vs. km recorridos)",
    pero el kilometraje no existe en ninguna de las 2 tablas `rpt_*` ni en
    ninguna otra vista publicada del nivel táctico. Los únicos km del sistema
    viven en `ordenes.km_entrada`/`km_salida` (Mongo), y la Sección 2 de la
    spec estratégica prohíbe explícitamente consultar Mongo para un informe
    de este nivel. Se declara `km_disponible=false` en metadata en vez de
    inventar un proxy -- mismo criterio que el gap de zona.

    El único acceso a Mongo de esta función resuelve la **placa** de cada
    vehículo del ranking (dato descriptivo, no una métrica), exactamente el
    mismo patrón ya aceptado en `obtener_costo_mantenimiento_top` del nivel
    táctico.
    """
    client = get_clickhouse_client()
    try:
        preventivo = fetch_latest_snapshot(client, "rpt_cumplimiento_plan_preventivo")
        costos = fetch_latest_snapshot(client, "rpt_costo_mantenimiento_vehiculo")
    finally:
        client.close()

    periodos = ultimos_periodos([f["periodo"] for f in preventivo] + [f["periodo"] for f in costos], meses)
    periodos_set = set(periodos)

    por_periodo_prev = agrupar([f for f in preventivo if f["periodo"] in periodos_set], "periodo")
    tendencia_preventivo = [
        {
            "periodo": periodo,
            "pct_cumplimiento": promedio_ponderado(por_periodo_prev[periodo], "pct_cumplimiento", "total_ordenes")
            or 0.0,
            "total_ordenes": sum(f["total_ordenes"] for f in por_periodo_prev[periodo]),
        }
        for periodo in periodos
        if periodo in por_periodo_prev
    ]

    por_periodo_costo = agrupar([f for f in costos if f["periodo"] in periodos_set], "periodo")
    tendencia_costo = [
        {
            "periodo": periodo,
            "costo_total": round(sum(f["costo_total"] for f in por_periodo_costo[periodo]), 2),
            "total_ordenes": sum(f["total_ordenes"] for f in por_periodo_costo[periodo]),
        }
        for periodo in periodos
        if periodo in por_periodo_costo
    ]

    pct_actual = tendencia_preventivo[-1]["pct_cumplimiento"] if tendencia_preventivo else None
    pct_previo = tendencia_preventivo[-2]["pct_cumplimiento"] if len(tendencia_preventivo) > 1 else None
    costo_actual = tendencia_costo[-1]["costo_total"] if tendencia_costo else None
    costo_previo = tendencia_costo[-2]["costo_total"] if len(tendencia_costo) > 1 else None
    # Tier 1, punto 6 (H-T5): `pct_cumplimiento_preventivo` es un promedio
    # ponderado por `total_ordenes` -- el n real del periodo anterior es ese
    # peso, no el propio `pct_previo`. `costo_previo` en cambio ya es una
    # suma en dólares, no un ratio; se usa `total_ordenes` del mismo periodo
    # como proxy de cuántas órdenes reales respaldan esa cifra.
    ordenes_previas_preventivo = (
        tendencia_preventivo[-2]["total_ordenes"] if len(tendencia_preventivo) > 1 else None
    )
    ordenes_previas_costo = tendencia_costo[-2]["total_ordenes"] if len(tendencia_costo) > 1 else None

    acumulado: dict[str, dict] = {}
    for fila in costos:
        if fila["periodo"] not in periodos_set:
            continue
        acc = acumulado.setdefault(
            fila["vehiculo_id"],
            {"vehiculo_id": fila["vehiculo_id"], "costo_total": 0.0, "total_ordenes": 0, "periodos": 0},
        )
        acc["costo_total"] += fila["costo_total"]
        acc["total_ordenes"] += fila["total_ordenes"]
        acc["periodos"] += 1

    candidatos = sorted(acumulado.values(), key=lambda f: f["costo_total"], reverse=True)[:top]
    placas = await obtener_placas_vehiculos(db, {f["vehiculo_id"] for f in candidatos})
    for fila in candidatos:
        fila["costo_total"] = round(fila["costo_total"], 2)
        fila["vehiculo_placa"] = placas.get(fila["vehiculo_id"])
        fila["costo_promedio_mes"] = round(fila["costo_total"] / fila["periodos"], 2) if fila["periodos"] else None
        fila["km_recorridos"] = None  # ver docstring: no existe en ninguna rpt_*

    return {
        "kpis": {
            "pct_cumplimiento_preventivo": pct_actual,
            "variacion_cumplimiento_pct": variacion_pct(pct_actual, pct_previo),
            "costo_mantenimiento_periodo": costo_actual,
            "variacion_costo_pct": variacion_pct(costo_actual, costo_previo),
            "costo_acumulado": round(sum(f["costo_total"] for f in acumulado.values()), 2) if acumulado else None,
        },
        "tendencia_preventivo": tendencia_preventivo,
        "tendencia_costo": tendencia_costo,
        "candidatos_reemplazo": candidatos,
        "metadata": {
            "meses": meses,
            "km_disponible": False,
            "fuentes": ["rpt_cumplimiento_plan_preventivo", "rpt_costo_mantenimiento_vehiculo"],
            "registros_previos": {
                "variacion_cumplimiento_pct": ordenes_previas_preventivo,
                "variacion_costo_pct": ordenes_previas_costo,
            },
        },
    }
