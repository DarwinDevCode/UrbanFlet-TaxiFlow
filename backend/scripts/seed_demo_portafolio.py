"""Siembra completa de demostración, desde una base VACÍA, para levantar
UrbanFleet con un solo `docker compose up` (servicio `seed` de
docker-compose.yml).

A diferencia de los `seed_*_demo.py` históricos (que asumían un pool de
usuarios creado a mano en sesiones anteriores), este script crea TODO lo
necesario: configuración base (tarifas, comisión, zonas, catálogos),
cuentas de personal (mismas credenciales documentadas en CLAUDE.md §8.7 y
en el README), pasajeros, postulaciones de conductores (las aprobadas
generan vehículo + documentos vía la transacción real de aprobación),
carreras de los últimos 3 meses pasando por el flujo real completo
(solicitar -> despacho -> aceptar -> en camino -> llegada -> iniciar ->
traza GPS -> finalizar -> cobro -> calificación), liquidaciones semanales,
órdenes de mantenimiento, referidos y notificaciones in-app.

Todos los datos son FICTICIOS (nombres, teléfonos, cédulas y placas
generados), ambientados en Quevedo, Los Ríos (Ecuador).

Fechas históricas: igual que `seed_liquidaciones_demo.py`, se congela el
reloj que ven los módulos de negocio (`datetime.now(UTC)`) en cada paso,
así cada documento queda con marcas de tiempo coherentes del pasado sin
tocar ninguna regla de negocio.

Idempotente: al terminar escribe `_meta_seed/{_id: "demo-portafolio"}`; si
ese documento existe, el script no hace nada. Para resembrar desde cero:
`docker compose down -v && docker compose up --build`.

Uso: python -m scripts.seed_demo_portafolio
"""

from __future__ import annotations

import asyncio
import io
import math
import random
import struct
import time
import uuid
import zlib
from datetime import UTC, date, datetime, timedelta

from fastapi import UploadFile
from starlette.datastructures import Headers

from src.archivos import service as archivos_service
from src.captacion import schemas as captacion_schemas
from src.captacion import service as captacion_service
from src.auth import service as auth_service
from src.catalogos import service as catalogos_service
from src.core import audit as core_audit
from src.core.db_mongo import ensure_indexes, get_database
from src.core.db_redis import get_redis
from src.core.notifications import NoopNotificationDispatcher
from src.core.security import hash_password
from src.mantenimiento import schemas as mant_schemas
from src.mantenimiento import service as mant_service
from src.notificaciones import service as notif_service
from src.parametros import service as parametros_service
from src.recaudacion import service as recaudacion_service
from src.recaudacion.service import _periodo_cerrado_mas_reciente
from src.reportes_falla import service as fallas_service
from src.viajes import schemas as viaje_schemas
from src.viajes import service as viajes_service
from src.viajes import service_dispatch, service_ejecucion, service_finalizacion

MARCA_SEED = "demo-portafolio"
random.seed(20261123)

QUEVEDO = (-1.0225, -79.4636)
DIAS_HISTORIA = 90
VIAJES_OBJETIVO = 2300

# ---------------------------------------------------------------------------
# Reloj controlado (mismo mecanismo que seed_liquidaciones_demo.py)
# ---------------------------------------------------------------------------

_MODULOS_CON_RELOJ = [
    viajes_service,
    service_dispatch,
    service_ejecucion,
    service_finalizacion,
    recaudacion_service,
    core_audit,
    captacion_service,
    mant_service,
    auth_service,
    notif_service,
    archivos_service,
    fallas_service,
]


class _Reloj(datetime):
    ahora: datetime = datetime.now(UTC)

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls.ahora.astimezone(tz) if tz is not None else cls.ahora


class reloj:
    """`with reloj(): ...` parchea el reloj; `reloj.fijar(instante)` lo mueve."""

    _originales: dict = {}  # noqa: RUF012 -- estado compartido a propósito entre usos del context manager

    @staticmethod
    def fijar(instante: datetime) -> None:
        _Reloj.ahora = instante

    def __enter__(self):
        for modulo in _MODULOS_CON_RELOJ:
            self._originales[modulo] = modulo.datetime
            modulo.datetime = _Reloj
        return self

    def __exit__(self, *exc):
        for modulo, original in self._originales.items():
            modulo.datetime = original


# ---------------------------------------------------------------------------
# Datos ficticios ambientados en Quevedo
# ---------------------------------------------------------------------------

NOMBRES_H = [
    "Carlos",
    "Luis",
    "Jorge",
    "Andrés",
    "Miguel",
    "José",
    "Fernando",
    "Ricardo",
    "Diego",
    "Javier",
    "Byron",
    "Washington",
    "Geovanny",
    "Kléber",
    "Patricio",
    "Wilson",
    "Darío",
    "Marco",
    "Édison",
    "Holger",
]
NOMBRES_M = [
    "María",
    "Ana",
    "Gabriela",
    "Daniela",
    "Verónica",
    "Lorena",
    "Andrea",
    "Paola",
    "Karla",
    "Jessica",
    "Mónica",
    "Silvia",
    "Fernanda",
    "Diana",
    "Katherine",
    "Johanna",
    "Patricia",
    "Estefanía",
    "Mayra",
    "Lucía",
]
APELLIDOS = [
    "Mora",
    "Cedeño",
    "Zambrano",
    "Bajaña",
    "Vera",
    "Macías",
    "Alvarado",
    "Villamar",
    "Chávez",
    "Mendoza",
    "Bravo",
    "León",
    "Torres",
    "Muñoz",
    "Ponce",
    "Rivas",
    "Montoya",
    "Briones",
    "Moreira",
    "Intriago",
    "Loor",
    "Pincay",
    "Saltos",
    "Franco",
    "Aguirre",
    "Yépez",
    "Castro",
    "Salazar",
    "Palma",
    "Carranza",
]

