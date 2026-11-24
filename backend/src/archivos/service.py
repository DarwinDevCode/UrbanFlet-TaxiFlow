"""Archivos — primer mecanismo de carga de archivos del proyecto (Ronda 2 de
flujo de fallas, Fase A). Antes de este módulo no existía NINGÚN endpoint de
`UploadFile`/multipart en todo el backend — lo que la spec llamaba "carga de
documentos" (`documentos.url_objeto`) era siempre un `str` que el cliente
pegaba a mano, nunca un archivo real subido (confirmado en la auditoría de
UX, ver AUDITORIA_UX_CATALOGOS.md).

Almacenamiento local en disco dentro del contenedor (volumen con nombre,
`archivos_dir`/`archivos_data`, mismo patrón ya usado por Módulo 7.1 de
admin_sistema para `respaldos_dir`/`respaldos_data`) -- nada de S3/MinIO
nuevo, coherente con las restricciones de infraestructura ya documentadas
del proyecto (§8.6a de CLAUDE.md, techo de memoria del stack).

Diseño genérico a propósito, para que un consumidor futuro (la carga de
documentos de postulación, backlog ya documentado) pueda reusarlo sin tocar
este módulo: el control de acceso de lectura no está acoplado a "reportes de
falla" -- se resuelve por `contexto` (una etiqueta de string) contra
`CONTEXTOS_PERMITIDOS`, un diccionario contexto -> roles adicionales
permitidos a leer, decidido SIEMPRE del lado del servidor (nunca aceptado
del cliente en la subida, para que un cliente no pueda auto-otorgarse
visibilidad). Agregar un contexto nuevo es una entrada nueva en ese
diccionario, no un cambio de lógica.
"""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.config import get_settings
from src.core.exceptions import DomainError

# CU-O07 A4 (evidencia de incidencia) y CU-O12/13 (evidencia de orden) piden
# fotos -- imágenes solamente, no cualquier archivo. `content_type` reportado
# por el cliente no es de fiar por sí solo (se puede falsificar), pero acá
# solo gobierna la extensión con la que se guarda en disco -- el contenido
# real nunca se ejecuta ni se interpreta, solo se sirve de vuelta tal cual
# (mismo riesgo que servir cualquier imagen estática), así que no hace falta
# inspeccionar bytes mágicos para este alcance.
CONTENT_TYPES_PERMITIDOS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# 5 MB: generoso para una foto de celular comprimida, acotado para no dejar
# que un solo archivo se coma un porcentaje relevante del volumen Docker
# (ver límites de memoria/disco ya documentados en CLAUDE.md §8.6a).
TAMANO_MAXIMO_BYTES = 5 * 1024 * 1024
_TAMANO_CHUNK = 1024 * 1024

# Contexto -> roles ADICIONALES (además del propio propietario, que siempre
# puede ver lo suyo) con permiso de lectura. Decidido en el servidor, nunca
# aceptado del cliente al subir -- ver docstring del módulo.
CONTEXTOS_PERMITIDOS: dict[str, frozenset[str]] = {
    # Fase C/D de la Ronda 2: evidencia de una incidencia/falla reportada por
    # el conductor -- la ve el propio conductor que la subió, el Jefe de
    # Mantenimiento (quien decide si se convierte en orden), y roles de
    # supervisión/auditoría (gerencia, supervisor_cumplimiento) igual que el
    # resto de la bitácora de eventos sensibles.
    "reporte_falla": frozenset({"jefe_mantenimiento", "admin_sistema", "gerencia", "supervisor_cumplimiento"}),
    # Fase F: evidencia adjunta a una actividad de seguimiento de una orden
    # ya abierta -- mismos roles que reporte_falla, es la continuación del
    # mismo caso.
    "actividad_orden": frozenset({"jefe_mantenimiento", "admin_sistema", "gerencia", "supervisor_cumplimiento"}),
    # Cierre del gap de renovación documental (CU-O03 A2): evidencia de la
    # renovación que el propio conductor sube -- la ve él mismo (dueño,
    # siempre puede ver lo suyo) y quien decide si la aprueba.
    "documento_renovacion": frozenset({"supervisor_cumplimiento", "admin_sistema", "gerencia"}),
    # Gestión documental en la postulación (CU-O01): licencia/matrícula que
    # el postulante sube al postular -- la ve él mismo (dueño) y
    # admin_captacion, que es quien revisa la solicitud completa.
    "documento_postulacion": frozenset({"admin_captacion", "admin_sistema"}),
}

