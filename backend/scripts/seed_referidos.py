"""Inserta un conjunto pequeño de referidos ficticios pero coherentes en MongoDB.

No existe ningún caso de uso operativo en specs/nivel-operativo/ que respalde un
módulo de Referidos (el término solo aparece como ejemplo de `dim_canal` en
diseno_base_datos.md). Este script solo pobla la colección `referidos` con
datos de prueba referenciando usuarios reales de la base, para que el
pipeline ETL táctico tenga algo real que procesar.

Ampliado (demo con datos ricos): los 10 `REGISTROS` fijos originales se
mantienen literales (documentación/trazabilidad de la siembra inicial). Se
agregan además `REGISTROS_GENERADOS` -- pares determinísticos adicionales
sobre el pool real de usuarios pasajero/conductor ya presentes en Mongo en
el momento de la corrida (incluye los conductores nuevos que generó
`seed_solicitudes_demo.py` al aprobar solicitudes) -- hasta sumar ≥100
referidos en total. Mismo patrón de idempotencia que los 10 originales
(`_id` determinista + `$setOnInsert` + upsert), y respeta el índice único
`(referente_id, referido_id)` -- nunca genera un par repetido ni un
autoreferido.

Uso: python -m scripts.seed_referidos
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta

from src.core.db_mongo import get_database

CANALES_EXTRA = ["app", "web", "referido", "campaña", "whatsapp"]
ESTADOS_EXTRA = ["OTORGADO", "PENDIENTE", "NO_APLICA"]
OBJETIVO_TOTAL = 110  # >= 100 pedido, con margen

random.seed(20260803)

# (id, referente_id, referido_id, canal, estado_incentivo, fecha_referido) —
# ids fijos (deterministas) para que reejecutar el script sea idempotente;
# referente_id/referido_id tomados de usuarios reales ya presentes en la
# colección `usuarios` (pares pasajero->pasajero y conductor->conductor,
# coherentes con quién puede referir a quién).
REGISTROS = [
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000001",
        "referente_id": "a7e220a7-5129-4e58-9680-e78efb783e05",  # Juan Pérez (conductor)
        "referido_id": "58adf453-3078-4f5e-8e26-b60b72ca29b6",  # María López (pasajero)
        "canal": "app",
        "estado_incentivo": "OTORGADO",
        "fecha_referido": datetime(2026, 6, 3, 14, 22, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000002",
        "referente_id": "a7e220a7-5129-4e58-9680-e78efb783e05",  # Juan Pérez (conductor)
        "referido_id": "d27a0434-7921-431c-b811-942a8c4ae93a",  # Darwin (pasajero)
        "canal": "referido",
        "estado_incentivo": "PENDIENTE",
        "fecha_referido": datetime(2026, 6, 10, 9, 5, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000003",
        "referente_id": "d27a0434-7921-431c-b811-942a8c4ae93a",  # Darwin (pasajero)
        "referido_id": "b0cfeb42-93bb-4b0a-bf3e-c33ff53f24f7",  # Ronaldo (pasajero)
        "canal": "web",
        "estado_incentivo": "OTORGADO",
        "fecha_referido": datetime(2026, 6, 18, 18, 47, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000004",
        "referente_id": "58adf453-3078-4f5e-8e26-b60b72ca29b6",  # María López (pasajero)
        "referido_id": "7984b24b-b348-4b4f-9660-30b0b11e6cfc",  # Khriz (pasajero)
        "canal": "campaña",
        "estado_incentivo": "NO_APLICA",
        "fecha_referido": datetime(2026, 7, 1, 11, 30, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000005",
        "referente_id": "b0cfeb42-93bb-4b0a-bf3e-c33ff53f24f7",  # Ronaldo (pasajero)
        "referido_id": "37242d0f-323c-4f69-a155-775d9358b83f",  # Pasajera Prueba
        "canal": "app",
        "estado_incentivo": "PENDIENTE",
        "fecha_referido": datetime(2026, 7, 9, 20, 12, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000006",
        "referente_id": "7984b24b-b348-4b4f-9660-30b0b11e6cfc",  # Khriz (pasajero)
        "referido_id": "bf1c76db-3082-421b-837f-9b168da4599a",  # Smoke Test (conductor)
        "canal": "web",
        "estado_incentivo": "OTORGADO",
        "fecha_referido": datetime(2026, 7, 15, 8, 3, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000007",
        "referente_id": "a7e220a7-5129-4e58-9680-e78efb783e05",  # Juan Pérez (conductor)
        "referido_id": "ad451c06-9d4a-4d39-ba5f-cf4582d9a8ab",  # Pasajero Email
        "canal": "referido",
        "estado_incentivo": "PENDIENTE",
        "fecha_referido": datetime(2026, 7, 22, 16, 40, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000008",
        "referente_id": "37242d0f-323c-4f69-a155-775d9358b83f",  # Pasajera Prueba
        "referido_id": "5412b9e3-78a4-4563-ac54-833d6da7d48b",  # Pasajera Slice1
        "canal": "campaña",
        "estado_incentivo": "OTORGADO",
        "fecha_referido": datetime(2026, 8, 1, 7, 55, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000009",
        "referente_id": "a7e220a7-5129-4e58-9680-e78efb783e05",  # Juan Pérez (conductor)
        "referido_id": "8288728d-69c7-445e-9d3a-b3927b51ad38",  # Postulante QA Panel (conductor)
        "canal": "app",
        "estado_incentivo": "NO_APLICA",
        "fecha_referido": datetime(2026, 8, 1, 9, 10, tzinfo=UTC),
    },
    {
        "_id": "e1a2b3c4-1111-4a2b-8c3d-000000000010",
        "referente_id": "d27a0434-7921-431c-b811-942a8c4ae93a",  # Darwin (pasajero)
        "referido_id": "3f26c091-2e17-4b6f-a7e9-c800815f0829",  # Verificador Mapa Conductor (pasajero)
        "canal": "whatsapp",
        "estado_incentivo": "PENDIENTE",
        "fecha_referido": datetime(2026, 8, 1, 15, 30, tzinfo=UTC),
    },
]


async def _generar_registros_extra(db, ya_usados: set[tuple[str, str]], faltan: int) -> list[dict]:
    """Genera `faltan` referidos adicionales deterministas sobre el pool real
    de usuarios pasajero/conductor presente en Mongo -- incluye los
    conductores nuevos que aprobó `seed_solicitudes_demo.py`. `ya_usados`
    trae los pares (referente_id, referido_id) de `REGISTROS` para no
    duplicar contra el índice único."""
    pool = [u["_id"] async for u in db.usuarios.find({"roles": {"$in": ["pasajero", "conductor"]}}, {"_id": 1})]
    if len(pool) < 2:
        return []

    generados: list[dict] = []
    intentos = 0
    while len(generados) < faltan and intentos < faltan * 20:
        intentos += 1
        referente_id, referido_id = random.sample(pool, 2)
        par = (referente_id, referido_id)
        if par in ya_usados:
            continue
        ya_usados.add(par)
        indice = len(generados)
        dias_atras = random.randint(0, 150)
        generados.append(
            {
                "_id": f"e1a2b3c4-2222-4a2b-8c3d-{indice:012d}",
                "referente_id": referente_id,
                "referido_id": referido_id,
                "canal": random.choice(CANALES_EXTRA),
                "estado_incentivo": random.choice(ESTADOS_EXTRA),
                "fecha_referido": datetime.now(UTC) - timedelta(days=dias_atras),
            }
        )
    return generados


async def seed_referidos() -> None:
    db = get_database()

    await db.referidos.create_index([("referente_id", 1), ("referido_id", 1)], unique=True)

    ya_usados = {(r["referente_id"], r["referido_id"]) for r in REGISTROS}
    faltan = max(0, OBJETIVO_TOTAL - len(REGISTROS))
    registros_extra = await _generar_registros_extra(db, ya_usados, faltan)
    todos = REGISTROS + registros_extra

    insertados = 0
    for registro in todos:
        resultado = await db.referidos.update_one(
            {"_id": registro["_id"]},
            {"$setOnInsert": registro},
            upsert=True,
        )
        if resultado.upserted_id is not None:
            insertados += 1

    print(f"Referidos insertados: {insertados}/{len(todos)} (resto ya existía).")


if __name__ == "__main__":
    asyncio.run(seed_referidos())
