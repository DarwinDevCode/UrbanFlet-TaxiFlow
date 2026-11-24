"""Catálogos — Ola 3 (PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md §3.2): siembra
idempotente del catálogo `repuestos`.

A diferencia de `seed_catalogos_ronda1.py`, esta siembra no deriva de datos
reales medidos (la propia propuesta documentó "solo 3 entradas humanas
reales" al momento de la auditoría) -- es un catálogo de referencia
razonable para el dominio real del sistema (flota de taxis urbanos, sedanes
compactos), con nombres y precios de referencia creíbles por categoría, no
placeholders genéricos. Precios en USD (moneda real del resto del sistema
-- tarifas, pagos, liquidaciones -- todas ya en USD).

Uso: python -m scripts.seed_repuestos
"""

import asyncio
import uuid

from src.core.db_mongo import get_database

_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def _id_para(nombre: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"repuestos:{nombre}"))


REPUESTOS = [
    # Motor
    {"nombre": "Filtro de aceite", "categoria": "Motor", "precio_referencial": 8.50, "unidad": "unidad"},
    {"nombre": "Filtro de aire", "categoria": "Motor", "precio_referencial": 12.00, "unidad": "unidad"},
    {"nombre": "Filtro de combustible", "categoria": "Motor", "precio_referencial": 15.00, "unidad": "unidad"},
    {"nombre": "Aceite de motor 20W-50", "categoria": "Motor", "precio_referencial": 6.50, "unidad": "litro"},
    {"nombre": "Bujías (juego de 4)", "categoria": "Motor", "precio_referencial": 28.00, "unidad": "juego"},
    {"nombre": "Correa de distribución", "categoria": "Motor", "precio_referencial": 45.00, "unidad": "unidad"},
    # Frenos
    {
        "nombre": "Pastillas de freno delanteras (juego)",
        "categoria": "Frenos",
        "precio_referencial": 35.00,
        "unidad": "juego",
    },
    {
        "nombre": "Pastillas de freno traseras (juego)",
        "categoria": "Frenos",
        "precio_referencial": 30.00,
        "unidad": "juego",
    },
    {"nombre": "Disco de freno delantero", "categoria": "Frenos", "precio_referencial": 40.00, "unidad": "unidad"},
    {"nombre": "Líquido de frenos DOT4", "categoria": "Frenos", "precio_referencial": 9.00, "unidad": "litro"},
    # Eléctrico
    {"nombre": "Batería 12V 60Ah", "categoria": "Eléctrico", "precio_referencial": 85.00, "unidad": "unidad"},
    {"nombre": "Alternador", "categoria": "Eléctrico", "precio_referencial": 120.00, "unidad": "unidad"},
    {"nombre": "Foco delantero H4", "categoria": "Eléctrico", "precio_referencial": 7.50, "unidad": "unidad"},
    {
        "nombre": "Bomba de combustible eléctrica",
        "categoria": "Eléctrico",
        "precio_referencial": 55.00,
        "unidad": "unidad",
    },
    # Suspensión
    {"nombre": "Amortiguador delantero", "categoria": "Suspensión", "precio_referencial": 48.00, "unidad": "unidad"},
    {"nombre": "Amortiguador trasero", "categoria": "Suspensión", "precio_referencial": 42.00, "unidad": "unidad"},
    {"nombre": "Rótula de suspensión", "categoria": "Suspensión", "precio_referencial": 22.00, "unidad": "unidad"},
    # Neumáticos
    {"nombre": "Neumático 185/65 R15", "categoria": "Neumáticos", "precio_referencial": 65.00, "unidad": "unidad"},
    {"nombre": "Válvula de neumático", "categoria": "Neumáticos", "precio_referencial": 3.50, "unidad": "unidad"},
]


async def _upsert(db, nombre: str, extra: dict) -> bool:
    doc = {"_id": _id_para(nombre), "nombre": nombre, "activo": True, **extra}
    resultado = await db.repuestos.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
    return resultado.upserted_id is not None


async def seed_repuestos() -> None:
    db = get_database()

    insertados = 0
    for r in REPUESTOS:
        extra = {k: v for k, v in r.items() if k != "nombre"}
        if await _upsert(db, r["nombre"], extra):
            insertados += 1

    total = await db.repuestos.count_documents({})
    print(f"Repuestos sembrados: {insertados} registros nuevos (resto ya existía). Total en catálogo: {total}.")


if __name__ == "__main__":
    asyncio.run(seed_repuestos())
