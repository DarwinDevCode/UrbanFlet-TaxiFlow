"""Captación — CU-O01 (solicitud de conductor), CU-O02 (registro de
pasajero), CU-O03 (verificar documentación).

Regla de write-ahead (CU-O17, la misma que expuso el bug de Fase 0 en
auth/rbac): en cada función de este módulo, `write_audit_event(...)` se
llama SIEMPRE antes de la escritura que produce el efecto de negocio
correspondiente, nunca después. Si la escritura de auditoría falla,
`AuditWriteError` propaga y el efecto de abajo nunca se ejecuta. Cada función
que muta estado dice explícitamente, en un comentario, qué evento cubre esa
llamada — para que el próximo módulo (Fase 2) no tenga que adivinar el patrón.
"""

import uuid
from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.archivos import service as archivos_service
from src.auth import service as auth_service
from src.captacion import schemas
from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.agregacion_estrategica import agrupar, promedio_ponderado, ultimos_periodos, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, fetch_snapshot_history, get_clickhouse_client
from src.core.db_mongo import get_mongo_client
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.core.notifications import NotificationDispatcher


class SolicitudCedulaActivaError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="SOLICITUD_CEDULA_ACTIVA",
            message="Ya existe una solicitud activa (ENVIADA, EN_VERIFICACION u OBSERVADA) con esta cédula",
            status_code=409,
        )


class ApplicantAlreadyMemberError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="APPLICANT_ALREADY_MEMBER",
            message="La cédula ya pertenece a un socio conductor activo",
            status_code=409,
        )


class SolicitudNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="SOLICITUD_NO_ENCONTRADA", message="La solicitud no existe", status_code=404)


class SolicitudEstadoInvalidoError(DomainError):
    def __init__(self, esperado: str) -> None:
        super().__init__(
            code="SOLICITUD_ESTADO_INVALIDO",
            message=f"La solicitud debe estar en uno de estos estados: {esperado}",
            status_code=409,
        )


class MotivoRequeridoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="MOTIVO_REQUERIDO", message="RECHAZADA y OBSERVADA requieren un motivo", status_code=400
        )


class TipoDocumentoInvalidoError(DomainError):
    def __init__(self, tipos_invalidos: set[str]) -> None:
        super().__init__(
            code="TIPO_DOCUMENTO_INVALIDO",
            message=f"Tipo(s) de documento no reconocidos en el catálogo: {', '.join(sorted(tipos_invalidos))}",
            status_code=422,
        )


class ArchivoNoValidoParaDocumentoError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="ARCHIVO_NO_VALIDO_PARA_DOCUMENTO",
            message="El archivo no existe, no te pertenece, o no se subió como documento de postulación",
            status_code=422,
        )


async def _resolver_documentos(
    db: AsyncIOMotorDatabase, documentos: list[schemas.DocumentoInput], usuario_id: str
) -> list[dict]:
    """Resuelve cada `archivo_id` del cliente contra un archivo real ya
    subido (`POST /archivos`, contexto "documento_postulacion") -- verifica
    que exista, que pertenezca a ESTE postulante y que se haya subido con el
    contexto correcto (no reciclar evidencia de otro flujo). El hash real
    sale del archivo (`hash_sha256`, calculado en el servidor durante la
    subida), nunca del cliente. Guarda en las mismas claves que ya usa
    `_aprobar_solicitud_en_transaccion` (`url_objeto`/`hash_archivo`) y que
    ya usa `documento_renovacion` -- el archivo_id vive en `url_objeto` desde
    antes de esta ronda, mismo convenio interno, cero cambios en el código
    que ya consume `solicitud["documentos"]`."""
    resueltos: list[dict] = []
    for d in documentos:
        archivo = await archivos_service.obtener_archivo(db, archivo_id=d.archivo_id)
        if archivo["propietario_id"] != usuario_id or archivo["contexto"] != "documento_postulacion":
            raise ArchivoNoValidoParaDocumentoError()
        resueltos.append(
            {
                "tipo": d.tipo,
                "propietario_tipo": d.propietario_tipo,
                "url_objeto": archivo["_id"],
                "hash_archivo": archivo["hash_sha256"],
                "fecha_emision": d.fecha_emision.isoformat() if d.fecha_emision else None,
                "fecha_vencimiento": d.fecha_vencimiento.isoformat() if d.fecha_vencimiento else None,
            }
        )
    return resueltos


