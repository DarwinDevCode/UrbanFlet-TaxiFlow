"""Verificación puntual (no seed permanente): confirma que un cambio real de
comisión, hecho desde la pantalla nueva `Comisión de la cooperativa`, llega
hasta el KPI "Margen de comisión prom." (Liquidación táctico / Integridad
Financiera estratégico) para los viajes correspondientes, sin alterar los
que ya cerraron antes de la fecha de vigencia.

Contexto real ya verificado antes de correr esto (movimientos reales en
Mongo, confirmados por consulta directa):
  - 3 viajes de Juan Pérez (+593911223344), ts_fin entre 2026-07-30 y
    2026-08-14 -- ANTES de la nueva vigencia (2026-08-15) -- comisión real
    calculada al 20% (la vigente en ESA fecha).
  - 2 viajes de Christopher Anderson (+593980010), ts_fin 2026-08-17 --
    DESPUÉS de la nueva vigencia -- comisión real calculada al 25%.
  - Los 3+2 movimientos COMISION/NETO_SOCIO existen y tienen `liquidacion_id:
    None` (nunca liquidados) porque nacieron hoy, dentro de la semana en
    curso (viernes-a-viernes) -- `generar_liquidaciones` (CU-O11) solo opera
    sobre el periodo YA CERRADO más reciente respecto a "ahora", así que
    llamarlo con el reloj real no los recogería hasta que esa semana cierre
    de verdad.

Este script usa el MISMO mecanismo ya establecido en
`seed_liquidaciones_demo.py` (`reloj_congelado`) para que
`recaudacion.service` vea un "ahora" posterior al cierre de la semana que
contiene esos movimientos -- no fabrica ningún dato, solo hace que el botón
real de "Generar liquidaciones" (CU-O11 pasos 1-2) se dispare para el
periodo real donde ya viven esos movimientos reales.

Uso: python -m scripts.verificar_comision_en_liquidacion
"""

import asyncio
from datetime import UTC, datetime

from src.core import audit as core_audit
from src.core.db_mongo import get_database
from src.recaudacion import service as recaudacion_service

# Sábado después del cierre viernes-a-viernes que contiene el 2026-08-25
# (semana real: 2026-08-21 a 2026-08-28) -- con esto `ahora` ve esa semana
# como YA CERRADA, sin tocar ninguna otra.
_AHORA_CONGELADA = datetime(2026, 8, 29, 17, 0, 0, tzinfo=UTC)

_MODULOS_CON_RELOJ = [recaudacion_service, core_audit]


class _RelojCongelado(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        if tz is not None:
            return _AHORA_CONGELADA.astimezone(tz)
        return _AHORA_CONGELADA


async def main() -> None:
    db = get_database()

    originales = {}
    for modulo in _MODULOS_CON_RELOJ:
        originales[modulo] = modulo.datetime
        modulo.datetime = _RelojCongelado
    try:
        resultado = await recaudacion_service.generar_liquidaciones(db, autorizador_id="staff-verificacion")
    finally:
        for modulo, original in originales.items():
            modulo.datetime = original

    print("generar_liquidaciones:", resultado)


if __name__ == "__main__":
    asyncio.run(main())
