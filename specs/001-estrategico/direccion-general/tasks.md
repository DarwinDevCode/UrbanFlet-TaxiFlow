# Tareas (retroactivo): Dirección General

Desglose real de cómo se construyó, en el orden real en que ocurrió — no un plan idealizado.
Trazabilidad completa en `CLAUDE.md` §12-13.

## Fase 3 — Backend (`CLAUDE.md` §12)

1. Crear `backend/src/estrategico/` con los 2 endpoints sin dominio dueño (Rentabilidad, Tablero
   Ejecutivo).
2. Agregar `GET /<dominio>/panel-estrategico/...` a los 7 routers de dominio existentes
   (captación, viajes, mantenimiento, plataforma, liquidaciones, cumplimiento, auditoría).
3. Crear `core/agregacion_estrategica.py` con los 4 helpers compartidos.
4. Resolver el puente de taxonomías de franja (`FRACCION_DIURNA_POR_BUCKET`) para poder cruzar
   `rpt_flota_activa_franja` (buckets de 6h) con `rpt_tiempo_asignacion` (DIURNA/NOCTURNA).
5. Escribir 19 tests nuevos (`backend/tests/estrategico/test_nivel_estrategico.py`): 403
   parametrizado sobre las 9 rutas, el 403 exclusivo de Gobernanza, agregación real, y la fórmula
   de Rentabilidad con snapshots falsos.
6. Verificar los 9 endpoints con `curl` real contra el backend en Docker, token real de `gerencia`.

## Fase 4 — Frontend (`CLAUDE.md` §13)

1. Resolver H4 (bloqueador previo): construir `navegacion.ts` para que un botón "Ver detalle"
   dentro de un panel pueda invocar `setSeccionActiva` sin cambiar la firma de `Seccion.render`.
2. Agregar el grupo "Panel Estratégico" al array `SECCIONES`, **después** de "Panel Táctico" y
   antes de "Administración" (no al final — verificado rol por rol que ningún índice 0 se
   desplaza).
3. Construir los 9 componentes de panel + `TableroEjecutivo`, reusando exclusivamente componentes
   ya existentes de `shared-ui`.
4. Construir `MiniTendencia` (única visualización nueva de la fase) para el Tablero Ejecutivo.
5. Cablear las banderas de `metadata` de cada endpoint a notas visibles en pantalla.
6. Verificar en navegador real: 9 endpoints con 200, patrón Z vs. F medido con `getComputedStyle`,
   un filtro real por dashboard con efecto verificado, navegación cruzada real sin recargar,
   Tablero con las 8 tarjetas coincidiendo con su detalle, RBAC confirmado con 2 cuentas
   (`gerencia` y `staff-verificacion`).

## Ronda posterior — Punto 3 de "claridad y profundidad analítica" (`CLAUDE.md` §17.4)

7. Investigar por qué ningún `rpt_*` agregaba por conductor — confirmar que `fact_ciclo_viaje`
   nunca tuvo `conductor_id` a propósito.
8. Agregar 2 columnas nuevas (`conductor_id` a `fact_ciclo_viaje`, `calificacion_puntaje` a
   `fact_viaje`) verificando primero que ningún consumidor real usa `SELECT *` sobre esas tablas.
9. Corregir el bug real encontrado en la primera corrida (columnas faltantes también en Bronze, no
   solo en Gold).
10. Construir `rpt_desempeno_conductor` y `rpt_ingreso_conductor`, y el panel
    `PanelDesempenoConductores` (el 9º real, agregado después de los 8 originales).
11. Corregir el hallazgo real de que la ventana reciente no evitaba la advertencia de
    concentración histórica cuando el rango total de datos solo tenía 3 periodos.

## Ronda de drill-down en KPIs (`CLAUDE.md` §17.6-17.11)

12. Auditar los ~77 `KpiCard` reales del sistema para identificar candidatos a ampliación con
    detalle (drill-down).
13. Construir `KpiDetalleModal` compartido, con `KpiCard.onClick` opcional (retrocompatible con
    los ~77 usos existentes).
14. Aplicar drill-down por lotes a los paneles estratégicos y tácticos relevantes, incluido un
    caso con hallazgo real de RBAC corregido en el camino (`documentos-por-vencer` no estaba
    accesible para `gerencia` pese a que el panel que lo necesitaba sí lo es).