async def _validar_tipos_documento(db: AsyncIOMotorDatabase, documentos: list[schemas.DocumentoInput]) -> None:
    """Punto #3 de la ronda de usabilidad de admin_sistema: `tipo` de
    documento nunca fue texto 100% libre, se valida contra el catálogo
    `tipos_documento` (Módulo 3.2) antes de cualquier efecto de negocio.
    Extraído de `crear_solicitud` para que `enviar_solicitud_con_documentos`
    (Fase 1 de gestión documental en la postulación) reuse exactamente la
    misma regla, sin duplicarla."""
    if not documentos:
        return
    tipos_pedidos = {d.tipo for d in documentos}
    validos = {
        t["nombre"]
        async for t in db.tipos_documento.find({"nombre": {"$in": list(tipos_pedidos)}, "activo": True})
    }
    invalidos = tipos_pedidos - validos
    if invalidos:
        raise TipoDocumentoInvalidoError(invalidos)


# ---------------------------------------------------------------------------
# CU-O02 — Registrar un pasajero
# ---------------------------------------------------------------------------


async def registrar_pasajero(
    db: AsyncIOMotorDatabase,
    *,
    nombre: str,
    telefono: str | None,
    email: str | None,
    password: str,
    version_consentimiento: str,
    canal: str = "web",
) -> dict:
    # La cuenta base (USUARIO) la crea auth.registrar_usuario, que ya aplica
    # su propio write-ahead (CREDENCIAL_CREACION) para ESE efecto. Aquí se
    # audita, por separado, el efecto específico de Captación: convertir esa
    # cuenta en un perfil de pasajero con consentimiento de datos.
    usuario = await auth_service.registrar_usuario(db, nombre=nombre, telefono=telefono, email=email, password=password)

    ahora = datetime.now(UTC)

    # Write-ahead para CU-O02: el evento se escribe antes de aplicar rol y
    # consentimiento sobre el usuario recién creado.
    await write_audit_event(
        db,
        actor_id=usuario["_id"],
        rol=None,
        accion=AccionAuditoria.PASAJERO_REGISTRO,
        entidad="usuarios",
        entidad_id=usuario["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"version_consentimiento": version_consentimiento},
    )

    await db.usuarios.update_one(
        {"_id": usuario["_id"]},
        {
            "$addToSet": {"roles": "pasajero"},
            "$set": {
                "pasajero": {"calificacion_promedio": None},
                "consentimiento": {"version": version_consentimiento, "fecha": ahora},
                "canal": canal,
            },
        },
    )

    return {"usuario_id": usuario["_id"], "estado": usuario["estado"]}


# ---------------------------------------------------------------------------
# CU-O01 — Registrar la solicitud de un conductor
# ---------------------------------------------------------------------------


async def crear_solicitud(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    nombre: str,
    telefono: str | None,
    email: str | None,
    password: str,
    cedula: str,
    licencia_numero: str,
    vehiculo: schemas.VehiculoInput,
    documentos: list[schemas.DocumentoInput],
    enviar: bool,
    canal: str = "web",
) -> dict:
    # Precondición de CU-O01: ninguna solicitud activa con la misma cédula.
    activa = await db.solicitudes.find_one(
        {"cedula": cedula, "estado": {"$in": ["ENVIADA", "EN_VERIFICACION", "OBSERVADA"]}}
    )
    if activa is not None:
        raise SolicitudCedulaActivaError()

    # A2: la cédula ya es de un socio conductor activo.
    ya_socio = await db.usuarios.find_one({"conductor.cedula": cedula, "estado": "ACTIVO"})
    if ya_socio is not None:
        raise ApplicantAlreadyMemberError()

    # Punto #3 de la ronda de usabilidad de admin_sistema (2026-08-07):
    # `DocumentoInput.tipo` era texto libre sin validar contra el catálogo
    # `tipos_documento` (Módulo 3.2) que ya existe -- se valida acá, antes
    # de cualquier efecto de negocio, para no crear la cuenta/solicitud si
    # el tipo no es reconocido.
    await _validar_tipos_documento(db, documentos)

    usuario = await auth_service.registrar_usuario(db, nombre=nombre, telefono=telefono, email=email, password=password)

    # Gestión documental en la postulación: el flujo real de `web-conductor`
    # nunca llega acá con `documentos` no vacío (sube los archivos DESPUÉS,
    # vía `enviar_solicitud_con_documentos`, porque `POST /archivos` exige un
    # actor que recién existe desde la línea de arriba) -- pero si algún
    # llamador SÍ manda documentos junto con la cuenta en el mismo request,
    # se resuelven igual contra el `usuario_id` recién creado, nunca se
    # confía en el `archivo_id` sin verificar dueño/contexto.
    documentos_resueltos = await _resolver_documentos(db, documentos, usuario["_id"])

    # A3: la placa ya existe en la flota → marca de revisión reforzada
    # (decisión confirmada con el cliente: solo una etiqueta en la bandeja,
    # sin flujo adicional automatizado).
    placa_existente = await db.vehiculos.find_one({"placa": vehiculo.placa})
    revision_reforzada = placa_existente is not None

    ahora = datetime.now(UTC)
    solicitud = {
        "_id": str(uuid.uuid4()),
        "usuario_id": usuario["_id"],
        "cedula": cedula,
        "licencia_numero": licencia_numero,
        "estado": "ENVIADA" if enviar else "BORRADOR",
        "fecha_envio": ahora if enviar else None,
        "fecha_decision": None,
        "verificador_id": None,
        "motivo_rechazo": None,
        "vehiculo": vehiculo.model_dump(),
        "documentos": documentos_resueltos,
        "revision_reforzada": revision_reforzada,
        "canal": canal,
    }

    if enviar:
        # Write-ahead para CU-O01: el evento de envío se escribe antes de
        # persistir la solicitud como ENVIADA. Un BORRADOR (enviar=False) no
        # es todavía un evento sensible — no dispara auditoría.
        await _auditar_envio(
            db,
            usuario_id=usuario["_id"],
            solicitud_id=solicitud["_id"],
            cedula=cedula,
            revision_reforzada=revision_reforzada,
        )

    await db.solicitudes.insert_one(solicitud)

    if enviar:
        await _notificar_nueva_solicitud(db, dispatcher, solicitud_id=solicitud["_id"])

    # El nombre ya se conoce en este mismo request (se acaba de crear la
    # cuenta con él) — no hace falta ir a buscarlo de vuelta a `usuarios`.
    return {**solicitud, "usuario_nombre": nombre}


async def _auditar_envio(
    db: AsyncIOMotorDatabase, *, usuario_id: str, solicitud_id: str, cedula: str, revision_reforzada: bool
) -> None:
    await write_audit_event(
        db,
        actor_id=usuario_id,
        rol=None,
        accion=AccionAuditoria.SOLICITUD_CONDUCTOR_ENVIO,
        entidad="solicitudes",
        entidad_id=solicitud_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"cedula": cedula, "revision_reforzada": revision_reforzada},
    )