LUGARES = [
    ("Terminal Terrestre de Quevedo", -1.0153, -79.4706),
    ("Malecón de Quevedo", -1.0262, -79.4672),
    ("Parque Central 7 de Octubre", -1.0228, -79.4637),
    ("Hospital IESS Quevedo", -1.0371, -79.4595),
    ("Universidad Técnica Estatal de Quevedo", -1.0127, -79.4691),
    ("Paseo Shopping Quevedo", -1.0441, -79.4718),
    ("Mercado Municipal", -1.0241, -79.4622),
    ("Av. Walter Andrade y 7 de Octubre", -1.0302, -79.4568),
    ("Cdla. San José", -1.0083, -79.4602),
    ("Barrio 24 de Mayo", -1.0352, -79.4688),
    ("Av. June Guzmán de Cortez", -1.0195, -79.4551),
    ("Coliseo Municipal", -1.0279, -79.4610),
    ("Cdla. El Desquite", -1.0496, -79.4643),
    ("San Camilo", -1.0331, -79.4774),
    ("Venus del Río Quevedo", -1.0412, -79.4512),
    ("Cdla. Viva Alfaro", -1.0064, -79.4524),
    ("Cdla. La Esperanza", -1.0532, -79.4585),
    ("Av. Bolívar y Calle Novena", -1.0236, -79.4659),
    ("Gasolinera Primax Av. Quito", -1.0170, -79.4583),
    ("Clínica Santa Marianita", -1.0258, -79.4594),
]

MARCAS_MODELOS = [
    ("Hyundai", "Accent"),
    ("Kia", "Rio"),
    ("Chevrolet", "Aveo"),
    ("Chevrolet", "Sail"),
    ("Nissan", "Sentra"),
    ("Toyota", "Yaris"),
    ("Kia", "Soluto"),
    ("Hyundai", "Elantra"),
]
COLORES = ["Amarillo", "Amarillo", "Amarillo", "Blanco"]  # taxis amarillos, como en Ecuador

COMENTARIOS_PASAJERO = [
    "Muy amable y puntual.",
    "Conduce con cuidado, recomendado.",
    "Auto limpio y cómodo.",
    "Llegó rápido.",
    "Excelente servicio.",
    None,
    None,
    None,
]
COMENTARIOS_CONDUCTOR = ["Pasajero puntual.", "Muy respetuoso.", None, None, None, None]


def _nombre(mujer: bool) -> str:
    nombre = random.choice(NOMBRES_M if mujer else NOMBRES_H)
    return f"{nombre} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"


def _telefono(usados: set[str]) -> str:
    while True:
        tel = f"+5939{random.randint(60000000, 99999999)}"
        if tel not in usados:
            usados.add(tel)
            return tel


def _placa(usadas: set[str]) -> str:
    # Formato ecuatoriano: letra de provincia + 2 letras + 4 dígitos.
    # R = Los Ríos (Quevedo); algunas de Guayas (G) y Pichincha (P).
    while True:
        provincia = random.choices(["R", "G", "P"], weights=[7, 2, 1])[0]
        letras = "ABCDEGHKLMNOPSTUVWXY"
        placa = f"{provincia}{random.choice(letras)}{random.choice(letras)}-{random.randint(1000, 9999)}"
        if placa not in usadas:
            usadas.add(placa)
            return placa


def _cedula() -> str:
    return f"12{random.randint(10000000, 99999999)}"  # 12 = código de Los Ríos


def _png_documento(color_cabecera: tuple[int, int, int], semilla: int) -> bytes:
    """PNG mínimo (320x200) que imita una credencial: franja de color arriba,
    cuerpo claro con "líneas de texto" grises y un recuadro de foto. Se arma
    a mano con zlib porque la imagen del backend no trae Pillow; el servicio
    de archivos solo acepta jpeg/png/webp."""
    ancho, alto = 320, 200
    rnd = random.Random(semilla)
    largos = [rnd.randint(90, 190) for _ in range(5)]
    filas = bytearray()
    for y in range(alto):
        filas.append(0)  # filtro "None" por fila
        for x in range(ancho):
            if y < 42:
                px = color_cabecera
            elif 70 <= y < 160 and 18 <= x < 96:
                px = (196, 204, 210)  # recuadro de foto
            elif x >= 116 and any(70 + i * 18 <= y < 78 + i * 18 and x < 116 + largos[i] for i in range(5)):
                px = (150, 156, 162)  # renglones
            else:
                px = (246, 247, 244)
            filas += bytes(px)

    def _chunk(tipo: bytes, datos: bytes) -> bytes:
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", cabecera)
        + _chunk(b"IDAT", zlib.compress(bytes(filas), 9))
        + _chunk(b"IEND", b"")
    )


def _upload_png(contenido: bytes, nombre: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(contenido), size=len(contenido), filename=nombre, headers=Headers({"content-type": "image/png"})
    )


def _cerca(lat: float, lon: float, metros: float) -> tuple[float, float]:
    ang = random.uniform(0, 2 * math.pi)
    d = random.uniform(0, metros) / 111_000
    return lat + d * math.sin(ang), lon + d * math.cos(ang)


def _instante_aleatorio(dia: date) -> datetime:
    # Distribución horaria realista en hora local (UTC-5): picos de mañana y tarde.
    hora_local = random.choices(
        range(24), weights=[1, 1, 1, 1, 1, 2, 5, 9, 8, 6, 5, 6, 8, 7, 6, 6, 7, 9, 10, 9, 7, 5, 3, 2]
    )[0]
    local = datetime(dia.year, dia.month, dia.day, hora_local, random.randint(0, 59), random.randint(0, 59))
    return (local + timedelta(hours=5)).replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Configuración base
# ---------------------------------------------------------------------------

STAFF = [
    # (_id, nombre, telefono, email, password, roles) -- credenciales de CLAUDE.md §8.7
    (
        "staff-verificacion",
        "Carolina Mendoza Vera",
        "+593900000001",
        "carolina.mendoza@urbanfleet.example",
        "VerifDash123!",
        [
            "admin_captacion",
            "jefe_mantenimiento",
            "supervisor_cumplimiento",
            "coordinador_flota",
            "coordinador_operaciones",
            "admin_financiero",
            "responsable_plataforma",
        ],
    ),
    (
        "gerencia-demo-01",
        "Roberto Alvarado Ponce",
        "+593900000010",
        "gerencia@urbanfleet.example",
        "Gerencia123!",
        ["gerencia"],
    ),
    (
        "admin-plataforma-qa",
        "Luis Bajaña Torres",
        "+593911998822",
        "plataforma@urbanfleet.example",
        "AdminPlataforma123!",
        ["admin_plataforma"],
    ),
    (
        "integracion-externa-demo-01",
        "Integración Contable (API)",
        "+593900000011",
        None,
        "Integracion123!",
        ["integracion_externa"],
    ),
    (
        "admin-sistema-qa",
        "Diana Zambrano Ríos",
        "+593900000099",
        "sistemas@urbanfleet.example",
        "AdminSistema123!",
        ["admin_sistema"],
    ),
]
ACTOR = "staff-verificacion"


