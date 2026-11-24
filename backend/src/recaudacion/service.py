"""CU-O09 (registrar el pago del viaje) y CU-O10 (calcular la comisión de la
cooperativa) — pkg-recaudacion.

Regla inviolable del departamento (operativo_finanzas.md, encabezado):
"ningún pago cuyo monto no sea consistente con la tarifa calculada del viaje
entra al circuito de liquidación. Los registros inconsistentes van a
cuarentena, nunca se corrigen en silencio." Por eso la validación de monto
(paso 2) decide TODO lo que sigue: si coincide, pago + transición a PAGADO +
movimientos de comisión/neto ocurren como una sola unidad atómica
(with_transaction, igual que Fase 3 con la cadena de despacho); si no
coincide, el pago se registra en DISCREPANCIA y ahí se detiene — ni el viaje
pasa a PAGADO ni se calcula comisión (CU-O10 precondición: "existe un
registro de recaudación VALIDADO").

Cortes de alcance explícitos en este slice (decisión ya confirmada con el
cliente, no un hueco de la spec): MVP financiero cubre 100% el camino
EFECTIVO. El campo `metodo` y el estado `PENDIENTE_CONFIRMACION` existen en
el modelo para que ELECTRONICO no esté cerrado, pero no hay integración real
con ninguna pasarela (CU-O09 pasos 3/A2/A3) — no hay proveedor elegido.
"""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.config import get_settings
from src.core.agregacion_estrategica import agrupar, promedio_ponderado, ultimos_periodos, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client
from src.core.db_mongo import get_mongo_client
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.core.tiempo import como_utc
from src.parametros import service as parametros_service


class ViajeNoFinalizadoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VIAJE_NO_FINALIZADO",
            message="No tienes un viaje FINALIZADO pendiente de pago",
            status_code=409,
        )


class PagoYaRegistradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="PAGO_YA_REGISTRADO", message="Este viaje ya tiene un pago registrado", status_code=409)


class DiscrepanciaNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="DISCREPANCIA_NO_ENCONTRADA",
            message="No hay una discrepancia sin resolver con ese id",
            status_code=404,
        )


class LiquidacionNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="LIQUIDACION_NO_ENCONTRADA", message="No existe una liquidación con ese id", status_code=404
        )


class LiquidacionEstadoInvalidoError(DomainError):
    def __init__(self, esperado: str) -> None:
        super().__init__(
            code="LIQUIDACION_ESTADO_INVALIDO",
            message=f"La liquidación debe estar en estado {esperado} para esta acción",
            status_code=409,
        )


class AjusteMontoRequeridoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="AJUSTE_MONTO_REQUERIDO",
            message="Se requiere un monto de ajuste cuando la respuesta no ratifica la liquidación",
            status_code=422,
        )


class ViajeSinRecaudacionValidaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="VIAJE_SIN_RECAUDACION_VALIDA",
            message="El viaje no tiene un pago VALIDADO — no se puede crear un ajuste sobre él",
            status_code=409,
        )


VIAJE_SIN_PAGO_HORAS = 24


async def obtener_nombres_conductores(db: AsyncIOMotorDatabase, conductor_ids: set[str]) -> dict[str, str]:
    """Resuelve `conductor_id` -> `nombre` en un solo `$in`, para que las
    pantallas de Finanzas (discrepancias, pagos sin cobro, alertas de saldo
    negativo, liquidaciones) no muestren el UUID crudo del socio. Mismo
    criterio de batch que `captacion.service.enriquecer_con_usuario_nombre`."""
    conductor_ids = {c for c in conductor_ids if c}
    if not conductor_ids:
        return {}
    usuarios = await db.usuarios.find({"_id": {"$in": list(conductor_ids)}}).to_list(length=len(conductor_ids))
    return {u["_id"]: u["nombre"] for u in usuarios}


async def _crear_movimientos(db: AsyncIOMotorDatabase, *, viaje: dict, pago: dict, session) -> None:
    """CU-O10: comisión y neto del socio, calculados con el porcentaje
    vigente a la fecha del VIAJE (no de hoy — un cambio de porcentaje a
    mitad de periodo no debe alterar viajes ya cerrados, CU-O10 A1)."""
    ts_fin = como_utc(viaje["ts_fin"])
    comision_param = await parametros_service.obtener_vigente(db, tipo="comision", fecha=ts_fin)
    porcentaje = comision_param["valores"]["porcentaje"]

    monto = pago["monto"]
    # round() de Python ya redondea half-to-even (bancario) para el caso
    # típico de 2 decimales que pide la spec.
    comision = round(monto * porcentaje, 2)
    neto_socio = round(monto - comision, 2)

    ahora = datetime.now(UTC)
    mov_comision = {
        "_id": str(uuid.uuid4()),
        "viaje_id": viaje["_id"],
        "tipo": "COMISION",
        "monto_firmado": -comision,
        "comision_version_id": comision_param["_id"],
        "motivo": None,
        "autorizador_id": None,
        "ts": ahora,
        "liquidacion_id": None,
    }
    mov_neto = {
        "_id": str(uuid.uuid4()),
        "viaje_id": viaje["_id"],
        "tipo": "NETO_SOCIO",
        "monto_firmado": neto_socio,
        "comision_version_id": comision_param["_id"],
        "motivo": None,
        "autorizador_id": None,
        "ts": ahora,
        "liquidacion_id": None,
    }

    await write_audit_event(
        db,
        actor_id=None,
        rol=None,
        accion=AccionAuditoria.PAGO_REGISTRO,
        entidad="movimientos",
        entidad_id=viaje["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"comision": comision, "neto_socio": neto_socio, "porcentaje": porcentaje},
        session=session,
    )
    await db.movimientos.insert_many([mov_comision, mov_neto], session=session)


async def crear_ajuste_movimiento(
    db: AsyncIOMotorDatabase, *, viaje_id: str, monto: float, motivo: str, autorizador_id: str
) -> dict:
    """CU-O10 A2: "movimiento de ajuste autorizado" — un caso DISTINTO de la
    observación de un socio sobre su liquidación (CU-O11 A2, resuelta por
    `responder_observacion`, que corrige los agregados `ajustes`/`saldo` de
    UN documento `liquidacion` ya emitido). Aquí el disparador es otro: un
    Administrador Financiero corrige algo del lado de la cooperativa (p. ej.
    un error de sistema en una comisión) ANTES de que necesariamente exista
    siquiera una liquidación para ese periodo — CU-O10 A2 pide un movimiento
    ADICIONAL, trazable por separado (viaje_id, signo, motivo, autorizador),
    nunca una edición del COMISION/NETO_SOCIO original del viaje.

    Precondición explícita (mismo criterio que CU-O10 general: "existe un
    registro de recaudación VALIDADO"): solo se puede ajustar un viaje que
    ya tiene un pago VALIDADO — un viaje sin pago, o con un pago en
    DISCREPANCIA sin resolver, todavía no entró al circuito de liquidación y
    no tiene nada que ajustar.

    Escritura de una sola colección (`movimientos`) — mismo criterio que el
    camino "rechazar" de `resolver_discrepancia`: write-ahead de auditoría
    seguido de un solo insert, sin `with_transaction`, porque no cruza más
    de una colección de negocio."""
    pago = await db.pagos.find_one({"viaje_id": viaje_id, "estado": "VALIDADO"})
    if pago is None:
        raise ViajeSinRecaudacionValidaError()

    ahora = datetime.now(UTC)
    mov_id = str(uuid.uuid4())
    mov_ajuste = {
        "_id": mov_id,
        "viaje_id": viaje_id,
        "tipo": "AJUSTE",
        "monto_firmado": round(monto, 2),
        "comision_version_id": None,
        "motivo": motivo,
        "autorizador_id": autorizador_id,
        "ts": ahora,
        "liquidacion_id": None,
    }

    await write_audit_event(
        db,
        actor_id=autorizador_id,
        rol="admin_financiero",
        accion=AccionAuditoria.PAGO_AJUSTE,
        entidad="movimientos",
        entidad_id=mov_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"viaje_id": viaje_id, "monto_firmado": mov_ajuste["monto_firmado"], "motivo": motivo},
    )
    await db.movimientos.insert_one(mov_ajuste)
    return mov_ajuste


