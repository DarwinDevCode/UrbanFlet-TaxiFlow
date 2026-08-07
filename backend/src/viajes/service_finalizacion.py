"""CU-O08 — Finalizar el viaje: EN_CURSO -> FINALIZADO con tarifa final,
más CU-O08 paso 5 (calificaciones, opcionales, hasta 24h después).

Cortes de alcance explícitos en este slice:
- Paso 4 ("el sistema dispara el registro del pago, CU-O09"): CU-O09 es
  Control Financiero — Fase 4, bloqueada explícitamente por esta fase según
  el plan (Fase 4 depende de un viaje FINALIZADO con tarifa_final, no al
  revés). No se registra ningún pago aquí.
- A2 (traza GPS incompleta -> estimar el tramo faltante con la ruta óptima):
  requiere un motor de ruteo que no existe en el stack (mismo corte que
  CU-O04/O05). Si la traza está incompleta, la tarifa se calcula igual sobre
  los km ya acumulados — sin el campo `tarifa_parcial=true` que exigiría
  poder distinguir "incompleta por desconexión" de "viaje corto real".
- A4 (destino real lejos del declarado, > 500 m): el modelo físico
  (diseno_base_datos.md §1.4) reserva un único par de campos
  destino_lat/destino_lon, no uno "declarado" y otro "real" — se prioriza el
  modelo físico ya definido. Se conserva el destino declarado (útil para el
  historial/comprobante, CU-O14) y la tarifa se calcula igual sobre la traza
  GPS real, no sobre el destino declarado. No se agrega una validación que
  bloquee la finalización por esta distancia (la spec dice "se permite").
"""

import uuid
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_mongo import get_mongo_client
from src.core.db_redis import get_redis
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.core.tiempo import como_utc
from src.parametros import service as parametros_service
from src.parametros.service import ParametroNoVigenteError
from src.viajes.service import resolver_franja
from src.viajes.service_ejecucion import TransicionInvalidaError

DISCREPANCIA_REVISION_UMBRAL = 0.30
VENTANA_CALIFICACION_HORAS = 24


class YaCalificadoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="YA_CALIFICADO", message="Ya calificaste este viaje", status_code=409)


class VentanaCalificacionVencidaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VENTANA_CALIFICACION_VENCIDA",
            message=f"Solo se puede calificar hasta {VENTANA_CALIFICACION_HORAS}h después de finalizado el viaje",
            status_code=409,
        )


class ViajeNoCalificableError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VIAJE_NO_CALIFICABLE", message="El viaje no está en un estado que permita calificar", status_code=409
        )


async def finalizar_viaje(db: AsyncIOMotorDatabase, *, conductor_id: str) -> dict:
    viaje = await db.viajes.find_one({"conductor_id": conductor_id, "estado": "EN_CURSO"})
    if viaje is None:
        raise TransicionInvalidaError("EN_CURSO")

    # A3: sin destino declarado -> se registra como destino la posición
    # actual del conductor al pulsar "Finalizar viaje".
    destino_lat = viaje.get("destino_lat")
    destino_lon = viaje.get("destino_lon")
    if destino_lat is None:
        redis = get_redis()
        cache = await redis.hgetall(f"pos:{viaje['vehiculo_id']}")
        if cache.get("lat"):
            destino_lat = float(cache["lat"])
            destino_lon = float(cache["lon"])

    # CU-O08 paso 2: "la franja aplicable es la de la hora de INICIO del
    # viaje" — no la franja resuelta en CU-O04 al momento de la solicitud,
    # que puede quedar obsoleta si el despacho tardó y cruzó el corte
    # diurno/nocturno mientras el viaje esperaba conductor.
    ts_inicio = como_utc(viaje["ts_inicio"])
    franja_final = resolver_franja(ts_inicio)
    try:
        tarifa = await parametros_service.obtener_vigente(db, tipo="tarifa", fecha=ts_inicio, franja=franja_final)
    except ParametroNoVigenteError:
        tarifa = None

    km_recorridos = viaje.get("km_recorridos") or 0.0
    min_espera = viaje.get("min_espera") or 0.0

    if tarifa is not None:
        valores = tarifa["valores"]
        bruto = valores["arrancada"] + valores["costo_km"] * km_recorridos + valores["costo_min_espera"] * min_espera
        tarifa_final = round(max(bruto, valores["carrera_minima"]), 2)
        tarifa_version_id_final = tarifa["_id"]
    else:
        # Degenerado: no hay parámetro de tarifa vigente para esta franja en
        # esta fecha — no debería ocurrir en operación real (parametros/
        # siempre debería tener una serie vigente), pero no se bloquea la
        # finalización del viaje por un problema de configuración ajeno al
        # pasajero/conductor.
        tarifa_final = 0.0
        tarifa_version_id_final = None

    tarifa_estimada = viaje.get("tarifa_estimada")
    revision_tarifa = False
    if tarifa_estimada:
        discrepancia = abs(tarifa_final - tarifa_estimada) / tarifa_estimada
        revision_tarifa = discrepancia > DISCREPANCIA_REVISION_UMBRAL

    ahora = datetime.now(UTC)
    updates = {
        "estado": "FINALIZADO",
        "ts_fin": ahora,
        "destino_lat": destino_lat,
        "destino_lon": destino_lon,
        "tarifa_final": tarifa_final,
        "tarifa_version_id_final": tarifa_version_id_final,
        "franja": franja_final,
        "revision_tarifa": revision_tarifa,
    }

    async def _en_transaccion(session):
        await write_audit_event(
            db,
            actor_id=conductor_id,
            rol="conductor",
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=viaje["_id"],
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": "EN_CURSO"},
            datos_posteriores={"estado": "FINALIZADO", "tarifa_final": tarifa_final},
            session=session,
        )
        # Sección 1.2 de ux_complementaria.md: un viaje FINALIZADO ya no debe
        # ser consultable vía un enlace compartido -- el filtro de estado en
        # `service_compartir.py` ya lo bloquearía, pero se limpia el token
        # explícitamente como defensa en profundidad (higiene de datos, no
        # dejar un token vivo indefinidamente en un documento cerrado).
        await db.viajes.update_one(
            {"_id": viaje["_id"]},
            {"$set": updates, "$unset": {"token_compartir": "", "token_compartir_expira_en": ""}},
            session=session,
        )
        await db.usuarios.update_one(
            {"_id": conductor_id}, {"$set": {"conductor.estado_servicio": "DISPONIBLE"}}, session=session
        )
        return session

    await with_transaction(get_mongo_client(), _en_transaccion)

    viaje.update(updates)
    return viaje