async def _configuracion_base(db) -> None:
    hace_un_anio = datetime.now(UTC) - timedelta(days=365)
    for franja, arr, km, esp, minima in [("DIURNA", 0.60, 0.55, 0.08, 1.50), ("NOCTURNA", 0.75, 0.62, 0.09, 1.75)]:
        await parametros_service.crear_parametro_tarifa(
            db,
            actor_id=ACTOR,
            rol="admin_financiero",
            franja=franja,
            arrancada=arr,
            costo_km=km,
            costo_min_espera=esp,
            carrera_minima=minima,
            vigente_desde=hace_un_anio,
        )
    await parametros_service.crear_parametro_comision(
        db, actor_id=ACTOR, rol="admin_financiero", porcentaje=0.20, vigente_desde=hace_un_anio
    )

    for nombre, desc, aplica in [
        ("LICENCIA_CONDUCIR", "Licencia profesional tipo C o superior", "conductor"),
        ("MATRICULA_VEHICULAR", "Matrícula vigente emitida por la ANT", "vehiculo"),
        ("SOAT", "Seguro obligatorio de accidentes de tránsito", "vehiculo"),
        ("PERMISO_OPERACION", "Permiso de operación de la cooperativa", "vehiculo"),
    ]:
        await catalogos_service.crear_tipo_documento(
            db, actor_id=ACTOR, rol="admin_sistema", nombre=nombre, descripcion=desc, aplica_a=aplica, activo=True
        )
    for nombre, cat in [
        ("Pasajero cambió de planes", "cancelacion"),
        ("Tiempo de espera excesivo", "cancelacion"),
        ("Dirección incorrecta", "cancelacion"),
        ("Vehículo averiado", "incidencia"),
        ("Accidente leve", "incidencia"),
        ("Discusión con el pasajero", "incidencia"),
    ]:
        await catalogos_service.crear_motivo(
            db, actor_id=ACTOR, rol="admin_sistema", nombre=nombre, descripcion=nombre, categoria=cat, activo=True
        )
    for nombre, direccion, tel in [
        ("Taller Mecánico Los Ríos", "Av. Walter Andrade km 1", "052750111"),
        ("Lubricadora El Cóndor", "Av. 7 de Octubre y Calle 12", "052750222"),
        ("Autoservicio Quevedo", "Vía a Valencia km 2", "052750333"),
        ("Frenos y Embragues Moreira", "Calle Bolívar 418", "052750444"),
        ("Electroauto San Camilo", "Cdla. San Camilo, Mz. 4", "052750555"),
    ]:
        await catalogos_service.crear_taller(
            db,
            actor_id=ACTOR,
            rol="admin_sistema",
            nombre=nombre,
            direccion=direccion,
            telefono=tel,
            url_maps=f"https://www.google.com/maps/search/?api=1&query={nombre.replace(' ', '+')}+Quevedo",
            activo=True,
        )
    for marca in sorted({m for m, _ in MARCAS_MODELOS} | {"Renault", "Suzuki"}):
        await catalogos_service.crear_marca_vehiculo(db, actor_id=ACTOR, rol="admin_sistema", nombre=marca, activo=True)
    for color in ["Amarillo", "Blanco", "Plateado", "Negro", "Rojo"]:
        await catalogos_service.crear_color_vehiculo(db, actor_id=ACTOR, rol="admin_sistema", nombre=color, activo=True)
    for nombre, categoria, precio, unidad in [
        ("Aceite 10W-30 (galón)", "Motor", 28.0, "unidad"),
        ("Filtro de aceite", "Motor", 6.5, "unidad"),
        ("Filtro de aire", "Motor", 12.0, "unidad"),
        ("Bujías", "Motor", 4.5, "unidad"),
        ("Pastillas de freno delanteras", "Frenos", 32.0, "juego"),
        ("Líquido de frenos DOT4", "Frenos", 9.0, "litro"),
        ("Batería 12V 45Ah", "Eléctrico", 85.0, "unidad"),
        ("Carbones de alternador", "Eléctrico", 15.0, "juego"),
        ("Amortiguador delantero", "Suspensión", 48.0, "unidad"),
        ("Bujes de mesa", "Suspensión", 7.5, "unidad"),
        ("Neumático 185/65 R15", "Neumáticos", 62.0, "unidad"),
        ("Kit de embrague", "Otro", 145.0, "juego"),
    ]:
        await catalogos_service.crear_repuesto(
            db,
            actor_id=ACTOR,
            rol="admin_sistema",
            nombre=nombre,
            categoria=categoria,
            precio_referencial=precio,
            unidad=unidad,
            activo=True,
        )


async def _crear_staff(db) -> None:
    ahora = datetime.now(UTC)
    for _id, nombre, tel, email, password, roles in STAFF:
        doc = {
            "_id": _id,
            "nombre": nombre,
            "telefono": tel,
            "hash_password": hash_password(password),
            "roles": roles,
            "estado": "ACTIVO",
            "fecha_registro": ahora - timedelta(days=200),
            "forzar_cambio_password": False,
            "password_actualizada_en": ahora,
            "canal": "web",
        }
        if email:
            doc["email"] = email
        await db.usuarios.update_one({"_id": _id}, {"$setOnInsert": doc}, upsert=True)


# ---------------------------------------------------------------------------
# Pasajeros y conductores
# ---------------------------------------------------------------------------


async def _crear_pasajeros(db, telefonos: set[str]) -> list[str]:
    ids: list[str] = []
    hoy = datetime.now(UTC)
    canales = ["app", "app", "web", "referido", "campana"]
    # Cuenta demo documentada (CLAUDE.md §8.7)
    cuentas = [("María José Cedeño Vera", "+593987001122", "DemoPasajero123!", "app", 150)]
    telefonos.add("+593987001122")
    for i in range(44):
        cuentas.append(
            (
                _nombre(i % 2 == 0),
                _telefono(telefonos),
                "Pasajero2026!",
                random.choice(canales),
                random.randint(0, DIAS_HISTORIA + 30),
            )
        )
    for nombre, tel, password, canal, dias in cuentas:
        reloj.fijar(hoy - timedelta(days=dias, hours=random.randint(0, 23)))
        res = await captacion_service.registrar_pasajero(
            db, nombre=nombre, telefono=tel, email=None, password=password, version_consentimiento="v1", canal=canal
        )
        ids.append(res["usuario_id"])
    return ids


