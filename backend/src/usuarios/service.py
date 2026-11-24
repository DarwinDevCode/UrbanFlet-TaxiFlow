"""Gestión de cuentas, roles y sesiones — Módulo 1 de admin_sistema
(specs/specs-administrativas/admin_sistema.md, IAM). Toda acción de este
módulo pasa por `write_audit_event` (regla transversal de la spec) y por
`seguridad.service` para la política de contraseña vigente.

Nota sobre "suspender invalida la sesión de inmediato" (§1.1 de la spec):
no hace falta un mecanismo aparte para eso -- `rbac.get_current_actor` ya
relee `usuarios.estado` de Mongo en CADA petición (CU-O18 A3, para que un
cambio de rol o una revocación apliquen sin esperar a que el token expire).
Poner `estado` en `SUSPENDIDO`/`BAJA` (cualquier valor distinto de
`ACTIVO`) ya lo bloquea en la siguiente petición, igual que ya bloquea el
login (`auth/service.py::login_con_password`). El registro de sesiones
activas (Módulo 1.4, `core/sessions.py`) es para el caso más fino de cerrar
UNA sesión puntual sin tocar el resto de la cuenta.
"""

import uuid
from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from src.auth.service import EmailAlreadyRegisteredError, PhoneAlreadyRegisteredError
from src.core import sessions as core_sessions
from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
# Fuente de verdad única de "viaje vivo" -- se importa en vez de duplicar la
# lista acá, para que agregar un estado nuevo (como pasó con PROGRAMADO) no
# deje este guard desactualizado en silencio. Sin riesgo de import circular:
# `viajes` no importa `usuarios` en ninguna dirección (verificado).
from src.viajes.service import ESTADOS_ACTIVOS as ESTADOS_VIAJE_ACTIVO
from src.core.exceptions import DomainError, WeakPasswordError
# Decisión 2: la baja de un socio retira sus vehículos reusando el MISMO
# servicio que la baja manual (Decisión 3), no una copia. Sin riesgo de
# import circular: `mantenimiento` no importa `usuarios` en ninguna
# dirección (verificado, igual que con `viajes` más abajo).
from src.mantenimiento import service as mantenimiento_service
from src.core.rbac import ROLES
from src.core.security import generar_password_segura, hash_password
from src.seguridad.service import obtener_politica_vigente

# CU-O01/CU-O02: pasajero/conductor se autorregistran -- este módulo es
# exclusivamente para "personal interno" (spec §1.1). admin_sistema no
# puede usarlo para fabricar cuentas de pasajero/conductor por este canal.
ROLES_STAFF = frozenset(ROLES - {"pasajero", "conductor"})

_ESTADOS_REACTIVABLES = {"SUSPENDIDO"}


class UsuarioNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="USUARIO_NO_ENCONTRADO", message="El usuario no existe", status_code=404)


class RolInvalidoError(DomainError):
    def __init__(self, roles_invalidos: set[str]) -> None:
        super().__init__(
            code="ROL_INVALIDO",
            message=f"Rol(es) no permitidos para cuentas de personal interno: {', '.join(sorted(roles_invalidos))}",
            status_code=422,
        )


class EstadoInvalidoError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(code="ESTADO_INVALIDO", message=message, status_code=409)


class BajaConViajeActivoError(DomainError):
    """Caso borde de la baja lógica de cuentas (ronda de personalización/QA).

    Se BLOQUEA, no se permite con advertencia: un viaje activo tiene un
    pasajero real esperando o ya a bordo, y dar de baja al conductor lo
    dejaría sin poder siquiera abrir la app para cerrarlo (`rbac` relee
    `estado` en cada petición) -- el viaje quedaría atascado a mitad de su
    máquina de estados, sin actor que pueda avanzarlo. A diferencia del caso
    del vehículo habilitado (ver `dar_de_baja_usuario`), este SÍ tiene salida
    para el administrador: terminar o cancelar el viaje y reintentar.
    """

    def __init__(self, viaje_id: str, estado: str) -> None:
        super().__init__(
            code="BAJA_CON_VIAJE_ACTIVO",
            message=(
                f"No se puede dar de baja: la cuenta tiene un viaje en curso ({estado}). "
                f"Termina o cancela el viaje {viaje_id[:8]}… y vuelve a intentarlo."
            ),
            status_code=409,
        )


