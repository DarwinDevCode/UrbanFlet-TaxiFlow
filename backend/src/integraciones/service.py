"""Integraciones Externas — Módulo 4 de admin_sistema
(specs/specs-administrativas/admin_sistema.md).

**4.1 (credenciales)** -- cierra un gap que el propio proyecto ya había
identificado (CU-T03/OT2.1: "Administrar las integraciones externas"), pero
verificado ANTES de construir (no asumido): `GET /ext/v1/...` que la spec
da por existente **no existe en el código** -- solo está documentado como
diseño en `arquitectura_software.md`. `rpt_uso_integraciones` (dashboard
táctico de Auditoría) se alimenta de `fact_integracion_api`, que el propio
DAG (`analytics/plugins/indicadores.py`) documenta como "aproximado desde
bitácora", no de tráfico real. Alcance confirmado con el usuario: el CRUD
de credenciales se construye completo y real (hash irreversible, revocar
con efecto inmediato) -- sin el middleware de validación contra un
endpoint que no existe. `usos_registrados` queda en 0 con ese motivo
explícito, mismo criterio que "% error API" en el dashboard de Auditoría.

**4.2 (servicios externos)** -- Google Maps es el único servicio externo
real que el sistema ya integra (`core/config.py::Settings.google_maps_api_key`,
usado en `viajes/service.py::estimar_ruta`). SMS y S3 aparecen en la spec
como servicios "que la arquitectura ya define" pero no hay integración
real con ninguno de los dos en el codebase (SMS/OTP es backlog consciente
desde que el login migró a usuario+contraseña, ver CLAUDE.md §4; S3 nunca
se conectó) -- se muestran como "no_configurado" siempre, nunca simulados
como activos. La rotación de la key de Google Maps es real: escribe en
`servicios_externos_config` (Mongo), que `viajes/service.py::estimar_ruta`
consulta en cada llamada ANTES que la variable de entorno -- así se logra
"sin reiniciar el backend" de verdad, no un mock.
"""

import secrets
import uuid
from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.config import get_settings
from src.core.exceptions import DomainError
from src.core.security import hash_password

SERVICIOS_SIN_INTEGRACION_REAL = ("sms", "s3")


class CredencialNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="CREDENCIAL_NO_ENCONTRADA", message="La credencial no existe", status_code=404)


class CredencialYaRevocadaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="CREDENCIAL_YA_REVOCADA", message="La credencial ya estaba revocada", status_code=409)


async def crear_credencial(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, nombre: str, alcance: str
) -> tuple[dict, str]:
    secreto = secrets.token_urlsafe(32)
    ahora = datetime.now(UTC)
    doc = {
        "_id": str(uuid.uuid4()),
        "nombre": nombre,
        "hash_secreto": hash_password(secreto),
        "alcance": alcance,
        "vigente_desde": ahora,
        "vigente_hasta": None,
        "revocada": False,
        "usos_registrados": 0,
    }
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.INTEGRACION_CREDENCIAL_CREACION,
        entidad="credenciales_integracion",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"nombre": nombre, "alcance": alcance},
    )
    await db.credenciales_integracion.insert_one(doc)
    return doc, secreto


async def listar_credenciales(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.credenciales_integracion.find().sort("vigente_desde", -1).to_list(length=500)


async def revocar_credencial(db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, credencial_id: str) -> dict:
    doc = await db.credenciales_integracion.find_one({"_id": credencial_id})
    if doc is None:
        raise CredencialNoEncontradaError()
    if doc["revocada"]:
        raise CredencialYaRevocadaError()

    ahora = datetime.now(UTC)
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.INTEGRACION_CREDENCIAL_REVOCACION,
        entidad="credenciales_integracion",
        entidad_id=credencial_id,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"revocada": False},
        datos_posteriores={"revocada": True, "vigente_hasta": ahora.isoformat()},
    )
    await db.credenciales_integracion.update_one(
        {"_id": credencial_id}, {"$set": {"revocada": True, "vigente_hasta": ahora}}
    )
    return await db.credenciales_integracion.find_one({"_id": credencial_id})


def _enmascarar(api_key: str) -> str:
    if len(api_key) <= 4:
        return "••••"
    return f"••••{api_key[-4:]}"


async def obtener_google_maps_api_key(db: AsyncIOMotorDatabase) -> str:
    """Punto único de lectura de la key de Google Maps -- el override en
    Mongo gana sobre la variable de entorno si existe, para que rotar la
    key desde Módulo 4.2 tenga efecto inmediato sin reiniciar el backend."""
    override = await db.servicios_externos_config.find_one({"_id": "google_maps"})
    if override and override.get("api_key"):
        return override["api_key"]
    return get_settings().google_maps_api_key


async def listar_servicios_externos(db: AsyncIOMotorDatabase) -> list[dict]:
    key = await obtener_google_maps_api_key(db)
    salida = [
        {
            "nombre": "google_maps",
            "estado": "activo" if key else "no_configurado",
            "key_enmascarada": _enmascarar(key) if key else None,
        }
    ]
    for nombre in SERVICIOS_SIN_INTEGRACION_REAL:
        salida.append({"nombre": nombre, "estado": "no_configurado", "key_enmascarada": None})
    return salida


async def rotar_google_maps_key(db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, api_key: str) -> dict:
    anterior = await obtener_google_maps_api_key(db)

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.INTEGRACION_SERVICIO_ROTACION,
        entidad="servicios_externos_config",
        entidad_id="google_maps",
        resultado=ResultadoAuditoria.OK,
        datos_previos={"key_enmascarada": _enmascarar(anterior)} if anterior else None,
        datos_posteriores={"key_enmascarada": _enmascarar(api_key)},
    )
    await db.servicios_externos_config.update_one(
        {"_id": "google_maps"},
        {"$set": {"api_key": api_key, "actualizado_en": datetime.now(UTC)}},
        upsert=True,
    )
    return {"nombre": "google_maps", "estado": "activo", "key_enmascarada": _enmascarar(api_key)}