async def _documentos(
    db, usuario_id: str, cedula: str, dia_emision: date, estado_doc: str
) -> list[captacion_schemas.DocumentoInput]:
    """Sube 2 imágenes reales (licencia y matrícula) como el propio postulante,
    contexto `documento_postulacion` -- mismo camino que la UI de web-conductor
    (POST /archivos y luego adjuntar a la solicitud en borrador)."""
    hoy = date.today()
    if estado_doc == "vigente":
        venc = hoy + timedelta(days=random.randint(90, 700))
    elif estado_doc == "por_vencer":
        venc = hoy + timedelta(days=random.randint(3, 28))
    else:
        venc = hoy - timedelta(days=random.randint(5, 120))
    semilla = int(cedula)
    licencia = await archivos_service.guardar_archivo(
        db,
        actor_id=usuario_id,
        contexto="documento_postulacion",
        upload=_upload_png(_png_documento((31, 95, 168), semilla), f"licencia-{cedula}.png"),
    )
    matricula = await archivos_service.guardar_archivo(
        db,
        actor_id=usuario_id,
        contexto="documento_postulacion",
        upload=_upload_png(_png_documento((242, 164, 19), semilla + 1), f"matricula-{cedula}.png"),
    )
    return [
        captacion_schemas.DocumentoInput(
            tipo="LICENCIA_CONDUCIR",
            propietario_tipo="CONDUCTOR",
            archivo_id=licencia["_id"],
            fecha_emision=dia_emision,
            fecha_vencimiento=venc,
        ),
        captacion_schemas.DocumentoInput(
            tipo="MATRICULA_VEHICULAR",
            propietario_tipo="VEHICULO",
            archivo_id=matricula["_id"],
            fecha_emision=dia_emision,
            fecha_vencimiento=hoy + timedelta(days=random.randint(30, 360)) if estado_doc != "vencido" else venc,
        ),
    ]


async def _crear_conductores(db, telefonos: set[str], placas: set[str]) -> None:
    dispatcher = NoopNotificationDispatcher()
    hoy = datetime.now(UTC)
    estados = ["APROBADA"] * 29 + ["ENVIADA"] * 5 + ["EN_VERIFICACION"] * 3 + ["OBSERVADA"] * 3 + ["RECHAZADA"] * 2
    random.shuffle(estados)
    # Conductor demo documentado (CLAUDE.md §8.7) -- siempre aprobado, docs vigentes.
    filas = [("Juan Carlos Pérez Mora", "+593911223344", "DemoConductor123!", "PBA-1234", "APROBADA", 160, "vigente")]
    telefonos.add("+593911223344")
    placas.add("PBA-1234")
    for estado in estados:
        dias = random.randint(5, 150) if estado == "APROBADA" else random.randint(0, 25)
        filas.append(
            (
                _nombre(random.random() < 0.15),
                _telefono(telefonos),
                "Conductor2026!",
                _placa(placas),
                estado,
                dias,
                random.choices(["vigente", "por_vencer", "vencido"], weights=[6, 2, 2])[0],
            )
        )

    for nombre, tel, password, placa, estado, dias, estado_doc in filas:
        cedula = _cedula()
        marca, modelo = random.choice(MARCAS_MODELOS)
        anio = random.randint(2014, 2023)
        envio = hoy - timedelta(days=dias, hours=random.randint(0, 12))
        reloj.fijar(envio)
        sol = await captacion_service.crear_solicitud(
            db,
            dispatcher,
            nombre=nombre,
            telefono=tel,
            email=None,
            password=password,
            cedula=cedula,
            licencia_numero=f"LC-{random.randint(100000, 999999)}",
            vehiculo=captacion_schemas.VehiculoInput(
                placa=placa, marca=marca, modelo=modelo, anio=anio, color=random.choice(COLORES), capacidad=4
            ),
            documentos=[],
            enviar=False,
            canal=random.choice(["app", "web", "web", "referido", "campana"]),
        )
        documentos = await _documentos(
            db, sol["usuario_id"], cedula, (envio - timedelta(days=random.randint(200, 900))).date(), estado_doc
        )
        sol = await captacion_service.enviar_solicitud_con_documentos(
            db, dispatcher, actor_id=sol["usuario_id"], documentos=documentos
        )
        if estado == "ENVIADA":
            continue
        reloj.fijar(envio + timedelta(hours=random.randint(2, 30)))
        await captacion_service.tomar_solicitud(
            db, solicitud_id=sol["_id"], verificador_id=ACTOR, verificador_rol="admin_captacion"
        )
        if estado == "EN_VERIFICACION":
            continue
        reloj.fijar(envio + timedelta(days=random.randint(1, 4), hours=random.randint(0, 8)))
        motivo = {
            "OBSERVADA": "La foto de la matrícula está borrosa; por favor vuelva a cargarla.",
            "RECHAZADA": "El vehículo supera la antigüedad máxima permitida por la cooperativa.",
        }.get(estado)
        await captacion_service.decidir_solicitud(
            db,
            dispatcher,
            solicitud_id=sol["_id"],
            verificador_id=ACTOR,
            verificador_rol="admin_captacion",
            decision=estado,
            motivo=motivo,
        )

    # Calificación inicial razonable para que el despacho y los listados no
    # muestren "sin calificación" en todos los socios.
    await db.usuarios.update_many(
        {"roles": "conductor", "conductor.calificacion_promedio": None},
        {"$set": {"conductor.calificacion_promedio": 4.7}},
    )


# ---------------------------------------------------------------------------
# Carreras (flujo real completo)
# ---------------------------------------------------------------------------


async def _cargar_pares(db) -> list[tuple[str, str]]:
    pares = []
    async for u in db.usuarios.find({"roles": "conductor"}):
        veh = await db.vehiculos.find_one({"propietario_id": u["_id"], "estado_habilitacion": "HABILITADO"})
        if veh is not None:
            pares.append((u["_id"], veh["_id"]))
    return pares


async def _set_servicio(db, conductor_id: str, estado: str) -> None:
    await db.usuarios.update_one({"_id": conductor_id}, {"$set": {"conductor.estado_servicio": estado}})


