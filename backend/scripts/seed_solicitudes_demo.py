"""Siembra solicitudes de conductor ricas para demo (CU-O01/O03), pasando
por el servicio real (`captacion.service`) en vez de insertar documentos a
mano -- así cada solicitud queda con exactamente los efectos secundarios
reales que produciría un flujo real: `usuarios` (cuenta base), auditoría
write-ahead, y para las que se aprueban, `vehiculos` + `documentos` +
rol `conductor` vía la misma transacción que usa el endpoint real
(`_aprobar_solicitud_en_transaccion`). Esto también es lo que enriquece
Flota con más vehículos "de forma legítima" (vía aprobación, no a mano).

Distribución de estado (160 solicitudes, ponderada hacia APROBADA para
generar también volumen real en `vehiculos`/`documentos`):
    ENVIADA         25
    EN_VERIFICACION 20
    OBSERVADA       25
    RECHAZADA       20
    APROBADA        70  -> ~140 documentos reales (2 por solicitud:
                           LICENCIA_CONDUCIR + MATRICULA_VEHICULAR),
                           con fecha_vencimiento variada (vigente/por
                           vencer/vencido) para dar volumen real a
                           Vigencia Documental.

Fechas de envío distribuidas en los últimos 120 días (no todas "hoy").

Idempotente: cada solicitud usa una `cedula` determinista con prefijo
`SEED-` (nunca colisiona con cédulas reales de 10 dígitos) -- si ya existe
una solicitud con esa cédula, se salta esa fila entera.

Uso: cd backend && ./.venv/Scripts/python.exe -m scripts.seed_solicitudes_demo
"""

import asyncio
import random
import uuid
from datetime import UTC, date, datetime, timedelta

from src.captacion import schemas, service
from src.core.db_mongo import get_database
from src.core.notifications import NoopNotificationDispatcher

N = 160
VERIFICADOR_ID = "staff-verificacion"
VERIFICADOR_ROL = "admin_captacion"

CANALES: list[schemas.Canal] = ["app", "web", "referido", "campana"]
MARCAS = ["Chevrolet", "Toyota", "Kia", "Hyundai", "Nissan", "Suzuki"]
COLORES = ["Blanco", "Gris", "Rojo", "Azul", "Negro", "Plata"]

random.seed(20260803)  # determinista -- misma corrida, mismos datos


def _distribucion(n: int) -> list[str]:
    conteos = {"ENVIADA": 25, "EN_VERIFICACION": 20, "OBSERVADA": 25, "RECHAZADA": 20, "APROBADA": n - 90}
    estados = [e for e, c in conteos.items() for _ in range(c)]
    random.shuffle(estados)
    return estados


def _fecha_vencimiento(indice: int) -> date:
    """Mezcla real: ~1/3 vigente (>60d), ~1/3 por vencer (<30d), ~1/3 vencido."""
    hoy = date.today()
    bucket = indice % 3
    if bucket == 0:
        return hoy + timedelta(days=random.randint(90, 400))  # vigente
    if bucket == 1:
        return hoy + timedelta(days=random.randint(1, 29))  # por vencer
    return hoy - timedelta(days=random.randint(1, 200))  # vencido


def _documentos_para(indice: int) -> list[schemas.DocumentoInput]:
    return [
        schemas.DocumentoInput(
            tipo="LICENCIA_CONDUCIR",
            propietario_tipo="CONDUCTOR",
            url_objeto=f"seed://licencia-{indice}.pdf",
            hash_archivo=f"seedhash-lic-{indice:05d}",
            fecha_emision=date.today() - timedelta(days=400),
            fecha_vencimiento=_fecha_vencimiento(indice),
        ),
        schemas.DocumentoInput(
            tipo="MATRICULA_VEHICULAR",
            propietario_tipo="VEHICULO",
            url_objeto=f"seed://matricula-{indice}.pdf",
            hash_archivo=f"seedhash-mat-{indice:05d}",
            fecha_emision=date.today() - timedelta(days=200),
            fecha_vencimiento=_fecha_vencimiento(indice + 1),
        ),
    ]


