# Tareas (retroactivo): Mantenimiento (Táctico)

1. Construir `dag_mantenimiento_gold` completo (Bronze→Silver→Gold→trigger de publicación).
2. Construir los 3 endpoints tácticos y `PanelMantenimiento.tsx`.
3. Ampliar "órdenes abiertas" a 3 estados tras agregar `ESPERANDO_REPUESTO` a nivel operativo (Fase
   E del flujo de fallas), verificando explícitamente que el DAG no necesitaba cambios (su filtro ya
   era "sin `fecha_cierre`", que sigue excluyendo el estado nuevo del mismo modo que excluía
   `EN_TALLER`).

Trazabilidad completa en `CLAUDE.md` §3 (nota del DAG) y §18 Fase E.
