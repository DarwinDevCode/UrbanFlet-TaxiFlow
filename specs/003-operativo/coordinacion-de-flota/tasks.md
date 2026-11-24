# Tareas (retroactivo): Coordinación de Flota

1. Construir `GET /flota/tablero` como snapshot completo sin paginar (decisión explícita, ver
   `plan.md`).
2. Migrar la pantalla al patrón WorkPanel (búsqueda + `ActionBar` con verbos de edición
   deshabilitados y explicados) en la ronda de unificación de patrones de `web-interno`
   (`CLAUDE.md` §7 punto 1).
3. Confirmar y documentar el gap de zona: `fact_ubicacion_flota` (nivel táctico) no tiene dimensión
   zona — filtro deshabilitado con nota, no construido a medias.
4. Bug real corregido en el proceso de datos táctico (`dag_flota_gold`): `posiciones` nunca trae
   `estado_servicio` en el propio documento (vive en `usuarios.conductor.estado_servicio`) —
   corregido con un join de lectura, no relevante para el módulo operativo en sí pero comparte la
   misma fuente de datos.
