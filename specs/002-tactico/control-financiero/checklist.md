# Checklist de validación: Control Financiero (Táctico)

## Funcional (nuevos)

- [ ] **CHK-TFI-001** — El margen de comisión del panel de Liquidación coincide con la comisión
  vigente real (verificable en `Comision.tsx`, nivel operativo).
- [ ] **CHK-TFI-002** — Filtrar Conciliación por método de pago reduce la tabla con efecto real.

## Automatizado

- [ ] `backend/tests/recaudacion/` — informes tácticos.

## No verificable automáticamente

- [ ] Corrida real de `dag_finanzas_gold`.