async def _recalcular_calificacion_promedio(db: AsyncIOMotorDatabase, *, usuario_id: str, campo_viaje: str) -> None:
    """`calificacion_promedio` es un derivado materializado (diseno_base_datos.md
    §1.4: "decisión declarada, se recalcula desde CALIFICACION") — nunca un
    promedio incremental. `campo_viaje` es el subdocumento embebido del que
    se toma el puntaje: `calificacion_pasajero_a_conductor` cuando se
    recalcula el promedio de un CONDUCTOR, `calificacion_conductor_a_pasajero`
    cuando se recalcula el de un PASAJERO."""
    filtro_id = "conductor_id" if campo_viaje == "calificacion_pasajero_a_conductor" else "pasajero_id"
    cursor = db.viajes.aggregate(
        [
            {"$match": {filtro_id: usuario_id, f"{campo_viaje}.puntaje": {"$exists": True}}},
            {"$group": {"_id": None, "promedio": {"$avg": f"${campo_viaje}.puntaje"}}},
        ]
    )
    resultado = await cursor.to_list(length=1)
    promedio = round(resultado[0]["promedio"], 2) if resultado else None

    sub_campo = "conductor.calificacion_promedio" if filtro_id == "conductor_id" else "pasajero.calificacion_promedio"
    await db.usuarios.update_one({"_id": usuario_id}, {"$set": {sub_campo: promedio}})


async def calificar_viaje(
    db: AsyncIOMotorDatabase, *, viaje_id: str, actor_id: str, rol: str, puntaje: int, comentario: str | None
) -> dict:
    viaje = await db.viajes.find_one({"_id": viaje_id})
    if viaje is None or viaje["estado"] not in ("FINALIZADO", "PAGADO"):
        raise ViajeNoCalificableError()

    if rol == "pasajero":
        if viaje["pasajero_id"] != actor_id:
            raise ViajeNoCalificableError()
        campo = "calificacion_pasajero_a_conductor"
        calificado_id = viaje.get("conductor_id")
        campo_promedio = "calificacion_pasajero_a_conductor"
    else:
        if viaje["conductor_id"] != actor_id:
            raise ViajeNoCalificableError()
        campo = "calificacion_conductor_a_pasajero"
        calificado_id = viaje.get("pasajero_id")
        campo_promedio = "calificacion_conductor_a_pasajero"

    if viaje.get(campo) is not None:
        raise YaCalificadoError()

    ts_fin = como_utc(viaje["ts_fin"])
    if datetime.now(UTC) > ts_fin + timedelta(hours=VENTANA_CALIFICACION_HORAS):
        raise VentanaCalificacionVencidaError()

    ahora = datetime.now(UTC)
    calificacion = {
        "_id": str(uuid.uuid4()),
        "puntaje": puntaje,
        "comentario": comentario,
        "ts": ahora,
    }

    # Es una escritura de una sola entidad (el propio viaje) — no necesita
    # una transacción multi-documento; el recálculo del promedio en
    # `usuarios` es un derivado, no una escritura crítica de negocio (no
    # pierde nada si, en un caso extremo, quedara desactualizado un instante).
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
        entidad="viajes",
        entidad_id=viaje_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"evento": "CALIFICACION", "emisor": rol, "puntaje": puntaje},
    )
    await db.viajes.update_one({"_id": viaje_id}, {"$set": {campo: calificacion}})

    if calificado_id:
        await _recalcular_calificacion_promedio(db, usuario_id=calificado_id, campo_viaje=campo_promedio)

    viaje[campo] = calificacion
    return viaje
