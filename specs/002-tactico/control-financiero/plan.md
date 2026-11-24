# Plan técnico (retroactivo): Control Financiero (Táctico)

## Backend

- `ts_pago` ya existía en `LiquidacionOut`/`recaudacion/service.py` (sorpresa positiva encontrada al
  construir este panel) — el gap real estaba solo en el DAG, que nunca lo propagaba a Gold.
- `dag_finanzas_gold` y `fact_liquidacion` ampliados con `ts_emision`/`ts_pago`.
- `rpt_margen_comision` (+ `horas_hasta_pago_promedio`); `rpt_tasa_discrepancias` rediseñado (de
  snapshot por día sin método a mes + método + % conciliado, tabla recreada desde cero).
- Sin endpoints admin nuevos para los informes simples (`GET /pagos/discrepancias` y
  `GET /liquidaciones` ya existían completos) — solo 2 endpoints nuevos para los compuestos.

## Frontend

- `PanelConciliacion.tsx`, `PanelLiquidacion.tsx` — ambos patrón Z.
