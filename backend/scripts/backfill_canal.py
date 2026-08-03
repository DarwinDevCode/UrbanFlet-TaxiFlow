"""Backfill de `canal` para registros de `solicitudes` y `usuarios` creados
antes de que ese campo existiera (CU-T01/T02, specs/nivel-tactico/tactico_captacion.md).

Ninguno de los 2 frontends pedía canal de adquisición hasta ahora -- los
registros existentes se completan con el valor por defecto "web" (mismo
default que ahora aplican `SolicitudCrearRequest`/`PasajeroRegistroRequest`
para altas nuevas). Idempotente: solo toca documentos sin el campo.

Uso: python -m scripts.backfill_canal
"""

import asyncio

from src.core.db_mongo import get_database


async def main() -> None:
    db = get_database()

    resultado_solicitudes = await db.solicitudes.update_many(
        {"canal": {"$exists": False}}, {"$set": {"canal": "web"}}
    )
    resultado_usuarios = await db.usuarios.update_many({"canal": {"$exists": False}}, {"$set": {"canal": "web"}})

    print(f"solicitudes actualizadas: {resultado_solicitudes.modified_count}")
    print(f"usuarios actualizados: {resultado_usuarios.modified_count}")


if __name__ == "__main__":
    asyncio.run(main())