async def registrar_pago_efectivo(
    db: AsyncIOMotorDatabase, *, conductor_id: str, viaje_id: str, monto_cobrado: float
) -> dict:
    # El viaje se identifica por id explícito, no por "el FINALIZADO del
    # conductor" — CU-O09 A4 anticipa que un conductor puede tener MÁS DE UN
    # viaje FINALIZADO sin pagar a la vez (si el pago se demora), así que esa
    # búsqueda implícita sería ambigua. Bug real encontrado verificando este
    # slice en navegador: con dos viajes FINALIZADO del mismo conductor, la
    # versión anterior (sin viaje_id) podía registrar el pago contra el
    # viaje equivocado.
    viaje = await db.viajes.find_one({"_id": viaje_id, "conductor_id": conductor_id, "estado": "FINALIZADO"})
    if viaje is None:
        raise ViajeNoFinalizadoError()

    # Idempotencia estructural: pagos.viaje_id es único (core/db_mongo.py) —
    # un reintento con el mismo viaje nunca duplica el registro. Se comprueba
    # también aquí para devolver un error de negocio claro, no un 500 crudo
    # de índice duplicado.
    if await db.pagos.find_one({"viaje_id": viaje["_id"]}) is not None:
        raise PagoYaRegistradoError()

    tarifa_final = viaje["tarifa_final"]
    # CU-O09 paso 2: "tolerancia $0.00; el redondeo ya está resuelto en la
    # tarifa" — comparación exacta, no una tolerancia inventada.
    coincide = round(monto_cobrado, 2) == round(tarifa_final, 2)
    diferencia = None if coincide else round(monto_cobrado - tarifa_final, 2)

    ahora = datetime.now(UTC)
    pago_id = str(uuid.uuid4())
    pago = {
        "_id": pago_id,
        "viaje_id": viaje["_id"],
        "conductor_id": conductor_id,
        "metodo": "EFECTIVO",
        "monto": monto_cobrado,
        "tarifa_final": tarifa_final,
        "diferencia": diferencia,
        "referencia_externa": None,
        "estado": "VALIDADO" if coincide else "DISCREPANCIA",
        "ts_registro": ahora,
        "ts_confirmacion": ahora if coincide else None,
        "resuelto": False,
        "resolucion_motivo": None,
        "resolucion_aceptado": None,
        "resolucion_autorizador_id": None,
        "resolucion_ts": None,
    }

    if not coincide:
        # A1: "el registro se acepta pero entra en DISCREPANCIA... no pasa a
        # liquidación." Una sola entidad de negocio (el propio pago) — el
        # write-ahead de una escritura ya basta, sin transacción.
        await write_audit_event(
            db,
            actor_id=conductor_id,
            rol="conductor",
            accion=AccionAuditoria.PAGO_REGISTRO,
            entidad="pagos",
            entidad_id=pago_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"estado": "DISCREPANCIA", "diferencia": diferencia},
        )
        await db.pagos.insert_one(pago)
        return pago

    async def _en_transaccion(session):
        await write_audit_event(
            db,
            actor_id=conductor_id,
            rol="conductor",
            accion=AccionAuditoria.PAGO_REGISTRO,
            entidad="pagos",
            entidad_id=pago_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"estado": "VALIDADO", "monto": monto_cobrado},
            session=session,
        )
        await db.pagos.insert_one(pago, session=session)

        await write_audit_event(
            db,
            actor_id=conductor_id,
            rol="conductor",
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=viaje["_id"],
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": "FINALIZADO"},
            datos_posteriores={"estado": "PAGADO"},
            session=session,
        )
        await db.viajes.update_one({"_id": viaje["_id"]}, {"$set": {"estado": "PAGADO"}}, session=session)

        # CU-O10, encadenado en la misma transacción: si no hay un
        # porcentaje de comisión vigente, TODA la cadena se revierte — un
        # pago no puede quedar "validado" sin su contrapartida contable
        # (misma regla inviolable del encabezado del documento).
        await _crear_movimientos(db, viaje=viaje, pago=pago, session=session)
        return session

    await with_transaction(get_mongo_client(), _en_transaccion)
    return pago