async def _un_viaje(
    db, redis, t0: datetime, pasajero_id: str, par: tuple[str, str], resultado: str, stats: dict
) -> None:
    conductor_id, vehiculo_id = par
    origen = random.choice(LUGARES)
    destino = random.choice([lg for lg in LUGARES if lg[0] != origen[0]])
    o_lat, o_lon = _cerca(origen[1], origen[2], 150)
    d_lat, d_lon = _cerca(destino[1], destino[2], 150)
    body = viaje_schemas.SolicitarViajeRequest(
        origen_lat=o_lat,
        origen_lon=o_lon,
        origen_direccion=origen[0],
        destino_lat=d_lat,
        destino_lon=d_lon,
        destino_direccion=destino[0],
    )

    if resultado == "SIN_CONDUCTOR":
        reloj.fijar(t0)
        await viajes_service.solicitar_viaje(
            db, pasajero_id=pasajero_id, body=body
        )  # nadie DISPONIBLE -> SIN_CONDUCTOR
        stats["SIN_CONDUCTOR"] += 1
        return

    # Vehículo a 200-900 m del origen, posición "fresca" según el reloj congelado.
    v_lat, v_lon = _cerca(o_lat, o_lon, 250)
    await redis.hset(
        f"pos:{vehiculo_id}",
        mapping={
            "lat": v_lat,
            "lon": v_lon,
            "ts_servidor": t0.isoformat(),
            "estado_servicio": "DISPONIBLE",
        },
    )
    await _set_servicio(db, conductor_id, "DISPONIBLE")
    try:
        reloj.fijar(t0)
        viaje = await viajes_service.solicitar_viaje(db, pasajero_id=pasajero_id, body=body)
        if viaje["estado"] != "OFERTADO" or viaje.get("conductor_ofertado_id") != conductor_id:
            stats["fallidos"] += 1
            return

        t = t0 + timedelta(seconds=random.randint(4, 13))  # dentro de la ventana de la oferta
        if resultado == "CANCELADO":
            reloj.fijar(t)
            await viajes_service.cancelar_viaje_pasajero(
                db,
                pasajero_id=pasajero_id,
                motivo=random.choice(
                    ["Pasajero cambió de planes", "Tiempo de espera excesivo", "Dirección incorrecta"]
                ),
            )
            stats["CANCELADO"] += 1
            return

        reloj.fijar(t)
        await service_dispatch.responder_oferta(db, conductor_id=conductor_id, aceptar=True)
        t += timedelta(seconds=random.randint(5, 30))
        reloj.fijar(t)
        await service_ejecucion.marcar_en_camino(db, conductor_id=conductor_id)
        t += timedelta(minutes=random.randint(2, 7))
        reloj.fijar(t)
        # El taxi llegó al punto de recogida (iniciar_viaje exige <= 150 m del origen).
        llegada_lat, llegada_lon = _cerca(o_lat, o_lon, 40)
        await redis.hset(
            f"pos:{vehiculo_id}",
            mapping={
                "lat": llegada_lat,
                "lon": llegada_lon,
                "ts_servidor": t.isoformat(),
                "estado_servicio": "OCUPADO",
            },
        )
        await service_ejecucion.marcar_llegada(db, conductor_id=conductor_id)
        t += timedelta(seconds=random.randint(30, 180))
        reloj.fijar(t)
        await service_ejecucion.iniciar_viaje(db, conductor_id=conductor_id)

        # Traza GPS: puntos intermedios con algo de desvío (la ruta real no es recta)
        # y alguna parada corta (semáforo/tráfico) que suma minutos de espera.
        pasos = random.randint(6, 10)
        for k in range(pasos + 1):
            f = k / pasos
            lat = o_lat + (d_lat - o_lat) * f + (random.uniform(-0.0015, 0.0015) if 0 < k < pasos else 0)
            lon = o_lon + (d_lon - o_lon) * f + (random.uniform(-0.0015, 0.0015) if 0 < k < pasos else 0)
            if k:
                t += timedelta(seconds=random.randint(45, 110))
            velocidad = random.uniform(3, 8) if random.random() < 0.15 else random.uniform(18, 45)
            await service_ejecucion.registrar_punto_traza(
                db, conductor_id=conductor_id, lat=lat, lon=lon, velocidad=velocidad, ts_servidor=t
            )
        t += timedelta(seconds=20)
        reloj.fijar(t)
        final = await service_finalizacion.finalizar_viaje(db, conductor_id=conductor_id)

        t += timedelta(seconds=random.randint(20, 90))
        reloj.fijar(t)
        monto = final["tarifa_final"]
        if random.random() < 0.04:  # discrepancia de cobro (CU-O09 A3)
            monto = round(monto + random.choice([-1.0, -0.5, 0.5, 1.0]), 2)
            stats["discrepancias"] += 1
        await recaudacion_service.registrar_pago_efectivo(
            db, conductor_id=conductor_id, viaje_id=final["_id"], monto_cobrado=max(monto, 0.5)
        )

        t += timedelta(minutes=random.randint(1, 30))
        reloj.fijar(t)
        if random.random() < 0.85:
            await service_finalizacion.calificar_viaje(
                db,
                viaje_id=final["_id"],
                actor_id=pasajero_id,
                rol="pasajero",
                puntaje=random.choices([5, 4, 3, 2], weights=[70, 22, 6, 2])[0],
                comentario=random.choice(COMENTARIOS_PASAJERO),
            )
        if random.random() < 0.7:
            await service_finalizacion.calificar_viaje(
                db,
                viaje_id=final["_id"],
                actor_id=conductor_id,
                rol="conductor",
                puntaje=random.choices([5, 4, 3], weights=[80, 17, 3])[0],
                comentario=random.choice(COMENTARIOS_CONDUCTOR),
            )
        stats["PAGADO"] += 1
    finally:
        await _set_servicio(db, conductor_id, "FUERA_DE_LINEA")