def _valor_anidado(doc: dict, clave: str):
    """Soporta claves con notación de punto (ej. `conductor.foto_url`, usada
    por `perfil/service.py` para el sub-documento `usuarios.conductor`) --
    `dict.get()` plano no resuelve rutas anidadas, así que sin esto el
    "antes" de la auditoría quedaría siempre `None` para esos campos."""
    valor = doc
    for parte in clave.split("."):
        if not isinstance(valor, dict):
            return None
        valor = valor.get(parte)
    return valor


def _validar_roles_staff(roles: list[str]) -> None:
    invalidos = set(roles) - ROLES_STAFF
    if invalidos:
        raise RolInvalidoError(invalidos)


async def crear_cuenta_staff(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    nombre: str,
    telefono: str | None,
    email: str | None,
    password: str | None,
    roles: list[str],
) -> tuple[dict, str | None]:
    """Devuelve `(usuario, password_generada)`. `password_generada` es la
    contraseña en texto plano SOLO cuando `admin_sistema` la dejó en blanco
    para que el sistema la genere -- si mandó una propia, se devuelve `None`
    (nunca se hace eco de una contraseña que el propio llamador ya conoce)."""
    _validar_roles_staff(roles)
    politica = await obtener_politica_vigente(db)

    password_generada: str | None = None
    if password is None:
        password_generada = generar_password_segura(max(politica["longitud_minima_password"], 12))
        password = password_generada
    elif len(password) < politica["longitud_minima_password"]:
        raise WeakPasswordError(politica["longitud_minima_password"])

    ahora = datetime.now(UTC)
    usuario: dict = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "hash_password": hash_password(password),
        "roles": roles,
        "estado": "ACTIVO",
        "fecha_registro": ahora,
        "forzar_cambio_password": True,
        "password_actualizada_en": ahora,
    }
    if telefono:
        usuario["telefono"] = telefono
    if email:
        usuario["email"] = email

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_CREACION,
        entidad="usuarios",
        entidad_id=usuario["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre, "roles": roles},
    )

    try:
        await db.usuarios.insert_one(usuario)
    except DuplicateKeyError as exc:
        campo_en_conflicto = next(iter(exc.details.get("keyPattern", {})), None) if exc.details else None
        if campo_en_conflicto == "email":
            raise EmailAlreadyRegisteredError() from exc
        raise PhoneAlreadyRegisteredError() from exc

    return usuario, password_generada


async def restablecer_password(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str
) -> str:
    """Genera una contraseña nueva para un usuario existente y la devuelve en
    texto plano UNA sola vez -- el llamador (router) es responsable de
    mostrarla y nunca volver a exponerla. Fuerza cambio en el próximo login,
    mismo criterio que una cuenta recién creada."""
    usuario = await obtener_usuario(db, usuario_id)
    politica = await obtener_politica_vigente(db)
    password_generada = generar_password_segura(max(politica["longitud_minima_password"], 12))
    ahora = datetime.now(UTC)

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_PASSWORD_RESTABLECIDA,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": usuario.get("nombre")},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id},
        {
            "$set": {
                "hash_password": hash_password(password_generada),
                "forzar_cambio_password": True,
                "password_actualizada_en": ahora,
            }
        },
    )
    return password_generada


