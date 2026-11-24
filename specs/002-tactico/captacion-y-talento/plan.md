# Plan técnico (retroactivo): Captación y Talento (Táctico)

## Backend

- `dag_captacion_gold` extrae 2 fuentes en la misma corrida: `usuarios` (→ `fact_registro_usuario`)
  y `solicitudes` (→ `fact_solicitud_captacion`, tabla Gold nueva). 2 `rpt_*`:
  `rpt_conversion_captacion`, `rpt_altas_retencion_canal`.
- 3 endpoints nuevos en `captacion/router.py` (referidos-pendientes simple + conversión/altas-
  retención compuestos).
- Requirió cerrar antes el gap de `canal`: campo nuevo propagado a `solicitudes` y `usuarios`, con
  backfill real corrido sobre datos existentes.

## Frontend

- `PanelCaptacion.tsx` — patrón Z.

## Bug real corregido en el camino

`dag_captacion_gold` filtraba usuarios por `ts_creacion`, un campo que `usuarios` nunca tuvo (el
campo real es `fecha_registro`) — `fact_registro_usuario` llevaba 0 filas desde siempre, nunca
detectado porque nada dependía de ese dato hasta este panel.
