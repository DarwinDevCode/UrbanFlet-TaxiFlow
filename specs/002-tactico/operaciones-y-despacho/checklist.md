# Checklist de validación: Operaciones y Despacho (Táctico)

## Funcional (nuevos)

- [ ] **CHK-TDE-001** — La tasa de cancelación coincide con un conteo manual en Mongo para un
  periodo real.
- [ ] **CHK-TDE-002** — Con "Ventana reciente" + "Último mes" y datos operativos suficientes, la
  advertencia de concentración histórica **no** aparece; con un rango que igual incluye NYC 2021,
  sí aparece.
- [ ] **CHK-TDE-003** — Filtrar Despacho por zona/franja recalcula el gráfico con efecto real.

## Automatizado

- [ ] `backend/tests/viajes/` — incluye el test de regresión de la advertencia de concentración.

## No verificable automáticamente

- [ ] Corrida real de `dag_viajes_core` con el volumen completo del entorno.
