"""Script de preparación única del dataset semilla NYC (no forma parte del pipeline).

Toma el CSV real descargado de NYC Open Data (2yzn-sicd, yellow taxi agosto 2015)
y le agrega deliberadamente un ~3% de filas corruptas -- una por cada regla Silver
de CU-O15 -- para poder demostrar en un solo lote tanto la cuarentena como la
alerta WARN por >1% de rechazo. El dataset real descargado no trae registros
inválidos garantizados, así que esta contaminación controlada es necesaria para
probar el camino alterno A2 con datos reales de origen.
"""

import csv
import copy
import random

random.seed(42)

SRC = "nyc_yellow_tripdata_2015-08_sample.csv"
DST = "nyc_yellow_tripdata_2015-08_seed.csv"

with open(SRC, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

n = len(rows)
target_corrupt = int(n * 0.03)  # ~3%, por encima del umbral de WARN (>1%)
idx_pool = list(range(n))
random.shuffle(idx_pool)

corrupt_idx = idx_pool[:target_corrupt]
buckets = [corrupt_idx[i::4] for i in range(4)]  # 4 categorías de corrupción

for i in buckets[0]:
    rows[i]["trip_distance"] = "0"  # DISTANCIA_CERO

for i in buckets[1]:
    # FECHAS_INVALIDAS: dropoff antes que pickup
    rows[i]["dropoff_datetime"], rows[i]["pickup_datetime"] = (
        rows[i]["pickup_datetime"],
        rows[i]["dropoff_datetime"],
    )

for i in buckets[2]:
    # ERROR_MONTO: total_amount no coincide con la suma de componentes
    rows[i]["total_amount"] = str(float(rows[i]["total_amount"]) + 500)

dup_rows = []
for i in buckets[3]:
    # No duplicado: se duplica la fila tal cual (mismo id_origen derivado)
    dup_rows.append(copy.deepcopy(rows[i]))

rows_out = rows + dup_rows
random.shuffle(rows_out)

for i, r in enumerate(rows_out):
    r["id_origen"] = f"nyc-2015-08-{i:06d}" if r not in dup_rows else r.get("id_origen", "")

# Asignar id_origen determinístico ANTES de mezclar duplicados: se reconstruye
# a partir de una clave estable (pickup_datetime+dropoff_datetime+vendor_id+
# trip_distance) para que la fila duplicada comparta el mismo id_origen que su
# original, tal como exige la regla de deduplicación.
for r in rows_out:
    key = f"{r['vendor_id']}|{r['pickup_datetime']}|{r['dropoff_datetime']}|{r['trip_distance']}|{r['pickup_longitude']}|{r['pickup_latitude']}"
    r["id_origen"] = str(abs(hash(key)) % (10**12))

fieldnames_out = fieldnames + ["id_origen"]
with open(DST, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames_out)
    writer.writeheader()
    writer.writerows(rows_out)

print(f"filas originales: {n}")
print(f"filas corruptas inyectadas: {target_corrupt} ({target_corrupt/n:.1%})")
print(f"duplicados agregados: {len(dup_rows)}")
print(f"total filas en semilla: {len(rows_out)}")
