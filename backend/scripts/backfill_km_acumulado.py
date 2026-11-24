"""Flujo de fallas — Ronda 2, Fase B (H7): backfill de `vehiculos.km_acumulado`
a partir de los viajes ya cerrados.

Estado real antes de este backfill (confirmado en la auditoría de la
propuesta): el campo `km_acumulado` existe en el esquema de `vehiculos`
desde siempre, pero **nada lo escribía** -- los 81 vehículos reales del
entorno de desarrollo estaban en 0. `viajes/service_finalizacion.py::
finalizar_viaje` ahora alimenta el campo hacia adelante (`$inc` en cada
viaje finalizado); este script cubre el histórico ya cerrado antes de ese
cambio.

Idempotente por construcción: `$set` a un valor absoluto recalculado desde
cero (suma de `km_recorridos` de todos los viajes FINALIZADO/PAGADO de cada
vehículo), no `$inc` -- reejecutar el script no duplica nada, siempre
converge al mismo total mientras no haya viajes nuevos cerrados entre
corridas (y si los hay, el recálculo los incluye correctamente).

Uso: python -m scripts.backfill_km_acumulado
"""

import asyncio

from src.core.db_mongo import get_database

ESTADOS_CERRADOS = ["FINALIZADO", "PAGADO"]


async def backfill_km_acumulado() -> None:
    db = get_database()

    pipeline = [
        {"$match": {"estado": {"$in": ESTADOS_CERRADOS}, "vehiculo_id": {"$ne": None}}},
        {"$group": {"_id": "$vehiculo_id", "km_total": {"$sum": {"$ifNull": ["$km_recorridos", 0]}}}},
    ]
    totales = {doc["_id"]: doc["km_total"] async for doc in db.viajes.aggregate(pipeline)}

    actualizados = 0
    async for vehiculo in db.vehiculos.find({}, {"_id": 1}):
        km_total = round(totales.get(vehiculo["_id"], 0.0), 3)
        resultado = await db.vehiculos.update_one({"_id": vehiculo["_id"]}, {"$set": {"km_acumulado": km_total}})
        if resultado.modified_count:
            actualizados += 1

    total_vehiculos = await db.vehiculos.count_documents({})
    print(f"km_acumulado recalculado para {total_vehiculos} vehículos ({actualizados} con cambio real de valor).")
    print(f"Vehículos con viajes cerrados que aportan km: {len(totales)}.")


if __name__ == "__main__":
    asyncio.run(backfill_km_acumulado())