async def _crear_viajes(db, redis, pasajeros: list[str]) -> dict:
    pares = await _cargar_pares(db)
    stats = {"PAGADO": 0, "CANCELADO": 0, "SIN_CONDUCTOR": 0, "fallidos": 0, "discrepancias": 0}
    await db.usuarios.update_many({"roles": "conductor"}, {"$set": {"conductor.estado_servicio": "FUERA_DE_LINEA"}})

    hoy = date.today()
    instantes: list[datetime] = []
    for d in range(DIAS_HISTORIA, 0, -1):
        dia = hoy - timedelta(days=d)
        # Crecimiento suave de la demanda + más carreras viernes/sábado.
        base = 16 + (DIAS_HISTORIA - d) / DIAS_HISTORIA * 8 + (6 if dia.weekday() in (4, 5) else 0)
        instantes += [_instante_aleatorio(dia) for _ in range(max(1, int(random.gauss(base, 3))))]
    instantes.sort()
    # Conductores "estrella" con más carreras, para que rankings y listados se vean naturales.
    pesos_pares = [random.uniform(0.4, 2.5) for _ in pares]
    # El conductor demo (+593911223344) entre los que más trabajan, para que
    # su historial y sus liquidaciones se vean llenos en la demo.
    juan = await db.usuarios.find_one({"telefono": "+593911223344"}, {"_id": 1})
    pesos_pares = [3.5 if p[0] == juan["_id"] else w for p, w in zip(pares, pesos_pares, strict=True)]

    for t0 in instantes[:VIAJES_OBJETIVO]:
        resultado = random.choices(["PAGADO", "CANCELADO", "SIN_CONDUCTOR"], weights=[88, 7, 5])[0]
        await _un_viaje(
            db, redis, t0, random.choice(pasajeros), random.choices(pares, weights=pesos_pares)[0], resultado, stats
        )
    return stats


async def _crear_liquidaciones(db) -> dict:
    hoy = datetime.now(UTC)
    resumen = {"generadas": 0, "APROBADA": 0, "PAGADA": 0, "OBSERVADA": 0}
    semanas = DIAS_HISTORIA // 7
    for s in range(semanas, -1, -1):
        _, fin = _periodo_cerrado_mas_reciente(hoy - timedelta(weeks=s))
        reloj.fijar(fin + timedelta(hours=14))
        resultado = await recaudacion_service.generar_liquidaciones(db, autorizador_id=ACTOR)
        generadas = resultado["generadas"]
        resumen["generadas"] += len(generadas)
        # Periodos viejos casi todos pagados; los recientes quedan en revisión.
        for liq in generadas:
            r = random.random()
            reloj.fijar(fin + timedelta(days=1, hours=random.randint(0, 20)))
            if (s >= 3 and r < 0.85) or (s in (1, 2) and r < 0.45):
                await recaudacion_service.aprobar_liquidacion(db, liquidacion_id=liq["_id"], aprobador_id=ACTOR)
                reloj.fijar(fin + timedelta(days=2, hours=random.randint(0, 20)))
                await recaudacion_service.pagar_liquidacion(db, liquidacion_id=liq["_id"], autorizador_id=ACTOR)
                resumen["PAGADA"] += 1
            elif s in (1, 2) and r < 0.75:
                await recaudacion_service.aprobar_liquidacion(db, liquidacion_id=liq["_id"], aprobador_id=ACTOR)
                resumen["APROBADA"] += 1
            elif r > 0.93:
                await recaudacion_service.observar_liquidacion(
                    db,
                    liquidacion_id=liq["_id"],
                    conductor_id=liq["conductor_id"],
                    motivo="El número de carreras no coincide con mi registro personal.",
                )
                resumen["OBSERVADA"] += 1
    return resumen


# ---------------------------------------------------------------------------
# Mantenimiento, referidos, estado en vivo, notificaciones
# ---------------------------------------------------------------------------

TRABAJOS = {
    "PREVENTIVA": [
        ("Cambio de aceite y filtros (5.000 km)", [("Aceite 10W-30 (galón)", 1, 28.0), ("Filtro de aceite", 1, 6.5)]),
        ("Alineación, balanceo y rotación de llantas", [("Contrapesos", 8, 0.5)]),
        ("Revisión de frenos programada", [("Pastillas de freno delanteras", 1, 32.0)]),
        ("Mantenimiento de 20.000 km", [("Bujías", 4, 4.5), ("Filtro de aire", 1, 12.0)]),
    ],
    "CORRECTIVA": [
        ("Cambio de amortiguadores delanteros", [("Amortiguador delantero", 2, 48.0)]),
        ("Falla en el sistema de aire acondicionado", [("Recarga de gas R134a", 1, 35.0)]),
        ("Reparación de alternador", [("Carbones de alternador", 1, 15.0)]),
        ("Cambio de embrague", [("Kit de embrague", 1, 145.0)]),
        ("Ruido en suspensión, cambio de bujes", [("Bujes de mesa", 4, 7.5)]),
    ],
}


