"""Backfill de `fecha_registro` para cuentas creadas directo en Mongo antes
de que `crear_cuenta_staff`/el registro de pasajero lo hicieran obligatorio.

Hallazgo real (ronda de usabilidad de admin_sistema, punto #5, 2026-08-07):
al construir el buscador de usuarios (`UserPicker`), una búsqueda por texto
real reventó `GET /usuarios` con `KeyError: 'fecha_registro'` -- 5 cuentas
de demo/QA (incluida `staff-verificacion`, la cuenta que acumula los 7
roles tácticos) fueron insertadas a mano en sesiones anteriores sin ese
campo. La fecha real de alta de esas cuentas no se puede recuperar -- se
usa el instante del backfill, documentado como tal en vez de simular un
dato que no existe. Idempotente: solo toca documentos sin el campo.

Uso: python -m scripts.backfill_fecha_registro
"""

import asyncio
from datetime import datetime, UTC

from src.core.db_mongo import get_database


async def main() -> None:
    db = get_database()
    ahora = datetime.now(UTC)

    faltantes = await db.usuarios.find({"fecha_registro": {"$exists": False}}, {"_id": 1, "nombre": 1}).to_list(
        length=1000
    )
    for u in faltantes:
        print(f"backfill: {u['_id']} ({u.get('nombre')})")

    resultado = await db.usuarios.update_many(
        {"fecha_registro": {"$exists": False}}, {"$set": {"fecha_registro": ahora}}
    )
    print(f"usuarios actualizados: {resultado.modified_count}")


if __name__ == "__main__":
    asyncio.run(main())
