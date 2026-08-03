# Especificación táctica — Mantenimiento

Responsable: Jefe de Mantenimiento

## Objetivos tácticos

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT7.1 | Cumplimiento del plan de mantenimiento preventivo de la flota | OE2 |
| OT7.2 | Control del costo de mantenimiento por vehículo y periodo | OE2 |

## Casos de uso tácticos de referencia

- **CU-T04 — Planificar y controlar el mantenimiento de la flota** (OT7.1): incluye "Consultar el kilometraje y la última intervención del vehículo"; extiende "Retirar el vehículo de servicio".
- **CU-T11 — Analizar el costo de mantenimiento por vehículo y periodo** (OT7.2): incluye "Consolidar las órdenes de trabajo del periodo"; extiende "Marcar el vehículo como candidato a reemplazo".

## Informes

| Informe | Tipo | Fuente | Objetivo | Pregunta de negocio |
|---|---|---|---|---|
| Órdenes abiertas y vehículos retirados de servicio | Simple | MongoDB | OT7.1 | ¿Qué vehículos están fuera de servicio y qué orden los retiene? |
| Cumplimiento del plan preventivo por mes | Compuesto | ClickHouse | OT7.1 | ¿Qué proporción de intervenciones preventivas se hizo a tiempo? |
| Costo de mantenimiento por vehículo y periodo | Compuesto | ClickHouse | OT7.2 | ¿Qué vehículos cuestan más de lo que producen y son candidatos a reemplazo? |

### Ejemplo de consulta — informe simple

**Órdenes abiertas y vehículos retirados** — colección `ordenes`:

```javascript
db.ordenes.find(
  { estado: { $in: ["ABIERTA","EN_TALLER"] } },
  { vehiculo_id: 1, tipo: 1, estado: 1, fecha_programada: 1 }
).sort({ fecha_programada: 1 })
```

### Transformación — informes compuestos (etapa Transform del DAG)

| Informe compuesto | Transformación / agregación |
|---|---|
| Cumplimiento preventivo | Órdenes preventivas cerradas dentro del umbral de km/fecha sobre las planificadas, por mes |
| Costo por vehículo | Suma de costos de órdenes cerradas (mano de obra + repuestos) por vehículo y periodo, contra sus km recorridos |

DAG responsable: `dag_mantenimiento_gold` (corrida diaria). Extrae órdenes `CERRADA` por `fecha_cierre` (único datetime real disponible en `ordenes`; las `ANULADA` no quedan con fecha usable).

## Dashboard: Panel de Mantenimiento y Costos

**1 dashboard** (departamento sin división).

**Contenido:**
- KPIs: órdenes abiertas, vehículos retirados, cumplimiento preventivo (%), costo del mes
- Gráfico: costo de mantenimiento por vehículo (top 5, compuesto, ClickHouse)
- Lista: órdenes abiertas y vehículos retirados (simple, MongoDB)
- Filtros: rango de fechas, tipo de orden (preventiva/correctiva), vehículo

**Patrón de layout recomendado: Z**
Justificación: mismo patrón que los anteriores — KPIs de estado operativo inmediato arriba, gráfico de ranking de costos y lista de carga de taller abajo.