async def listar_usuarios(
    db: AsyncIOMotorDatabase,
    *,
    rol: str | None = None,
    estado: str | None = None,
    texto: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filtro: dict = {}
    if rol:
        filtro["roles"] = rol
    if estado:
        filtro["estado"] = estado
    if texto:
        filtro["$or"] = [
            {"nombre": {"$regex": texto, "$options": "i"}},
            {"telefono": {"$regex": texto, "$options": "i"}},
            {"email": {"$regex": texto, "$options": "i"}},
        ]
    total = await db.usuarios.count_documents(filtro)
    cursor = db.usuarios.find(filtro).sort("fecha_registro", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return items, total


async def obtener_usuario(db: AsyncIOMotorDatabase, usuario_id: str) -> dict:
    usuario = await db.usuarios.find_one({"_id": usuario_id})
    if usuario is None:
        raise UsuarioNoEncontradoError()
    return usuario


async def editar_usuario(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_rol: str,
    usuario_id: str,
    cambios: dict,
    accion: AccionAuditoria = AccionAuditoria.USUARIO_EDICION,
) -> dict:
    """`accion` por defecto es `USUARIO_EDICION` (Módulo 1.1, un admin_sistema
    editando la cuenta de un tercero). `perfil/service.py` reutiliza esta
    misma función para autoservicio, pasando `AccionAuditoria.PERFIL_EDICION`
    -- para que el filtro administrativo de Auditoría distinga "un admin
    editó a otro" de "alguien editó lo suyo", sin duplicar el resto de la
    lógica (chequeo de unicidad de teléfono/correo incluido)."""
    usuario = await obtener_usuario(db, usuario_id)
    if not cambios:
        return usuario

    antes = {k: _valor_anidado(usuario, k) for k in cambios}
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=accion,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos=antes,
        datos_posteriores=cambios,
    )
    try:
        await db.usuarios.update_one({"_id": usuario_id}, {"$set": cambios})
    except DuplicateKeyError as exc:
        campo_en_conflicto = next(iter(exc.details.get("keyPattern", {})), None) if exc.details else None
        if campo_en_conflicto == "email":
            raise EmailAlreadyRegisteredError() from exc
        raise PhoneAlreadyRegisteredError() from exc
    return await obtener_usuario(db, usuario_id)


async def asignar_roles(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, roles: list[str]
) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    roles_previos = usuario.get("roles", [])
    # Si la cuenta ya es de pasajero/conductor (autorregistro), no se le
    # puede reasignar a un rol de personal interno por este canal ni
    # viceversa -- evita mezclar el ciclo de vida de las dos apps externas
    # con el de `web-interno`.
    era_staff = not (set(roles_previos) & {"pasajero", "conductor"})
    if era_staff:
        _validar_roles_staff(roles)
    elif set(roles) - set(roles_previos):
        raise RolInvalidoError(set(roles) - set(roles_previos))

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ROL_MODIFICACION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"roles": roles_previos},
        datos_posteriores={"roles": roles},
    )
    await db.usuarios.update_one({"_id": usuario_id}, {"$set": {"roles": roles}})
    return await obtener_usuario(db, usuario_id)


async def suspender_usuario(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, motivo: str
) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    if usuario["estado"] != "ACTIVO":
        raise EstadoInvalidoError(f"Solo se puede suspender una cuenta ACTIVA (estado actual: {usuario['estado']})")

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_SUSPENSION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "ACTIVO"},
        datos_posteriores={"estado": "SUSPENDIDO", "motivo": motivo},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id}, {"$set": {"estado": "SUSPENDIDO", "motivo_suspension": motivo}}
    )
    return await obtener_usuario(db, usuario_id)


async def reactivar_usuario(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    if usuario["estado"] not in _ESTADOS_REACTIVABLES:
        raise EstadoInvalidoError(
            f"Solo una cuenta SUSPENDIDA se puede reactivar (estado actual: {usuario['estado']})"
        )

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_REACTIVACION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": "SUSPENDIDO"},
        datos_posteriores={"estado": "ACTIVO"},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id}, {"$set": {"estado": "ACTIVO", "motivo_suspension": None}}
    )
    return await obtener_usuario(db, usuario_id)


