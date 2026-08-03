"""Genera liquidaciones REALES para demo (CU-O11), corriendo el proceso
real (`recaudacion.service.generar_liquidaciones`) sobre viajes/pagos
NUEVOS que a su vez pasan por el flujo real completo de un viaje
(solicitar -> despacho -> aceptar -> en camino -> llegada -> iniciar ->
finalizar -> pagar en efectivo), NO insertados a mano y SIN tocar el
dataset NYC (1.3M) -- son viajes nuevos, propios de este script.

Por qué no basta con `generar_liquidaciones()` a secas para varios
periodos históricos (hallazgo de la sesión, documentado en CLAUDE.md):
la función siempre calcula "la última semana YA CERRADA respecto a AHORA
MISMO" -- no acepta un periodo como parámetro, porque no hay scheduler en
el stack (es un botón, no un cron). Para poder generarla sobre 5 semanas
pasadas distintas, este script congela el reloj que ven los módulos de
negocio (`viajes.service`, `viajes.service_dispatch`,
`viajes.service_ejecucion`, `viajes.service_finalizacion`,
`recaudacion.service`, `core.audit` -- los únicos que llaman
`datetime.now(UTC)`) a un instante dentro de cada semana objetivo,
exactamente el mismo efecto que lograría correr la app real en esa fecha.
No se modifica ninguna regla de negocio -- se llama la función real, sin
parámetros nuevos, con el reloj del proceso ya apuntando a esa semana.

Segunda restricción real encontrada: `generar_liquidaciones` lee de
`movimientos` (no de `pagos` directamente) -- por eso los 1.24M pagos del
dataset NYC (que nunca pasaron por `registrar_pago_efectivo`) no producen
ninguna liquidación real: nunca generaron movimientos. Este script evita
ese problema por construcción, generando viajes/pagos que SÍ pasan por el
flujo real de pago.

5 semanas pasadas, ~16 viajes reales por semana repartidos entre varios
socios (conductores) y pasajeros del pool real, montos = tarifa_final
exacta (pago VALIDADO siempre, nunca DISCREPANCIA -- ya hay 3 discrepancias
reales sembradas a mano en otra sesión, este script no las duplica). Al
cierre de cada semana se llama `generar_liquidaciones()` una vez (reloj
congelado justo después del cierre de esa semana) y luego, para variar el
estado final de las liquidaciones entre periodos (para que Liquidación se
vea con varios estados, no solo EMITIDA), se aprueban/pagan/observan
algunas vía las funciones reales `aprobar_liquidacion`/`pagar_liquidacion`/
`observar_liquidacion`.

Idempotente: si ya existe una liquidación para (conductor_id,
periodo_inicio), `generar_liquidaciones` la salta sola (columna
`ya_existian` del resultado) -- reejecutar el script no duplica. Los
viajes en sí se marcan con `origen_direccion` con el prefijo
`SEED-LIQ-DEMO` y se verifica antes de generarlos si ya existen suficientes
para esa semana, para no re-sembrar viajes de más en una segunda corrida
(no hay una clave natural para deduplicar viaje por viaje como en
solicitudes/órdenes, así que la idempotencia es por semana completa: si ya
hay >= el objetivo de viajes pagados con el prefijo en esa ventana, se
salta la semana entera).

Uso: cd backend && ./.venv/Scripts/python.exe -m scripts.seed_liquidaciones_demo
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta

from src.core import audit as core_audit
from src.core.db_mongo import get_database
from src.core.db_redis import get_redis
from src.recaudacion import service as recaudacion_service
from src.recaudacion.service import _periodo_cerrado_mas_reciente
from src.viajes import schemas as viaje_schemas
from src.viajes import service as viajes_service
from src.viajes import service_dispatch, service_ejecucion, service_finalizacion

ACTOR_ID = "staff-verificacion"  # tiene admin_financiero entre sus roles
MARCA = "SEED-LIQ-DEMO"
SEMANAS = 5
VIAJES_POR_SEMANA = 16
QUEVEDO_LAT = -1.0225
QUEVEDO_LON = -79.4636

random.seed(20260803)

_MODULOS_CON_RELOJ = [
    viajes_service,
    service_dispatch,
    service_ejecucion,
    service_finalizacion,
    recaudacion_service,
    core_audit,
]


class _RelojCongelado(datetime):
    _ahora: datetime

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        if tz is not None:
            return cls._ahora.astimezone(tz)
        return cls._ahora


class reloj_congelado:
    """Congela `datetime.now(UTC)` en los módulos de negocio reales que lo
    llaman internamente -- ver docstring del módulo para la justificación.
    No modifica ninguna regla de negocio, solo qué instante ven."""

    def __init__(self, instante: datetime) -> None:
        self.instante = instante
        self._originales: dict = {}

    def __enter__(self):
        _RelojCongelado._ahora = self.instante
        for modulo in _MODULOS_CON_RELOJ:
            self._originales[modulo] = modulo.datetime
            modulo.datetime = _RelojCongelado
        return self

    def __exit__(self, *exc):
        for modulo, original in self._originales.items():
            modulo.datetime = original


async def _cargar_pools(db):
    pasajeros = [u["_id"] async for u in db.usuarios.find({"roles": "pasajero", "estado": "ACTIVO"}, {"_id": 1})]
    pares = []
    async for u in db.usuarios.find({"roles": "conductor"}):
        veh = await db.vehiculos.find_one({"propietario_id": u["_id"], "estado_habilitacion": "HABILITADO"})
        if veh is not None:
            pares.append((u["_id"], veh["_id"]))
    return pasajeros, pares


async def _poner_disponible(db, conductor_id: str, disponible: bool) -> None:
    await db.usuarios.update_one(
        {"_id": conductor_id},
        {"$set": {"conductor.estado_servicio": "DISPONIBLE" if disponible else "FUERA_DE_LINEA"}},
    )


async def _generar_viaje_pagado(db, redis, *, pasajero_id: str, conductor_id: str, vehiculo_id: str) -> bool:
    """Corre el flujo real completo. Devuelve True si el viaje quedó PAGADO."""
    # Posición del vehículo == origen del viaje (distancia 0) -- garantiza
    # que el despacho encuentre a este candidato en el primer radio (300m)
    # sin depender de reintentos/expansión de radio, que este script no
    # simula (esos requieren llamadas de poll adicionales, ver
    # service_dispatch.py).
    lat = QUEVEDO_LAT + random.uniform(-0.02, 0.02)
    lon = QUEVEDO_LON + random.uniform(-0.02, 0.02)
    await redis.hset(
        f"pos:{vehiculo_id}",
        mapping={"lat": lat, "lon": lon, "ts_servidor": datetime.now(UTC).isoformat(), "estado_servicio": "DISPONIBLE"},
    )

    await _poner_disponible(db, conductor_id, True)
    try:
        body = viaje_schemas.SolicitarViajeRequest(
            origen_lat=lat,
            origen_lon=lon,
            origen_direccion=f"{MARCA} origen",
            destino_lat=lat + random.uniform(-0.02, 0.02),
            destino_lon=lon + random.uniform(-0.02, 0.02),
            destino_direccion=f"{MARCA} destino",
        )
        viaje = await viajes_service.solicitar_viaje(db, pasajero_id=pasajero_id, body=body)
        if viaje["estado"] != "OFERTADO" or viaje.get("conductor_ofertado_id") != conductor_id:
            return False  # despacho no encontró a este candidato (posición vencida, etc.)

        await service_dispatch.responder_oferta(db, conductor_id=conductor_id, aceptar=True)
        await service_ejecucion.marcar_en_camino(db, conductor_id=conductor_id)
        await service_ejecucion.marcar_llegada(db, conductor_id=conductor_id)
        await service_ejecucion.iniciar_viaje(db, conductor_id=conductor_id)
        viaje_final = await service_finalizacion.finalizar_viaje(db, conductor_id=conductor_id)

        await recaudacion_service.registrar_pago_efectivo(
            db, conductor_id=conductor_id, viaje_id=viaje_final["_id"], monto_cobrado=viaje_final["tarifa_final"]
        )
        return True
    finally:
        await _poner_disponible(db, conductor_id, False)


async def _semana_ya_sembrada(db, periodo_inicio: datetime, periodo_fin: datetime) -> int:
    return await db.viajes.count_documents(
        {
            "origen_direccion": f"{MARCA} origen",
            "estado": "PAGADO",
            "ts_solicitud": {"$gte": periodo_inicio, "$lt": periodo_fin},
        }
    )


async def main() -> None:
    db = get_database()
    redis = get_redis()
    pasajeros, pares = await _cargar_pools(db)
    if not pasajeros or not pares:
        print("Pool de pasajeros/conductores insuficiente -- correr seed_solicitudes_demo.py primero.")
        return

    resumen: list[dict] = []

    for semanas_atras in range(SEMANAS, 0, -1):
        ahora_referencia = datetime.now(UTC) - timedelta(weeks=semanas_atras)
        periodo_inicio, periodo_fin = _periodo_cerrado_mas_reciente(ahora_referencia)

        ya = await _semana_ya_sembrada(db, periodo_inicio, periodo_fin)
        if ya >= VIAJES_POR_SEMANA:
            print(f"Semana {periodo_inicio.date()}..{periodo_fin.date()}: ya sembrada ({ya} viajes), se salta.")
        else:
            pagados = 0
            for i in range(VIAJES_POR_SEMANA):
                pasajero_id = random.choice(pasajeros)
                conductor_id, vehiculo_id = random.choice(pares)
                segundos_en_semana = random.randint(0, int((periodo_fin - periodo_inicio).total_seconds()) - 1)
                instante = periodo_inicio + timedelta(seconds=segundos_en_semana)
                with reloj_congelado(instante):
                    ok = await _generar_viaje_pagado(db, redis, pasajero_id=pasajero_id, conductor_id=conductor_id, vehiculo_id=vehiculo_id)
                if ok:
                    pagados += 1
            print(f"Semana {periodo_inicio.date()}..{periodo_fin.date()}: {pagados}/{VIAJES_POR_SEMANA} viajes reales pagados.")

        # Generar liquidaciones para esta semana (reloj justo después del cierre).
        with reloj_congelado(periodo_fin + timedelta(hours=2)):
            resultado = await recaudacion_service.generar_liquidaciones(db, autorizador_id=ACTOR_ID)
        generadas = resultado["generadas"]
        print(
            f"  -> generar_liquidaciones: {len(generadas)} nuevas, "
            f"{len(resultado['ya_existian'])} ya existían para este periodo."
        )
        resumen.append({"periodo_inicio": periodo_inicio, "periodo_fin": periodo_fin, "generadas": generadas})

    # Variar el estado final entre periodos para que Liquidación se vea con
    # varios estados reales (no solo EMITIDA) -- vía las funciones reales.
    todas_generadas = [(liq, r["periodo_fin"]) for r in resumen for liq in r["generadas"]]
    random.shuffle(todas_generadas)
    aprobadas = pagadas = observadas = 0
    for indice, (liq, periodo_fin) in enumerate(todas_generadas):
        destino = indice % 4  # 0: queda EMITIDA, 1: APROBADA, 2: PAGADA, 3: OBSERVADA
        with reloj_congelado(periodo_fin + timedelta(hours=3)):
            if destino == 1:
                await recaudacion_service.aprobar_liquidacion(db, liquidacion_id=liq["_id"], aprobador_id=ACTOR_ID)
                aprobadas += 1
            elif destino == 2:
                await recaudacion_service.aprobar_liquidacion(db, liquidacion_id=liq["_id"], aprobador_id=ACTOR_ID)
                await recaudacion_service.pagar_liquidacion(db, liquidacion_id=liq["_id"], autorizador_id=ACTOR_ID)
                pagadas += 1
            elif destino == 3:
                await recaudacion_service.observar_liquidacion(
                    db, liquidacion_id=liq["_id"], conductor_id=liq["conductor_id"], motivo="Saldo no coincide con lo registrado en mi bitácora personal."
                )
                observadas += 1

    print(
        f"\nTotal liquidaciones nuevas: {len(todas_generadas)} sobre {SEMANAS} periodos. "
        f"Estados aplicados: {aprobadas} APROBADA, {pagadas} PAGADA, {observadas} OBSERVADA, "
        f"resto EMITIDA."
    )
    socios = {liq["conductor_id"] for liq, _ in todas_generadas}
    print(f"Socios distintos con liquidación nueva: {len(socios)}.")


if __name__ == "__main__":
    asyncio.run(main())
