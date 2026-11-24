# Checklist de validación: Control Financiero

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PD-01** (parcial) — el cobro y su eventual discrepancia forman parte del ciclo completo del
  viaje.

## Funcional (nuevos)

- [ ] **CHK-FIN-001** — "Generar liquidaciones" pulsado dos veces seguidas no duplica el lote ya
  emitido.
- [ ] **CHK-FIN-002** — Un intento manual de insertar una segunda comisión vigente en Mongo es
  rechazado por el índice único (`E11000 duplicate key`).
- [ ] **CHK-FIN-003** — Dos viajes cobrados a ambos lados de una fecha de cambio de comisión
  aplican, cada uno, la comisión vigente en su propia fecha (no la más reciente).
- [ ] **CHK-FIN-004** — Una liquidación `PAGADA` no ofrece ningún control de edición de su monto.

## Automatizado

- [ ] `backend/tests/recaudacion/` — incluye `test_ajuste_movimiento.py`.

## No verificable automáticamente

- [ ] Resolución real de una discrepancia con datos reales del entorno (evitar consumir la única
  discrepancia real disponible sin necesidad, ver `AUDITORIA_FUNCIONAL_OPERATIVO.md` §5).
