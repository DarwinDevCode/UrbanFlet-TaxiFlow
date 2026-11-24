# Especificación: Cumplimiento Regulatorio (Nivel Táctico)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_TACTICO.md` §3, verificada contra
> `backend/src/cumplimiento/` y `backend/src/auditoria/`. Este departamento tiene **2 dashboards
> reales**, no 1 — Vigencia Documental y Auditoría e Integraciones.

## 1. Objetivo

Dar a Cumplimiento visibilidad agregada de dos cosas distintas: el riesgo legal por documentación
vencida, y quién hizo qué en el sistema (incluidos los intentos denegados).

## 2. Contexto

Sin este nivel, el control documental (nivel operativo) solo detecta caso por caso — este panel
muestra tendencia y volumen. La bitácora completa existe a nivel transversal; este departamento
consume una vista con indicadores propios sobre esa misma fuente.

## 3. Actores

- **`supervisor_cumplimiento`** — único actor con acceso a ambos paneles.

## 4. Requisitos funcionales

### RF-TCU-001 — Panel de Vigencia Documental: KPIs
Vencidos, por vencer (≤30d), % vigente, bloqueados.

### RF-TCU-002 — Documentación vigente por tipo (compuesto)
Licencia vs. matrícula, con franjas de color (peligro/advertencia/bueno).

### RF-TCU-003 — Tendencia mensual de % vigente (compuesto)
Serie histórica desde el primer corte real del proceso de datos.

### RF-TCU-004 — Panel de Auditoría e Integraciones: KPIs
Eventos hoy, accesos denegados, integraciones usadas (**ya no incluye "% de errores"** — se quitó
de la interfaz por no tener nunca dato real detrás).

### RF-TCU-005 — Uso de integraciones por ruta (compuesto)
Ranking de rutas reales por conteo de solicitudes (patrón F: la tabla domina, único de los 10
paneles tácticos con este layout).

### RF-TCU-006 — Filtros
Vigencia Documental: tipo de documento, rango de vencimiento. Auditoría: actor, acción, resultado.

## 5-6. Requisitos no funcionales / Reglas de negocio

Ninguno propio adicional.

## 7. Entradas

Filtros por panel (ver RF-TCU-006).

## 8. Salidas

KPIs + gráficos + tablas por panel, según RF-TCU-001 a 005.

## 9. Estados posibles

No aplica a este nivel.

## 10. Escenarios

### Escenario 1: Vigencia documental con datos reales
Dado que el entorno tiene 142+ documentos reales
Cuando `supervisor_cumplimiento` abre Vigencia Documental
Entonces ve vencidos/por vencer/% vigente reales, sin ningún "—".

### Escenario 2: Auditoría sin el KPI retirado
Dado que nunca existió ningún dominio de credenciales/latencia de integraciones
Cuando se abre Auditoría e Integraciones
Entonces el panel muestra 3 KPIs (no 4) — "% de errores" ya no aparece en la interfaz.

## 11. Criterios de aceptación

### CA-TCU-001
"Vencidos" en este panel coincide con el conteo real de `documentos` con `fecha_vencimiento` pasada
del nivel operativo.

### CA-TCU-002
El panel de Auditoría es el único de los 10 con patrón F, medible con `getComputedStyle`.

## 12. Dependencias

- **003-operativo/cumplimiento-regulatorio** — fuente de documentos.
- **004-transversal/auditoria-y-trazabilidad** — fuente de la bitácora.

## 13. Fuera de alcance

- **"% de errores" de integraciones** — quitado de la interfaz, no existe ningún dominio de
  credenciales/latencia/error de integraciones en el sistema; se decidió no ocupar espacio con un
  indicador que nunca podría mostrar un número real.
