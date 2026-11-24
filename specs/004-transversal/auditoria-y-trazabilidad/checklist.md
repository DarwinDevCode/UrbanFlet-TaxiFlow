# Checklist de validación: Auditoría y Trazabilidad

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] Cierre de cualquier bloque de demo: ejecutar una acción real de cualquier nivel y confirmar
  el evento recién generado en la bitácora (patrón recomendado en los 3 documentos de auditoría
  funcional).

## Funcional (nuevos)

- [ ] **CHK-AUD-001** — Un evento visible en la vista filtrada de Administración es exactamente el
  mismo (mismo id/hora) que en la vista completa de Cumplimiento.
- [ ] **CHK-AUD-002** — "Ver antes/después" en un evento con cambio real muestra el valor exacto
  del campo, no un texto genérico.
- [ ] **CHK-AUD-003** — Con una corrida de hoy fallida en un dominio, el catálogo de informes de
  ese dominio sigue mostrando la última versión buena, con aviso de retraso.

## Automatizado

- [ ] `backend/tests/auditoria/`.

## No verificable automáticamente

- [ ] Confirmar en vivo que una corrida real de Airflow actualiza el catálogo de informes.
