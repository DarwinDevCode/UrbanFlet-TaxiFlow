# Tareas (retroactivo): Cumplimiento Regulatorio (Táctico)

1. Construir Vigencia Documental (3 endpoints, `PanelDocumentacion.tsx`, patrón Z).
2. Construir Auditoría e Integraciones reusando la bitácora operativa tal cual + 1 endpoint nuevo
   de uso de integraciones.
3. Corregir el desproporcionado real entre bitácora (sin límite de alto) y gráfico: agregar
   `altoMaximo` a `DataTable` (compartido, reutilizable por cualquier pantalla futura).
4. Corregir el ancho excesivo real de la columna Rol (un evento con 4+ roles concatenados estiraba
   toda la tabla): agregar `width` fijo por columna a `DataTable`.
5. Ronda de claridad de lenguaje: quitar "% de errores" (renombrado antes, retirado después) y
   traducir jerga de desarrollador visible en pantalla ("endpoint" → "integración", "API" →
   lenguaje llano) — ver `CLAUDE.md` §17.1 y §27.

Trazabilidad completa en `CLAUDE.md` §7 punto 5 y §5.2.
