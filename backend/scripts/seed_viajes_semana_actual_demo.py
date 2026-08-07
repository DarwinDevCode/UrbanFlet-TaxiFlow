"""Siembra un puñado de viajes reales dentro del periodo semanal (viernes a
viernes) que `POST /liquidaciones/generar` procesaría AHORA MISMO si se
pulsa el botón real de Finanzas (`Generar liquidaciones del periodo
cerrado`) -- pensado para dejar el sistema listo antes de grabar un video
de demo, sin generar la liquidación por script (eso debe quedar para el
clic real en la UI durante la grabación).

Por qué no son literalmente "viajes de esta semana calendario": el
periodo que la función real calcula es la última semana viernes-a-viernes
YA CERRADA respecto al reloj real -- no la semana calendario en curso
(que todavía está abierta). Este script consulta ese periodo exacto vía
la misma función real (`_periodo_cerrado_mas_reciente`) en vez de
adivinar fechas, y reutiliza el helper de flujo completo de
`seed_liquidaciones_demo.py` (mismo camino real: solicitar -> despacho ->
aceptar -> en camino -> llegada -> iniciar -> finalizar -> pagar).

Usa socios que TODAVÍA NO tienen liquidación para ese periodo exacto
(se verifica antes de sembrar) -- si ya la tuvieran, generar_liquidaciones
los saltaría silenciosamente y el botón no mostraría nada nuevo en el
video.

Uso: cd backend && ./.venv/Scripts/python.exe -m scripts.seed_viajes_semana_actual_demo
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta

from scripts.seed_liquidaciones_demo import _cargar_pools, _generar_viaje_pagado, reloj_congelado
from src.core.db_mongo import get_database
from src.core.db_redis import get_redis
from src.recaudacion.service import _periodo_cerrado_mas_reciente

VIAJES_A_SEMBRAR = 3
random.seed(20260803)


async def main() -> None:
    db = get_database()
    redis = get_redis()

    ahora = datetime.now(UTC)
    periodo_inicio, periodo_fin = _periodo_cerrado_mas_reciente(ahora)
    print(f"Periodo que procesará el botón AHORA MISMO: {periodo_inicio.date()} -> {periodo_fin.date()}")

    ya_liquidados = {
        doc["conductor_id"]
        async for doc in db.liquidaciones.find({"periodo_inicio": periodo_inicio}, {"conductor_id": 1})
    }
    print(f"Socios que YA tienen liquidación en ese periodo (se evitan): {len(ya_liquidados)}")

    pasajeros, pares = await _cargar_pools(db)
    pares_libres = [p for p in pares if p[0] not in ya_liquidados]
    if not pares_libres:
        print("No hay conductores libres para este periodo -- nada que sembrar.")
        return

    # Excluir pasajeros con un viaje activo real en este momento (ej. de
    # pruebas manuales previas en navegador) -- no se toca ese viaje, solo
    # se evita elegir a ese pasajero para no chocar con
    # ViajeActivoExistenteError.
    con_viaje_activo = {
        doc["pasajero_id"]
        async for doc in db.viajes.find(
            {"estado": {"$in": ["SOLICITADO", "OFERTADO", "ASIGNADO", "EN_CAMINO", "EN_CURSO"]}},
            {"pasajero_id": 1},
        )
    }
    pasajeros_libres = [p for p in pasajeros if p not in con_viaje_activo]
    if con_viaje_activo:
        print(f"Pasajeros con viaje activo real (excluidos, no tocados): {len(con_viaje_activo)}")
    pasajeros = pasajeros_libres or pasajeros

    pagados = 0
    conductores_usados = set()
    for i in range(VIAJES_A_SEMBRAR):
        pasajero_id = random.choice(pasajeros)
        conductor_id, vehiculo_id = random.choice(pares_libres)
        segundos = random.randint(0, int((periodo_fin - periodo_inicio).total_seconds()) - 1)
        instante = periodo_inicio + timedelta(seconds=segundos)
        with reloj_congelado(instante):
            ok = await _generar_viaje_pagado(db, redis, pasajero_id=pasajero_id, conductor_id=conductor_id, vehiculo_id=vehiculo_id)
        if ok:
            pagados += 1
            conductores_usados.add(conductor_id)

    print(f"Viajes reales pagados sembrados: {pagados}/{VIAJES_A_SEMBRAR}, socios nuevos involucrados: {len(conductores_usados)}.")
    print("Listo -- el botón 'Generar liquidaciones del periodo cerrado' en Finanzas ahora debería mostrar resultado nuevo.")


if __name__ == "__main__":
    asyncio.run(main())
