# Tareas (retroactivo): Auditoría y Trazabilidad

1. Construir `write_audit_event` como mecanismo write-ahead único, adoptado por todos los dominios
   desde el inicio del proyecto.
2. Construir la vista completa (Cumplimiento) y, en la ronda de Administración del Sistema, la vista
   filtrada administrativa con "Ver antes/después".
3. Corrección estructural real: el mirror manual de `ACCIONES_ADMINISTRATIVAS` en el frontend se
   desincronizó del backend (un módulo nuevo agregó acciones que quedaron invisibles en el filtro,
   sin que ningún test lo detectara) — eliminada la causa raíz exponiendo la lista real por API en
   vez de solo agregar un test que la detecte.
4. Construir el catálogo de informes publicados (`Indicadores.tsx`), consumiendo la tabla `corridas`
   real.

Trazabilidad completa en `CLAUDE.md` §9 (Módulo 6.1) y §9 corrección post-8.1.
