"""Ronda de foto de perfil + siembra de 26 usuarios ficticios.

Fase 3 de `prompt_foto_perfil_y_siembra_usuarios.md` (documento adjuntado
por el usuario para esta sesión, no versionado en el repo) -- se corre
DESPUÉS de que las Fases 1 (backend) y 2 (frontend) de foto de perfil ya
estén verificadas funcionando, nunca antes (sembrar sobre una feature que
no funciona todavía sería crear datos sobre un mecanismo roto).

Fuente de las 26 fotos: `analytics/seed_data/avatares/` (extraído del zip
"Perfiles de personas o avatar.zip" adjuntado por el usuario), 27 archivos
-- `AvataPorDefecto.png` (ya copiado como asset del repo en la Fase 1, acá
se ignora) + 26 fotos de persona con el patrón de nombre real
`<Genero> <Edad> años.<ext>` (`Hombre`/`Mujer`, edad en años, extensión jpg
o png -- un archivo trae el typo real "naños" en vez de "años", el patrón
de abajo lo tolera a propósito por eso solo ancla el género + el número).
Ese patrón es el único identificador real disponible en el nombre de
archivo -- se usa como criterio de asignación determinista, documentado acá
en vez de asumido: las 26 se ordenan por edad DESCENDENTE (empate roto
alfabéticamente, "Hombre" antes que "Mujer") y se reparten en 3 bloques
consecutivos (staff/conductor/pasajero, ver distribución abajo) -- las
fotos de más edad al bloque de personal interno, sin que esto sea ninguna
regla de negocio real, solo un criterio estético de asignación.

Dentro del contenedor del backend, las imágenes viven en
`/app/seed_avatares` -- copiadas ahí con `docker cp` antes de correr este
script (no es un bind mount permanente en `docker-compose.yml`, es un
asset de siembra de un solo uso):

    docker cp analytics/seed_data/avatares urbanflet-taxiflow-backend-1:/app/seed_avatares
    docker exec urbanflet-taxiflow-backend-1 python -m scripts.seed_usuarios_ficticios

Cada usuario se crea vía el servicio real correspondiente a su rol -- nunca
`insert_one` directo (mismo criterio que el resto de `seed_*.py`):
- Los 10 roles de personal interno (11 roles reales del sistema salvo
  `integracion_externa`, que no tiene ninguna pantalla ni cuenta de demo
  por diseño -- rol pensado para acceso máquina-a-máquina, ver CLAUDE.md
  §8.7): `usuarios.service.crear_cuenta_staff`.
- `pasajero`: `captacion.service.registrar_pasajero` (CU-O02).
- `conductor`: `captacion.service.crear_solicitud` +
  `decidir_solicitud(decision="APROBADA")` (CU-O01, mismo flujo real de
  aprobación que ya usa `seed_solicitudes_demo.py` -- genera también un
  vehículo y 2 documentos reales por conductor, efecto legítimo de la
  transacción de aprobación, no un atajo).

La foto se asocia con el MISMO mecanismo construido en la Fase 1 -- nunca
escrita directo en Mongo: se abre el archivo real, se arma un
`fastapi.UploadFile` en memoria, se sube vía
`archivos.service.guardar_archivo(contexto="foto_perfil")` (la misma
función que expone `POST /archivos`), y el id resultante se aplica con
`perfil.service.editar_foto_perfil` (la misma función que expone
`PATCH /perfil/foto`).

Idempotente y sin tocar cuentas existentes: cada persona usa un teléfono
determinista con prefijo `+593980` (NINGUNA cuenta demo documentada en
CLAUDE.md §8.7 usa ese prefijo -- todas usan `+59390`/`+59391`/`+59399`) --
si ya existe una cuenta con ese teléfono, se salta esa fila entera sin
tocar nada (ni rol, ni foto, ni ningún otro campo).

Uso: ver el bloque `docker cp` + `docker exec` de arriba. No correr desde
el venv local -- el replica set de Mongo anuncia internamente el hostname
`mongo:27017`, inalcanzable fuera de la red de docker-compose (mismo
problema ya documentado para `seed_viajes_nyc.py` en CLAUDE.md §7).
"""

import asyncio
import io
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import UploadFile
from starlette.datastructures import Headers

from src.archivos import service as archivos_service
from src.captacion import schemas as captacion_schemas
from src.captacion import service as captacion_service
from src.core.db_mongo import get_database
from src.core.notifications import NoopNotificationDispatcher
from src.perfil import service as perfil_service
from src.usuarios import service as usuarios_service

RUTA_AVATARES = Path("/app/seed_avatares")
PASSWORD_DEMO = "UsuarioDemo123!"
VERIFICADOR_ID = "staff-verificacion"

CONTENT_TYPE_POR_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

