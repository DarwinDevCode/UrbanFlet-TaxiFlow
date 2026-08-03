"""Gate de cobertura para los 3 módulos exigidos explícitamente al 80%
(arquitectura_software.md línea 123: "cobertura mínima 80% en módulos de
viajes, recaudacion y auditoria"). Los demás módulos no tienen umbral fijado
por la spec y no se bloquean aquí.

Lee `coverage.json` (generado con `coverage json`) y falla si algún módulo de
la lista, cuando ya existe en `src/`, está por debajo del umbral. Un módulo
que todavía no se ha construido (fases futuras) se omite sin hacer fallar el
build — no hay nada que medir todavía.
"""

import json
import sys
from pathlib import Path

THRESHOLD = 80.0
MODULOS_EXIGIDOS = ["viajes", "recaudacion", "auditoria"]


def main() -> int:
    coverage_path = Path("coverage.json")
    if not coverage_path.exists():
        print("No se encontró coverage.json; ejecuta `coverage json` antes de este script.")
        return 1

    data = json.loads(coverage_path.read_text())
    files = data["files"]

    ok = True
    for modulo in MODULOS_EXIGIDOS:
        prefix = f"src/{modulo}/"
        archivos_modulo = {path: info for path, info in files.items() if path.replace("\\", "/").startswith(prefix)}

        if not archivos_modulo:
            print(f"[omitido] src/{modulo}/ todavía no existe en esta fase — sin gate.")
            continue

        covered = sum(info["summary"]["covered_lines"] for info in archivos_modulo.values())
        total = sum(info["summary"]["num_statements"] for info in archivos_modulo.values())
        pct = (covered / total * 100) if total else 100.0

        estado = "OK" if pct >= THRESHOLD else "FALLA"
        print(f"[{estado}] src/{modulo}/: {pct:.1f}% (mínimo {THRESHOLD}%)")
        if pct < THRESHOLD:
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
