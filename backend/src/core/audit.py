"""Bitácora de auditoría — CU-O17 (operativo_cumplimiento.md).

Contrato que todo módulo de dominio debe respetar (write-ahead, línea 120 de
arquitectura_software.md): se llama a `write_audit_event(...)` INMEDIATAMENTE
ANTES de ejecutar el efecto de negocio (la escritura que cambia estado — crear
un viaje, registrar un pago, aprobar una solicitud, etc.), nunca después.
Si esta función lanza `AuditWriteError`, el módulo llamante debe abortar la
operación sin ejecutar el efecto — no atraparla en silencio.

La colección `bitacora` es de solo inserción: ninguna API del sistema expone
update/delete sobre ella (ver §1.6 de diseno_base_datos.md).
"""

from datetime import datetime, UTC
from enum import StrEnum
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession, AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from src.core.exceptions import AuditWriteError


class ResultadoAuditoria(StrEnum):
    OK = "OK"
    DENEGADO = "DENEGADO"
    ERROR = "ERROR"


# Catálogo mínimo de eventos sensibles (CU-O17, precondición): toda escritura de
# negocio relevante debe usar una de estas acciones para que el catálogo se
# mantenga auditable y consistente entre módulos.
class AccionAuditoria(StrEnum):
    VIAJE_TRANSICION_ESTADO = "VIAJE_TRANSICION_ESTADO"
    VIAJE_CANCELADO_PASAJERO = "VIAJE_CANCELADO_PASAJERO"
    PASAJERO_REGISTRO = "PASAJERO_REGISTRO"
    SOLICITUD_CONDUCTOR_ENVIO = "SOLICITUD_CONDUCTOR_ENVIO"
    SOLICITUD_CONDUCTOR_TOMA = "SOLICITUD_CONDUCTOR_TOMA"
    SOLICITUD_CONDUCTOR_DECISION = "SOLICITUD_CONDUCTOR_DECISION"
    VEHICULO_RETIRO = "VEHICULO_RETIRO"
    VEHICULO_HABILITACION = "VEHICULO_HABILITACION"
    ORDEN_MANTENIMIENTO_REGISTRO = "ORDEN_MANTENIMIENTO_REGISTRO"
    ORDEN_MANTENIMIENTO_CIERRE = "ORDEN_MANTENIMIENTO_CIERRE"
    ORDEN_MANTENIMIENTO_ANULACION = "ORDEN_MANTENIMIENTO_ANULACION"
    CUMPLIMIENTO_BANDERA_CAMBIO = "CUMPLIMIENTO_BANDERA_CAMBIO"
    PAGO_REGISTRO = "PAGO_REGISTRO"
    PAGO_AJUSTE = "PAGO_AJUSTE"
    LIQUIDACION_EMISION = "LIQUIDACION_EMISION"
    LIQUIDACION_APROBACION = "LIQUIDACION_APROBACION"
    LIQUIDACION_PAGO = "LIQUIDACION_PAGO"
    LIQUIDACION_OBSERVACION = "LIQUIDACION_OBSERVACION"
    DOCUMENTACION_BLOQUEO = "DOCUMENTACION_BLOQUEO"
    CREDENCIAL_CREACION = "CREDENCIAL_CREACION"
    CREDENCIAL_REVOCACION = "CREDENCIAL_REVOCACION"
    SESION_INICIO = "SESION_INICIO"
    PARAMETRO_CAMBIO = "PARAMETRO_CAMBIO"
    ACCESO_DENEGADO = "ACCESO_DENEGADO"
    LOGIN_FALLIDO_CONSECUTIVO = "LOGIN_FALLIDO_CONSECUTIVO"
    POSIBLE_GPS_SPOOFING = "POSIBLE_GPS_SPOOFING"


async def _next_evento_id(db: AsyncIOMotorDatabase, session: AsyncIOMotorClientSession | None) -> int:
    counter = await db.counters.find_one_and_update(
        {"_id": "evento_auditoria"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    return counter["seq"]


async def write_audit_event(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str | None,
    rol: str | None,
    accion: AccionAuditoria | str,
    entidad: str,
    entidad_id: str | None,
    resultado: ResultadoAuditoria,
    ip: str | None = None,
    dispositivo: str | None = None,
    datos_previos: dict[str, Any] | None = None,
    datos_posteriores: dict[str, Any] | None = None,
    session: AsyncIOMotorClientSession | None = None,
) -> dict[str, Any]:
    """`session`: para que esta escritura participe en una transacción
    multi-documento (ver core/db_transaction.with_transaction), pásala tal
    cual la recibe el callback de la transacción. Por defecto None — igual
    que antes de que existiera el helper, para todo el código que no
    necesita atomicidad multi-documento."""
    evento_id = await _next_evento_id(db, session)
    evento = {
        "evento_id": evento_id,
        "ts": datetime.now(UTC),
        "actor_id": actor_id,
        "rol": rol,
        "accion": str(accion),
        "entidad": entidad,
        "entidad_id": entidad_id,
        "resultado": resultado.value,
        "ip": ip,
        "dispositivo": dispositivo,
        "datos_previos": datos_previos,
        "datos_posteriores": datos_posteriores,
    }
    try:
        # La garantía de durabilidad del write-ahead (ambigüedad D5 del plan)
        # se fija con write_concern "majority" a nivel de conexión, en
        # core/db_mongo.py — no aquí por-llamada, para que aplique a toda
        # escritura de la bitácora sin depender de una opción por request.
        await db.bitacora.insert_one(evento, session=session)
    except PyMongoError as exc:
        raise AuditWriteError() from exc
    return evento
