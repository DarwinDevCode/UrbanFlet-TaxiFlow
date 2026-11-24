# Especificación: Mantenimiento (Nivel Táctico)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_TACTICO.md` §2.

## 1. Objetivo

Dar al Jefe de Mantenimiento visibilidad de costos y cumplimiento del plan preventivo sin sumar
manualmente cada orden operativa.

## 2. Contexto

Con 130+ órdenes reales en el entorno, no es viable evaluar costo/cumplimiento fila por fila — este
panel agrega esa realidad operativa en indicadores accionables.

## 3. Actores

- **`jefe_mantenimiento`** — único actor con acceso.

## 4. Requisitos funcionales

### RF-TMA-001 — KPIs de estado y costo
El panel debe mostrar: órdenes abiertas, vehículos retirados, % de cumplimiento del plan
preventivo, y costo acumulado (top 5 vehículos).

### RF-TMA-002 — Costo por vehículo (compuesto)
Gráfico de costo de mantenimiento por vehículo, top 5, agregando todos los periodos del snapshot
antes de tomar el top (porque la fuente trae una fila por vehículo×mes).

### RF-TMA-003 — Cumplimiento del plan preventivo en el tiempo (compuesto)
Serie temporal de % de órdenes preventivas cerradas en o antes de su fecha programada.

### RF-TMA-004 — Filtros
Tipo de orden (preventiva/correctiva), placa, y rango de fechas sobre la tabla inferior.

## 5-6. Requisitos no funcionales / Reglas de negocio

Ninguno propio adicional a `000-sistema-general/reglas.md`.

## 7. Entradas

Filtros de tipo/placa/fecha.

## 8. Salidas

4 KPIs, 2 gráficos compuestos, tablas de órdenes abiertas/vehículos retirados (simple).

## 9. Estados posibles

No aplica a este nivel.

## 10. Escenarios

### Escenario 1: Panel con datos reales completos
Dado que el entorno tiene 130+ órdenes reales
Cuando `jefe_mantenimiento` abre el panel
Entonces los 4 KPIs muestran cifra real, sin ningún "—".

## 11. Criterios de aceptación

### CA-TMA-001
"Órdenes abiertas" cuenta exactamente las órdenes en `ABIERTA`/`EN_TALLER`/`ESPERANDO_REPUESTO` del
nivel operativo — verificable comparando con el conteo directo en Mongo.

## 12. Dependencias

- **003-operativo/mantenimiento** — fuente de órdenes y vehículos retirados.

## 13. Fuera de alcance

- **Corrección de una afirmación desactualizada de `CLAUDE.md`**: ese documento afirma en varios
  puntos que "no hay spec de nivel táctico en el repo" para esta agregación — verificado contra el
  archivo real, eso ya no es cierto: `specs/nivel-tactico/tactico_mantenimiento.md` sí define
  `CU-T11`/`OT7.1`/`OT7.2` con la fórmula exacta de cumplimiento preventivo y costo por vehículo. La
  afirmación de `CLAUDE.md` era correcta en el momento en que se escribió (la spec se agregó
  después) pero quedó desactualizada — no repetirla sin verificar contra el archivo real.
- **Kilometraje recorrido como dimensión del costo por vehículo**: la spec original (`OT7.2`) pide
  el costo "contra sus km recorridos" — el sistema real muestra el costo por vehículo sin cruzarlo
  con kilometraje en este panel táctico (esa relación sí aparece a nivel operativo, en la ficha del
  vehículo). Discrepancia real entre la spec original y el sistema construido, no oculta.
