"""Flujo de fallas -- Ronda 2, Fase C (PROPUESTA_FLUJO_FALLA_VEHICULO.md):
reporte de falla del conductor, con o sin viaje activo.

CU-O07 A4 (impide_continuar=true + viaje EN_CURSO): el viaje se cancela y se
crea una nueva solicitud para el pasajero desde la posición del incidente --
reutiliza `viajes.service_ejecucion.cancelar_por_incidencia` (la mitad de
cancelación, mismo patrón write-ahead que el resto del dominio) y
`viajes.service.solicitar_viaje` (la mitad de creación + auto-despacho) tal
cual, sin duplicar ninguna de las dos. Ninguna de las dos funciones se
envuelve junto con la inserción de `reportes_falla` en una sola transacción
multi-documento: cada paso ya es atómico por sí mismo (mismo criterio ya
aplicado en `viajes.service.cancelar_por_conductor`, que tampoco envuelve su
redespacho posterior en la transacción de cancelación) -- un reporte de
falla insertado sin que el redespacho haya terminado todavía es un estado
intermedio válido, no corrupto.

Notificación al Jefe de Mantenimiento: reusa `disparar_alerta` (Módulo 6.3
de admin_sistema), el mismo mecanismo configurable ya usado por
`flota/service.py` para GPS spoofing -- no se reinventa un canal nuevo.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_redis import get_redis
from src.core.exceptions import DomainError
from src.core.notifications import NotificationDispatcher
from src.mantenimiento import service as mantenimiento_service
from src.reportes_falla import schemas
from src.viajes import schemas as viajes_schemas
from src.viajes import service as viajes_service
from src.viajes import service_ejecucion


class VehiculoNoAsignadoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VEHICULO_NO_ASIGNADO", message="No tienes un vehículo asignado", status_code=404
        )


class VehiculoSinPropietarioError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VEHICULO_SIN_PROPIETARIO",
            message="El vehículo no tiene un socio conductor asociado",
            status_code=422,
        )


class TipoFallaInvalidoError(DomainError):
    def __init__(self, tipo_falla: str) -> None:
        super().__init__(
            code="TIPO_FALLA_INVALIDO",
            message=f"'{tipo_falla}' no es un tipo de falla válido o está inactivo",
            status_code=422,
        )


class ReporteFallaNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="REPORTE_FALLA_NO_ENCONTRADO", message="El reporte de falla no existe", status_code=404)


class ReporteFallaYaResueltoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="REPORTE_FALLA_YA_RESUELTO",
            message="El reporte ya fue convertido en orden o descartado",
            status_code=409,
        )


async def _validar_tipo_falla(db: AsyncIOMotorDatabase, tipo_falla: str) -> None:
    doc = await db.motivos_cancelacion.find_one({"nombre": tipo_falla, "categoria": "incidencia", "activo": True})
    if doc is None:
        raise TipoFallaInvalidoError(tipo_falla)


async def crear_reporte_falla(
    db: AsyncIOMotorDatabase,
    *,
    conductor_id: str,
    tipo_falla: str,
    descripcion: str,
    lat: float,
    lon: float,
    impide_continuar: bool,
    evidencias: list[str],
    dispatcher: Any = None,
) -> dict:
    await _validar_tipo_falla(db, tipo_falla)

    vehiculo = await db.vehiculos.find_one({"propietario_id": conductor_id})
    if vehiculo is None:
        raise VehiculoNoAsignadoError()

    viaje = await db.viajes.find_one({"conductor_id": conductor_id, "estado": "EN_CURSO"})
    viaje_id = viaje["_id"] if viaje else None

    reporte_id = str(uuid.uuid4())
    reporte = {
        "_id": reporte_id,
        "vehiculo_id": vehiculo["_id"],
        "vehiculo_placa": vehiculo.get("placa"),
        "conductor_id": conductor_id,
        "viaje_id": viaje_id,
        "tipo_falla": tipo_falla,
        "descripcion": descripcion,
        "lat": lat,
        "lon": lon,
        "ts": datetime.now(UTC),
        "impide_continuar": impide_continuar,
        "estado": "PENDIENTE",
        "orden_id": None,
        "evidencias": evidencias,
        "motivo_descarte": None,
    }

    await write_audit_event(
        db,
        actor_id=conductor_id,
        rol="conductor",
        accion=AccionAuditoria.INCIDENCIA_REPORTADA,
        entidad="reportes_falla",
        entidad_id=reporte_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={
            "vehiculo_id": vehiculo["_id"],
            "tipo_falla": tipo_falla,
            "viaje_id": viaje_id,
            "impide_continuar": impide_continuar,
        },
    )
    await db.reportes_falla.insert_one(reporte)

    viaje_cancelado_id: str | None = None
    # CU-O07 A4: impide_continuar + viaje EN_CURSO -> cancela y dispara una
    # nueva solicitud para el pasajero desde la posición del incidente.
    if impide_continuar and viaje is not None and viaje["estado"] == "EN_CURSO":
        viaje_cancelado = await service_ejecucion.cancelar_por_incidencia(
            db, conductor_id=conductor_id, viaje_id=viaje["_id"]
        )
        viaje_cancelado_id = viaje_cancelado["_id"]
        if viaje_cancelado.get("pasajero_id"):
            nueva_solicitud = viajes_schemas.SolicitarViajeRequest(
                origen_lat=lat,
                origen_lon=lon,
                origen_direccion="Posición del incidente reportado",
                destino_lat=viaje_cancelado.get("destino_lat"),
                destino_lon=viaje_cancelado.get("destino_lon"),
                destino_direccion=viaje_cancelado.get("destino_direccion"),
            )
            try:
                await viajes_service.solicitar_viaje(
                    db, pasajero_id=viaje_cancelado["pasajero_id"], body=nueva_solicitud
                )
            except viajes_service.ViajeActivoExistenteError:
                # Defensivo: no debería poder ocurrir -- el viaje anterior
                # del mismo pasajero acaba de quedar CANCELADO (ya no está
                # en ESTADOS_ACTIVOS) un paso antes.
                pass

        if dispatcher is not None:
            await dispatcher.notify_user(
                viaje_cancelado["pasajero_id"], "VIAJE_CANCELADO_CONDUCTOR", {"viaje_id": viaje_cancelado_id}
            )

    from src.notificaciones.service import disparar_alerta

    motivo_alerta = f"Vehículo {vehiculo.get('placa', vehiculo['_id'])}: {tipo_falla}"
    if impide_continuar:
        motivo_alerta += " (impide continuar)"
    # Dos avisos con propósitos distintos por la MISMA incidencia, ninguno
    # reemplaza al otro -- ver nota en notificaciones/service.py:
    # "reporte_falla" alimenta la bandeja de pre-órdenes del Jefe de
    # Mantenimiento (Fase D); "incidencia_operativa" es el aviso en vivo al
    # Coordinador de Operaciones que exige CU-O07 A4, siempre que se
    # registre una incidencia -- con o sin impide_continuar, con o sin
    # viaje activo, nunca condicionado a si el viaje terminó cancelándose.
    await disparar_alerta(db, dispatcher, tipo_alerta="reporte_falla", motivo=motivo_alerta)
    await disparar_alerta(db, dispatcher, tipo_alerta="incidencia_operativa", motivo=motivo_alerta)

    return reporte


async def crear_reporte_falla_staff(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    vehiculo_id: str,
    tipo_falla: str,
    descripcion: str,
    evidencias: list[str],
    dispatcher: Any = None,
) -> dict:
    """Variante de `crear_reporte_falla` para personal interno
    (`jefe_mantenimiento`) creando el reporte desde `web-interno` en vez del
    conductor desde su app -- mismo modelo de datos (`reportes_falla`), sin
    `viaje_id` ni la lógica de `impide_continuar` (CU-O07 A4): acá no hay
    ningún viaje EN_CURSO de por medio, el vehículo se elige directamente en
    vez de inferirse de un conductor en turno, así que no hay nada que
    cancelar ni redespachar.

    `conductor_id` se resuelve al revés que en el flujo del conductor
    (vehículo -> propietario, en vez de conductor -> vehículo) para que el
    reporte siga significando "este es el socio dueño del vehículo" y para
    que ese socio pueda verlo más tarde en su propio `GET /reportes-falla/
    mias` -- transparencia real, no solo un dato interno.

    `lat`/`lon` se resuelven de la última posición real conocida del vehículo
    (misma caché de Redis que ya usa `flota/service.py` para el tablero en
    vivo) en vez de pedírselas a quien crea el reporte desde un escritorio,
    que no tiene GPS de por medio -- si el vehículo nunca reportó posición,
    quedan en 0.0/0.0 como valor de respaldo (mismo criterio que "sin señal"
    en el resto del sistema, nunca se inventa una coordenada real)."""
    await _validar_tipo_falla(db, tipo_falla)

    vehiculo = await db.vehiculos.find_one({"_id": vehiculo_id})
    if vehiculo is None:
        raise mantenimiento_service.VehiculoNoEncontradoError()

    conductor_id = vehiculo.get("propietario_id")
    if not conductor_id:
        raise VehiculoSinPropietarioError()

    redis = get_redis()
    cache = await redis.hgetall(f"pos:{vehiculo_id}")
    lat = float(cache["lat"]) if cache.get("lat") else 0.0
    lon = float(cache["lon"]) if cache.get("lon") else 0.0

    reporte_id = str(uuid.uuid4())
    reporte = {
        "_id": reporte_id,
        "vehiculo_id": vehiculo["_id"],
        "vehiculo_placa": vehiculo.get("placa"),
        "conductor_id": conductor_id,
        "viaje_id": None,
        "tipo_falla": tipo_falla,
        "descripcion": descripcion,
        "lat": lat,
        "lon": lon,
        "ts": datetime.now(UTC),
        "impide_continuar": False,
        "estado": "PENDIENTE",
        "orden_id": None,
        "evidencias": evidencias,
        "motivo_descarte": None,
    }

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.INCIDENCIA_REPORTADA,
        entidad="reportes_falla",
        entidad_id=reporte_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={
            "vehiculo_id": vehiculo["_id"],
            "tipo_falla": tipo_falla,
            "origen": "personal_interno",
        },
    )
    await db.reportes_falla.insert_one(reporte)

    from src.notificaciones.service import disparar_alerta

    motivo_alerta = f"Vehículo {vehiculo.get('placa', vehiculo['_id'])}: {tipo_falla}"
    # Mismos 2 avisos que el reporte del conductor (ver crear_reporte_falla) --
    # "reporte_falla" a jefe_mantenimiento (puede ser redundante si quien lo
    # creó ya tiene ese rol, pero no hay razón para tratarlo distinto de
    # cualquier otra acción que notifica al mismo rol que la ejecuta) e
    # "incidencia_operativa" a coordinador_operaciones.
    await disparar_alerta(db, dispatcher, tipo_alerta="reporte_falla", motivo=motivo_alerta)
    await disparar_alerta(db, dispatcher, tipo_alerta="incidencia_operativa", motivo=motivo_alerta)

    return reporte


async def listar_reportes_falla(
    db: AsyncIOMotorDatabase, *, estado: str | None = None, conductor_id: str | None = None
) -> list[dict]:
    """Listado de reportes de falla.

    `conductor_id` acota el resultado a los reportes de UN conductor -- es lo
    que usa el autoservicio del propio conductor (`GET /reportes-falla/mias`),
    a diferencia de la bandeja del Jefe de Mantenimiento, que ve todos.
    """
    filtro: dict = {}
    if estado:
        filtro["estado"] = estado
    if conductor_id:
        filtro["conductor_id"] = conductor_id
    return await db.reportes_falla.find(filtro).sort("ts", -1).to_list(length=500)


async def obtener_reporte_falla(db: AsyncIOMotorDatabase, *, reporte_id: str) -> dict:
    doc = await db.reportes_falla.find_one({"_id": reporte_id})
    if doc is None:
        raise ReporteFallaNoEncontradoError()
    return doc


async def _reporte_pendiente(db: AsyncIOMotorDatabase, *, reporte_id: str) -> dict:
    reporte = await obtener_reporte_falla(db, reporte_id=reporte_id)
    if reporte["estado"] != "PENDIENTE":
        raise ReporteFallaYaResueltoError()
    return reporte


def _descripcion_desde_reporte(reporte: dict) -> str:
    """Ronda 2, Fase D: la orden no tiene un campo propio de posición
    (`ordenes` nunca tuvo lat/lon, a diferencia de `viajes`) -- se pliega
    junto con tipo de falla y descripción dentro del texto libre de la
    orden, que sí existe, en vez de inventar un campo nuevo que ningún otro
    consumidor necesita."""
    return (
        f"[Reportado por conductor] {reporte['tipo_falla']}: {reporte['descripcion']} "
        f"(posición: {reporte['lat']:.5f}, {reporte['lon']:.5f})"
    )


async def convertir_reporte_en_orden(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    actor_id: str,
    actor_rol: str,
    reporte_id: str,
    body: schemas.ConvertirReporteRequest,
) -> dict:
    reporte = await _reporte_pendiente(db, reporte_id=reporte_id)

    # Una falla reportada por el conductor es, por definición, reactiva --
    # nunca el chequeo programado que representa PREVENTIVA. No se expone
    # `tipo` en el formulario de conversión a propósito, para no dejar que
    # el Jefe de Mantenimiento reclasifique un reporte real como preventivo.
    orden = await mantenimiento_service.crear_orden(
        db,
        dispatcher,
        actor_id=actor_id,
        actor_rol=actor_rol,
        vehiculo_id=reporte["vehiculo_id"],
        tipo="CORRECTIVA",
        descripcion=_descripcion_desde_reporte(reporte),
        km_entrada=body.km_entrada,
        taller=body.taller,
        fecha_programada=body.fecha_programada,
        retirar_vehiculo=body.retirar_vehiculo,
        repuestos_estimados=body.repuestos_estimados,
        evidencias=reporte.get("evidencias", []),
    )

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.REPORTE_FALLA_CONVERSION,
        entidad="reportes_falla",
        entidad_id=reporte_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "PENDIENTE"},
        datos_posteriores={"estado": "CONVERTIDO_A_ORDEN", "orden_id": orden["_id"]},
    )
    await db.reportes_falla.update_one(
        {"_id": reporte_id}, {"$set": {"estado": "CONVERTIDO_A_ORDEN", "orden_id": orden["_id"]}}
    )
    reporte["estado"] = "CONVERTIDO_A_ORDEN"
    reporte["orden_id"] = orden["_id"]
    return reporte


async def corregir_reporte(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    reporte_id: str,
    tipo_falla: str | None,
    descripcion: str | None,
    motivo: str,
) -> dict:
    """Corrección acotada: `tipo_falla`/`descripcion` mal tecleados por el
    conductor (o por el Jefe de Mantenimiento, en el reporte creado desde
    `web-interno`) -- solo mientras `PENDIENTE`. Reusa `_reporte_pendiente`,
    el MISMO guard que ya bloquean `convertir_reporte_en_orden`/
    `descartar_reporte` -- una vez CONVERTIDO_A_ORDEN o DESCARTADO, el 409
    ya sale de ahí, sin duplicar la validación.

    `vehiculo_id`/`impide_continuar` quedan deliberadamente fuera: el
    primero ya alimentó la notificación de alerta y (si aplica) la
    cancelación real de un viaje EN_CURSO al crear el reporte -- cambiar de
    vehículo después desalinearía esa consecuencia ya ocurrida del vehículo
    real; el segundo, si es `True`, YA disparó esa cancelación + una nueva
    solicitud para el pasajero, una consecuencia irreversible en otra
    entidad transaccional (`viajes`) que ningún valor de corrección puede
    deshacer."""
    reporte = await _reporte_pendiente(db, reporte_id=reporte_id)

    cambios: dict = {}
    if tipo_falla is not None:
        await _validar_tipo_falla(db, tipo_falla)
        cambios["tipo_falla"] = tipo_falla
    if descripcion is not None:
        cambios["descripcion"] = descripcion

    if not cambios:
        return reporte

    datos_previos = {k: reporte.get(k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.REPORTE_FALLA_CORRECCION,
        entidad="reportes_falla",
        entidad_id=reporte_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=datos_previos,
        datos_posteriores={**cambios, "motivo": motivo},
    )
    await db.reportes_falla.update_one({"_id": reporte_id}, {"$set": cambios})
    reporte.update(cambios)
    return reporte


async def descartar_reporte(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, reporte_id: str, motivo: str
) -> dict:
    reporte = await _reporte_pendiente(db, reporte_id=reporte_id)

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.REPORTE_FALLA_DESCARTE,
        entidad="reportes_falla",
        entidad_id=reporte_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "PENDIENTE"},
        datos_posteriores={"estado": "DESCARTADO", "motivo": motivo},
    )
    await db.reportes_falla.update_one(
        {"_id": reporte_id}, {"$set": {"estado": "DESCARTADO", "motivo_descarte": motivo}}
    )
    reporte["estado"] = "DESCARTADO"
    reporte["motivo_descarte"] = motivo
    return reporte
