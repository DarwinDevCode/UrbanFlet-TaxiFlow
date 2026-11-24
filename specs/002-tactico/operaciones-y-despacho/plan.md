# Plan técnico (retroactivo): Operaciones y Despacho (Táctico)

## Backend

- `dag_viajes_core` ampliado con `fact_ciclo_viaje` (todos los estados, por `ts_solicitud`, no solo
  `PAGADO` como `fact_viaje`) — validación Silver mínima a propósito, para no rechazar los mismos
  registros de `SIN_CONDUCTOR`/`CANCELADO` que este informe necesita.
- `rpt_tiempo_asignacion`, `rpt_tasa_cancelacion` (corregida con JOIN contra una segunda agregación
  sin la dimensión motivo/actor).
- `rpt_desempeno_conductor`/`rpt_ingreso_conductor` (2 tablas nuevas, grano distinto — viaje vs.
  ciclo de liquidación — bucketadas a mes cada una).
- 2 índices nuevos en `viajes` detectados con la app real bajo carga (no adivinados): uno para el
  filtro `estado IN [SIN_CONDUCTOR,CANCELADO]`, otro para `estado=FINALIZADO` sin pago.

## Frontend

- `PanelDespacho.tsx`, `PanelRendimientoConductores.tsx` — ambos patrón Z.

## Decisión de arquitectura: por qué Rendimiento de Conductores es un panel propio

Se evaluó extender el panel de Despacho en vez de crear uno nuevo, y se descartó: Despacho es sobre
la salud del pipeline de despacho a nivel flota/zona; este panel es sobre identidad y comparación
individual de cada socio — dominios genuinamente distintos, gateados al mismo rol pero con
propósitos diferentes.
