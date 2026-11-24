# Especificación: Coordinación de Flota (Nivel Táctico)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_TACTICO.md` §1, verificada contra
> `backend/src/flota/` (`panel-tactico/`) y `apps/web-interno/src/sections/tactico/PanelFlota.tsx`.

## 1. Objetivo

Dar al Coordinador de Flota un resumen agregado del estado de la flota — cobertura actual y su
evolución por franja horaria — sin tener que sumar manualmente el tablero operativo en vivo.

## 2. Contexto

El tablero operativo (`003-operativo/coordinacion-de-flota`) es un snapshot del instante. Este nivel
agrega esa misma fuente en el tiempo, vía el proceso de datos (Airflow → ClickHouse), para responder
"¿cómo viene la cobertura este período?", no solo "¿cómo está ahora mismo?".

## 3. Actores

- **`coordinador_flota`** — único actor con acceso.

## 4. Requisitos funcionales

### RF-TFL-001 — KPIs de cobertura actual
El panel debe mostrar: vehículos en servicio, vehículos disponibles, vehículos sin señal, y % de
flota activa — todos leídos del mismo snapshot en vivo que ya usa el tablero operativo (informe
simple, MongoDB).

### RF-TFL-002 — % de flota activa por franja horaria (compuesto)
El panel debe mostrar un gráfico de % de flota activa agrupado por los 4 buckets de 6 horas
(00-06/06-12/12-18/18-24), agregado por Airflow.

### RF-TFL-003 — Filtro por franja
El gráfico debe poder filtrarse por franja horaria, con efecto real verificable.

## 5. Requisitos no funcionales

Ninguno adicional a los ya establecidos en `000-sistema-general/reglas.md`.

## 6. Reglas de negocio

Ninguna propia — hereda el comportamiento del nivel operativo del mismo departamento.

## 7. Entradas

- Filtro de franja horaria.

## 8. Salidas

- 4 KPIs con dato real.
- Gráfico de % de flota activa por franja.
- Tabla de vehículos sin señal o en alerta.

## 9. Estados posibles

No aplica — nivel de agregación, sin entidad con máquina de estados propia.

## 10. Escenarios

### Escenario 1: Consulta con conductores en línea
Dado que hay conductores con turno activo
Cuando `coordinador_flota` abre el panel
Entonces ve "En servicio" y "% flota activa" con cifra real mayor que cero.

### Escenario 2: Filtro por franja con efecto real
Dado que el gráfico muestra las 4 franjas
Cuando se filtra a una sola
Entonces el gráfico recalcula mostrando solo esa franja, confirmable en la red.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md` **PUS-05** (drill-down en la misma pantalla, donde aplique).

### CA-TFL-001
Con datos reales del entorno, el panel muestra los 4 KPIs sin ningún "—".

### CA-TFL-002
El filtro por zona aparece deshabilitado con una nota explícita, nunca oculto.

## 12. Dependencias

- **003-operativo/coordinacion-de-flota** — fuente última del dato.
- **004-transversal/auditoria-y-trazabilidad** — el proceso de datos que alimenta este panel se
  monitorea ahí (Plataforma).

## 13. Fuera de alcance

- **Filtro por zona geográfica** — `fact_ubicacion_flota` no tiene dimensión zona (gap heredado del
  nivel operativo).
