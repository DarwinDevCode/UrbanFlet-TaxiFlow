"""Carga el dataset crudo NYC Yellow Taxi (2021, ~1.3M filas) completo a la
colección PocketBase `raw_trips`, sin muestreo (exigencia del docente).

Decisión de diseño (ver CLAUDE.md, sección de cambio de arquitectura):
escribe directo al archivo SQLite de PocketBase (`pb_data/data.db`, tabla
`raw_trips`) en vez de usar la API REST — a 1.3M filas, ~2600+ round-trips
HTTP (aun agrupados en lotes de 500) tardarían horas y son frágiles
(expiración de token, reintentos). Un `executemany` de sqlite3 con commits
periódicos carga el mismo volumen en minutos. Requiere que el contenedor
`pocketbase` esté DETENIDO mientras corre (SQLite + WAL no está pensado para
que un proceso externo escriba miles de filas mientras el servidor real
también escribe) -- el script no lo detiene por sí mismo, ver
`analytics/scripts/README.md` para el procedimiento completo.

Idempotente: `id` es determinista (`nyc{numero_de_fila:09d}`, generado a
partir de la posición de la fila en el CSV, no de un random) e
`INSERT OR IGNORE` -- reejecutar el script no duplica filas.

Uso (con el contenedor pocketbase detenido y este volumen montado en
/pb_data, y el CSV en /data):
    python3 load_raw_trips_pocketbase.py

Variables de entorno opcionales:
    PB_DB_PATH   default /pb_data/data.db
    CSV_PATH     default /data/yellow_tripdata.csv
    BATCH_SIZE   default 10000
"""

from __future__ import annotations

import csv
import os
import sqlite3
import time
from datetime import datetime

PB_DB_PATH = os.environ.get("PB_DB_PATH", "/pb_data/data.db")
CSV_PATH = os.environ.get("CSV_PATH", "/data/yellow_tripdata.csv")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10000"))
LOG_EVERY_N_BATCHES = 10


def _num(v: str, default: float = 0.0) -> float:
    """El CSV usa coma como separador decimal ("2,34") -- normaliza antes de float()."""
    v = (v or "").strip()
    if not v:
        return default
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return default


def _pb_datetime(v: str) -> str:
    """'01/01/2021 03:19:25 PM' -> '2021-01-01 15:19:25.000Z' (formato PocketBase)."""
    v = (v or "").strip()
    if not v:
        return ""
    dt = datetime.strptime(v, "%m/%d/%Y %I:%M:%S %p")
    return dt.strftime("%Y-%m-%d %H:%M:%S.000Z")


COLUMNS = (
    "id", "vendor_id", "pickup_datetime", "dropoff_datetime", "passenger_count",
    "trip_distance", "ratecode_id", "store_and_fwd_flag", "pu_location_id",
    "do_location_id", "payment_type", "fare_amount", "extra", "mta_tax",
    "tip_amount", "tolls_amount", "improvement_surcharge", "total_amount",
    "congestion_surcharge",
)

INSERT_SQL = f"""
INSERT OR IGNORE INTO raw_trips ({", ".join(f'`{c}`' for c in COLUMNS)})
VALUES ({", ".join("?" for _ in COLUMNS)})
"""


def _fila_a_tupla(numero_fila: int, r: dict) -> tuple:
    return (
        f"nyc{numero_fila:09d}",
        r.get("VendorID") or "",
        _pb_datetime(r.get("tpep_pickup_datetime", "")),
        _pb_datetime(r.get("tpep_dropoff_datetime", "")),
        _num(r.get("passenger_count")),
        _num(r.get("trip_distance")),
        r.get("RatecodeID") or "",
        r.get("store_and_fwd_flag") or "",
        r.get("PULocationID") or "",
        r.get("DOLocationID") or "",
        r.get("payment_type") or "",
        _num(r.get("fare_amount")),
        _num(r.get("extra")),
        _num(r.get("mta_tax")),
        _num(r.get("tip_amount")),
        _num(r.get("tolls_amount")),
        _num(r.get("improvement_surcharge")),
        _num(r.get("total_amount")),
        _num(r.get("congestion_surcharge")),
    )


def main() -> None:
    t0 = time.time()
    conn = sqlite3.connect(PB_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    total_insertadas = 0
    total_leidas = 0
    lote: list[tuple] = []
    lote_num = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for numero_fila, r in enumerate(reader, start=1):
            lote.append(_fila_a_tupla(numero_fila, r))
            total_leidas += 1

            if len(lote) >= BATCH_SIZE:
                cur.executemany(INSERT_SQL, lote)
                conn.commit()
                total_insertadas += cur.rowcount if cur.rowcount != -1 else len(lote)
                lote_num += 1
                lote = []
                if lote_num % LOG_EVERY_N_BATCHES == 0:
                    transcurrido = time.time() - t0
                    velocidad = total_leidas / transcurrido if transcurrido > 0 else 0
                    print(
                        f"[lote {lote_num}] {total_leidas:,} filas leídas, "
                        f"{transcurrido:.0f}s transcurridos, {velocidad:.0f} filas/s"
                    )

        if lote:
            cur.executemany(INSERT_SQL, lote)
            conn.commit()
            lote_num += 1

    conn.close()
    dur = time.time() - t0
    print(f"Listo: {total_leidas:,} filas leídas del CSV en {lote_num} lotes, {dur:.0f}s totales.")


if __name__ == "__main__":
    main()