async def listar_bandeja_discrepancias(db: AsyncIOMotorDatabase) -> tuple[list[dict], list[dict]]:
    """CU-O09 A1 (pagos en DISCREPANCIA sin resolver) + A4 (viajes FINALIZADO
    hace más de 24h sin ningún pago registrado, VIAJE_SIN_PAGO). Este último
    se calcula bajo demanda al abrir la bandeja — no hay scheduler en el
    stack (mismo corte que "push proactivo SIN_SEÑAL" en flota/service.py),
    así que en vez de un job en segundo plano que marque los viajes, se
    deriva la lista en el momento de la consulta."""
    discrepancias = await db.pagos.find({"estado": "DISCREPANCIA", "resuelto": False}).sort("ts_registro", -1).to_list(
        length=500
    )

    limite = datetime.now(UTC) - timedelta(hours=VIAJE_SIN_PAGO_HORAS)
    # Más reciente primero (ronda de orden por defecto en tablas) -- antes
    # sin `.sort()`, quedaba en el orden natural de Mongo, no confiable.
    candidatos = (
        await db.viajes.find({"estado": "FINALIZADO", "ts_fin": {"$lt": limite}})
        .sort("ts_fin", -1)
        .to_list(length=500)
    )
    viaje_ids = [v["_id"] for v in candidatos]

    ids_con_pago: set[str] = set()
    if viaje_ids:
        async for p in db.pagos.find({"viaje_id": {"$in": viaje_ids}}, {"viaje_id": 1}):
            ids_con_pago.add(p["viaje_id"])

    viajes_sin_pago = [
        {
            "viaje_id": v["_id"],
            "conductor_id": v["conductor_id"],
            "tarifa_final": v["tarifa_final"],
            "ts_fin": como_utc(v["ts_fin"]),
        }
        for v in candidatos
        if v["_id"] not in ids_con_pago
    ]

    return discrepancias, viajes_sin_pago


async def resolver_discrepancia(
    db: AsyncIOMotorDatabase, *, pago_id: str, autorizador_id: str, aceptar: bool, motivo: str
) -> dict:
    """CU-O09 A1: "resuelve con un ajuste justificado". No hay una spec de
    detalle para esta resolución (CU-T09, referenciado como «extend», no
    forma parte de los documentos de specs/ provistos) — se implementa el
    mecanismo más directo y trazable dentro de lo que SÍ está especificado:
    - Aceptar: el monto realmente cobrado (el discrepante) se toma como
      válido — se calculan comisión/neto sobre ESE monto (CU-O10) y el viaje
      pasa a PAGADO. La justificación queda en la bitácora (actor, motivo),
      que es exactamente para esto (CU-O17) — no se inventa un movimiento
      MOVIMIENTO adicional con monto $0 solo para "dejar rastro", ya que la
      bitácora ya cumple ese rol sin inventar semántica de monto.
    - Rechazar: el pago queda marcado como revisado pero nunca pasa a
      liquidación — el viaje se queda sin cobrar (una pérdida operativa que
      el Administrador decidió no perseguir, o que documenta para otra vía).
    """
    pago = await db.pagos.find_one({"_id": pago_id, "estado": "DISCREPANCIA", "resuelto": False})
    if pago is None:
        raise DiscrepanciaNoEncontradaError()

    ahora = datetime.now(UTC)
    resolucion = {
        "resuelto": True,
        "resolucion_motivo": motivo,
        "resolucion_aceptado": aceptar,
        "resolucion_autorizador_id": autorizador_id,
        "resolucion_ts": ahora,
    }

    if not aceptar:
        await write_audit_event(
            db,
            actor_id=autorizador_id,
            rol="admin_financiero",
            accion=AccionAuditoria.PAGO_AJUSTE,
            entidad="pagos",
            entidad_id=pago_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"aceptado": False, "motivo": motivo},
        )
        await db.pagos.update_one({"_id": pago_id}, {"$set": resolucion})
        pago.update(resolucion)
        return pago

    viaje = await db.viajes.find_one({"_id": pago["viaje_id"], "estado": "FINALIZADO"})
    if viaje is None:
        raise ViajeNoFinalizadoError()

    async def _en_transaccion(session):
        await write_audit_event(
            db,
            actor_id=autorizador_id,
            rol="admin_financiero",
            accion=AccionAuditoria.PAGO_AJUSTE,
            entidad="pagos",
            entidad_id=pago_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"aceptado": True, "motivo": motivo},
            session=session,
        )
        await db.pagos.update_one({"_id": pago_id}, {"$set": resolucion}, session=session)

        await write_audit_event(
            db,
            actor_id=autorizador_id,
            rol="admin_financiero",
            accion=AccionAuditoria.VIAJE_TRANSICION_ESTADO,
            entidad="viajes",
            entidad_id=viaje["_id"],
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": "FINALIZADO"},
            datos_posteriores={"estado": "PAGADO"},
            session=session,
        )
        await db.viajes.update_one({"_id": viaje["_id"]}, {"$set": {"estado": "PAGADO"}}, session=session)

        await _crear_movimientos(db, viaje=viaje, pago=pago, session=session)
        return session

    await with_transaction(get_mongo_client(), _en_transaccion)
    pago.update(resolucion)
    return pago


