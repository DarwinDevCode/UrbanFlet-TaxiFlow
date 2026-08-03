"""Transacciones multi-documento de MongoDB — helper reutilizable.

Nace del hallazgo en Fase 1 (Captación): una cadena de escrituras que abarca
más de una entidad de negocio (decisión de solicitud + habilitación de
vehículo + asignación de rol) puede quedar parcialmente aplicada si algo
falla a mitad de camino, aunque cada escritura individual respete el
write-ahead de CU-O17. Este helper existe para que Fase 3 (despacho) y sobre
todo Fase 4 (pago → comisión → liquidación, con dinero real) puedan envolver
sus propias cadenas multi-documento sin reinventar el patrón.

Requiere que MongoDB corra como replica set, aunque sea de un solo nodo (ver
servicio `mongo-init` en docker-compose.yml) — las transacciones multi-
documento no existen en un `mongod` standalone.

`mongomock` (usado en toda la suite de pruebas por velocidad/portabilidad) no
implementa sesiones en absoluto: `client.start_session()` lanza
`NotImplementedError`. Por eso este helper detecta esa limitación en tiempo
de ejecución y, solo en ese caso, ejecuta el callback sin sesión —
exactamente el mismo comportamiento (secuencial, sin atomicidad) que tenía el
código antes de que existiera este helper, así que no rompe ningún test
existente. Contra un Mongo real la transacción sí es real: si el callback
lanza una excepción, MongoDB descarta todas las escrituras hechas con esa
sesión. La prueba de esta garantía real vive en
tests/core/test_db_transaction_integration.py, contra un Mongo de verdad
(mongomock no sirve para probar esto — no tiene rollback que probar).
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorClientSession

T = TypeVar("T")


async def with_transaction(
    client: AsyncIOMotorClient, callback: Callable[[AsyncIOMotorClientSession | None], Awaitable[T]]
) -> T:
    """Ejecuta `callback(session)` dentro de una transacción multi-documento.

    El callback debe pasar `session=session` a cada llamada de Mongo que
    quiera participar en la transacción (incluyendo las de
    `core/audit.write_audit_event`, que ya acepta ese parámetro). Si
    `session` es `None` (backend sin soporte de sesiones), simplemente no se
    pasa `session=` a esas llamadas — Motor/mongomock lo tratan como
    "sin sesión", el comportamiento normal.
    """
    try:
        session = await client.start_session()
    except NotImplementedError:
        return await callback(None)

    async with session:
        return await session.with_transaction(callback)