async def main() -> None:
    db = get_database()
    dispatcher = NoopNotificationDispatcher()
    estados = _distribucion(N)

    creadas = 0
    saltadas = 0
    aprobadas = 0
    observadas = 0
    rechazadas = 0
    en_verificacion = 0

    for i in range(N):
        cedula = f"SEED-{i:06d}"
        existente = await db.solicitudes.find_one({"cedula": cedula})
        if existente is not None:
            saltadas += 1
            continue

        estado_objetivo = estados[i]
        nombre = f"Postulante Demo {i:03d}"
        telefono = f"+59370{i:06d}"
        placa = f"DEM-{i:04d}"

        solicitud = await service.crear_solicitud(
            db,
            dispatcher,
            nombre=nombre,
            telefono=telefono,
            email=None,
            password="SeedDemo123!",
            cedula=cedula,
            licencia_numero=f"LIC-{i:06d}",
            vehiculo=schemas.VehiculoInput(
                placa=placa,
                marca=random.choice(MARCAS),
                modelo=str(2015 + (i % 10)),
                anio=2015 + (i % 10),
                color=random.choice(COLORES),
                capacidad=4,
            ),
            documentos=_documentos_para(i),
            enviar=True,
            canal=random.choice(CANALES),
        )
        creadas += 1

        # Retro-fechar fecha_envio para distribuir en los últimos 120 días
        # (crear_solicitud siempre usa "ahora" -- se corrige después, directo
        # en Mongo, ya que el servicio no acepta una fecha inyectada).
        dias_atras = random.randint(0, 120)
        fecha_envio = datetime.now(UTC) - timedelta(days=dias_atras)
        await db.solicitudes.update_one({"_id": solicitud["_id"]}, {"$set": {"fecha_envio": fecha_envio}})

        if estado_objetivo == "ENVIADA":
            continue

        await service.tomar_solicitud(db, solicitud_id=solicitud["_id"], verificador_id=VERIFICADOR_ID, verificador_rol=VERIFICADOR_ROL)
        en_verificacion += 1

        if estado_objetivo == "EN_VERIFICACION":
            continue

        if estado_objetivo == "OBSERVADA":
            await service.decidir_solicitud(
                db, dispatcher, solicitud_id=solicitud["_id"], verificador_id=VERIFICADOR_ID,
                verificador_rol=VERIFICADOR_ROL, decision="OBSERVADA", motivo="Documento de licencia ilegible, favor reenviar.",
            )
            observadas += 1
        elif estado_objetivo == "RECHAZADA":
            await service.decidir_solicitud(
                db, dispatcher, solicitud_id=solicitud["_id"], verificador_id=VERIFICADOR_ID,
                verificador_rol=VERIFICADOR_ROL, decision="RECHAZADA", motivo="No cumple con los requisitos mínimos del vehículo.",
            )
            rechazadas += 1
        elif estado_objetivo == "APROBADA":
            await service.decidir_solicitud(
                db, dispatcher, solicitud_id=solicitud["_id"], verificador_id=VERIFICADOR_ID,
                verificador_rol=VERIFICADOR_ROL, decision="APROBADA", motivo=None,
            )
            aprobadas += 1

    print(
        f"Solicitudes creadas: {creadas} (saltadas por ya existir: {saltadas}). "
        f"Aprobadas: {aprobadas}, Observadas: {observadas}, Rechazadas: {rechazadas}, "
        f"En verificación (sin decidir más): {en_verificacion - observadas - rechazadas - aprobadas}."
    )
    total_docs = await db.documentos.count_documents({"hash_archivo": {"$regex": "^seedhash-"}})
    total_vehiculos = await db.vehiculos.count_documents({"placa": {"$regex": "^DEM-"}})
    print(f"Documentos reales generados por aprobación: {total_docs}. Vehículos nuevos en Flota: {total_vehiculos}.")


if __name__ == "__main__":
    asyncio.run(main())