def _periodo_cerrado_mas_reciente(ahora_utc: datetime) -> tuple[datetime, datetime]:
    """CU-O11 precondición: "cierre del periodo de liquidación (semanal,
    parámetro de la junta)". Corte CONFIRMADO con el cliente: semana
    viernes-a-viernes (core/config.py: periodo_liquidacion_inicio_semana=4).
    Se resuelve en hora LOCAL de operación, igual que la franja
    diurna/nocturna (viajes/service.py) — el cierre de una semana de trabajo
    es un concepto de calendario local, no un corte UTC absoluto.

    Devuelve el periodo [inicio, fin) YA CERRADO más reciente respecto a
    `ahora_utc` — nunca un periodo en curso, porque no hay forma de que el
    Administrador Financiero dispare esto antes de que termine (no hay
    scheduler en el stack; esto es un botón, no un cron)."""
    settings = get_settings()
    local = ahora_utc.astimezone(ZoneInfo(settings.zona_horaria_operacion))
    dias = settings.periodo_liquidacion_dias
    dias_desde_corte = (local.weekday() - settings.periodo_liquidacion_inicio_semana) % dias
    fin_local = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias_desde_corte)
    inicio_local = fin_local - timedelta(days=dias)
    return inicio_local.astimezone(UTC), fin_local.astimezone(UTC)


async def generar_liquidaciones(db: AsyncIOMotorDatabase, *, autorizador_id: str) -> dict:
    """CU-O11 pasos 1-2: al cierre del periodo, consolida por socio los
    viajes PAGADOS del periodo y emite la liquidación en EMITIDA. Pasos 3-4
    (aprobar/pagar el lote) y A2/A3 (observar, saldo negativo) quedan para
    los slices siguientes.

    Cómo se agrupan los viajes del periodo por socio, y por qué esto también
    resuelve A1 sin lógica adicional: se parte de los MOVIMIENTOS (no de los
    pagos ni de los viajes) filtrados por `ts` dentro de [inicio, fin) y
    `liquidacion_id: None` (para no re-liquidar algo ya liquidado). Un viaje
    con una discrepancia abierta al cierre nunca tiene movimientos (estos
    solo se crean cuando el pago se VALIDA o la discrepancia se ACEPTA — ver
    `_crear_movimientos`), así que automáticamente queda excluido del
    periodo. Si esa discrepancia se resuelve después, sus movimientos nacen
    con un `ts` posterior, y por construcción caen en el periodo que
    corresponda a ESE momento — exactamente "se arrastran al siguiente una
    vez resueltos" (CU-O11 A1), sin necesitar una cola de reintentos.

    Cómo se calcula el saldo (MVP 100% efectivo — ver encabezado del
    módulo): el socio ya tiene en mano el efectivo cobrado, así que la
    cooperativa no le transfiere nada por esos viajes; al contrario, el
    socio le DEBE a la cooperativa la comisión retenida sobre ese efectivo.
    Con `neto_electronico = 0` (no hay camino electrónico construido
    todavía), la fórmula del paso 1 (`saldo = neto_electronico -
    comision_sobre_efectivo`) se reduce siempre a `-comisiones`: el saldo
    será negativo en el 100% de los casos de este MVP — es el
    comportamiento ESPERADO (CU-O11 A3 lo anticipa explícitamente), no un
    error de signo.

    `ajustes`: suma de los `monto_firmado` de movimientos `tipo=AJUSTE`
    (CU-O10 A2, `crear_ajuste_movimiento`) todavía sin `liquidacion_id`
    (nunca liquidados). A diferencia de COMISION/NETO_SOCIO, un AJUSTE se
    autoriza a mano en cualquier momento — su `ts` de creación normalmente
    cae DESPUÉS de que el periodo del viaje ya cerró (y a menudo después de
    que `ahora` mismo ya dejó atrás ese periodo cerrado), así que filtrarlo
    por `ts` dentro de [inicio, fin) lo excluiría casi siempre. En su lugar
    se recoge TODO ajuste pendiente (`liquidacion_id: None`) sin importar su
    `ts`, y se arrastra al primer `generar_liquidaciones` que corra después
    de creado — exactamente "se arrastran al siguiente una vez resueltos"
    (CU-O11 A1), sin necesitar una cola de reintentos. Por eso el viaje
    asociado a un AJUSTE no entra al recálculo de `bruto`/`detalle` por
    viaje de abajo (ese recálculo solo recorre viajes con movimientos
    COMISION/NETO_SOCIO propios de ESTE periodo) — solo aporta su monto al
    agregado `ajustes` de la liquidación del socio, y
    `saldo = ajustes - comisiones`."""
    ahora = datetime.now(UTC)
    periodo_inicio, periodo_fin = _periodo_cerrado_mas_reciente(ahora)

    # Sin filtrar por `liquidacion_id` aquí a propósito para COMISION/NETO_SOCIO:
    # si se filtrara, reintentar generar() para un periodo ya procesado no
    # encontraría NADA (todos sus movimientos ya están enlazados) y el reporte
    # `ya_existian` quedaría siempre vacío en un reintento — el chequeo de
    # "¿ya existe?" de abajo, por conductor, es el que de verdad decide si se
    # salta. Los AJUSTE pendientes se agregan aparte (ver docstring): no se
    # filtran por `ts`, solo por no estar ya enlazados a una liquidación.
    movimientos = await db.movimientos.find({"ts": {"$gte": periodo_inicio, "$lt": periodo_fin}}).to_list(
        length=10000
    )
    ajustes_pendientes = await db.movimientos.find({"tipo": "AJUSTE", "liquidacion_id": None}).to_list(
        length=10000
    )
    ids_ya_incluidos = {m["_id"] for m in movimientos}
    movimientos += [m for m in ajustes_pendientes if m["_id"] not in ids_ya_incluidos]

    if not movimientos:
        return {"periodo_inicio": periodo_inicio, "periodo_fin": periodo_fin, "generadas": [], "ya_existian": []}

    viaje_ids = list({m["viaje_id"] for m in movimientos})
    viajes = await db.viajes.find({"_id": {"$in": viaje_ids}}).to_list(length=len(viaje_ids))
    viaje_por_id = {v["_id"]: v for v in viajes}
    pagos = await db.pagos.find({"viaje_id": {"$in": viaje_ids}}).to_list(length=len(viaje_ids))
    pago_por_viaje = {p["viaje_id"]: p for p in pagos}

    movs_por_conductor: dict[str, list[dict]] = {}
    for m in movimientos:
        viaje = viaje_por_id.get(m["viaje_id"])
        if viaje is None or m["viaje_id"] not in pago_por_viaje:
            continue
        movs_por_conductor.setdefault(viaje["conductor_id"], []).append(m)

    ya_existian: list[str] = []
    generadas: list[dict] = []

    for conductor_id, movs in movs_por_conductor.items():
        existente = await db.liquidaciones.find_one(
            {"conductor_id": conductor_id, "periodo_inicio": periodo_inicio}
        )
        if existente is not None:
            ya_existian.append(conductor_id)
            continue

        bruto = 0.0
        comisiones = 0.0
        neto = 0.0
        detalle = []
        # Solo los viajes con su propio COMISION/NETO_SOCIO en ESTE periodo
        # entran al detalle por viaje / bruto — un AJUSTE puede apuntar a un
        # viaje cuyo COMISION/NETO_SOCIO ya se liquidó en un periodo anterior
        # (ver docstring), y ese viaje no debe re-sumar su `pago["monto"]`
        # aquí de nuevo.
        viajes_con_movimiento_principal = {
            m["viaje_id"] for m in movs if m["tipo"] in ("COMISION", "NETO_SOCIO")
        }
        for viaje_id in viajes_con_movimiento_principal:
            pago = pago_por_viaje[viaje_id]
            movs_viaje = [m for m in movs if m["viaje_id"] == viaje_id]
            comision_viaje = round(-sum(m["monto_firmado"] for m in movs_viaje if m["tipo"] == "COMISION"), 2)
            neto_viaje = round(sum(m["monto_firmado"] for m in movs_viaje if m["tipo"] == "NETO_SOCIO"), 2)
            bruto += pago["monto"]
            comisiones += comision_viaje
            neto += neto_viaje
            detalle.append(
                {
                    "viaje_id": viaje_id,
                    "metodo": pago["metodo"],
                    "monto": pago["monto"],
                    "comision": comision_viaje,
                    "neto_socio": neto_viaje,
                    "ts": max(m["ts"] for m in movs_viaje),
                }
            )

        # Más reciente primero (auditoría exhaustiva de orden de tablas). Se
        # arma iterando un `set` de viaje_id, así que sin este sort el orden
        # de la tabla "Viajes de la liquidación" es el de iteración del set:
        # no determinista entre corridas. Cada fila ya trae su `ts`.
        detalle.sort(key=lambda d: d["ts"], reverse=True)

        bruto = round(bruto, 2)
        comisiones = round(comisiones, 2)
        neto = round(neto, 2)
        ajustes = round(sum(m["monto_firmado"] for m in movs if m["tipo"] == "AJUSTE"), 2)
        saldo = round(ajustes - comisiones, 2)

        liquidacion_id = str(uuid.uuid4())
        liquidacion = {
            "_id": liquidacion_id,
            "conductor_id": conductor_id,
            "periodo_inicio": periodo_inicio,
            "periodo_fin": periodo_fin,
            "estado": "EMITIDA",
            "bruto": bruto,
            "comisiones": comisiones,
            "ajustes": ajustes,
            "neto": neto,
            "saldo": saldo,
            "detalle": detalle,
            "ts_emision": ahora,
            "ts_aprobacion": None,
            "ts_pago": None,
            "aprobador_id": None,
            "liquidacion_ref_id": None,
            "observacion_motivo": None,
            "observacion_ts": None,
        }

        async def _en_transaccion(session, liquidacion=liquidacion, movs=movs):
            await write_audit_event(
                db,
                actor_id=autorizador_id,
                rol="admin_financiero",
                accion=AccionAuditoria.LIQUIDACION_EMISION,
                entidad="liquidaciones",
                entidad_id=liquidacion["_id"],
                resultado=ResultadoAuditoria.OK,
                datos_posteriores={
                    "conductor_id": liquidacion["conductor_id"],
                    "saldo": liquidacion["saldo"],
                    "periodo_fin": liquidacion["periodo_fin"],
                },
                session=session,
            )
            await db.liquidaciones.insert_one(liquidacion, session=session)
            await db.movimientos.update_many(
                {"_id": {"$in": [m["_id"] for m in movs]}},
                {"$set": {"liquidacion_id": liquidacion["_id"]}},
                session=session,
            )
            return session

        await with_transaction(get_mongo_client(), _en_transaccion)
        generadas.append(liquidacion)

    return {
        "periodo_inicio": periodo_inicio,
        "periodo_fin": periodo_fin,
        "generadas": generadas,
        "ya_existian": ya_existian,
    }


