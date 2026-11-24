# Checklist de validación: Coordinación de Flota

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PUS-14** (aplicado a este contexto) — un vehículo/conductor retirado no debería aparecer
  ofrecido en ningún selector que dependa de flota activa.

## Funcional (nuevos)

- [ ] **CHK-FLO-001** — Iniciar turno de un conductor de prueba hace aparecer su vehículo en el
  tablero en menos de 10 segundos (el ciclo de refresco).
- [ ] **CHK-FLO-002** — Terminar turno lo retira del tablero en el siguiente refresco.
- [ ] **CHK-FLO-003** — El filtro por placa/conductor reduce la lista visible sin disparar una
  nueva petición de red (client-side).

## Automatizado

- [ ] `backend/tests/flota/` — reporte de posición, detección de salto imposible.

## No verificable automáticamente

- [ ] Refresco real cada 10 segundos observado en el tiempo.
