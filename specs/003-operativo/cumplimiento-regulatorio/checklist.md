# Checklist de validación: Cumplimiento Regulatorio

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PD-10** — Documentación del socio de punta a punta, incluida la advertencia visible sin
  bloqueo de acciones.

## Funcional (nuevos)

- [ ] **CHK-CUM-001** — Ejecutar el control de vigencia dos veces seguidas sobre el mismo
  documento vencido no duplica la notificación ni el efecto de bandera.
- [ ] **CHK-CUM-002** — El conductor puede subir una renovación real desde "Mis documentos"; queda
  visible en la bandeja de `supervisor_cumplimiento`.
- [ ] **CHK-CUM-003** — Ninguna acción del sistema (iniciar turno, aceptar oferta) queda bloqueada
  por un documento vencido — solo aparece la advertencia.

## Automatizado

- [ ] `backend/tests/cumplimiento/test_cumplimiento.py`.

## No verificable automáticamente

- [ ] Notificación real recibida por el propietario correcto (conductor vs. dueño del vehículo).