async def verificar_sin_viaje_activo(db: AsyncIOMotorDatabase, usuario_id: str) -> None:
    """Guard compartido por la baja ADMINISTRATIVA (`dar_de_baja_usuario`) y
    por el autoservicio de cierre de cuenta (`perfil/service.py`) -- una sola
    definición de "no se puede cortar el acceso con un viaje vivo", para que
    no puedan divergir.

    Se consulta como pasajero O como conductor: cualquiera de los dos lados
    de un viaje vivo deja el viaje sin actor si se le corta el acceso.
    """
    viaje_activo = await db.viajes.find_one(
        {
            "$or": [{"conductor_id": usuario_id}, {"pasajero_id": usuario_id}],
            "estado": {"$in": list(ESTADOS_VIAJE_ACTIVO)},
        }
    )
    if viaje_activo is not None:
        raise BajaConViajeActivoError(viaje_activo["_id"], viaje_activo["estado"])


async def listar_vehiculos_habilitados_de(db: AsyncIOMotorDatabase, usuario_id: str) -> list[str]:
    """Placas HABILITADAS a nombre de la cuenta. Lo usan la baja
    administrativa (para retirarlas, Decisión 2) y el autoservicio (para
    ADVERTIR al titular antes de que confirme) -- misma consulta, un solo
    lugar."""
    vehiculos = await db.vehiculos.find(
        {"propietario_id": usuario_id, "estado_habilitacion": "HABILITADO"}, {"placa": 1}
    ).to_list(length=50)
    return [v.get("placa") for v in vehiculos if v.get("placa")]


async def dar_de_baja_usuario(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, motivo: str
) -> dict:
    usuario = await obtener_usuario(db, usuario_id)
    if usuario["estado"] == "BAJA":
        raise EstadoInvalidoError("La cuenta ya está dada de baja")

    # Caso borde 1 -- viaje activo: se BLOQUEA (ver BajaConViajeActivoError).
    await verificar_sin_viaje_activo(db, usuario_id)

    # Caso borde 2 -- vehículo habilitado a su nombre (Decisión 2): se retira
    # AUTOMÁTICAMENTE de la flota. Antes solo se advertía y el vehículo
    # quedaba HABILITADO, es decir, seguía en el pool de despacho a nombre de
    # alguien que ya no puede operar.
    #
    # Reusa `mantenimiento.dar_de_baja_vehiculo` TAL CUAL -- el mismo
    # mecanismo y el mismo estado (`DADO_DE_BAJA`) que la baja manual de la
    # Decisión 3, no una segunda forma de decir "este vehículo no está
    # disponible". `origen` referencia esta baja de cuenta para que quede
    # trazable por qué el vehículo salió sin que nadie lo tocara directamente.
    vehiculos_habilitados = await db.vehiculos.find(
        {"propietario_id": usuario_id, "estado_habilitacion": "HABILITADO"}, {"placa": 1}
    ).to_list(length=50)
    placas_retiradas = [v.get("placa") for v in vehiculos_habilitados if v.get("placa")]

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_BAJA,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"estado": usuario["estado"]},
        datos_posteriores={
            "estado": "BAJA",
            "motivo": motivo,
            "vehiculos_dados_de_baja": placas_retiradas,
        },
    )
    await db.usuarios.update_one({"_id": usuario_id}, {"$set": {"estado": "BAJA", "motivo_baja": motivo}})

    # Después de la baja de la cuenta, no antes: si un vehículo no se pudiera
    # retirar (p. ej. le quedó una orden abierta), la baja del socio ya es un
    # hecho de negocio completo por sí sola y no debe revertirse. El caso se
    # registra igual en la bitácora del vehículo, no se pierde.
    for vehiculo in vehiculos_habilitados:
        try:
            await mantenimiento_service.dar_de_baja_vehiculo(
                db,
                actor_id=actor_id,
                actor_rol=actor_rol,
                vehiculo_id=vehiculo["_id"],
                motivo=f"Baja automática: su socio conductor fue dado de baja ({motivo})",
                origen=f"usuario_baja:{usuario_id}",
            )
        except DomainError:
            # Ya dado de baja, o con una orden abierta que lo retiene. No
            # bloquea la baja del socio, que ya está aplicada arriba.
            continue

    return await obtener_usuario(db, usuario_id)


