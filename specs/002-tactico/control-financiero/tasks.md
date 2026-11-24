# Tareas (retroactivo): Control Financiero (Táctico)

1. Confirmar que `ts_pago` ya se seteaba correctamente al pagar (nivel operativo) — el gap real
   estaba solo en el proceso de datos.
2. Ampliar `dag_finanzas_gold`/`fact_liquidacion` con `ts_emision`/`ts_pago`.
3. Rediseñar `rpt_tasa_discrepancias` desde cero (antes por día sin dimensión de método).
4. Construir `PanelConciliacion.tsx`/`PanelLiquidacion.tsx`.

Trazabilidad completa en `CLAUDE.md` §7 punto 5, entrada 6.1/6.2.
