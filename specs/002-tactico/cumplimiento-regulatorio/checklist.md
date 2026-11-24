# Checklist de validación: Cumplimiento Regulatorio (Táctico)

## Funcional (nuevos)

- [ ] **CHK-TCU-001** — El panel de Auditoría muestra exactamente 3 KPIs ("Eventos hoy", "Accesos
  denegados", "Integraciones usadas") — confirmar que "% de errores" no está presente.
- [ ] **CHK-TCU-002** — El panel de Auditoría mide `320px : resto` (patrón F), distinto de los
  demás paneles tácticos (`getComputedStyle`).
- [ ] **CHK-TCU-003** — La columna Rol de la bitácora tiene ancho fijo (no se estira con un evento
  de rol múltiple concatenado).
- [ ] **CHK-TCU-004** — Filtrar Vigencia Documental por tipo de documento reduce la tabla con
  efecto real.

## Automatizado

- [ ] `backend/tests/cumplimiento/` y `backend/tests/auditoria/`.
- [ ] `npm run test -w @urbanflet/web-interno`.

## No verificable automáticamente

- [ ] Medición visual real del patrón F vs. Z con `getComputedStyle`.
