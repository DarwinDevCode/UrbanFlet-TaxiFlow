# Checklist de validación: Mantenimiento

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PD-03** — Ciclo completo de una orden con todos sus estados y desviación de costo real
  (`+30.9%` en la corrida de verificación).
- [ ] **PD-04** — Reporte de falla desde los 2 orígenes, misma bandeja.
- [ ] **PU-04**/**PU-05** — Versión en lenguaje simple.
- [ ] **TU-05** — Conductor reporta una falla sin instrucciones; anotar si predice "Fallas del
  vehículo" o busca dentro de "Mi turno" primero.
- [ ] **TU-06** — Convertir un reporte real en orden sin instrucciones; anotar si descubre las 3
  pestañas por su cuenta o intenta crear la orden suelta con "Nuevo".

## Funcional (nuevos)

- [ ] **CHK-MAN-001** — Marcar "En taller" queda registrado en la bitácora de auditoría (evento
  `ORDEN_MANTENIMIENTO_EN_TALLER`).
- [ ] **CHK-MAN-002** — Elegir un repuesto del catálogo precarga el costo unitario sugerido, pero
  el campo sigue editable sin restricción.
- [ ] **CHK-MAN-003** — El selector de tipo de falla no ofrece "Otro"; un intento de mandar un
  valor libre por API devuelve 422.

## Automatizado

- [ ] `backend/tests/mantenimiento/` y `backend/tests/reportes_falla/`.
- [ ] `npm run test -w @urbanflet/web-interno` y `-w @urbanflet/web-conductor`.

## No verificable automáticamente

- [ ] Subida real de evidencia fotográfica y su ampliación a pantalla completa (Lightbox).