async def contar_viajes_en_revision(
    db: AsyncIOMotorDatabase, *, liquidaciones: list[dict]
) -> dict[str, int]:
    """CU-O11 A1: cuántos pagos en DISCREPANCIA sin resolver del socio caen
    dentro del periodo de CADA liquidación. `generar_liquidaciones` ya deja
    a estos viajes fuera del lote sin ningún código extra (ver su docstring:
    un pago DISCREPANCIA nunca genera movimientos, así que nunca entra a la
    consolidación) — lo único que faltaba era CONTARLOS para que la UI
    explique el porqué. Se usa `ts_registro` del pago (no `ts_fin` del
    viaje) porque es el mismo campo que ya filtra la bandeja de
    discrepancias, y en la práctica el pago se registra a los pocos minutos
    de terminado el viaje."""
    resultado: dict[str, int] = {}
    for liq in liquidaciones:
        resultado[liq["_id"]] = await db.pagos.count_documents(
            {
                "conductor_id": liq["conductor_id"],
                "estado": "DISCREPANCIA",
                "resuelto": False,
                "ts_registro": {"$gte": liq["periodo_inicio"], "$lt": liq["periodo_fin"]},
            }
        )
    return resultado


async def listar_liquidaciones(
    db: AsyncIOMotorDatabase,
    *,
    conductor_id: str | None = None,
    estado: str | None = None,
    periodo_inicio: datetime | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    filtro: dict = {}
    if conductor_id:
        filtro["conductor_id"] = conductor_id
    if estado:
        filtro["estado"] = estado
    # Punto 5 de la ronda de correcciones (agosto 2026): permite enlazar
    # directo desde "Generar liquidaciones del periodo cerrado" a la MISMA
    # tabla de abajo, ya filtrada -- comparación exacta contra el
    # `periodo_inicio` real (el mismo valor que el propio endpoint de
    # generación ya devuelve), no un rango aproximado.
    if periodo_inicio is not None:
        filtro["periodo_inicio"] = periodo_inicio
    cursor = db.liquidaciones.find(filtro).sort("periodo_fin", -1)
    if limit is not None:
        cursor = cursor.skip(offset).limit(limit)
        return await cursor.to_list(length=limit)
    return await cursor.to_list(length=500)


async def contar_liquidaciones(
    db: AsyncIOMotorDatabase,
    *,
    conductor_id: str | None = None,
    estado: str | None = None,
    periodo_inicio: datetime | None = None,
) -> int:
    filtro: dict = {}
    if conductor_id:
        filtro["conductor_id"] = conductor_id
    if estado:
        filtro["estado"] = estado
    if periodo_inicio is not None:
        filtro["periodo_inicio"] = periodo_inicio
    return await db.liquidaciones.count_documents(filtro)


async def aprobar_liquidacion(db: AsyncIOMotorDatabase, *, liquidacion_id: str, aprobador_id: str) -> dict:
    """CU-O11 paso 3, primera mitad: "el Administrador Financiero revisa el
    lote del periodo y lo aprueba; las liquidaciones pasan a APROBADA".

    Se aprueba una liquidación a la vez (no el lote completo de un golpe):
    el "lote" en la UI es la tabla completa de liquidaciones EMITIDA del
    periodo, y "revisar" cada una antes de aprobarla es justamente lo que
    ese flujo permite — igual que el patrón ya usado en Cumplimiento para
    aprobar/observar renovaciones una por una.

    No toca `movimientos` ni ninguna otra colección — solo cambia el estado
    de este documento — por eso no usa `with_transaction` (mismo criterio
    que el camino "rechazar" de `resolver_discrepancia`: transacción solo
    cuando la cadena de escrituras cruza más de una colección de negocio)."""
    liquidacion = await db.liquidaciones.find_one({"_id": liquidacion_id})
    if liquidacion is None:
        raise LiquidacionNoEncontradaError()
    if liquidacion["estado"] != "EMITIDA":
        raise LiquidacionEstadoInvalidoError("EMITIDA")

    ahora = datetime.now(UTC)
    await write_audit_event(
        db,
        actor_id=aprobador_id,
        rol="admin_financiero",
        accion=AccionAuditoria.LIQUIDACION_APROBACION,
        entidad="liquidaciones",
        entidad_id=liquidacion_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "EMITIDA"},
        datos_posteriores={"estado": "APROBADA"},
    )
    await db.liquidaciones.update_one(
        {"_id": liquidacion_id},
        {"$set": {"estado": "APROBADA", "ts_aprobacion": ahora, "aprobador_id": aprobador_id}},
    )
    liquidacion.update({"estado": "APROBADA", "ts_aprobacion": ahora, "aprobador_id": aprobador_id})
    return liquidacion


