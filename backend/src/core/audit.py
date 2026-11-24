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
    # CU-O07 A6: "si la posición se aleja más de 2 km de la ruta prevista sin
    # recálculo, el sistema recalcula la ruta y lo registra... el dato queda
    # para auditoría". El recálculo en sí ocurre del lado del cliente (ver
    # UMBRAL_DESVIO_RUTA_KM en apps/shared-ui/src/api/rutas.ts) -- esta
    # acción es exclusivamente el registro que la spec exige, vía
    # POST /viajes/conductor/recalculo-ruta (viajes/service_ejecucion.py).
    VIAJE_RECALCULO_RUTA = "VIAJE_RECALCULO_RUTA"
    PASAJERO_REGISTRO = "PASAJERO_REGISTRO"
    SOLICITUD_CONDUCTOR_ENVIO = "SOLICITUD_CONDUCTOR_ENVIO"
    SOLICITUD_CONDUCTOR_TOMA = "SOLICITUD_CONDUCTOR_TOMA"
    SOLICITUD_CONDUCTOR_DECISION = "SOLICITUD_CONDUCTOR_DECISION"
    # Misma ronda de corrección acotada: cédula/licencia/datos del vehículo
    # declarado, mientras la solicitud no llegó a APROBADA -- recién ahí se
    # copian a `usuarios.conductor` y a un documento `vehiculos` nuevo
    # (`_aprobar_solicitud_en_transaccion`); antes de eso viven solo en
    # `solicitudes`, sin usarse en ningún otro lado.
    SOLICITUD_CONDUCTOR_CORRECCION = "SOLICITUD_CONDUCTOR_CORRECCION"
    VEHICULO_RETIRO = "VEHICULO_RETIRO"
    VEHICULO_HABILITACION = "VEHICULO_HABILITACION"
    # Decisión 3 (baja lógica de vehículos): acción propia, NO se reusa
    # VEHICULO_RETIRO. Ese es el retiro TEMPORAL y automático por una orden
    # de mantenimiento (se revierte solo al cerrarla); esto es la salida
    # PERMANENTE de la flota operativa. Compartir la misma acción dejaría los
    # dos casos indistinguibles en la bitácora, que es justo donde hay que
    # poder diferenciarlos.
    VEHICULO_BAJA = "VEHICULO_BAJA"
    # Cierre del CRUD de vehículos (Punto 3): corrección de datos
    # descriptivos, distinta del retiro/baja de estado.
    VEHICULO_EDICION = "VEHICULO_EDICION"
    ORDEN_MANTENIMIENTO_REGISTRO = "ORDEN_MANTENIMIENTO_REGISTRO"
    ORDEN_MANTENIMIENTO_CIERRE = "ORDEN_MANTENIMIENTO_CIERRE"
    ORDEN_MANTENIMIENTO_ANULACION = "ORDEN_MANTENIMIENTO_ANULACION"
    # Ronda 2, Fase E (H8 + CU-O12 A3): "en taller" nunca se auditaba, a
    # diferencia de crear/cerrar/anular -- corregido de paso en esta misma
    # fase (ver Fase G, punto 3, mismo hallazgo, cerrado ya acá para no
    # dejarlo pendiente dos veces). ESPERA_REPUESTO/REANUDACION son las 2
    # transiciones nuevas del estado intermedio.
    ORDEN_MANTENIMIENTO_EN_TALLER = "ORDEN_MANTENIMIENTO_EN_TALLER"
    ORDEN_MANTENIMIENTO_ESPERA_REPUESTO = "ORDEN_MANTENIMIENTO_ESPERA_REPUESTO"
    ORDEN_MANTENIMIENTO_REANUDACION = "ORDEN_MANTENIMIENTO_REANUDACION"
    # Ronda de "corrección acotada por estado": distinta de REGISTRO/CIERRE/
    # ANULACION -- ajusta un campo puntual (descripción/taller/fecha
    # programada/repuestos estimados/mano de obra estimada) mientras la
    # orden sigue en un estado donde ese campo todavía no generó ninguna
    # consecuencia real (ver análisis en el resumen de esa ronda), nunca
    # tras el cierre.
    ORDEN_MANTENIMIENTO_CORRECCION = "ORDEN_MANTENIMIENTO_CORRECCION"
    # Ronda 2 del flujo de fallas (PROPUESTA_FLUJO_FALLA_VEHICULO.md), Fase C:
    # el conductor reporta una falla del vehículo (con o sin viaje activo).
    # Distinta de ORDEN_MANTENIMIENTO_REGISTRO -- un reporte no es todavía una
    # orden, puede convertirse en una (Fase D) o descartarse.
    INCIDENCIA_REPORTADA = "INCIDENCIA_REPORTADA"
    # Ronda 2, Fase D: decisión del Jefe de Mantenimiento sobre un reporte
    # PENDIENTE -- convertirlo en orden real (ORDEN_MANTENIMIENTO_REGISTRO se
    # audita aparte, dentro de mantenimiento.service.crear_orden, sin
    # duplicar) o descartarlo con motivo.
    REPORTE_FALLA_CONVERSION = "REPORTE_FALLA_CONVERSION"
    REPORTE_FALLA_DESCARTE = "REPORTE_FALLA_DESCARTE"
    # Misma ronda de corrección acotada: solo mientras el reporte sigue
    # PENDIENTE -- una vez CONVERTIDO_A_ORDEN o DESCARTADO ya es historial,
    # el propio servicio lo bloquea (`_reporte_pendiente`).
    REPORTE_FALLA_CORRECCION = "REPORTE_FALLA_CORRECCION"
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

    # Módulo de Administración del Sistema (specs/specs-administrativas/
    # admin_sistema.md) — acciones administrativas de alto privilegio,
    # todas sobre la misma bitácora (regla transversal de la spec: "ninguna
    # acción administrativa debe evitar la bitácora ya existente"). El
    # dashboard de Auditoría (Módulo 6.1, PanelAuditoria) filtra por estas
    # para la vista "solo acciones administrativas".
    USUARIO_CREACION = "USUARIO_CREACION"
    USUARIO_EDICION = "USUARIO_EDICION"
    USUARIO_SUSPENSION = "USUARIO_SUSPENSION"
    USUARIO_REACTIVACION = "USUARIO_REACTIVACION"
    USUARIO_BAJA = "USUARIO_BAJA"
    # Autoservicio de baja de cuenta con periodo de gracia (30 días). Son 3
    # acciones distintas de `USUARIO_BAJA` a propósito: esa es la baja
    # ADMINISTRATIVA (un admin la aplica sobre otra cuenta, efecto inmediato);
    # estas son la solicitud del propio titular, su arrepentimiento, y el
    # vencimiento automático del plazo. Nada de esto es la anonimización de
    # CU-O17 A2 (`USUARIO_ANONIMIZACION`), que sigue siendo una acción legal
    # aparte sobre datos personales y nunca se dispara sola desde acá.
    CUENTA_BAJA_SOLICITADA = "CUENTA_BAJA_SOLICITADA"
    CUENTA_BAJA_CANCELADA = "CUENTA_BAJA_CANCELADA"
    CUENTA_BAJA_EFECTIVA = "CUENTA_BAJA_EFECTIVA"
    ROL_MODIFICACION = "ROL_MODIFICACION"
    POLITICA_AUTH_CAMBIO = "POLITICA_AUTH_CAMBIO"
    SESION_CIERRE_REMOTO = "SESION_CIERRE_REMOTO"
    PASSWORD_CAMBIO = "PASSWORD_CAMBIO"
    FLAG_CREACION = "FLAG_CREACION"
    FLAG_MODIFICACION = "FLAG_MODIFICACION"
    # Acción propia (no reutiliza PARAMETRO_CAMBIO) para que el filtro
    # administrativo de Módulo 6.1 no mezcle esto con cambios de
    # tarifa/comisión, que usan la misma entidad genérica "parametros" mas
    # no son acciones administrativas de este documento.
    PARAMETRO_SISTEMA_CAMBIO = "PARAMETRO_SISTEMA_CAMBIO"
    # Módulo 3 (Catálogos y Parámetros de Negocio): genéricas para las 3
    # tablas maestras (zonas, tipos de documento, motivos de cancelación) --
    # `entidad` distingue cuál catálogo cambió, no hace falta una acción por
    # catálogo.
    CATALOGO_CREACION = "CATALOGO_CREACION"
    CATALOGO_EDICION = "CATALOGO_EDICION"
    CATALOGO_ELIMINACION = "CATALOGO_ELIMINACION"
    # Módulo 8.1: registro manual de un despliegue (alcance recortado, ver
    # PLAN_ADMIN_SISTEMA.md §3 nota de 8.1 -- no hay CI/CD real).
    DESPLIEGUE_REGISTRO = "DESPLIEGUE_REGISTRO"
    # Módulo 6.2: TTL de tokens + umbrales de los 3 mecanismos de rate
    # limiting ya existentes (login, refresh, denegaciones RBAC) -- acción
    # propia, distinta de POLITICA_AUTH_CAMBIO (Módulo 1.3, que es solo
    # longitud/complejidad de password y bloqueo de login).
    POLITICA_SEGURIDAD_CAMBIO = "POLITICA_SEGURIDAD_CAMBIO"
    # Módulo 6.3: canal/destinatarios/activo por tipo de alerta -- la nota
    # de seguridad de la spec exige que desactivar una alerta quede
    # auditado, no que sea imposible; este evento cumple esa exigencia.
    ALERTA_CONFIG_CAMBIO = "ALERTA_CONFIG_CAMBIO"
    # Módulo 4: credenciales de integración externa (CU-T03/OT2.1) y
    # rotación de claves de servicios externos ya configurados en el
    # sistema (hoy solo Google Maps -- ver notificaciones/service.py y
    # PLAN_ADMIN_SISTEMA.md para el resto de servicios "no configurados").
    INTEGRACION_CREDENCIAL_CREACION = "INTEGRACION_CREDENCIAL_CREACION"
    INTEGRACION_CREDENCIAL_REVOCACION = "INTEGRACION_CREDENCIAL_REVOCACION"
    INTEGRACION_SERVICIO_ROTACION = "INTEGRACION_SERVICIO_ROTACION"
    # Módulo 5 (Monitoreo): umbrales de latencia/disponibilidad por
    # componente (backend/mongo/redis/clickhouse/airflow) usados para
    # colorear el panel de salud bajo demanda -- ver
    # PLAN_ADMIN_SISTEMA.md §16, nota de alcance 5.2 (sin motor de alertas
    # en tiempo real, evaluación al abrir el panel).
    MONITOREO_UMBRAL_CAMBIO = "MONITOREO_UMBRAL_CAMBIO"
    # Módulo 8.2 (Gobernanza de datos): anonimización irreversible de una
    # cuenta (CU-O17 A2 / derechos ARCO, LOPDP). El evento en sí NUNCA lleva
    # el nombre/teléfono/correo real que se está purgando en
    # `datos_previos`/`datos_posteriores` -- eso derrotaría el propósito de
    # la anonimización, ya que `bitacora` es insert-only y este evento
    # quedaría para siempre. Solo documenta que ocurrió y el seudónimo nuevo
    # (que no es información personal). Ver PLAN_ADMIN_SISTEMA.md §17.
    USUARIO_ANONIMIZACION = "USUARIO_ANONIMIZACION"
    # Módulo 7.1 (Respaldos): disparo manual + restauración de prueba. La
    # restauración SIEMPRE apunta a una base "_restore_test" (nunca
    # `urbanflet`/`urbanflet_gold` reales) -- eso es una garantía de código,
    # no solo un dato del evento, ver `respaldos/service.py`.
    RESPALDO_DISPARO = "RESPALDO_DISPARO"
    RESPALDO_RESTAURACION_PRUEBA = "RESPALDO_RESTAURACION_PRUEBA"
    # Módulo 7.2 (Plan de continuidad): RTO/RPO por dominio + registro de
    # simulacros -- ambos son insumos de un plan de DR, información sensible
    # por sí misma (revela puntos únicos de falla), de ahí que quede
    # auditada igual que el resto de cambios administrativos.
    PLAN_DR_CAMBIO = "PLAN_DR_CAMBIO"
    SIMULACRO_DR_REGISTRO = "SIMULACRO_DR_REGISTRO"
    # Paquete `pkg-ux-complementario` (specs/specs-administrativas/
    # ux_complementaria.md, Sección 1.3/2.2/3.1): autoservicio de cuenta
    # propia -- distinta de USUARIO_EDICION (Módulo 1.1, un admin_sistema
    # editando la cuenta de un tercero) para que el filtro administrativo no
    # mezcle "alguien editó lo suyo" con "un admin editó a otro".
    PERFIL_EDICION = "PERFIL_EDICION"
    # Sección 1.2 (Compartir viaje en tiempo real): generar un enlace público
    # de solo lectura es una acción sensible (expone la posición en vivo del
    # vehículo a quien tenga el enlace) -- se audita igual que cualquier otra
    # activación de algo que afecta la privacidad del viaje.
    VIAJE_COMPARTIR_ACTIVADO = "VIAJE_COMPARTIR_ACTIVADO"
    # Ronda de correcciones (agosto 2026): restablecimiento de contraseña de
    # un usuario existente por `admin_sistema` -- distinta de `PASSWORD_CAMBIO`
    # (autoservicio, el propio titular con su contraseña actual) a propósito,
    # mismo criterio ya aplicado a `CUENTA_BAJA_SOLICITADA` vs `USUARIO_BAJA`:
    # quien revise la bitácora debe poder distinguir "el usuario cambió su
    # propia contraseña" de "un administrador se la restableció".
    USUARIO_PASSWORD_RESTABLECIDA = "USUARIO_PASSWORD_RESTABLECIDA"


