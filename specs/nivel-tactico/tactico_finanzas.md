# Especificación táctica — Control Financiero

Responsable: Administrador Financiero

## Objetivos tácticos

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT5.1 | Conciliación de los pagos de viajes: cerrar cada discrepancia y sostener el 100% conciliado | OE5 |
| OT5.2 | Control de la liquidación de comisiones: exactitud del margen y puntualidad del pago al socio | OE5 |

## Casos de uso tácticos de referencia

- **CU-T09 — Conciliar pagos y comisiones** (OT5.1, OT5.2): incluye "Detectar discrepancias entre viajes y pagos"; extiende "Generar un ajuste financiero".
- **CU-T12 — Controlar la liquidación de comisiones del periodo** (OT5.2): incluye "Calcular la comisión retenida del periodo"; extiende "Reprocesar una liquidación observada por el socio".

## Informes

| Informe | Tipo | Fuente | Objetivo | Pregunta de negocio |
|---|---|---|---|---|
| Discrepancias abiertas (viaje sin pago / monto distinto) | Simple | MongoDB | OT5.1 | ¿Qué pagos requieren resolución hoy y cuánto suman? |
| Liquidaciones del periodo por socio y su estado | Simple | MongoDB | OT5.2 | ¿Qué liquidaciones faltan aprobar o pagar en este periodo? |
| Tasa de discrepancias y % de recaudación conciliada por mes | Compuesto | ClickHouse | OT5.1 | ¿Estamos conciliando el 100% y la tasa de errores baja o sube? |
| Margen de comisión y tiempo promedio de liquidación por mes | Compuesto | ClickHouse | OT5.2 | ¿Cuánto retiene la cooperativa y cuánto tardamos en pagar al socio? |

### Ejemplo de consulta — informe simple

**Discrepancias abiertas** — colección `pagos`:

```javascript
db.pagos.find(
  { estado: { $in: ["DISCREPANCIA","VIAJE_SIN_PAGO"] } },
  { viaje_id: 1, metodo: 1, monto: 1, estado: 1, ts_registro: 1 }
).sort({ ts_registro: 1 })
```

**Liquidaciones del periodo por socio** — colección `liquidaciones`:

```javascript
db.liquidaciones.find(
  { periodo_inicio: ISODate("<inicio del periodo>"),
    periodo_fin: ISODate("<fin del periodo>") },
  { conductor_id: 1, bruto: 1, comisiones: 1, neto: 1, estado: 1 }
).sort({ conductor_id: 1 })
```

### Transformación — informes compuestos (etapa Transform del DAG)

| Informe compuesto | Transformación / agregación |
|---|---|
| Tasa de discrepancias y conciliación | Pagos en discrepancia / pagos totales y monto conciliado / monto recaudado, por mes y método de pago |
| Margen de comisión y tiempo de liquidación | Suma de comisiones sobre recaudación bruta y promedio de horas entre emisión y pago de la liquidación, por periodo |

DAG responsable: `dag_finanzas_gold` (corrida diaria).

## Dashboards (2 — se divide por proceso y audiencia distintos)

### 1. Panel de Conciliación de Pagos (OT5.1)

**Contenido:**
- KPIs: discrepancias, monto en disputa, % conciliado, viajes sin pago
- Gráfico: tasa de discrepancias mensual (compuesto, ClickHouse)
- Lista: discrepancias abiertas, con método y diferencia (simple, MongoDB)
- Filtros: rango de fechas, método de pago

**Patrón de layout recomendado: Z**
Justificación: la audiencia (Administrador Financiero, foco en resolución diaria) necesita el resumen de riesgo abierto primero, luego la tendencia y el detalle accionable.

### 2. Panel de Liquidación de Comisiones (OT5.2)

**Contenido:**
- KPIs: liquidaciones emitidas, por aprobar, margen de comisión, tiempo promedio de pago
- Gráfico: margen de comisión por mes (compuesto, ClickHouse)
- Lista: liquidaciones del periodo por socio (simple, MongoDB)
- Filtros: periodo, estado de liquidación, socio

**Patrón de layout recomendado: Z**
Justificación: mismo razonamiento — decisión de aprobación requiere ver primero el resumen (cuántas por aprobar) antes de entrar al detalle por socio.
