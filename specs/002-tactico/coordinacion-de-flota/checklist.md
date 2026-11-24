# Checklist de validación: Coordinación de Flota (Táctico)

## Funcional (reusado)

- [ ] Verificación visual del patrón Z: gráfico y lista en 2 columnas iguales
  (`getComputedStyle` sobre `.dashboard-z-row`).

## Funcional (nuevos)

- [ ] **CHK-TFL-001** — Con al menos un conductor `DISPONIBLE`, "Disponibles" muestra un número
  mayor que cero.
- [ ] **CHK-TFL-002** — Filtrar por una franja horaria reduce el gráfico a esa franja.

## Automatizado

- [ ] `backend/tests/flota/` — informes tácticos.

## No verificable automáticamente

- [ ] Datos reales de ClickHouse (`rpt_flota_activa_franja`) con corrida real de Airflow.