# Ronda de foto de perfil: a diferencia de reporte_falla/actividad_orden
# (evidencia operativa sensible, gateada por rol), una foto de perfil es de
# LECTURA ABIERTA a propósito -- ni siquiera exige sesión. Dos razones: (1)
# no hay ningún dato sensible en juego, es el mismo tipo de dato que
# cualquier avatar público de cualquier app; (2) ya existía una superficie
# sin sesión que necesita mostrarla -- la vista pública de "Compartir viaje"
# (Sección 1.2 de ux_complementaria.md) muestra la foto del conductor a un
# contacto sin cuenta. El id del archivo (UUID aleatorio) es la única
# protección -- mismo criterio de "no listable, pero no requiere sesión" ya
# usado por el token de 256 bits de Compartir viaje.
CONTEXTOS_LECTURA_PUBLICA: frozenset[str] = frozenset({"foto_perfil"})


def _contexto_valido(contexto: str) -> bool:
    return contexto in CONTEXTOS_PERMITIDOS or contexto in CONTEXTOS_LECTURA_PUBLICA


class TipoArchivoNoPermitidoError(DomainError):
    def __init__(self, content_type: str) -> None:
        tipos = ", ".join(sorted(CONTENT_TYPES_PERMITIDOS))
        super().__init__(
            code="TIPO_ARCHIVO_NO_PERMITIDO",
            message=f"Tipo de archivo no permitido ({content_type}) -- solo se aceptan: {tipos}",
            status_code=422,
        )


class ArchivoDemasiadoGrandeError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="ARCHIVO_DEMASIADO_GRANDE",
            message=f"El archivo supera el límite de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB",
            status_code=413,
        )


class ContextoInvalidoError(DomainError):
    def __init__(self, contexto: str) -> None:
        super().__init__(
            code="CONTEXTO_INVALIDO", message=f"Contexto de carga no reconocido: {contexto}", status_code=422
        )


class ArchivoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="ARCHIVO_NO_ENCONTRADO", message="El archivo no existe", status_code=404)


def _ruta_archivos() -> Path:
    ruta = Path(get_settings().archivos_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def archivo_a_salida(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "nombre_original": doc["nombre_original"],
        "content_type": doc["content_type"],
        "tamano_bytes": doc["tamano_bytes"],
        "contexto": doc["contexto"],
        "propietario_id": doc["propietario_id"],
        "ts_creacion": doc["ts_creacion"],
    }


async def guardar_archivo(
    db: AsyncIOMotorDatabase, *, actor_id: str, contexto: str, upload: UploadFile
) -> dict:
    if not _contexto_valido(contexto):
        raise ContextoInvalidoError(contexto)

    content_type = upload.content_type or ""
    extension = CONTENT_TYPES_PERMITIDOS.get(content_type)
    if extension is None:
        raise TipoArchivoNoPermitidoError(content_type)

    archivo_id = str(uuid.uuid4())
    ruta = _ruta_archivos() / f"{archivo_id}{extension}"
    hasher = hashlib.sha256()
    tamano = 0

    # Escritura en streaming (nunca el archivo completo en memoria) con
    # límite de tamaño aplicado mientras se lee -- si un cliente manda un
    # archivo más grande de lo declarado, se corta y se borra el parcial en
    # vez de dejarlo a medio escribir en disco.
    try:
        with open(ruta, "wb") as f:
            while chunk := await upload.read(_TAMANO_CHUNK):
                tamano += len(chunk)
                if tamano > TAMANO_MAXIMO_BYTES:
                    raise ArchivoDemasiadoGrandeError()
                hasher.update(chunk)
                f.write(chunk)
    except ArchivoDemasiadoGrandeError:
        ruta.unlink(missing_ok=True)
        raise

    doc = {
        "_id": archivo_id,
        "nombre_original": upload.filename or archivo_id,
        "content_type": content_type,
        "tamano_bytes": tamano,
        "hash_sha256": hasher.hexdigest(),
        "ruta_disco": str(ruta),
        "contexto": contexto,
        "propietario_id": actor_id,
        "ts_creacion": datetime.now(UTC),
    }
    await db.archivos.insert_one(doc)
    return doc


async def obtener_archivo(db: AsyncIOMotorDatabase, *, archivo_id: str) -> dict:
    doc = await db.archivos.find_one({"_id": archivo_id})
    if doc is None:
        raise ArchivoNoEncontradoError()
    return doc


def puede_ver(doc: dict, *, actor_id: str | None, roles: list[str]) -> bool:
    if doc["contexto"] in CONTEXTOS_LECTURA_PUBLICA:
        return True
    if actor_id is not None and doc["propietario_id"] == actor_id:
        return True
    permitidos = CONTEXTOS_PERMITIDOS.get(doc["contexto"], frozenset())
    return bool(permitidos.intersection(roles))