# Módulo 6.1 de admin_sistema (specs/specs-administrativas/admin_sistema.md):
# "vista filtrada de la bitácora, con foco exclusivo en acciones
# administrativas (no operativas)". No es una bitácora nueva -- es un
# subconjunto de `AccionAuditoria` ya existente, mantenido a mano (mismo
# criterio que `usuarios/permisos_matriz.py`): si un módulo futuro (3/4/8)
# agrega una acción administrativa nueva, hay que sumarla acá Y en el
# `ACCIONES_ADMINISTRATIVAS` espejo de `apps/web-interno/src/sections/
# AuditoriaAdmin.tsx`.
ACCIONES_ADMINISTRATIVAS: frozenset[AccionAuditoria] = frozenset(
    {
        AccionAuditoria.USUARIO_CREACION,
        AccionAuditoria.USUARIO_EDICION,
        AccionAuditoria.USUARIO_SUSPENSION,
        AccionAuditoria.USUARIO_REACTIVACION,
        AccionAuditoria.USUARIO_BAJA,
        # El cierre de cuenta iniciado por el propio titular y su vencimiento
        # también son trazables desde la auditoría administrativa: quien
        # revise por qué una cuenta dejó de tener acceso debe poder ver que
        # fue voluntaria, no una acción de un administrador.
        AccionAuditoria.CUENTA_BAJA_SOLICITADA,
        AccionAuditoria.CUENTA_BAJA_CANCELADA,
        AccionAuditoria.CUENTA_BAJA_EFECTIVA,
        # Decisión 3: sacar un vehículo de la flota es una acción
        # administrativa sobre un dato maestro, igual que dar de baja una
        # cuenta -- pertenece a la misma vista de auditoría administrativa.
        AccionAuditoria.VEHICULO_BAJA,
        AccionAuditoria.VEHICULO_EDICION,
        AccionAuditoria.ROL_MODIFICACION,
        AccionAuditoria.POLITICA_AUTH_CAMBIO,
        AccionAuditoria.SESION_CIERRE_REMOTO,
        AccionAuditoria.PASSWORD_CAMBIO,
        AccionAuditoria.USUARIO_PASSWORD_RESTABLECIDA,
        AccionAuditoria.FLAG_CREACION,
        AccionAuditoria.FLAG_MODIFICACION,
        AccionAuditoria.PARAMETRO_SISTEMA_CAMBIO,
        AccionAuditoria.CATALOGO_CREACION,
        AccionAuditoria.CATALOGO_EDICION,
        AccionAuditoria.CATALOGO_ELIMINACION,
        AccionAuditoria.DESPLIEGUE_REGISTRO,
        AccionAuditoria.POLITICA_SEGURIDAD_CAMBIO,
        AccionAuditoria.ALERTA_CONFIG_CAMBIO,
        AccionAuditoria.INTEGRACION_CREDENCIAL_CREACION,
        AccionAuditoria.INTEGRACION_CREDENCIAL_REVOCACION,
        AccionAuditoria.INTEGRACION_SERVICIO_ROTACION,
        AccionAuditoria.MONITOREO_UMBRAL_CAMBIO,
        AccionAuditoria.USUARIO_ANONIMIZACION,
        AccionAuditoria.RESPALDO_DISPARO,
        AccionAuditoria.RESPALDO_RESTAURACION_PRUEBA,
        AccionAuditoria.PLAN_DR_CAMBIO,
        AccionAuditoria.SIMULACRO_DR_REGISTRO,
        AccionAuditoria.PERFIL_EDICION,
    }
)


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
