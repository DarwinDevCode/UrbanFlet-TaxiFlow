# Especificación: Captación y Talento (Nivel Táctico)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_TACTICO.md` §4, verificada contra
> `backend/src/captacion/`.

## 1. Objetivo

Medir el rendimiento del embudo de captación — no solo el volumen, sino qué tan bien convierte y
retiene.

## 2. Contexto

El nivel operativo procesa solicitud por solicitud; este nivel agrega esa realidad en indicadores de
gestión: conversión, tiempo de decisión, retención.

## 3. Actores

- **`admin_captacion`** — único actor con acceso.

## 4. Requisitos funcionales

### RF-TCA-001 — KPIs de embudo
Solicitudes pendientes, conversión del mes, tiempo promedio de aprobación, retención a 90 días (con
nota explícita de que es una aproximación por estado snapshoteado, no un re-chequeo real periódico).

### RF-TCA-002 — Conversión de altas por canal (compuesto)
Serie temporal por canal de origen (app/campaña/referido/web).

### RF-TCA-003 — Filtro por canal
Sobre la tabla de solicitudes pendientes.

## 5-6. Requisitos no funcionales / Reglas de negocio

Ninguno propio adicional.

## 7-8. Entradas / Salidas

Filtro de canal → KPIs + gráfico + tabla de solicitudes/referidos pendientes.

## 9. Estados posibles

No aplica a este nivel.

## 10. Escenarios

### Escenario 1: Panel con datos reales
Dado que el entorno tiene 170+ solicitudes reales
Cuando `admin_captacion` abre el panel
Entonces ve conversión y tiempo promedio reales, con la nota de retención explicada.

## 11. Criterios de aceptación

### CA-TCA-001
"Retención a 90 días" en 0.0% con datos de desarrollo reciente no se interpreta como error — la
nota en pantalla explica por qué.

## 12. Dependencias

- **003-operativo/captacion-y-talento** — fuente de solicitudes y altas.

## 13. Fuera de alcance

- **Retención real a 90 días** — no existe ningún proceso que reobserve usuarios periódicamente; el
  dato mostrado es una aproximación basada en el estado ya snapshoteado, documentada como tal en el
  propio panel.