async def _notificar_nueva_solicitud(
    db: AsyncIOMotorDatabase, dispatcher: NotificationDispatcher, *, solicitud_id: str
) -> None:
    async for admin in db.usuarios.find({"roles": "admin_captacion"}):
        await dispatcher.notify_user(admin["_id"], "NUEVA_SOLICITUD", {"solicitud_id": solicitud_id})


async def enviar_solicitud_con_documentos(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    actor_id: str,
    documentos: list[schemas.DocumentoInput],
) -> dict:
    """Segundo paso del flujo de postulación con documentos reales (Fase 1):
    el postulante ya tiene cuenta y una solicitud propia en BORRADOR (creada
    por `crear_solicitud(enviar=False)`), ya subió sus archivos autenticado
    como esa cuenta (`POST /archivos`, contexto "documento_postulacion") --
    acá se adjuntan, se valida cada uno, y la solicitud pasa a ENVIADA con
    el MISMO efecto (auditoría + notificación a admin_captacion) que el
    camino de un solo paso de `crear_solicitud(enviar=True)`."""
    solicitud = await db.solicitudes.find_one({"usuario_id": actor_id, "estado": "BORRADOR"})
    if solicitud is None:
        raise SolicitudNoEncontradaError()

    await _validar_tipos_documento(db, documentos)
    documentos_resueltos = await _resolver_documentos(db, documentos, actor_id)

    ahora = datetime.now(UTC)
    await _auditar_envio(
        db,
        usuario_id=actor_id,
        solicitud_id=solicitud["_id"],
        cedula=solicitud["cedula"],
        revision_reforzada=solicitud["revision_reforzada"],
    )
    await db.solicitudes.update_one(
        {"_id": solicitud["_id"]},
        {"$set": {"documentos": documentos_resueltos, "estado": "ENVIADA", "fecha_envio": ahora}},
    )
    await _notificar_nueva_solicitud(db, dispatcher, solicitud_id=solicitud["_id"])

    solicitud["documentos"] = documentos_resueltos
    solicitud["estado"] = "ENVIADA"
    solicitud["fecha_envio"] = ahora
    (solicitud,) = await enriquecer_con_usuario_nombre(db, [solicitud])
    return solicitud