PATRON_NOMBRE = re.compile(r"^(?P<genero>Hombre|Mujer)\s+(?P<edad>\d+)")


def _personas_desde_carpeta() -> list[dict]:
    """26 fotos de persona, ordenadas de MAYOR a MENOR edad (ver docstring
    del módulo para el razonamiento completo de este orden)."""
    personas = []
    for archivo in RUTA_AVATARES.iterdir():
        if archivo.name == "AvataPorDefecto.png":
            continue
        m = PATRON_NOMBRE.match(archivo.name)
        if not m:
            print(f"Aviso: '{archivo.name}' no coincide con el patrón esperado, se ignora.")
            continue
        personas.append({"ruta": archivo, "genero": m.group("genero"), "edad": int(m.group("edad"))})

    personas.sort(key=lambda p: (p["edad"], p["genero"]))
    personas.reverse()

    if len(personas) != 26:
        raise RuntimeError(
            f"Se esperaban 26 fotos de persona en {RUTA_AVATARES}, se encontraron {len(personas)}."
        )
    return personas


# Distribución de roles (26 = 10 staff + 8 conductor + 8 pasajero), ver
# docstring del módulo. Los 10 staff cubren los 11 roles reales de personal
# interno salvo `integracion_externa` (sin pantalla propia, ver arriba).
ROLES_STAFF_EN_ORDEN = [
    ("gerencia", "James", "Smith"),
    ("admin_sistema", "Michael", "Johnson"),
    ("admin_plataforma", "Robert", "Brown"),
    ("responsable_plataforma", "David", "Jones"),
    ("admin_financiero", "Mary", "Williams"),
    ("jefe_mantenimiento", "Richard", "Miller"),
    ("supervisor_cumplimiento", "Jennifer", "Young"),
    ("coordinador_operaciones", "Linda", "Allen"),
    ("coordinador_flota", "Joseph", "Davis"),
    ("admin_captacion", "Thomas", "Wilson"),
]

CONDUCTORES_EN_ORDEN = [
    ("Christopher", "Anderson"),
    ("Daniel", "Taylor"),
    ("Matthew", "Moore"),
    ("Andrew", "Jackson"),
    ("Kevin", "Martin"),
    ("Susan", "King"),
    ("Brian", "Lee"),
    ("Kenneth", "Thompson"),
]

PASAJEROS_EN_ORDEN = [
    ("Ryan", "White"),
    ("Karen", "Wright"),
    ("Jacob", "Harris"),
    ("Justin", "Clark"),
    ("Amanda", "Scott"),
    ("Brandon", "Lewis"),
    ("Eric", "Robinson"),
    ("Gary", "Walker"),
]


def _telefono(indice: int) -> str:
    return f"+593980{indice:03d}"


def _upload_file_desde(ruta: Path) -> UploadFile:
    contenido = ruta.read_bytes()
    content_type = CONTENT_TYPE_POR_EXTENSION[ruta.suffix.lower()]
    return UploadFile(
        file=io.BytesIO(contenido), size=len(contenido), filename=ruta.name, headers=Headers({"content-type": content_type})
    )


async def _asociar_foto(db, *, usuario_id: str, roles: list[str], ruta_foto: Path) -> None:
    upload = _upload_file_desde(ruta_foto)
    archivo = await archivos_service.guardar_archivo(db, actor_id=usuario_id, contexto="foto_perfil", upload=upload)
    await perfil_service.editar_foto_perfil(db, usuario_id=usuario_id, roles=roles, archivo_id=archivo["_id"])


async def _crear_staff(db, *, indice: int, rol: str, nombre_pila: str, apellido: str, persona: dict) -> bool:
    telefono = _telefono(indice)
    if await db.usuarios.find_one({"telefono": telefono}) is not None:
        return False

    usuario, _ = await usuarios_service.crear_cuenta_staff(
        db,
        actor_id=VERIFICADOR_ID,
        actor_rol="admin_sistema",
        nombre=f"{nombre_pila} {apellido}",
        telefono=telefono,
        email=None,
        password=PASSWORD_DEMO,
        roles=[rol],
    )
    await _asociar_foto(db, usuario_id=usuario["_id"], roles=[rol], ruta_foto=persona["ruta"])
    return True


async def _crear_pasajero(db, *, indice: int, nombre_pila: str, apellido: str, persona: dict) -> bool:
    telefono = _telefono(indice)
    if await db.usuarios.find_one({"telefono": telefono}) is not None:
        return False

    resultado = await captacion_service.registrar_pasajero(
        db,
        nombre=f"{nombre_pila} {apellido}",
        telefono=telefono,
        email=None,
        password=PASSWORD_DEMO,
        version_consentimiento="v1-2026-07",
        canal="app",
    )
    await _asociar_foto(db, usuario_id=resultado["usuario_id"], roles=["pasajero"], ruta_foto=persona["ruta"])
    return True


