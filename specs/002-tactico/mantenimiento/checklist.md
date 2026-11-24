# Checklist de validación: Mantenimiento (Táctico)

## Funcional (nuevos)

- [ ] **CHK-TMA-001** — "Órdenes abiertas" incluye órdenes en `ESPERANDO_REPUESTO`, no solo
  `ABIERTA`/`EN_TALLER`.
- [ ] **CHK-TMA-002** — El top 5 de costo por vehículo suma correctamente varios periodos del mismo
  vehículo antes de rankear.
- [ ] **CHK-TMA-003** — Filtrar por tipo de orden (preventiva/correctiva) reduce la tabla inferior
  con efecto real.

## Automatizado

- [ ] `backend/tests/mantenimiento/` — informes tácticos.

## No verificable automáticamente

- [ ] Corrida real del DAG con datos de producción reales.
