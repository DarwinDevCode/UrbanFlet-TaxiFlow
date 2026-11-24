# Checklist de validación: Notificaciones

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] Generar cualquier evento de negocio que dispare notificación (ver documentos de auditoría
  funcional por nivel) y confirmar el contador consistente en campana + sidebar.

## Funcional (nuevos)

- [ ] **CHK-NOT-001** — Marcar una notificación como leída baja el contador en campana y sidebar
  sin recargar la página.
- [ ] **CHK-NOT-002** — Filtrar la lista por un tipo no cambia el contador global de no leídas.
- [ ] **CHK-NOT-003** — Un tipo con acción rápida navega a la pantalla correcta según el rol real
  del destinatario.
- [ ] **CHK-NOT-004** — La categoría "seguridad" no aparece como desactivable en Ajustes.

## Automatizado

- [ ] `backend/tests/notificaciones/`.

## No verificable automáticamente

- [ ] Recepción real en 2 pestañas simultáneas.