async def pagar_liquidacion(db: AsyncIOMotorDatabase, *, liquidacion_id: str, autorizador_id: str) -> dict:
    """CU-O11 paso 3 (segunda mitad) y 4: "se ejecuta el movimiento
    (transferencia al socio o cobro al socio, según el signo del saldo)...
    confirmado el movimiento, la liquidación pasa a PAGADA".

    No hay pasarela bancaria ni proveedor de transferencias integrado en
    este MVP (mismo corte de alcance que el resto del módulo: 100% efectivo,
    sin proveedor elegido) — "ejecutar el movimiento" es, en este sistema,
    una acción que el Administrador Financiero hace por fuera (transferencia
    manual o cobro en persona) y luego CONFIRMA aquí. Este endpoint registra
    esa confirmación, no dispara ninguna transferencia real.

    El comprobante descargable del paso 4 queda fuera de alcance de este
    slice (mismo corte ya aplicado a CU-O09: generación de PDF diferida por
    falta de datos fiscales de la cooperativa)."""
    liquidacion = await db.liquidaciones.find_one({"_id": liquidacion_id})
    if liquidacion is None:
        raise LiquidacionNoEncontradaError()
    if liquidacion["estado"] != "APROBADA":
        raise LiquidacionEstadoInvalidoError("APROBADA")

    ahora = datetime.now(UTC)
    await write_audit_event(
        db,
        actor_id=autorizador_id,
        rol="admin_financiero",
        accion=AccionAuditoria.LIQUIDACION_PAGO,
        entidad="liquidaciones",
        entidad_id=liquidacion_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "APROBADA"},
        datos_posteriores={"estado": "PAGADA"},
    )
    await db.liquidaciones.update_one({"_id": liquidacion_id}, {"$set": {"estado": "PAGADA", "ts_pago": ahora}})
    liquidacion.update({"estado": "PAGADA", "ts_pago": ahora})
    return liquidacion


async def observar_liquidacion(
    db: AsyncIOMotorDatabase, *, liquidacion_id: str, conductor_id: str, motivo: str
) -> dict:
    """CU-O11 A2: "desde el portal [el socio] marca 'Observar' con motivo;
    la liquidación pasa a OBSERVADA y bloquea su pago individual (no el del
    lote)". El bloqueo no necesita código propio: `aprobar_liquidacion`
    exige estado EMITIDA, así que una vez OBSERVADA queda automáticamente
    fuera de ese camino hasta que el Administrador responda — el resto del
    lote (otros conductores) sigue su curso normal sin verse afectado.

    Ownership explícito por el mismo motivo que en `registrar_pago_efectivo`
    (Slice 1, hueco señalado por el cliente): el conductor solo puede
    observar SU PROPIA liquidación, nunca una ajena por id — de ahí que el
    filtro incluya `conductor_id`, no solo `_id`."""
    liquidacion = await db.liquidaciones.find_one({"_id": liquidacion_id, "conductor_id": conductor_id})
    if liquidacion is None:
        raise LiquidacionNoEncontradaError()
    if liquidacion["estado"] != "EMITIDA":
        raise LiquidacionEstadoInvalidoError("EMITIDA")

    ahora = datetime.now(UTC)
    await write_audit_event(
        db,
        actor_id=conductor_id,
        rol="conductor",
        accion=AccionAuditoria.LIQUIDACION_OBSERVACION,
        entidad="liquidaciones",
        entidad_id=liquidacion_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "EMITIDA"},
        datos_posteriores={"estado": "OBSERVADA", "motivo": motivo},
    )
    await db.liquidaciones.update_one(
        {"_id": liquidacion_id},
        {"$set": {"estado": "OBSERVADA", "observacion_motivo": motivo, "observacion_ts": ahora}},
    )
    liquidacion.update({"estado": "OBSERVADA", "observacion_motivo": motivo, "observacion_ts": ahora})
    return liquidacion