async def anonimizar_usuario(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str) -> dict:
    """Módulo 8.2 (Gobernanza de datos) -- CU-O17 A2 / derechos ARCO (LOPDP):
    "los datos personales se anonimizan en las entidades de negocio, pero
    los eventos de bitácora se conservan con el identificador seudonimizado;
    la propia anonimización queda registrada como evento".

    Irreversible: no hay operación inversa, ni en este service ni expuesta
    por ningún endpoint. `actor_id` en la bitácora (pasada y futura) sigue
    siendo el mismo UUID opaco que siempre fue -- nunca fue el dato
    personal en sí, así que no hace falta (ni se debe) tocar ningún evento
    ya escrito para "seudonimizarlo" ahí. Lo que sí se seudonimiza es la
    entidad `usuarios`: de ahí en adelante, cualquier pantalla que resuelva
    este `usuario_id` a un nombre para mostrar ve el seudónimo, nunca el
    dato real (que ya no existe en ningún documento vivo del sistema).
    """
    usuario = await obtener_usuario(db, usuario_id)
    if usuario.get("anonimizado"):
        raise EstadoInvalidoError("La cuenta ya fue anonimizada")

    seudonimo = f"Usuario Anonimizado {usuario_id[:8]}"
    ahora = datetime.now(UTC)

    # A propósito, `datos_previos`/`datos_posteriores` NO llevan el
    # nombre/teléfono/correo real: `bitacora` es insert-only, y grabar el
    # dato que se está purgando en un evento permanente derrotaría el
    # propósito de la anonimización. El evento documenta que ocurrió, con
    # el seudónimo nuevo (que no es información personal) -- no el detalle
    # de qué se borró.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.USUARIO_ANONIMIZACION,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"anonimizado": False},
        datos_posteriores={"anonimizado": True, "nombre_seudonimo": seudonimo},
    )
    await db.usuarios.update_one(
        {"_id": usuario_id},
        {
            "$set": {"nombre": seudonimo, "anonimizado": True, "anonimizado_en": ahora},
            "$unset": {"telefono": "", "email": ""},
        },
    )
    # Sección 1.1 de ux_complementaria.md: las direcciones favoritas son
    # datos personales de ubicación -- se purgan junto con el resto de la
    # cuenta, no quedan huérfanas apuntando a un usuario ya anonimizado.
    await db.direcciones_favoritas.delete_many({"usuario_id": usuario_id})
    return await obtener_usuario(db, usuario_id)


async def listar_accesos(db: AsyncIOMotorDatabase, usuario_id: str, *, limit: int = 50) -> list[dict]:
    """Historial de accesos (§1.1) e intentos fallidos (§1.4) en un único
    listado -- ambos ya son eventos de la misma bitácora (CU-O17),
    distinguibles por `resultado`."""
    acciones = [AccionAuditoria.SESION_INICIO.value, AccionAuditoria.LOGIN_FALLIDO_CONSECUTIVO.value]
    cursor = (
        db.bitacora.find({"entidad_id": usuario_id, "accion": {"$in": acciones}})
        .sort("ts", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def listar_sesiones(usuario_id: str) -> list[dict]:
    return await core_sessions.listar_sesiones(usuario_id)


async def revocar_sesion(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, usuario_id: str, jti: str
) -> bool:
    # Write-ahead (CU-O17): se registra el intento antes del efecto, igual
    # que el resto del módulo -- incluso si el jti ya no existía (sesión
    # vencida sola), el intento de un admin de cerrarla es en sí mismo un
    # evento de seguridad que vale la pena dejar trazado.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.SESION_CIERRE_REMOTO,
        entidad="usuarios",
        entidad_id=usuario_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"jti": jti},
    )
    return await core_sessions.revocar_sesion(db, usuario_id, jti)


