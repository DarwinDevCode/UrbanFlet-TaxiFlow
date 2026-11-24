"""Catálogos — Ronda 1 (Ola 0.2 + Ola 1.5): siembra idempotente de los 4
catálogos existentes (`talleres`, `tipos_documento`, `motivos_cancelacion`
categoría `cancelacion` e `incidencia`) con valores derivados de los datos
reales medidos en AUDITORIA_UX_CATALOGOS.md, más los 2 catálogos nuevos de
esta ronda (`marcas_vehiculo`, `colores_vehiculo`).

Estado real antes de correr este script (verificado en la auditoría): los 4
catálogos existentes tenían exactamente 1 registro de prueba cada uno
("Taller QA Cache", "Prueba motivo", "Prueba documento", "Prueba" en
`zonas`) y ninguno de los valores reales que ya circulan en `ordenes.taller`
o `documentos.tipo`. Este script:
1. Inserta los valores reales (idempotente: `$setOnInsert` + `_id`
   determinista, reejecutar el script no duplica ni pisa ediciones
   posteriores del administrador).
2. Borra los 4 registros de prueba -- incluido `zonas` (colección
   `parametros/zonas`, no `catalogos/`), aunque ese catálogo no se resiembra
   en esta ronda (fuera de alcance de Catálogos Ronda 1).

Uso: python -m scripts.seed_catalogos_ronda1
"""

import asyncio
import uuid

from src.core.db_mongo import get_database

# _id deterministas (uuid5 sobre un namespace fijo + el nombre) -- mismo
# efecto práctico que un _id fijo escrito a mano, sin tener que inventar 18
# UUIDs random y pegarlos.
_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def _id_para(coleccion: str, nombre: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{coleccion}:{nombre}"))


TALLERES = [
    {"nombre": "Taller Central", "direccion": "", "telefono": "", "url_maps": None, "activo": True},
    {"nombre": "Taller Norte", "direccion": "", "telefono": "", "url_maps": None, "activo": True},
    {"nombre": "Lubricadora Express", "direccion": "", "telefono": "", "url_maps": None, "activo": True},
    {"nombre": "Taller El Motor", "direccion": "", "telefono": "", "url_maps": None, "activo": True},
    {"nombre": "Servicio Rápido Quevedo", "direccion": "", "telefono": "", "url_maps": None, "activo": True},
]

# aplica_a coincide con el uso real observado: LICENCIA_CONDUCIR es del
# conductor, MATRICULA_VEHICULAR es del vehículo (71/71 documentos reales
# en cada categoría, ver auditoría §2 hallazgo H2/mina latente §3).
TIPOS_DOCUMENTO = [
    {"nombre": "LICENCIA_CONDUCIR", "descripcion": "Licencia de conducir vigente", "aplica_a": "conductor"},
    {"nombre": "MATRICULA_VEHICULAR", "descripcion": "Matrícula del vehículo vigente", "aplica_a": "vehiculo"},
]

MOTIVOS_CANCELACION = [
    {"nombre": "Pasajero ausente (NO_SHOW)", "descripcion": "", "categoria": "cancelacion"},
    {"nombre": "Cancelado por el pasajero", "descripcion": "", "categoria": "cancelacion"},
    {"nombre": "Cancelado en camino", "descripcion": "", "categoria": "cancelacion"},
    {"nombre": "Incidencia en ruta", "descripcion": "", "categoria": "cancelacion"},
    {"nombre": "Vehículo averiado", "descripcion": "", "categoria": "cancelacion"},
    {"nombre": "Avería mecánica", "descripcion": "", "categoria": "incidencia"},
    {"nombre": "Siniestro/choque", "descripcion": "", "categoria": "incidencia"},
    {"nombre": "Falla eléctrica", "descripcion": "", "categoria": "incidencia"},
    {"nombre": "Neumático", "descripcion": "", "categoria": "incidencia"},
    {"nombre": "Otro", "descripcion": "", "categoria": "incidencia"},
]

MARCAS_VEHICULO = ["Kia", "Toyota", "Chevrolet", "Nissan", "Hyundai", "Suzuki"]
COLORES_VEHICULO = ["Blanco", "Negro", "Azul", "Rojo", "Plata", "Gris", "Amarillo"]

# Los 4 registros de prueba que la auditoría encontró -- se borran como
# parte de la misma limpieza, no se resiembran.
REGISTROS_DE_PRUEBA = [
    ("talleres", {"nombre": "Taller QA Cache"}),
    ("motivos_cancelacion", {"nombre": "Prueba motivo"}),
    ("tipos_documento", {"nombre": "Prueba documento"}),
    ("zonas", {"nombre": "Prueba"}),
]


async def _upsert(db, coleccion: str, nombre: str, extra: dict) -> bool:
    doc = {"_id": _id_para(coleccion, nombre), "nombre": nombre, "activo": True, **extra}
    resultado = await db[coleccion].update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
    return resultado.upserted_id is not None


async def seed_catalogos_ronda1() -> None:
    db = get_database()

    insertados = 0
    for t in TALLERES:
        extra = {k: v for k, v in t.items() if k != "nombre"}
        if await _upsert(db, "talleres", t["nombre"], extra):
            insertados += 1

    for t in TIPOS_DOCUMENTO:
        extra = {k: v for k, v in t.items() if k != "nombre"}
        if await _upsert(db, "tipos_documento", t["nombre"], extra):
            insertados += 1

    for m in MOTIVOS_CANCELACION:
        extra = {k: v for k, v in m.items() if k != "nombre"}
        if await _upsert(db, "motivos_cancelacion", m["nombre"], extra):
            insertados += 1

    for nombre in MARCAS_VEHICULO:
        if await _upsert(db, "marcas_vehiculo", nombre, {}):
            insertados += 1

    for nombre in COLORES_VEHICULO:
        if await _upsert(db, "colores_vehiculo", nombre, {}):
            insertados += 1

    print(f"Catálogos sembrados: {insertados} registros nuevos (resto ya existía).")

    borrados = 0
    for coleccion, filtro in REGISTROS_DE_PRUEBA:
        resultado = await db[coleccion].delete_many(filtro)
        borrados += resultado.deleted_count

    print(f"Registros de prueba borrados: {borrados}.")


if __name__ == "__main__":
    asyncio.run(seed_catalogos_ronda1())