async def responder_observacion(
    db: AsyncIOMotorDatabase,
    *,
    liquidacion_id: str,
    autorizador_id: str,
    ratificar: bool,
    motivo: str,
    ajuste_monto: float | None,
) -> dict:
    """CU-O11 A2: "El Administrador la revisa y responde con ajuste o
    ratificación (CU-T12 «extend»)". CU-T12 no forma parte de los
    documentos de specs/ provistos (mismo hueco de spec que CU-T09 en
    Slice 2) — se implementa el mecanismo más directo dentro de lo que SÍ
    está especificado:
    - Ratificar: el Administrador confirma que la liquidación emitida es
      correcta tal cual — vuelve a EMITIDA sin cambios numéricos, lista para
      seguir el camino normal (aprobar → pagar).
    - Ajustar: el Administrador reconoce la observación del socio y corrige
      neto/saldo con un monto de ajuste con signo (mismo espíritu que CU-O10
      A2, "movimiento de ajuste... con signo, motivo y autorizador") — se
      suma a `ajustes` y a `saldo`, y la liquidación vuelve a EMITIDA con
      los montos ya corregidos. Tocar `ajustes`/`saldo` aquí es seguro
      porque la liquidación TODAVÍA no llegó a PAGADA — CU-O11 A4 prohíbe
      editar liquidaciones ya pagadas, no las que siguen en flujo previo."""
    liquidacion = await db.liquidaciones.find_one({"_id": liquidacion_id})
    if liquidacion is None:
        raise LiquidacionNoEncontradaError()
    if liquidacion["estado"] != "OBSERVADA":
        raise LiquidacionEstadoInvalidoError("OBSERVADA")
    if not ratificar and ajuste_monto is None:
        raise AjusteMontoRequeridoError()

    cambios: dict = {"estado": "EMITIDA"}
    if not ratificar:
        cambios["ajustes"] = round(liquidacion["ajustes"] + ajuste_monto, 2)
        cambios["saldo"] = round(liquidacion["saldo"] + ajuste_monto, 2)

    await write_audit_event(
        db,
        actor_id=autorizador_id,
        rol="admin_financiero",
        accion=AccionAuditoria.LIQUIDACION_OBSERVACION,
        entidad="liquidaciones",
        entidad_id=liquidacion_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "OBSERVADA"},
        datos_posteriores={"ratificar": ratificar, "motivo": motivo, "ajuste_monto": ajuste_monto, **cambios},
    )
    await db.liquidaciones.update_one({"_id": liquidacion_id}, {"$set": cambios})
    liquidacion.update(cambios)
    return liquidacion


async def listar_alertas_saldo_negativo(db: AsyncIOMotorDatabase) -> list[dict]:
    """CU-O11 A3: "a los 2 periodos con saldo negativo impago... el sistema
    alerta al Administrador". El umbral de periodos consecutivos es
    `liquidacion_periodos_saldo_negativo_alerta` (core/config.py, default 2,
    confirmado en la planificación de Fase 4).

    "Impago" se interpreta como: la liquidación todavía no llegó a PAGADA
    (que es, en este sistema, el momento en que el Administrador confirma
    que el cobro de esa comisión de efectivo ya se ejecutó — ver
    `pagar_liquidacion`). Se miran las `umbral` liquidaciones MÁS RECIENTES
    del socio (por `periodo_fin`); si todas tienen saldo negativo y ninguna
    está PAGADA, se alerta.

    La suspensión real del inicio de turno (resto de A3) queda en backlog —
    decisión ya confirmada en la planificación de Fase 4: a diferencia de
    `cumplimiento_ok`/`mantenimiento_ok` (Fase 2), no existe todavía una
    bandera financiera en el conductor para bloquearlo. Este slice cubre
    solo la alerta al Administrador, no la suspensión."""
    umbral = get_settings().liquidacion_periodos_saldo_negativo_alerta
    conductores = await db.liquidaciones.distinct("conductor_id")
    alertas: list[dict] = []
    for conductor_id in conductores:
        recientes = await db.liquidaciones.find({"conductor_id": conductor_id}).sort("periodo_fin", -1).to_list(
            length=umbral
        )
        if len(recientes) < umbral:
            continue
        if all(liq["saldo"] < 0 and liq["estado"] != "PAGADA" for liq in recientes):
            alertas.append(
                {"conductor_id": conductor_id, "periodos_consecutivos": len(recientes), "liquidaciones": recientes}
            )
    # Más reciente primero (ronda de orden por defecto en tablas): por el
    # periodo_fin de la liquidación más reciente de cada socio -- `recientes`
    # ya viene ordenada desc, así que `recientes[0]` es esa liquidación.
    alertas.sort(key=lambda a: a["liquidaciones"][0]["periodo_fin"], reverse=True)
    return alertas


def obtener_tasa_discrepancias() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico de Conciliación -- CU-T09/OT5.1."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_tasa_discrepancias")
    finally:
        client.close()
    return sorted(filas, key=lambda f: (f["fecha_periodo"], f["metodo"]))


def obtener_margen_comision() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico de Liquidación -- CU-T12/OT5.2."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_margen_comision")
    finally:
        client.close()
    return sorted(filas, key=lambda f: f["periodo"])


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Integridad Financiera
# (OE5 / CU-E04, nivel_estrategico.md §3.5, patrón Z)
# ---------------------------------------------------------------------------