# ---------------------------------------------------------------------------
# Autoservicio de baja de cuenta -- vencimiento del periodo de gracia.
# ---------------------------------------------------------------------------

async def procesar_bajas_vencidas(db: AsyncIOMotorDatabase) -> dict:
    """Aplica la baja lógica a las cuentas cuyo periodo de gracia de 30 días
    ya venció y que no cancelaron.

    Reusa el MISMO mecanismo de baja lógica que la baja administrativa
    (`estado: BAJA`, login bloqueado por `auth`/`rbac`, historial conservado)
    -- no un estado paralelo. Y NO dispara la anonimización de CU-O17 A2:
    cerrar la cuenta y borrar los datos personales por ley son intenciones
    distintas; la segunda sigue siendo una acción aparte que un administrador
    aplica si corresponde.

    Lo llama el endpoint interno `POST /usuarios/procesar-bajas-vencidas`
    desde `dag_procesar_bajas_cuenta` (Airflow), mismo patrón ya usado por
    `dag_disparar_viajes_programados` -- no se inventa un scheduler nuevo.

    Es idempotente: filtra por `estado: ACTIVO`, así que una cuenta ya
    procesada no se vuelve a tocar en la corrida siguiente.
    """
    ahora = datetime.now(UTC)
    vencidas = await db.usuarios.find(
        {"estado": "ACTIVO", "baja_efectiva_en": {"$ne": None, "$lte": ahora}},
        {"_id": 1, "baja_solicitada_en": 1, "baja_efectiva_en": 1},
    ).to_list(length=500)

    aplicadas, omitidas = [], []
    for doc in vencidas:
        usuario_id = doc["_id"]
        try:
            # El guard de viaje activo aplica igual acá: si al vencer el plazo
            # el titular está a mitad de un viaje, no se le corta el acceso --
            # queda para la corrida siguiente, cuando el viaje haya cerrado.
            await verificar_sin_viaje_activo(db, usuario_id)
        except BajaConViajeActivoError:
            omitidas.append(usuario_id)
            continue

        # Rastro propio del autoservicio: deja claro en la bitácora que esta
        # baja NO la decidió un administrador, sino el vencimiento del plazo
        # que el propio titular puso en marcha.
        await write_audit_event(
            db,
            actor_id=usuario_id,
            rol="sistema",
            accion=AccionAuditoria.CUENTA_BAJA_EFECTIVA,
            entidad="usuarios",
            entidad_id=usuario_id,
            resultado=ResultadoAuditoria.OK,
            datos_previos={"estado": "ACTIVO"},
            datos_posteriores={
                "estado": "BAJA",
                "motivo": "Vencimiento del periodo de gracia de la baja solicitada por el titular",
                "baja_solicitada_en": str(doc.get("baja_solicitada_en")),
            },
        )
        # El efecto en sí lo aplica `dar_de_baja_usuario` TAL CUAL, no una
        # copia: así el autoservicio hereda automáticamente los dos casos
        # borde ya resueltos para la baja administrativa (bloqueo por viaje
        # activo y retiro automático del vehículo habilitado, Decisión 2) --
        # si alguno cambia, cambia en un solo lugar para ambos caminos.
        await dar_de_baja_usuario(
            db,
            actor_id=usuario_id,
            actor_rol="sistema",
            usuario_id=usuario_id,
            motivo="Baja solicitada por el titular (periodo de gracia vencido)",
        )
        aplicadas.append(usuario_id)

    return {"aplicadas": len(aplicadas), "omitidas_por_viaje_activo": len(omitidas), "revisadas": len(vencidas)}
