from datetime import datetime, UTC

from src.core.security import TokenType, create_token


async def crear_usuario_activo(db, *, usuario_id: str, telefono: str, roles: list[str]) -> dict:
    usuario = {
        "_id": usuario_id,
        "nombre": "Actor de prueba",
        "telefono": telefono,
        "email": None,
        "hash_password": None,
        "roles": roles,
        "estado": "ACTIVO",
        "fecha_registro": datetime.now(UTC),
    }
    await db.usuarios.insert_one(usuario)
    return usuario


def token_para(usuario_id: str, roles: list[str]) -> str:
    return create_token(usuario_id, roles, TokenType.ACCESS)


def auth_headers(usuario_id: str, roles: list[str]) -> dict:
    return {"Authorization": f"Bearer {token_para(usuario_id, roles)}"}


async def crear_conductor_con_vehiculo(
    db,
    *,
    conductor_id: str,
    telefono: str,
    vehiculo_id: str,
    placa: str,
    estado_habilitacion: str = "HABILITADO",
    estado_servicio: str = "FUERA_DE_LINEA",
    cumplimiento_ok_conductor: bool | None = None,
    cumplimiento_ok_vehiculo: bool | None = None,
) -> tuple[dict, dict]:
    """Crea el par conductor+vehículo tal como quedaría tras una aprobación
    de Captación (Fase 1) — usado por las pruebas de Fase 2, que asumen ese
    estado ya existe."""
    conductor_sub: dict = {
        "cedula": "0000000000",
        "licencia_numero": "LIC-TEST",
        "calificacion_promedio": None,
        "estado_servicio": estado_servicio,
        "fecha_alta_socio": datetime.now(UTC),
    }
    if cumplimiento_ok_conductor is not None:
        conductor_sub["cumplimiento_ok"] = cumplimiento_ok_conductor

    usuario = {
        "_id": conductor_id,
        "nombre": "Conductor de prueba",
        "telefono": telefono,
        "email": None,
        "hash_password": None,
        "roles": ["conductor"],
        "estado": "ACTIVO",
        "fecha_registro": datetime.now(UTC),
        "conductor": conductor_sub,
    }
    await db.usuarios.insert_one(usuario)

    vehiculo: dict = {
        "_id": vehiculo_id,
        "placa": placa,
        "marca": "Marca",
        "modelo": "Modelo",
        "anio": 2020,
        "color": "Negro",
        "capacidad": 4,
        "estado_habilitacion": estado_habilitacion,
        "km_acumulado": 0,
        "propietario_id": conductor_id,
    }
    if cumplimiento_ok_vehiculo is not None:
        vehiculo["cumplimiento_ok"] = cumplimiento_ok_vehiculo

    await db.vehiculos.insert_one(vehiculo)
    return usuario, vehiculo


async def reportar_posicion_en_cache(redis, *, vehiculo_id: str, lat: float, lon: float) -> None:
    """Escribe directamente en el caché de posición (mismo formato que
    flota/service.py:reportar_posicion) sin pasar por el endpoint HTTP —
    usado por las pruebas de despacho (Fase 3), que solo necesitan que el
    candidato tenga una posición reciente, no ejercitar CU-O19 de nuevo."""
    await redis.hset(
        f"pos:{vehiculo_id}",
        mapping={"lat": lat, "lon": lon, "ts_servidor": datetime.now(UTC).isoformat(), "estado_servicio": "DISPONIBLE"},
    )
