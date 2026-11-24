# Especificación: Operaciones y Despacho (Nivel Táctico)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_TACTICO.md` §5, verificada contra
> `backend/src/viajes/`. Este departamento tiene **2 dashboards reales**: Despacho y Demanda, y
> Rendimiento de Conductores (este último agregado en una ronda posterior a los 9 originales).

## 1. Objetivo

Medir la salud del proceso de asignación de viajes (tiempo, cancelaciones) y comparar el desempeño
individual de los socios conductores.

## 2. Contexto

El nivel operativo resuelve viaje por viaje en tiempo real; este nivel agrega esa realidad para
detectar problemas de cobertura antes de que se acumulen quejas, y para identificar socios con bajo
desempeño u oportunidad de reconocimiento.

## 3. Actores

- **`coordinador_operaciones`** — único actor con acceso a ambos paneles.

## 4. Requisitos funcionales

### RF-TDE-001 — Panel de Despacho: KPIs
Viajes activos, tiempo de asignación promedio, sin conductor hoy, tasa de cancelación (corregida de
raíz en agosto 2026 — ver §13 del nivel operativo homólogo para la causa real).

### RF-TDE-002 — Tiempo de asignación por zona y franja (compuesto)
### RF-TDE-003 — Viajes SIN_CONDUCTOR y cancelados con motivo (simple)
### RF-TDE-004 — Panel de Rendimiento de Conductores: KPIs
Socios en la ventana, % de éxito promedio, cancelados, ingreso neto — todos sobre una ventana de
tiempo elegible (último mes/3/6/12 meses) con toggle "Ventana reciente"/"Histórico completo".

### RF-TDE-005 — Advertencia de concentración histórica
El sistema debe advertir explícitamente cuando la ventana filtrada igual incluye periodos del
dataset de calibración NYC 2021 — incluso con "Ventana reciente" activada, si el rango total de
datos disponibles solo tiene esos pocos periodos.

## 5-6. Requisitos no funcionales / Reglas de negocio

Ninguno propio adicional a `000-sistema-general/reglas.md`.

## 7-8. Entradas / Salidas

Filtros de zona/franja (Despacho); ventana + toggle histórico (Rendimiento).

## 9. Estados posibles

No aplica a este nivel.

## 10. Escenarios

### Escenario 1: Tasa de cancelación real, corregida
Dado que el defecto de agregación de `rpt_tasa_cancelacion` ya fue corregido
Cuando `coordinador_operaciones` abre Despacho
Entonces la tasa de cancelación muestra un porcentaje real distinto de 100% fijo.

### Escenario 2: Advertencia de concentración pese a "Ventana reciente"
Dado que el rango total de datos del entorno solo tiene 3 periodos, 2 de ellos del dataset NYC 2021
Cuando se activa "Ventana reciente"
Entonces la advertencia de concentración histórica sigue apareciendo, porque la ventana filtrada
igual incluye esos periodos.

## 11. Criterios de aceptación

### CA-TDE-001
La tasa de cancelación coincide con un conteo manual directo en Mongo para el mismo periodo
(verificado en 3 periodos reales durante la corrección).

## 12. Dependencias

- **003-operativo/operaciones-y-despacho** — fuente de viajes y cancelaciones.

## 13. Fuera de alcance / discrepancia corregida

- **Discrepancia real, ya corregida**: `rpt_tasa_cancelacion` daba 100% de forma permanente porque
  el denominador se calculaba con el mismo agrupamiento que separa los cancelados por motivo —
  corregido calculando el universo real de solicitados por separado. No es una limitación vigente,
  se documenta como corrección histórica.
- **2 taxonomías de "franja" que nunca se cruzan**: los buckets de 6h del panel de Flota y
  DIURNA/NOCTURNA de este panel son dimensiones distintas — un cruce entre ambas daría 100% de
  nulos, por eso se muestran en tablas separadas.