async def enriquecer_con_usuario_nombre(db: AsyncIOMotorDatabase, items: list[dict]) -> list[dict]:
    """Adjunta `usuario_nombre` (de `usuarios`, vía `usuario_id`) a cada
    solicitud, para que las pantallas internas (CU-O03, bandeja de
    Captación) no tengan que mostrar el UUID crudo del postulante. Batch
    fetch con un solo `$in` en vez de N+1 — mismo criterio de rendimiento
    que `viajes.service_historial.enriquecer_con_pasajero`, adaptado a
    listas en vez de un único registro."""
    usuario_ids = {item["usuario_id"] for item in items if item.get("usuario_id")}
    if not usuario_ids:
        return items
    usuarios = await db.usuarios.find({"_id": {"$in": list(usuario_ids)}}).to_list(length=len(usuario_ids))
    nombres = {u["_id"]: u["nombre"] for u in usuarios}
    return [{**item, "usuario_nombre": nombres.get(item.get("usuario_id"))} for item in items]


async def listar_solicitudes(
    db: AsyncIOMotorDatabase,
    *,
    estado: str | None = None,
    cedula: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filtro: dict = {}
    if estado:
        filtro["estado"] = estado
    if cedula:
        filtro["cedula"] = {"$regex": cedula, "$options": "i"}
    total = await db.solicitudes.count_documents(filtro)
    items = (
        await db.solicitudes.find(filtro)
        .sort("fecha_envio", -1)
        .skip(offset)
        .limit(limit)
        .to_list(length=limit)
    )
    items = await enriquecer_con_usuario_nombre(db, items)
    return items, total


# ---------------------------------------------------------------------------
# CU-O03 — Verificar la documentación del postulante
# ---------------------------------------------------------------------------


async def tomar_solicitud(
    db: AsyncIOMotorDatabase, *, solicitud_id: str, verificador_id: str, verificador_rol: str
) -> dict:
    solicitud = await db.solicitudes.find_one({"_id": solicitud_id})
    if solicitud is None:
        raise SolicitudNoEncontradaError()
    if solicitud["estado"] != "ENVIADA":
        raise SolicitudEstadoInvalidoError("ENVIADA")

    # Write-ahead: se audita la toma para revisión antes de bloquear la
    # solicitud contra doble revisión (evita que dos administradores la
    # trabajen a la vez, CU-O03 paso 1).
    await write_audit_event(
        db,
        actor_id=verificador_id,
        rol=verificador_rol,
        accion=AccionAuditoria.SOLICITUD_CONDUCTOR_TOMA,
        entidad="solicitudes",
        entidad_id=solicitud_id,
        resultado=ResultadoAuditoria.OK,
    )

    await db.solicitudes.update_one(
        {"_id": solicitud_id, "estado": "ENVIADA"},
        {"$set": {"estado": "EN_VERIFICACION", "verificador_id": verificador_id}},
    )
    solicitud["estado"] = "EN_VERIFICACION"
    solicitud["verificador_id"] = verificador_id
    (solicitud,) = await enriquecer_con_usuario_nombre(db, [solicitud])
    return solicitud


async def decidir_solicitud(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    solicitud_id: str,
    verificador_id: str,
    verificador_rol: str,
    decision: str,
    motivo: str | None,
) -> dict:
    solicitud = await db.solicitudes.find_one({"_id": solicitud_id})
    if solicitud is None:
        raise SolicitudNoEncontradaError()
    if solicitud["estado"] not in ("ENVIADA", "EN_VERIFICACION", "OBSERVADA"):
        raise SolicitudEstadoInvalidoError("ENVIADA, EN_VERIFICACION u OBSERVADA")
    if decision in ("RECHAZADA", "OBSERVADA") and not motivo:
        raise MotivoRequeridoError()

    ahora = datetime.now(UTC)

    if decision == "APROBADA":
        # La cadena de aprobación (decisión + habilitación de vehículo +
        # asignación de rol de conductor) toca más de una entidad de
        # negocio. Se envuelve en una transacción multi-documento para que,
        # si algo falla a mitad de camino, no quede aplicada solo una parte
        # (ver core/db_transaction.py — este es el mismo patrón que Fase 3 y
        # Fase 4 reutilizarán para despacho y para pago→comisión→liquidación).
        solicitud_actualizada = await with_transaction(
            get_mongo_client(),
            lambda session: _aprobar_solicitud_en_transaccion(
                db,
                solicitud,
                verificador_id=verificador_id,
                verificador_rol=verificador_rol,
                ahora=ahora,
                session=session,
            ),
        )
    else:
        # RECHAZADA/OBSERVADA muta una sola entidad de negocio (la propia
        # solicitud): el write-ahead de una escritura ya cubre la
        # consistencia que importa aquí, sin necesitar una transacción
        # multi-documento.
        await write_audit_event(
            db,
            actor_id=verificador_id,
            rol=verificador_rol,
            accion=AccionAuditoria.SOLICITUD_CONDUCTOR_DECISION,
            entidad="solicitudes",
            entidad_id=solicitud_id,
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": solicitud["estado"]},
            datos_posteriores={"estado": decision, "motivo": motivo},
        )
        await db.solicitudes.update_one(
            {"_id": solicitud_id},
            {
                "$set": {
                    "estado": decision,
                    "fecha_decision": ahora,
                    "verificador_id": verificador_id,
                    "motivo_rechazo": motivo,
                }
            },
        )
        solicitud_actualizada = dict(solicitud)
        solicitud_actualizada["estado"] = decision
        solicitud_actualizada["fecha_decision"] = ahora
        solicitud_actualizada["motivo_rechazo"] = motivo

    await dispatcher.notify_user(solicitud["usuario_id"], "SOLICITUD_DECISION", {"estado": decision, "motivo": motivo})

    (solicitud_actualizada,) = await enriquecer_con_usuario_nombre(db, [solicitud_actualizada])
    return solicitud_actualizada


async def _aprobar_solicitud_en_transaccion(
    db: AsyncIOMotorDatabase,
    solicitud: dict,
    *,
    verificador_id: str,
    verificador_rol: str,
    ahora: datetime,
    session,
) -> dict:
    """Todo lo que ocurre aquí participa en una única transacción — cada
    escritura recibe `session=session`. Si `session.with_transaction` decide
    reintentar (error transitorio) o abortar (una excepción escapa de aquí),
    MongoDB descarta TODAS las escrituras hechas con esta sesión, no solo la
    última — por eso `solicitud` nunca se muta in-place entre reintentos."""
    solicitud_id = solicitud["_id"]

    # Write-ahead #1: la decisión en sí, antes de tocar la solicitud.
    await write_audit_event(
        db,
        actor_id=verificador_id,
        rol=verificador_rol,
        accion=AccionAuditoria.SOLICITUD_CONDUCTOR_DECISION,
        entidad="solicitudes",
        entidad_id=solicitud_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": solicitud["estado"]},
        datos_posteriores={"estado": "APROBADA", "motivo": None},
        session=session,
    )
    await db.solicitudes.update_one(
        {"_id": solicitud_id},
        {
            "$set": {
                "estado": "APROBADA",
                "fecha_decision": ahora,
                "verificador_id": verificador_id,
                "motivo_rechazo": None,
            }
        },
        session=session,
    )

    usuario_id = solicitud["usuario_id"]
    vehiculo_id = str(uuid.uuid4())

    # Write-ahead #2: "vehicle enablements" es su propio ítem en el catálogo
    # mínimo de CU-O17, distinto de la decisión — se audita antes de crear
    # el vehículo, dentro de la misma transacción que el resto de la cadena.
    await write_audit_event(
        db,
        actor_id=verificador_id,
        rol=None,
        accion=AccionAuditoria.VEHICULO_HABILITACION,
        entidad="vehiculos",
        entidad_id=vehiculo_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"placa": solicitud["vehiculo"]["placa"]},
        session=session,
    )

    await db.vehiculos.insert_one(
        {
            "_id": vehiculo_id,
            **solicitud["vehiculo"],
            "estado_habilitacion": "HABILITADO",
            "km_acumulado": 0,
            "propietario_id": usuario_id,
        },
        session=session,
    )

    await db.usuarios.update_one(
        {"_id": usuario_id},
        {
            "$addToSet": {"roles": "conductor"},
            "$set": {
                "conductor": {
                    "cedula": solicitud["cedula"],
                    "licencia_numero": solicitud["licencia_numero"],
                    "calificacion_promedio": None,
                    "estado_servicio": "FUERA_DE_LINEA",
                    "fecha_alta_socio": ahora,
                },
                # CU-T02: el alta de socio (a diferencia de la cuenta base,
                # creada en `crear_solicitud`) hereda el canal de la
                # solicitud que la originó -- así "altas por canal" cuenta
                # el canal por el que entró el socio, no el de la cuenta.
                "canal": solicitud.get("canal", "web"),
            },
        },
        session=session,
    )

    for doc in solicitud["documentos"]:
        propietario_id = usuario_id if doc["propietario_tipo"] == "CONDUCTOR" else vehiculo_id
        await db.documentos.insert_one(
            {
                "_id": str(uuid.uuid4()),
                "tipo": doc["tipo"],
                "propietario_tipo": doc["propietario_tipo"],
                "propietario_id": propietario_id,
                "url_objeto": doc["url_objeto"],
                "hash_archivo": doc["hash_archivo"],
                "fecha_emision": doc.get("fecha_emision"),
                "fecha_vencimiento": doc.get("fecha_vencimiento"),
                "estado_verificacion": "CONFORME",
                "verificador_id": verificador_id,
                "fecha_verificacion": ahora,
            },
            session=session,
        )

    resultado = dict(solicitud)
    resultado["estado"] = "APROBADA"
    resultado["fecha_decision"] = ahora
    resultado["motivo_rechazo"] = None
    return resultado


