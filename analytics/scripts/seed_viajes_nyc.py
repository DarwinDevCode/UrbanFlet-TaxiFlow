"""Siembra viajes/pagos REALES en MongoDB a partir del dataset NYC Yellow Taxi
2021 completo (~1.36M filas), como fuente de volumen operativo real para los
9 dashboards tácticos. Decisión de arquitectura documentada en CLAUDE.md
(sección "Cambio de arquitectura -- dataset NYC como fuente de siembra
operativa real") -- Paso 2. NO toca `fact_viaje_historico`/`raw_trips`, que
siguen siendo el flujo de referencia aislado, sin cambios.

Mapeo NYC -> UrbanFleet (decisiones de diseño, todas explícitas):

- `pasajero_id`/(`conductor_id`,`vehiculo_id`): round-robin determinista
  (`numero_fila % len(pool)`) sobre el pool de usuarios de prueba YA
  sembrados en Mongo (9 pasajeros, 5 pares conductor->vehiculo reales via
  `propietario_id`) -- no se inventan usuarios nuevos. Con 1.36M viajes
  repartidos entre 5 conductores, cada uno queda con ~270K viajes
  históricos, cifra irreal para un solo socio pero aceptable para el
  propósito real de esta siembra (dar volumen a los dashboards tácticos,
  no simular una flota realista) -- si se necesitara una distribución más
  creíble por conductor, habría que generar más conductores/vehículos de
  prueba antes, decisión que se deja documentada aquí para la próxima
  sesión en vez de tomarla unilateralmente.
- Coordenadas de origen/destino: sintéticas, ancladas al área real de
  operación (Quevedo, Ecuador, ~-1.0225,-79.4636), NUNCA la coordenada NYC
  real (el dataset ni siquiera trae lat/lon, solo PULocationID/DOLocationID
  -- zonas TLC de Nueva York, sin ningún significado geográfico en Ecuador).
  Se usa `PULocationID`/`DOLocationID` + número de fila como semilla
  determinista (hash) para variar el punto dentro de un radio de ~0.4-2.7km
  del centro -- da variación reproducible sin fabricar un catálogo de zonas
  que no existe en este dominio (confirmado: la colección `zonas` está
  vacía y `viajes.zona_origen_id`/`zona_destino_id` son SIEMPRE `None` en
  datos reales, ver `backend/src/viajes/service.py`).
- `km_recorridos`: `trip_distance` (millas) x 1.60934.
- `ts_solicitud`=`ts_inicio`: `tpep_pickup_datetime`; `ts_fin`:
  `tpep_dropoff_datetime` (solo para viajes PAGADO).
- `tarifa_final`: `total_amount` directo (dato real NYC, no recalculado con
  la fórmula tarifaria de UrbanFleet -- mezclar orígenes de tarifa
  invalidaría el propósito de dar volumen real).
- `metodo` de pago: `payment_type` 1 (credit card) -> ELECTRONICO, 2 (cash)
  -> EFECTIVO. El resto (3 no-charge, 4 dispute, 5 unknown, 6 voided trip,
  vacío) se mapea a EFECTIVO -- `MetodoPago` en el backend solo admite
  EFECTIVO/ELECTRONICO (sin equivalente a disputa/anulado/desconocido), y
  EFECTIVO es la opción más neutral (no implica una liquidación electrónica
  que nunca ocurrió). Documentado aquí, no en el código de negocio --
  ninguna ruta real de la aplicación produce ELECTRONICO todavía (pago
  electrónico es backlog consciente, ver CLAUDE.md §3.1); esta siembra
  escribe el campo directo a Mongo, sin pasar por esa integración inexistente.
- `estado`: ~93% PAGADO, ~7% CANCELADO (fracción determinista por hash de
  fila, no random sin semilla -- reproducible). CANCELADO usa el único
  `motivo_cancelacion` que el código real llega a escribir
  ("Cancelado por el pasajero", ver `viajes/service.py`) + `actor_cancelacion:
  "pasajero"`; no lleva `ts_inicio`/`ts_fin`/`tarifa_final`/`km_recorridos`
  (igual que un cancelado real, que nunca llega a ejecutarse).
- Filtro de calidad: se descartan filas con `trip_distance<=0` o fechas
  inválidas (dropoff<=pickup o duración>=1440min) -- misma regla Silver que
  `dag_historico_nyc.py`, para no sembrar viajes con datos de origen
  corruptos. Deja ~1,334,229 de 1,360,493 filas (mismo conteo que la capa
  analítica, coincidencia esperada: es la misma regla).
- `pagos`: un documento por cada viaje PAGADO (nunca por CANCELADO, igual
  que el flujo real -- un pago solo existe para un viaje FINALIZADO/PAGADO).
  `monto`=`tarifa_final` exacto -> `diferencia: None`, `estado: "VALIDADO"`
  siempre. No se fabrican discrepancias: no hay ninguna señal en el dataset
  NYC que justifique inventar un monto distinto al cobrado; las
  discrepancias reales (10 documentos ya sembrados a mano) siguen siendo la
  única fuente de esa métrica.

Diseño para 1.3M+ filas: streaming (`csv.DictReader`, nunca el archivo
completo en memoria), `bulk_write` con `UpdateOne(..., upsert=True)` en
lotes de `BATCH_SIZE`, `_id` determinista (`viaje-nyc-{fila:09d}` /
`pago-nyc-{fila:09d}`) -- idempotente, reejecutar el script no duplica.
Los índices de `viajes`/`pagos` ya existen (`ensure_indexes()`, corridos al
levantar el backend) y no se tocan aquí.

Uso (con el CSV real montado o accesible localmente):
    cd backend && ./.venv/Scripts/python.exe -m analytics.scripts.seed_viajes_nyc
o, si se corre como script suelto:
    python analytics/scripts/seed_viajes_nyc.py

Variables de entorno opcionales:
    CSV_PATH      default data/nyc_taxi/yellow_tripdata.csv (relativo al repo)
    MONGO_URI     default mongodb://localhost:27017/?replicaSet=rs0
    MONGO_DB_NAME default urbanflet
    BATCH_SIZE    default 8000
    MAX_ROWS      default sin límite -- para la prueba de checkpoint, poner
                  un valor chico (ej. 300) antes de correr el archivo completo
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

_repo_parents = Path(__file__).resolve().parents
REPO_ROOT = _repo_parents[2] if len(_repo_parents) > 2 else Path(".")
CSV_PATH = os.environ.get("CSV_PATH", str(REPO_ROOT / "data" / "nyc_taxi" / "yellow_tripdata.csv"))
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/?replicaSet=rs0")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "urbanflet")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "8000"))
MAX_ROWS = int(os.environ["MAX_ROWS"]) if os.environ.get("MAX_ROWS") else None
LOG_EVERY_N_BATCHES = 10

DURACION_MAX_MIN = 1440
QUEVEDO_LAT = -1.0225
QUEVEDO_LON = -79.4636
GUAYAQUIL_TZ = ZoneInfo("America/Guayaquil")
MOTIVO_CANCELACION = "Cancelado por el pasajero"

PAYMENT_MAP = {"1": "ELECTRONICO", "2": "EFECTIVO"}


def _num(v: str, default: float = 0.0) -> float:
    """El CSV real usa coma decimal ("2,34") -- normaliza antes de float()."""
    v = (v or "").strip()
    if not v:
        return default
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return default


def _parse_dt(v: str) -> datetime | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None


def _coord(location_id: str, numero_fila: int, sal: str) -> tuple[float, float]:
    """Coordenada sintética determinista anclada a Quevedo. `location_id`
    (PULocationID/DOLocationID) + numero_fila + `sal` (para diferenciar
    origen de destino) alimentan un hash -> ángulo + radio, nunca una
    coordenada NYC real."""
    h = hashlib.md5(f"{sal}:{location_id}:{numero_fila}".encode()).hexdigest()
    angulo = (int(h[:8], 16) % 3600) / 10.0
    radio = 0.004 + (int(h[8:12], 16) % 200) / 10000.0
    rad = math.radians(angulo)
    lat = QUEVEDO_LAT + radio * math.sin(rad)
    lon = QUEVEDO_LON + radio * math.cos(rad)
    return round(lat, 6), round(lon, 6)


def _es_cancelado(numero_fila: int) -> bool:
    h = hashlib.md5(f"cancelado:{numero_fila}".encode()).hexdigest()
    return (int(h[:4], 16) % 100) < 7


def _franja(ts: datetime) -> str:
    hora_local = ts.replace(tzinfo=ZoneInfo("UTC")).astimezone(GUAYAQUIL_TZ).hour
    return "DIURNA" if 5 <= hora_local < 22 else "NOCTURNA"


def _valido(pickup: datetime | None, dropoff: datetime | None, trip_distance: float) -> bool:
    if trip_distance <= 0:
        return False
    if pickup is None or dropoff is None:
        return False
    if dropoff <= pickup:
        return False
    if (dropoff - pickup).total_seconds() / 60.0 >= DURACION_MAX_MIN:
        return False
    return True


async def _cargar_pools(db) -> tuple[list[dict], list[str]]:
    pares: list[dict] = []
    async for u in db.usuarios.find({"roles": "conductor"}):
        veh = await db.vehiculos.find_one({"propietario_id": u["_id"]})
        if veh is None:
            continue
        pares.append(
            {
                "conductor_id": u["_id"],
                "conductor_nombre": u.get("nombre"),
                "conductor_calificacion": (u.get("conductor") or {}).get("calificacion_promedio"),
                "vehiculo_id": veh["_id"],
                "vehiculo_placa": veh.get("placa"),
                "vehiculo_marca": veh.get("marca"),
                "vehiculo_color": veh.get("color"),
            }
        )
    if not pares:
        raise RuntimeError("No hay pares conductor->vehiculo en Mongo -- sembrar usuarios de prueba primero.")

    pasajeros = [u["_id"] async for u in db.usuarios.find({"roles": "pasajero"}, {"_id": 1})]
    if not pasajeros:
        raise RuntimeError("No hay pasajeros de prueba en Mongo -- sembrar usuarios de prueba primero.")

    return pares, pasajeros


def _fila_a_documentos(numero_fila: int, r: dict, pares: list[dict], pasajeros: list[str]) -> tuple[dict, dict | None]:
    pickup = _parse_dt(r.get("tpep_pickup_datetime", ""))
    dropoff = _parse_dt(r.get("tpep_dropoff_datetime", ""))
    trip_distance = _num(r.get("trip_distance"))
    total_amount = _num(r.get("total_amount"))

    pasajero_id = pasajeros[numero_fila % len(pasajeros)]
    par = pares[numero_fila % len(pares)]

    origen_lat, origen_lon = _coord(r.get("PULocationID") or "0", numero_fila, "origen")
    destino_lat, destino_lon = _coord(r.get("DOLocationID") or "0", numero_fila, "destino")

    viaje_id = f"viaje-nyc-{numero_fila:09d}"
    cancelado = _es_cancelado(numero_fila)

    viaje = {
        "_id": viaje_id,
        "pasajero_id": pasajero_id,
        "conductor_id": par["conductor_id"],
        "vehiculo_id": par["vehiculo_id"],
        "conductor_nombre": par["conductor_nombre"],
        "conductor_calificacion": par["conductor_calificacion"],
        "vehiculo_placa": par["vehiculo_placa"],
        "vehiculo_marca": par["vehiculo_marca"],
        "vehiculo_color": par["vehiculo_color"],
        "origen_lat": origen_lat,
        "origen_lon": origen_lon,
        "origen_direccion": "Quevedo (siembra NYC)",
        "destino_lat": destino_lat,
        "destino_lon": destino_lon,
        "destino_direccion": "Quevedo (siembra NYC)",
        "zona_origen_id": None,
        "zona_destino_id": None,
        "franja": _franja(pickup),
        "tarifa_version_id": None,
        "tarifa_version_id_final": None,
        "ts_solicitud": pickup,
        "ts_asignacion": pickup,
        "ts_llegada_origen": pickup,
        "conductor_ofertado_id": None,
        "ts_oferta_emitida": None,
        "radio_actual_m": None,
        "radio_idx": 0,
        "ofertas_totales": 0,
        "conductores_descartados": [],
        "traza": [],
        "calificacion_pasajero_a_conductor": None,
        "calificacion_conductor_a_pasajero": None,
        "revision_tarifa": False,
        "tarifa_parcial": False,
    }

    if cancelado:
        viaje.update(
            {
                "estado": "CANCELADO",
                "ts_inicio": None,
                "ts_fin": None,
                "km_recorridos": None,
                "tarifa_estimada": None,
                "tarifa_final": None,
                "motivo_cancelacion": MOTIVO_CANCELACION,
                "actor_cancelacion": "pasajero",
            }
        )
        return viaje, None

    viaje.update(
        {
            "estado": "PAGADO",
            "ts_inicio": pickup,
            "ts_fin": dropoff,
            "km_recorridos": round(trip_distance * 1.60934, 3),
            "tarifa_estimada": total_amount,
            "tarifa_final": total_amount,
            "motivo_cancelacion": None,
            "actor_cancelacion": None,
        }
    )

    metodo = PAYMENT_MAP.get((r.get("payment_type") or "").strip(), "EFECTIVO")
    pago = {
        "_id": f"pago-nyc-{numero_fila:09d}",
        "viaje_id": viaje_id,
        "conductor_id": par["conductor_id"],
        "metodo": metodo,
        "monto": total_amount,
        "tarifa_final": total_amount,
        "diferencia": None,
        "referencia_externa": None,
        "estado": "VALIDADO",
        "ts_registro": dropoff,
        "ts_confirmacion": dropoff,
        "resuelto": False,
        "resolucion_motivo": None,
        "resolucion_aceptado": None,
        "resolucion_autorizador_id": None,
        "resolucion_ts": None,
    }
    return viaje, pago


async def main() -> None:
    t0 = time.time()
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB_NAME]

    pares, pasajeros = await _cargar_pools(db)
    print(f"Pools cargados: {len(pares)} pares conductor->vehiculo, {len(pasajeros)} pasajeros.")

    total_leidas = 0
    total_validas = 0
    total_descartadas = 0
    total_viajes_insertados = 0
    total_pagos_insertados = 0
    lote_viajes: list[UpdateOne] = []
    lote_pagos: list[UpdateOne] = []
    lote_num = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for numero_fila, r in enumerate(reader, start=1):
            if MAX_ROWS is not None and numero_fila > MAX_ROWS:
                break
            total_leidas += 1

            pickup = _parse_dt(r.get("tpep_pickup_datetime", ""))
            dropoff = _parse_dt(r.get("tpep_dropoff_datetime", ""))
            trip_distance = _num(r.get("trip_distance"))
            if not _valido(pickup, dropoff, trip_distance):
                total_descartadas += 1
                continue
            total_validas += 1

            viaje, pago = _fila_a_documentos(numero_fila, r, pares, pasajeros)
            lote_viajes.append(
                UpdateOne({"_id": viaje["_id"]}, {"$setOnInsert": viaje}, upsert=True)
            )
            if pago is not None:
                lote_pagos.append(
                    UpdateOne({"_id": pago["_id"]}, {"$setOnInsert": pago}, upsert=True)
                )

            if len(lote_viajes) >= BATCH_SIZE:
                res_v = await db.viajes.bulk_write(lote_viajes, ordered=False)
                total_viajes_insertados += res_v.upserted_count
                if lote_pagos:
                    res_p = await db.pagos.bulk_write(lote_pagos, ordered=False)
                    total_pagos_insertados += res_p.upserted_count
                lote_num += 1
                lote_viajes = []
                lote_pagos = []
                if lote_num % LOG_EVERY_N_BATCHES == 0:
                    transcurrido = time.time() - t0
                    velocidad = total_leidas / transcurrido if transcurrido > 0 else 0
                    print(
                        f"[lote {lote_num}] {total_leidas:,} leídas, {total_validas:,} válidas, "
                        f"{total_viajes_insertados:,} viajes insertados, {total_pagos_insertados:,} pagos insertados, "
                        f"{transcurrido:.0f}s transcurridos, {velocidad:.0f} filas/s"
                    )

    if lote_viajes:
        res_v = await db.viajes.bulk_write(lote_viajes, ordered=False)
        total_viajes_insertados += res_v.upserted_count
        if lote_pagos:
            res_p = await db.pagos.bulk_write(lote_pagos, ordered=False)
            total_pagos_insertados += res_p.upserted_count
        lote_num += 1

    dur = time.time() - t0
    print(
        f"Listo: {total_leidas:,} filas leídas, {total_validas:,} válidas "
        f"({total_descartadas:,} descartadas por DISTANCIA_CERO/FECHAS_INVALIDAS), "
        f"{lote_num} lotes, {dur:.0f}s totales."
    )
    print(f"Viajes insertados (nuevos): {total_viajes_insertados:,}. Pagos insertados (nuevos): {total_pagos_insertados:,}.")

    client.close()


if __name__ == "__main__":
    if "--help" in sys.argv:
        print(__doc__)
    else:
        asyncio.run(main())
