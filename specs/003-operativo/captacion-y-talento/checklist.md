# Checklist de validación: Captación y Talento

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PD-02** — Postulación con documentos + aprobación, verificado en red (4 llamadas
  encadenadas) y en Mongo (2 documentos reales con hash correcto).
- [ ] **PU-03** — Versión en lenguaje simple, cualquier persona sin conocimiento técnico.
- [ ] **TU-07** — Captación revisa y decide sin instrucciones; medir si "Tomar" se entiende sin
  ayuda.
- [ ] **PD-09** parcial / **PUS-09** — el botón de decisión final permanece deshabilitado hasta
  completar el motivo cuando la decisión no es "Aprobar".

## Funcional (nuevos)

- [ ] **CHK-CAP-001** — Enviar una solicitud con un `tipo` de documento inexistente devuelve 422
  antes de crear la cuenta.
- [ ] **CHK-CAP-002** — Interrumpir el flujo entre el paso 1 y el 2 deja la solicitud en
  `BORRADOR`, invisible en la bandeja de Captación.
- [ ] **CHK-CAP-003** — El registro de pasajero deja la sesión iniciada de inmediato, sin paso
  adicional.

## Automatizado

- [ ] `backend/tests/captacion/test_captacion.py` — flujo completo con documentos, tipo inválido,
  tipo inactivo, aislamiento entre postulantes.
- [ ] `npm run test -w @urbanflet/web-conductor` y `-w @urbanflet/web-interno`.

## No verificable automáticamente

- [ ] Subida real de archivo con imagen genuina (no mock) — requiere navegador real.
- [ ] Visualización real de la imagen en el bloque de revisión de Captación.