async def _crear_ordenes(db) -> dict:
    dispatcher = NoopNotificationDispatcher()
    talleres = [t["nombre"] async for t in db.talleres.find({}, {"nombre": 1})]
    vehiculos = [v async for v in db.vehiculos.find({"estado_habilitacion": "HABILITADO"})]
    juan = await db.usuarios.find_one({"telefono": "+593911223344"})
    vehiculos = [v for v in vehiculos if v["propietario_id"] != juan["_id"]]  # el conductor demo queda libre
    hoy = datetime.now(UTC)
    estados = ["CERRADA"] * 20 + ["ABIERTA"] * 9 + ["EN_TALLER"] * 6 + ["ANULADA"] * 4
    conteo = {e: 0 for e in set(estados)}
    retirados: set[str] = set()
    for estado in estados:
        tipo = "PREVENTIVA" if random.random() < 0.7 else "CORRECTIVA"
        descripcion, repuestos = random.choice(TRABAJOS[tipo])
        disponibles = [v for v in vehiculos if v["_id"] not in retirados] if estado == "EN_TALLER" else vehiculos
        vehiculo = random.choice(disponibles)
        dias_atras = random.randint(5, DIAS_HISTORIA - 5) if estado == "CERRADA" else random.randint(0, 12)
        creada = hoy - timedelta(days=dias_atras, hours=random.randint(0, 10))
        programada = (creada + timedelta(days=random.randint(1, 6))).date()
        km = random.randint(45_000, 210_000)
        reloj.fijar(creada)
        orden = await mant_service.crear_orden(
            db,
            dispatcher,
            actor_id=ACTOR,
            actor_rol="jefe_mantenimiento",
            vehiculo_id=vehiculo["_id"],
            tipo=tipo,
            descripcion=descripcion,
            km_entrada=km,
            taller=random.choice(talleres),
            fecha_programada=programada,
            retirar_vehiculo=estado == "EN_TALLER" or (estado == "CERRADA" and tipo == "CORRECTIVA"),
            repuestos_estimados=[
                mant_schemas.RepuestoInput(descripcion=d, cantidad=c, costo_unitario=p) for d, c, p in repuestos
            ],
        )
        conteo[estado] += 1
        if estado == "ABIERTA":
            continue
        if estado == "ANULADA":
            reloj.fijar(creada + timedelta(hours=5))
            await mant_service.anular_orden(
                db,
                actor_id=ACTOR,
                actor_rol="jefe_mantenimiento",
                orden_id=orden["_id"],
                motivo="El socio resolvió el problema en su taller particular.",
            )
            continue
        reloj.fijar(creada + timedelta(hours=random.randint(6, 30)))
        await mant_service.marcar_en_taller(db, actor_id=ACTOR, actor_rol="jefe_mantenimiento", orden_id=orden["_id"])
        if estado == "EN_TALLER":
            retirados.add(vehiculo["_id"])
            continue
        # A veces se cierra después de la fecha programada (cumplimiento del plan < 100%).
        cierre = datetime.combine(programada, datetime.min.time(), tzinfo=UTC) + timedelta(
            hours=random.randint(10, 20) + (24 * random.randint(1, 5) if random.random() < 0.10 else 0)
        )
        reloj.fijar(min(cierre, hoy - timedelta(hours=1)))
        repuestos_costo = sum(c * p for _, c, p in repuestos)
        horas = round(random.uniform(1, 5), 1)
        await mant_service.cerrar_orden(
            db,
            dispatcher,
            actor_id=ACTOR,
            actor_rol="jefe_mantenimiento",
            orden_id=orden["_id"],
            body=mant_schemas.OrdenCerrarRequest(
                trabajos_realizados=f"{descripcion}. Se verificó el funcionamiento en prueba de ruta.",
                repuestos_consumidos=[
                    mant_schemas.RepuestoInput(descripcion=d, cantidad=c, costo_unitario=p) for d, c, p in repuestos
                ],
                costo_total=round(repuestos_costo + horas * 8.0, 2),
                horas_taller=horas,
                km_salida=km + random.randint(2, 15),
                habilitar_vehiculo=True,
            ),
        )
    return conteo


async def _crear_reportes_falla(db) -> int:
    """Reportes de falla PENDIENTES (CU-O07 A4 / bandeja de Mantenimiento),
    vía el servicio real, con una foto de evidencia subida por el conductor."""
    dispatcher = NoopNotificationDispatcher()
    juan = await db.usuarios.find_one({"telefono": "+593911223344"})
    pares = await _cargar_pares(db)
    elegidos = [p for p in pares if p[0] == juan["_id"]] + random.sample([p for p in pares if p[0] != juan["_id"]], 5)
    casos = [
        ("Vehículo averiado", "Se encendió la luz de check engine y el motor pierde fuerza en subida."),
        ("Vehículo averiado", "Ruido metálico al frenar, posible desgaste de pastillas."),
        ("Accidente leve", "Roce con una motocicleta en el retrovisor derecho, sin heridos."),
        ("Vehículo averiado", "El aire acondicionado dejó de enfriar."),
        ("Vehículo averiado", "Llanta delantera izquierda con pérdida lenta de aire."),
        ("Accidente leve", "Golpe leve en el parachoques trasero al estacionar."),
    ]
    hoy = datetime.now(UTC)
    for (conductor_id, _), (tipo, descripcion) in zip(elegidos, casos, strict=False):
        reloj.fijar(hoy - timedelta(hours=random.randint(2, 96)))
        foto = await archivos_service.guardar_archivo(
            db,
            actor_id=conductor_id,
            contexto="reporte_falla",
            upload=_upload_png(_png_documento((178, 58, 31), random.randint(1, 10**6)), "evidencia.png"),
        )
        lat, lon = _cerca(*QUEVEDO, 2500)
        await fallas_service.crear_reporte_falla(
            db,
            conductor_id=conductor_id,
            tipo_falla=tipo,
            descripcion=descripcion,
            lat=lat,
            lon=lon,
            impide_continuar=False,
            evidencias=[foto["_id"]],
            dispatcher=dispatcher,
        )
    return len(elegidos)


async def _crear_referidos(db) -> int:
    usuarios = [u["_id"] async for u in db.usuarios.find({"roles": {"$in": ["pasajero", "conductor"]}}, {"_id": 1})]
    pares: set[tuple[str, str]] = set()
    while len(pares) < 35:
        a, b = random.sample(usuarios, 2)
        pares.add((a, b))
    hoy = datetime.now(UTC)
    for a, b in pares:
        await db.referidos.update_one(
            {"referente_id": a, "referido_id": b},
            {
                "$setOnInsert": {
                    "_id": str(uuid.uuid4()),
                    "referente_id": a,
                    "referido_id": b,
                    "canal": random.choice(["app", "web", "referido", "whatsapp"]),
                    "estado_incentivo": random.choices(["OTORGADO", "PENDIENTE", "NO_APLICA"], weights=[5, 3, 1])[0],
                    "fecha_referido": hoy - timedelta(days=random.randint(1, DIAS_HISTORIA)),
                }
            },
            upsert=True,
        )
    return len(pares)


async def _estado_en_vivo(db, redis) -> int:
    """Deja ~14 socios en turno con posición reciente e historial GPS de los
    últimos 3 días (alimenta el tablero de Flota y `dag_flota_gold`). El
    servicio `flota-simulador` mantiene esas posiciones frescas después."""
    juan = await db.usuarios.find_one({"telefono": "+593911223344"})
    pares = [p for p in await _cargar_pares(db) if p[0] != juan["_id"]]
    en_turno = random.sample(pares, min(14, len(pares)))
    ahora = datetime.now(UTC)
    docs = []
    for conductor_id, vehiculo_id in pares:
        lat, lon = _cerca(*QUEVEDO, 3000)
        for h in range(72, 0, -1):
            if random.random() < 0.55:
                ts = ahora - timedelta(hours=h, minutes=random.randint(0, 59))
                lat, lon = _cerca(lat, lon, 400)
                docs.append(
                    {
                        "vehiculo_id": vehiculo_id,
                        "conductor_id": conductor_id,
                        "lat": lat,
                        "lon": lon,
                        "precision_m": random.uniform(4, 15),
                        "velocidad": random.uniform(0, 40),
                        "rumbo": random.uniform(0, 360),
                        "ts_dispositivo": ts,
                        "ts_servidor": ts,
                    }
                )
    if docs:
        await db.posiciones.insert_many(docs)
    for conductor_id, vehiculo_id in en_turno:
        lat, lon = _cerca(*QUEVEDO, 2500)
        await _set_servicio(db, conductor_id, "DISPONIBLE")
        await redis.hset(
            f"pos:{vehiculo_id}",
            mapping={"lat": lat, "lon": lon, "ts_servidor": ahora.isoformat(), "estado_servicio": "DISPONIBLE"},
        )
        await redis.expire(f"pos:{vehiculo_id}", 60)
    return len(en_turno)