async def listar_referidos_pendientes(db: AsyncIOMotorDatabase) -> list[dict]:
    """Panel táctico de Captación -- CU-T02/OT1.2, informe simple (MongoDB)."""
    cursor = db.referidos.find({"estado_incentivo": {"$in": ["PENDIENTE", "ACREDITADO"]}}).sort("fecha_referido", -1)
    return await cursor.to_list(length=200)


def obtener_conversion_captacion() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico -- CU-T01/OT1.1."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_conversion_captacion")
    finally:
        client.close()
    return sorted(filas, key=lambda f: (f["periodo"], f["canal"]))


def obtener_altas_retencion_canal() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico -- CU-T02/OT1.2."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_altas_retencion_canal")
    finally:
        client.close()
    return sorted(filas, key=lambda f: (f["periodo"], f["canal"]))


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Crecimiento Estratégico
# (OE1, nivel_estrategico.md §3.1, patrón Z)
# ---------------------------------------------------------------------------


def obtener_panel_crecimiento(*, meses: int = 12, cortes: int = 12) -> dict:
    """Segunda capa de agregación sobre las 3 `rpt_*` de Captación, sin tabla nueva.

    Fuentes: `rpt_conversion_captacion` y `rpt_altas_retencion_canal` (ambas
    con `periodo` propio -- caso 1) + `rpt_conversion_onboarding` (corte sin
    periodo -- caso 2, tendencia vía `fetch_snapshot_history`). La spec cita
    la tabla como `rpt_altas_retencion`; el nombre real publicado por
    `dag_captacion_gold` es `rpt_altas_retencion_canal`.

    **Dos limitaciones que este endpoint declara en metadata en vez de
    disimular:**

    1. `canal_cobertura_parcial=true`. La dimensión `canal` no cubre el 100%
       del padrón real: al 2026-08-08, 96 de 194 usuarios (49%) no tienen el
       campo -- lo agregaron rondas de siembra posteriores al backfill
       original, que no pasaron por el flujo que lo setea. Cualquier
       desglose por canal subrepresenta sistemáticamente a esa mitad. Es el
       mismo tratamiento que ya se le da al gap de zona: se sirve el dato y
       se marca la limitación para que la UI la muestre.
    2. `demanda_disponible=false`. La spec pide "crecimiento de demanda
       (viajes solicitados/mes)", pero **ninguna vista `rpt_*` publica los
       viajes solicitados por mes**: `rpt_tasa_cancelacion` es la única con
       periodo y volumen de viajes, y solo contiene los cancelados
       (`HAVING cancelados > 0`), así que su `solicitados` no es el universo
       de demanda. Leerlo de `fact_ciclo_viaje` sería saltarse la regla de la
       Sección 2 (agregar sobre `rpt_*`, no sobre los hechos Gold). Se
       devuelve `None` en vez de un número que parecería demanda sin serlo.
    """
    client = get_clickhouse_client()
    try:
        conversion = fetch_latest_snapshot(client, "rpt_conversion_captacion")
        altas = fetch_latest_snapshot(client, "rpt_altas_retencion_canal")
        onboarding = fetch_latest_snapshot(client, "rpt_conversion_onboarding")
        onboarding_hist = fetch_snapshot_history(client, "rpt_conversion_onboarding", limite_dias=cortes)
    finally:
        client.close()

    periodos = ultimos_periodos(
        [f["periodo"] for f in conversion] + [f["periodo"] for f in altas], meses
    )
    periodos_set = set(periodos)

    por_periodo_altas = agrupar([f for f in altas if f["periodo"] in periodos_set], "periodo")
    tendencia_altas = [
        {
            "periodo": periodo,
            "altas": sum(f["altas"] for f in por_periodo_altas[periodo]),
            "pct_retencion": promedio_ponderado(por_periodo_altas[periodo], "pct_retencion", "altas") or 0.0,
        }
        for periodo in periodos
        if periodo in por_periodo_altas
    ]

    por_periodo_conv = agrupar([f for f in conversion if f["periodo"] in periodos_set], "periodo")
    tendencia_conversion = [
        {
            "periodo": periodo,
            "pct_conversion": promedio_ponderado(
                por_periodo_conv[periodo], "pct_conversion", "total_solicitudes"
            )
            or 0.0,
            "total_solicitudes": sum(f["total_solicitudes"] for f in por_periodo_conv[periodo]),
        }
        for periodo in periodos
        if periodo in por_periodo_conv
    ]

    # Cierre Tier 1-2, punto 2.6 (N1): serie temporal de conversión POR
    # CANAL -- antes la tabla "Conversión por canal" solo mostraba el
    # consolidado de toda la ventana (`canales`, más abajo), sin evolución en
    # el tiempo. `rpt_conversion_captacion` ya trae `canal` + `periodo`
    # juntos en cada fila; esto es un reshape adicional (periodo x canal en
    # vez de solo periodo) sobre el mismo `conversion` ya cargado -- no una
    # consulta nueva. Agregado, no reemplaza `tendencia_conversion`.
    tendencia_conversion_por_canal = [
        {
            "periodo": periodo,
            "canal": canal,
            "pct_conversion": promedio_ponderado(filas_canal, "pct_conversion", "total_solicitudes") or 0.0,
            "total_solicitudes": sum(f["total_solicitudes"] for f in filas_canal),
        }
        for periodo in periodos
        if periodo in por_periodo_conv
        for canal, filas_canal in agrupar(por_periodo_conv[periodo], "canal").items()
    ]

    tendencia_onboarding = [
        {
            "periodo": str(fecha),
            "pct_activo": promedio_ponderado(filas, "pct_activo", "total_registros") or 0.0,
            "total_registros": sum(f["total_registros"] for f in filas),
        }
        for fecha, filas in sorted(agrupar(onboarding_hist, "fecha_datos").items())
    ]

    # Tabla: conversión consolidada por canal (todos los periodos de la ventana).
    por_canal = agrupar([f for f in conversion if f["periodo"] in periodos_set], "canal")
    canales = sorted(
        (
            {
                "canal": canal,
                "pct_conversion": promedio_ponderado(filas, "pct_conversion", "total_solicitudes") or 0.0,
                "total_solicitudes": sum(f["total_solicitudes"] for f in filas),
                "dias_aprobacion_promedio": promedio_ponderado(
                    filas, "dias_aprobacion_promedio", "total_solicitudes"
                ),
                "altas": sum(f["altas"] for f in agrupar(altas, "canal").get(canal, [])),
            }
            for canal, filas in por_canal.items()
        ),
        key=lambda f: f["total_solicitudes"],
        reverse=True,
    )

    altas_actual = tendencia_altas[-1]["altas"] if tendencia_altas else None
    altas_previo = tendencia_altas[-2]["altas"] if len(tendencia_altas) > 1 else None

    # Cierre Tier 1-2, punto 2.1 (C1 opción A): variación PROPIA de
    # `pct_conversion_onboarding` para la tarjeta de Crecimiento del Tablero
    # Ejecutivo -- antes esa tarjeta mostraba `variacion_altas_pct` (un KPI
    # distinto). `tendencia_onboarding[-1]` es el mismo corte que ya usa
    # `pct_conversion_onboarding` (ambos derivan de la corrida más reciente
    # de `rpt_conversion_onboarding`); `tendencia_onboarding[-2]` es el corte
    # anterior dentro de la misma ventana de `cortes`.
    onboarding_actual = tendencia_onboarding[-1]["pct_activo"] if tendencia_onboarding else None
    onboarding_previo = tendencia_onboarding[-2]["pct_activo"] if len(tendencia_onboarding) > 1 else None
    variacion_onboarding_pct = variacion_pct(onboarding_actual, onboarding_previo)
    registros_previos_onboarding = (
        tendencia_onboarding[-2]["total_registros"] if len(tendencia_onboarding) > 1 else None
    )

    return {
        "kpis": {
            "pct_conversion_onboarding": promedio_ponderado(onboarding, "pct_activo", "total_registros"),
            "variacion_onboarding_pct": variacion_onboarding_pct,
            "pct_retencion_90d": promedio_ponderado(altas, "pct_retencion", "altas"),
            "altas_periodo": altas_actual,
            "variacion_altas_pct": variacion_pct(altas_actual, altas_previo),
            "crecimiento_demanda_pct": None,  # ver limitación 2 del docstring
        },
        "tendencia_altas": tendencia_altas,
        "tendencia_conversion": tendencia_conversion,
        "tendencia_conversion_por_canal": tendencia_conversion_por_canal,
        "tendencia_onboarding": tendencia_onboarding,
        "canales": canales,
        "metadata": {
            "meses": meses,
            "canal_cobertura_parcial": True,
            "demanda_disponible": False,
            "fuentes": [
                "rpt_conversion_captacion",
                "rpt_altas_retencion_canal",
                "rpt_conversion_onboarding",
            ],
            # Tier 1 de la auditoría, punto 6 (H-T5): conteo de registros reales
            # que respaldan el periodo ANTERIOR de cada variación, para que el
            # frontend advierta "base insuficiente" sin ocultar el dato. Para
            # `variacion_altas_pct`, `altas` ya ES un conteo (no un promedio
            # ponderado), así que el propio `altas_previo` es el n real -- no
            # hace falta un campo de peso aparte.
            "registros_previos": {
                "variacion_altas_pct": altas_previo,
                "variacion_onboarding_pct": registros_previos_onboarding,
            },
        },
    }