async def _crear_conductor(
    db, dispatcher, *, indice: int, nombre_pila: str, apellido: str, persona: dict
) -> bool:
    telefono = _telefono(indice)
    if await db.usuarios.find_one({"telefono": telefono}) is not None:
        return False

    cedula = f"FICT-{indice:06d}"
    placa = f"FIC-{indice:04d}"
    hoy = date.today()

    solicitud = await captacion_service.crear_solicitud(
        db,
        dispatcher,
        nombre=f"{nombre_pila} {apellido}",
        telefono=telefono,
        email=None,
        password=PASSWORD_DEMO,
        cedula=cedula,
        licencia_numero=f"LICFICT-{indice:06d}",
        vehiculo=captacion_schemas.VehiculoInput(
            placa=placa, marca="Chevrolet", modelo="2022", anio=2022, color="Blanco", capacidad=4
        ),
        documentos=[
            captacion_schemas.DocumentoInput(
                tipo="LICENCIA_CONDUCIR",
                propietario_tipo="CONDUCTOR",
                url_objeto=f"seed://licencia-fict-{indice}.pdf",
                hash_archivo=f"seedhash-fict-lic-{indice:05d}",
                fecha_emision=hoy - timedelta(days=200),
                fecha_vencimiento=hoy + timedelta(days=365),
            ),
            captacion_schemas.DocumentoInput(
                tipo="MATRICULA_VEHICULAR",
                propietario_tipo="VEHICULO",
                url_objeto=f"seed://matricula-fict-{indice}.pdf",
                hash_archivo=f"seedhash-fict-mat-{indice:05d}",
                fecha_emision=hoy - timedelta(days=100),
                fecha_vencimiento=hoy + timedelta(days=365),
            ),
        ],
        enviar=True,
        canal="referido",
    )
    await captacion_service.tomar_solicitud(
        db, solicitud_id=solicitud["_id"], verificador_id=VERIFICADOR_ID, verificador_rol="admin_captacion"
    )
    await captacion_service.decidir_solicitud(
        db,
        dispatcher,
        solicitud_id=solicitud["_id"],
        verificador_id=VERIFICADOR_ID,
        verificador_rol="admin_captacion",
        decision="APROBADA",
        motivo=None,
    )
    await _asociar_foto(db, usuario_id=solicitud["usuario_id"], roles=["conductor"], ruta_foto=persona["ruta"])
    return True


async def main() -> None:
    if not RUTA_AVATARES.is_dir():
        raise RuntimeError(
            f"No existe {RUTA_AVATARES} dentro del contenedor -- correr primero "
            f"'docker cp analytics/seed_data/avatares <contenedor>:/app/seed_avatares'."
        )

    db = get_database()
    dispatcher = NoopNotificationDispatcher()
    personas = _personas_desde_carpeta()

    bloque_staff = personas[0:10]
    bloque_conductor = personas[10:18]
    bloque_pasajero = personas[18:26]

    filas: list[tuple[str, str, bool]] = []  # (nombre completo, rol, tiene_foto=True siempre)

    indice = 0
    for (rol, nombre_pila, apellido), persona in zip(ROLES_STAFF_EN_ORDEN, bloque_staff, strict=True):
        creado = await _crear_staff(
            db, indice=indice, rol=rol, nombre_pila=nombre_pila, apellido=apellido, persona=persona
        )
        filas.append((f"{nombre_pila} {apellido}", rol, creado))
        indice += 1

    for (nombre_pila, apellido), persona in zip(CONDUCTORES_EN_ORDEN, bloque_conductor, strict=True):
        creado = await _crear_conductor(
            db, dispatcher, indice=indice, nombre_pila=nombre_pila, apellido=apellido, persona=persona
        )
        filas.append((f"{nombre_pila} {apellido}", "conductor", creado))
        indice += 1

    for (nombre_pila, apellido), persona in zip(PASAJEROS_EN_ORDEN, bloque_pasajero, strict=True):
        creado = await _crear_pasajero(db, indice=indice, nombre_pila=nombre_pila, apellido=apellido, persona=persona)
        filas.append((f"{nombre_pila} {apellido}", "pasajero", creado))
        indice += 1

    creadas = sum(1 for _, _, c in filas if c)
    saltadas = len(filas) - creadas
    print(f"Usuarios ficticios creados: {creadas}. Saltados por ya existir: {saltadas}.")
    print(f"{'Nombre':<24} {'Rol':<26} {'Estado'}")
    for nombre, rol, creado in filas:
        estado = "creado (con foto)" if creado else "ya existía (sin tocar)"
        print(f"{nombre:<24} {rol:<26} {estado}")


if __name__ == "__main__":
    asyncio.run(main())