async def _eventos_seguridad(db) -> int:
    """Eventos DENEGADO reales del catálogo de CU-O17/CU-O18 (los que en
    operación generan core/rbac.py, el bloqueo de login y flota.service):
    sin ellos el panel de Auditoría (filtrado por defecto en "Denegado") y la
    alerta de seguridad de Cumplimiento se verían vacíos."""
    from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event

    conductores = [u["_id"] async for u in db.usuarios.find({"roles": "conductor"}, {"_id": 1})]
    pasajeros = [u["_id"] async for u in db.usuarios.find({"roles": "pasajero"}, {"_id": 1})]
    vehiculos = [v["_id"] async for v in db.vehiculos.find({}, {"_id": 1})]
    hoy = datetime.now(UTC)
    eventos = []
    for _ in range(6):  # pasajeros/conductores intentando pantallas de staff
        actor = random.choice(conductores + pasajeros)
        eventos.append(
            dict(
                actor_id=actor,
                rol="conductor" if actor in conductores else "pasajero",
                accion=AccionAuditoria.ACCESO_DENEGADO,
                entidad=random.choice(["liquidaciones", "usuarios", "parametros"]),
                entidad_id=None,
            )
        )
    for _ in range(4):  # saltos de GPS imposibles
        eventos.append(
            dict(
                actor_id=random.choice(conductores),
                rol="conductor",
                accion=AccionAuditoria.POSIBLE_GPS_SPOOFING,
                entidad="vehiculos",
                entidad_id=random.choice(vehiculos),
                datos_posteriores={"distancia_km": round(random.uniform(8, 40), 1)},
            )
        )
    for _ in range(3):  # bloqueo por intentos de login fallidos
        eventos.append(
            dict(
                actor_id=random.choice(pasajeros),
                rol=None,
                accion=AccionAuditoria.LOGIN_FALLIDO_CONSECUTIVO,
                entidad="usuarios",
                entidad_id=None,
            )
        )
    for i, ev in enumerate(eventos):
        # 4 dentro de las últimas 24 h (alimentan la alerta de Cumplimiento), el resto en la última semana.
        horas = random.uniform(1, 20) if i % 3 == 0 else random.uniform(24, 24 * 7)
        reloj.fijar(hoy - timedelta(hours=horas))
        await write_audit_event(
            db, resultado=ResultadoAuditoria.DENEGADO, ip=f"203.0.113.{random.randint(1, 254)}", **ev
        )
    return len(eventos)


async def _notificaciones_demo(db) -> None:
    juan = await db.usuarios.find_one({"telefono": "+593911223344"})
    maria = await db.usuarios.find_one({"telefono": "+593987001122"})
    hoy = datetime.now(UTC)
    eventos = [
        (maria["_id"], "VIAJE_ASIGNADO", 50),
        (maria["_id"], "CONDUCTOR_LLEGO", 45),
        (maria["_id"], "VIAJE_FINALIZADO", 20),
        (juan["_id"], "SOLICITUD_DECISION", 3000),
        (juan["_id"], "ORDEN_MANTENIMIENTO_CERRADA", 600),
        ("staff-verificacion", "NUEVA_SOLICITUD", 90),
        ("staff-verificacion", "NUEVA_SOLICITUD", 30),
        ("staff-verificacion", "ALERTA_SEGURIDAD", 15),
        ("admin-sistema-qa", "ALERTA_SEGURIDAD", 15),
    ]
    for usuario_id, evento, minutos in eventos:
        reloj.fijar(hoy - timedelta(minutes=minutos))
        await notif_service._persistir_notificacion(db, usuario_id, evento, {"demo": True})


# ---------------------------------------------------------------------------


async def main() -> None:
    db = get_database()
    redis = get_redis()
    if await db["_meta_seed"].find_one({"_id": MARCA_SEED}):
        print("Siembra de demo ya aplicada (_meta_seed). Nada que hacer.")
        return
    if await db.usuarios.count_documents({}) > 0:
        print(
            "La base ya tiene usuarios que no vienen de esta siembra; no se siembra encima. "
            "Use `docker compose down -v` para empezar de cero."
        )
        return

    inicio = time.monotonic()
    await ensure_indexes()
    await _crear_staff(db)
    await _configuracion_base(db)
    print("Configuración base y cuentas de personal: OK")

    telefonos: set[str] = set()
    placas: set[str] = set()
    with reloj():
        pasajeros = await _crear_pasajeros(db, telefonos)
        print(f"Pasajeros: {len(pasajeros)}")
        await _crear_conductores(db, telefonos, placas)
        print(
            f"Socios conductores: {await db.usuarios.count_documents({'roles': 'conductor'})}, "
            f"vehículos: {await db.vehiculos.count_documents({})}, "
            f"documentos: {await db.documentos.count_documents({})}"
        )
        stats = await _crear_viajes(db, redis, pasajeros)
        print(f"Carreras: {stats}")
        print(f"Liquidaciones: {await _crear_liquidaciones(db)}")
        print(f"Órdenes de mantenimiento: {await _crear_ordenes(db)}")
        print(f"Reportes de falla pendientes: {await _crear_reportes_falla(db)}")
        await _notificaciones_demo(db)
        print(f"Eventos de seguridad (DENEGADO): {await _eventos_seguridad(db)}")
    print(f"Referidos: {await _crear_referidos(db)}")
    print(f"Socios en turno ahora: {await _estado_en_vivo(db, redis)}")
    print(f"Eventos de bitácora: {await db.bitacora.count_documents({})}")

    await db["_meta_seed"].insert_one({"_id": MARCA_SEED, "ts": datetime.now(UTC)})
    print(f"Siembra completa en {time.monotonic() - inicio:.0f}s.")


if __name__ == "__main__":
    asyncio.run(main())
