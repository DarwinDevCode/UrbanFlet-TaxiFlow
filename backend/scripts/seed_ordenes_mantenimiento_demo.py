"""Siembra órdenes de mantenimiento ricas para demo (CU-O12/CU-O13), vía el
servicio real (`mantenimiento.service`) en vez de insertar documentos a
mano -- cada orden pasa por las mismas transacciones que usaría el endpoint
real (retiro/habilitación de vehículo cuando aplica), con auditoría
write-ahead real.

Distribución de estado (130 órdenes sobre el pool real de vehículos --
incluye los 70 que generó `seed_solicitudes_demo.py` al aprobar
solicitudes, además de los 5 originales):
    ABIERTA    25  (creada, sin más acción)
    EN_TALLER  20  (creada + marcada en taller)
    CERRADA    65  (creada + en taller + cerrada, con costo/horas/km reales)
    ANULADA    20  (creada + anulada, con motivo)

Tipo PREVENTIVA/CORRECTIVA mezclado. `fecha_programada` distribuida en los
últimos 150 días (pasado) y próximos 30 días (futuro cercano, para que
"cumplimiento preventivo" tenga variación real de vencidas/a tiempo).

Idempotente: cada orden lleva una marca `SEED-DEMO-{índice:05d}:` al inicio
de `descripcion` -- si ya existe una orden con esa marca, se salta.

Uso: cd backend && ./.venv/Scripts/python.exe -m scripts.seed_ordenes_mantenimiento_demo
"""

import asyncio
import random
from datetime import UTC, date, datetime, timedelta

from src.core.db_mongo import get_database
from src.core.notifications import NoopNotificationDispatcher
from src.mantenimiento import schemas, service

ACTOR_ID = "staff-verificacion"
ACTOR_ROL = "jefe_mantenimiento"

TALLERES = ["Taller Central", "Taller Norte", "Lubricadora Express", "Servicio Rápido Quevedo", "Taller El Motor"]
TIPOS: list[schemas.TipoOrden] = ["PREVENTIVA", "CORRECTIVA"]
DESCRIPCIONES_PREVENTIVA = ["Cambio de aceite y filtros", "Revisión de frenos programada", "Rotación de llantas", "Chequeo de 5000 km"]
DESCRIPCIONES_CORRECTIVA = ["Falla eléctrica en luces", "Ruido en suspensión delantera", "Fuga de líquido de frenos", "Motor no enciende en frío"]

random.seed(20260803)


def _distribucion(n: int) -> list[str]:
    conteos = {"ABIERTA": 25, "EN_TALLER": 20, "ANULADA": 20, "CERRADA": n - 65}
    estados = [e for e, c in conteos.items() for _ in range(c)]
    random.shuffle(estados)
    return estados


async def main() -> None:
    db = get_database()
    dispatcher = NoopNotificationDispatcher()

    vehiculos = [v["_id"] async for v in db.vehiculos.find({}, {"_id": 1})]
    if not vehiculos:
        print("No hay vehículos en Mongo -- correr seed_solicitudes_demo.py primero.")
        return

    n = 130
    estados = _distribucion(n)

    creadas = 0
    saltadas = 0
    contadores = {"ABIERTA": 0, "EN_TALLER": 0, "CERRADA": 0, "ANULADA": 0}

    for i in range(n):
        marca = f"SEED-DEMO-{i:05d}:"
        existente = await db.ordenes.find_one({"descripcion": {"$regex": f"^{marca}"}})
        if existente is not None:
            saltadas += 1
            continue

        tipo = TIPOS[i % 2]
        base_desc = random.choice(DESCRIPCIONES_PREVENTIVA if tipo == "PREVENTIVA" else DESCRIPCIONES_CORRECTIVA)
        vehiculo_id = vehiculos[i % len(vehiculos)]
        km_entrada = 5000 + (i * 137) % 60000
        dias_offset = random.randint(-150, 30)
        fecha_programada = date.today() + timedelta(days=dias_offset)
        estado_objetivo = estados[i]

        orden = await service.crear_orden(
            db,
            dispatcher,
            actor_id=ACTOR_ID,
            actor_rol=ACTOR_ROL,
            vehiculo_id=vehiculo_id,
            tipo=tipo,
            descripcion=f"{marca} {base_desc}",
            km_entrada=km_entrada,
            taller=random.choice(TALLERES),
            fecha_programada=fecha_programada,
            retirar_vehiculo=(estado_objetivo in ("EN_TALLER", "CERRADA")),
            repuestos_estimados=[
                schemas.RepuestoInput(descripcion="Repuesto estimado A", cantidad=1, costo_unitario=round(random.uniform(10, 80), 2))
            ],
        )
        creadas += 1
        contadores["ABIERTA"] += 1

        # Retro-fechar la orden para que no todas queden "creadas ahora".
        await db.ordenes.update_one({"_id": orden["_id"]}, {"$set": {"fecha_programada": fecha_programada.isoformat()}})

        if estado_objetivo == "ABIERTA":
            continue

        if estado_objetivo == "ANULADA":
            await service.anular_orden(db, actor_id=ACTOR_ID, actor_rol=ACTOR_ROL, orden_id=orden["_id"], motivo="Vehículo dado de baja antes de iniciar el trabajo.")
            contadores["ABIERTA"] -= 1
            contadores["ANULADA"] += 1
            continue

        await service.marcar_en_taller(db, orden_id=orden["_id"])
        contadores["ABIERTA"] -= 1
        contadores["EN_TALLER"] += 1

        if estado_objetivo == "EN_TALLER":
            continue

        km_salida = km_entrada + random.randint(0, 500)
        await service.cerrar_orden(
            db,
            dispatcher,
            actor_id=ACTOR_ID,
            actor_rol=ACTOR_ROL,
            orden_id=orden["_id"],
            body=schemas.OrdenCerrarRequest(
                trabajos_realizados=f"Trabajo realizado: {base_desc.lower()}",
                repuestos_consumidos=[
                    schemas.RepuestoInput(descripcion="Repuesto consumido A", cantidad=1, costo_unitario=round(random.uniform(10, 90), 2))
                ],
                costo_total=round(random.uniform(20, 350), 2),
                horas_taller=round(random.uniform(0.5, 8), 1),
                km_salida=km_salida,
                habilitar_vehiculo=True,
            ),
        )
        contadores["EN_TALLER"] -= 1
        contadores["CERRADA"] += 1

        # Retro-fechar el cierre también, coherente con fecha_programada.
        fecha_cierre = datetime.combine(fecha_programada, datetime.min.time(), tzinfo=UTC) + timedelta(hours=random.randint(1, 72))
        await db.ordenes.update_one({"_id": orden["_id"]}, {"$set": {"fecha_cierre": fecha_cierre}})

    print(f"Órdenes creadas: {creadas} (saltadas por ya existir: {saltadas}). Distribución final aplicada: {contadores}.")
    total = await db.ordenes.count_documents({"descripcion": {"$regex": "^SEED-DEMO-"}})
    print(f"Total de órdenes con marca SEED-DEMO en Mongo: {total}.")


if __name__ == "__main__":
    asyncio.run(main())
