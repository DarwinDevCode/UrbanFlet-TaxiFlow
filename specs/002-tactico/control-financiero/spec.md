# Especificación: Control Financiero (Nivel Táctico)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_TACTICO.md` §6, verificada contra
> `backend/src/recaudacion/`. **2 dashboards reales**: Conciliación de Pagos y Liquidación de
> Comisiones.

## 1. Objetivo

Medir la exactitud del cobro en efectivo y el margen real de comisión de la cooperativa, agregado
más allá de revisar caso por caso.

## 2. Contexto

El control operativo (nivel operativo) resuelve discrepancia por discrepancia; este nivel agrega
para responder "¿qué tan bien viene funcionando el cobro este mes?" y "¿cuál es el margen real de la
cooperativa?".

## 3. Actores

- **`admin_financiero`** — único actor con acceso a ambos paneles.

## 4. Requisitos funcionales

### RF-TFI-001 — Panel de Conciliación: KPIs
Discrepancias, monto en disputa, % conciliado, viajes sin pago.

### RF-TFI-002 — Tasa de discrepancias mensual (compuesto)
Serie por método de pago (efectivo/electrónico).

### RF-TFI-003 — Panel de Liquidación: KPIs
Liquidaciones emitidas, por aprobar, margen de comisión, tiempo promedio de pago.

### RF-TFI-004 — Margen de comisión y composición (compuestos)
Serie temporal del margen real + desglose bruto/comisión/neto.

### RF-TFI-005 — Filtros
Método de pago (Conciliación); estado y periodo (Liquidación).

## 5-6. Requisitos no funcionales / Reglas de negocio

Ninguno propio adicional.

## 7-8. Entradas / Salidas

Filtros por panel → KPIs + gráficos + tablas.

## 9. Estados posibles

No aplica a este nivel — refleja los estados de Liquidación gestionados a nivel operativo
(`003-operativo/control-financiero`).

## 10. Escenarios

### Escenario 1: Margen real coherente con la comisión vigente
Dado que la comisión vigente es 20%
Cuando se abre el panel de Liquidación
Entonces el margen de comisión mostrado coincide con ese 20% (con la composición bruto/comisión/
neto real).

## 11. Criterios de aceptación

### CA-TFI-001
Los 4 KPIs de Conciliación y los 4 de Liquidación muestran dato real, sin ningún "—" en un entorno
con datos completos.

## 12. Dependencias

- **003-operativo/control-financiero** — fuente de pagos y liquidaciones.

## 13. Fuera de alcance

Ninguno propio adicional a lo ya declarado en el nivel operativo homólogo (corrección de
liquidación `PAGADA`, pago electrónico).
