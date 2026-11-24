# Plan técnico (retroactivo): Mantenimiento (Táctico)

## Backend

- 3 endpoints nuevos en `mantenimiento/router.py`: `panel-tactico/vehiculos-retirados` (simple),
  `panel-tactico/cumplimiento-preventivo` y `panel-tactico/costo-top-vehiculos` (compuestos, este
  último agrega por vehículo sumando todos los periodos antes del top 5).
- "Órdenes abiertas" reusa `GET /mantenimiento/ordenes` llamado dos veces (`ABIERTA` +
  `EN_TALLER`) y mezclado client-side — no se tocó el endpoint existente (`estado` es de valor
  único, compartido con la pantalla operativa).
- DAG `dag_mantenimiento_gold`: extrae órdenes `CERRADA` por `fecha_cierre` (único datetime real en
  `ordenes`).

## Frontend

- `apps/web-interno/src/sections/tactico/PanelMantenimiento.tsx` — patrón Z.

## Nota de arquitectura

Tras la Fase E del flujo de fallas (nivel operativo), la lista de "órdenes abiertas" se amplió de 2
a 3 llamadas mezcladas client-side (`ABIERTA`+`EN_TALLER`+`ESPERANDO_REPUESTO`) para que el KPI
siga siendo exhaustivo tras agregar el estado intermedio nuevo.
