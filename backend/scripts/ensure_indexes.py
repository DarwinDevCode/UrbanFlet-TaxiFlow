"""Ejecuta la creación de índices mínimos fuera del ciclo de vida de FastAPI.

Uso: python -m scripts.ensure_indexes
(también se ejecuta automáticamente en el startup de la app, ver src/main.py)
"""

import asyncio

from src.core.db_mongo import ensure_indexes


if __name__ == "__main__":
    asyncio.run(ensure_indexes())
    print("Índices verificados/creados.")
