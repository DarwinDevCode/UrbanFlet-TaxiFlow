"""Simulador de flota SOLO para demostración (servicio `flota-simulador` de
docker-compose.yml).

En producción cada conductor reporta su GPS desde web-conductor cada pocos
segundos; la posición vive en Redis con TTL de 60 s y el tablero de Flota
marca "sin señal" a quien deja de reportar. En una demo sin teléfonos
reales, eso dejaría el tablero (y los autos cercanos del mapa del pasajero)
vacíos al minuto. Este proceso mueve suavemente a los socios que están en
turno (`conductor.estado_servicio` DISPONIBLE/OCUPADO) y refresca su
posición, igual que lo haría la app del conductor.

No toca a quien no esté en turno: el conductor demo (+593911223344) entra
en turno solo cuando alguien inicia sesión con él y pulsa "Iniciar turno";
desde ahí sus posiciones las reporta su propia pestaña del navegador.

Uso: python -m scripts.simular_flota_demo
"""

import asyncio
import math
import random
from datetime import UTC, datetime

from src.core.db_mongo import get_database
from src.core.db_redis import get_redis

INTERVALO_S = 15
QUEVEDO = (-1.0225, -79.4636)
DEMO_TELEFONO = "+593911223344"


async def _tick(db, redis, rumbos: dict[str, float], contador: int) -> None:
    ahora = datetime.now(UTC)
    posiciones = []
    async for u in db.usuarios.find(
        {
            "roles": "conductor",
            "telefono": {"$ne": DEMO_TELEFONO},
            "conductor.estado_servicio": {"$in": ["DISPONIBLE", "OCUPADO"]},
        },
        {"conductor": 1},
    ):
        veh = await db.vehiculos.find_one({"propietario_id": u["_id"]}, {"_id": 1})
        if veh is None:
            continue
        key = f"pos:{veh['_id']}"
        actual = await redis.hgetall(key)
        lat = float(actual["lat"]) if actual.get("lat") else QUEVEDO[0] + random.uniform(-0.02, 0.02)
        lon = float(actual["lon"]) if actual.get("lon") else QUEVEDO[1] + random.uniform(-0.02, 0.02)
        rumbo = rumbos.get(veh["_id"], random.uniform(0, 360)) + random.uniform(-35, 35)
        # Si se aleja del centro de Quevedo, gira de vuelta.
        if math.dist((lat, lon), QUEVEDO) > 0.03:
            rumbo = math.degrees(math.atan2(QUEVEDO[0] - lat, QUEVEDO[1] - lon))
        rumbos[veh["_id"]] = rumbo
        paso = random.uniform(40, 120) / 111_000
        lat += paso * math.sin(math.radians(rumbo))
        lon += paso * math.cos(math.radians(rumbo))
        estado = u["conductor"]["estado_servicio"]
        await redis.hset(
            key, mapping={"lat": lat, "lon": lon, "ts_servidor": ahora.isoformat(), "estado_servicio": estado}
        )
        await redis.expire(key, 60)
        if contador % 4 == 0:  # ~1 punto por minuto al histórico (alimenta dag_flota_gold)
            posiciones.append(
                {
                    "vehiculo_id": veh["_id"],
                    "conductor_id": u["_id"],
                    "lat": lat,
                    "lon": lon,
                    "precision_m": random.uniform(4, 12),
                    "velocidad": random.uniform(10, 40),
                    "rumbo": rumbo % 360,
                    "ts_dispositivo": ahora,
                    "ts_servidor": ahora,
                }
            )
    if posiciones:
        await db.posiciones.insert_many(posiciones)


async def main() -> None:
    db = get_database()
    redis = get_redis()
    rumbos: dict[str, float] = {}
    contador = 0
    print("Simulador de flota activo (intervalo 15 s).", flush=True)
    while True:
        try:
            await _tick(db, redis, rumbos, contador)
        except Exception as exc:  # noqa: BLE001 -- un tick fallido no debe matar la demo
            print(f"tick fallido: {exc}", flush=True)
        contador += 1
        await asyncio.sleep(INTERVALO_S)


if __name__ == "__main__":
    asyncio.run(main())