def obtener_panel_integridad_financiera(*, meses: int = 12) -> dict:
    """Segunda capa de agregación sobre `rpt_tasa_discrepancias` +
    `rpt_margen_comision`, sin tabla nueva.

    Las 2 fuentes ya traen su propia dimensión de periodo mensual dentro del
    último snapshot (`fecha_periodo` y `periodo` respectivamente), así que la
    tendencia extendida sale de `fetch_latest_snapshot` -- caso 1 de
    `core/agregacion_estrategica`, sin historial de cortes.

    **Comparación interanual**: se agrupa por año y solo se devuelve si hay
    2 o más años con datos. Advertencia real que este endpoint declara en
    metadata (`dataset_mixto`) cuando detecta más de un año: el histórico de
    este entorno mezcla el dataset NYC de calibración (2021, sembrado) con la
    operación de demo de la cooperativa (2026) -- son dos naturalezas de dato
    distintas y compararlas como "interanual" induce a error si no se marca.
    """
    client = get_clickhouse_client()
    try:
        discrepancias = fetch_latest_snapshot(client, "rpt_tasa_discrepancias")
        margen = fetch_latest_snapshot(client, "rpt_margen_comision")
    finally:
        client.close()

    # `fecha_periodo` es un Date de ClickHouse: se normaliza a mes YYYY-MM.
    for fila in discrepancias:
        fila["periodo"] = str(fila["fecha_periodo"])[:7]

    periodos = ultimos_periodos(
        [f["periodo"] for f in discrepancias] + [f["periodo"] for f in margen], meses
    )
    periodos_set = set(periodos)

    por_periodo_disc = agrupar([f for f in discrepancias if f["periodo"] in periodos_set], "periodo")
    tendencia_conciliacion = [
        {
            "periodo": periodo,
            "pct_conciliado": promedio_ponderado(por_periodo_disc[periodo], "pct_conciliado", "total_registros")
            or 0.0,
            "pct_discrepancia": promedio_ponderado(
                por_periodo_disc[periodo], "pct_discrepancia", "total_registros"
            )
            or 0.0,
            "total_registros": sum(f["total_registros"] for f in por_periodo_disc[periodo]),
        }
        for periodo in periodos
        if periodo in por_periodo_disc
    ]

    por_periodo_margen = agrupar([f for f in margen if f["periodo"] in periodos_set], "periodo")
    tendencia_margen = [
        {
            "periodo": periodo,
            "margen": round(
                promedio_ponderado(por_periodo_margen[periodo], "margen", "bruto_total")
                or (sum(f["margen"] for f in por_periodo_margen[periodo]) / len(por_periodo_margen[periodo])),
                4,
            ),
            "bruto_total": round(sum(f["bruto_total"] for f in por_periodo_margen[periodo]), 2),
            "comisiones_total": round(sum(f["comisiones_total"] for f in por_periodo_margen[periodo]), 2),
        }
        for periodo in periodos
        if periodo in por_periodo_margen
    ]

    conc_actual = tendencia_conciliacion[-1]["pct_conciliado"] if tendencia_conciliacion else None
    conc_previo = tendencia_conciliacion[-2]["pct_conciliado"] if len(tendencia_conciliacion) > 1 else None
    disc_actual = tendencia_conciliacion[-1]["pct_discrepancia"] if tendencia_conciliacion else None
    disc_previo = tendencia_conciliacion[-2]["pct_discrepancia"] if len(tendencia_conciliacion) > 1 else None
    # Tier 1, punto 6 (H-T5): `pct_conciliado`/`pct_discrepancia` son promedios
    # ponderados por `total_registros` -- ambos salen de la MISMA fila
    # (`tendencia_conciliacion[-2]`), así que comparten el mismo n real.
    registros_previos_conciliacion = (
        tendencia_conciliacion[-2]["total_registros"] if len(tendencia_conciliacion) > 1 else None
    )

    # Tabla: periodos con discrepancia relevante (> 0), del más alto al más bajo.
    periodos_con_discrepancia = sorted(
        (p for p in tendencia_conciliacion if p["pct_discrepancia"] > 0),
        key=lambda p: p["pct_discrepancia"],
        reverse=True,
    )

    # Comparación interanual (solo si hay 2+ años reales).
    por_anio = agrupar(
        [f for f in discrepancias if f["periodo"] in periodos_set], lambda f: f["periodo"][:4]
    )
    interanual = [
        {
            "anio": anio,
            "pct_conciliado": promedio_ponderado(filas, "pct_conciliado", "total_registros") or 0.0,
            "total_registros": sum(f["total_registros"] for f in filas),
        }
        for anio, filas in sorted(por_anio.items())
    ]
    if len(interanual) < 2:
        interanual = []

    return {
        "kpis": {
            "pct_conciliado": conc_actual,
            "variacion_conciliado_pct": variacion_pct(conc_actual, conc_previo),
            "tasa_discrepancias": disc_actual,
            "variacion_discrepancias_pct": variacion_pct(disc_actual, disc_previo),
            # Cierre Tier 1-2, punto 2.3 (C5): antes era una media aritmética
            # simple entre periodos -- un mes con 3 liquidaciones pesaba igual
            # que uno con 300. `promedio_ponderado` por `bruto_total` (ya
            # usado más arriba para construir cada punto de `tendencia_margen`
            # a nivel de fila individual) le da a cada mes el peso real de su
            # volumen recaudado.
            "margen_comision_promedio": promedio_ponderado(tendencia_margen, "margen", "bruto_total"),
        },
        "tendencia_conciliacion": tendencia_conciliacion,
        "tendencia_margen": tendencia_margen,
        "periodos_con_discrepancia": periodos_con_discrepancia,
        "interanual": interanual,
        "metadata": {
            "meses": meses,
            "interanual_disponible": bool(interanual),
            "dataset_mixto": len({p[:4] for p in periodos}) > 1,
            "registros_previos": {
                "variacion_conciliado_pct": registros_previos_conciliacion,
                "variacion_discrepancias_pct": registros_previos_conciliacion,
            },
            "fuentes": ["rpt_tasa_discrepancias", "rpt_margen_comision"],
        },
    }
