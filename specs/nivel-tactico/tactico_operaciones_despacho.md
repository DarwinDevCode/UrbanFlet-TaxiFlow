# Especificación táctica — Operaciones y Despacho

Responsable: Coordinador de Operaciones

## Objetivos tácticos

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT4.1 | Confiabilidad del despacho automático: controlar el tiempo de asignación por zona y franja | OE2 |
| OT4.2 | Reducción de viajes no atendidos y de cancelaciones, por motivo y actor | OE2 |

## Casos de uso tácticos de referencia

- **CU-T07 — Supervisar el desempeño del despacho automático** (OT4.1): incluye "Consultar los tiempos de asignación por zona y hora"; extiende "Ajustar el radio de búsqueda de conductores".
- **CU-T08 — Analizar cancelaciones y viajes sin conductor asignado** (OT4.2): incluye "Clasificar el motivo de cancelación"; extiende "Emitir alerta de zona desatendida".

## Informes

| Informe | Tipo | Fuente | Objetivo | Pregunta de negocio |
|---|---|---|---|---|
| Viajes activos y su estado en vivo | Simple | MongoDB | OT4.1 | ¿Qué viajes están en curso ahora y en qué estado? |
| Viajes SIN_CONDUCTOR y cancelados del día, con motivo | Simple | MongoDB | OT4.2 | ¿Qué solicitudes de hoy no pudimos atender y por qué? |
| Tiempo promedio de asignación por zona y franja | Compuesto | ClickHouse | OT4.1 | ¿Dónde y a qué hora tarda más el sistema en asignar un taxi? |
| Tasa de cancelación por motivo, actor, zona y mes | Compuesto | ClickHouse | OT4.2 | ¿Qué causa concentra las cancelaciones y dónde crece la demanda desatendida? |

### Ejemplo de consulta — informe simple

**Viajes activos** — colección `viajes`:

```javascript
db.viajes.find(
  { estado: { $in: ["SOLICITADO","OFERTADO","ASIGNADO","EN_CAMINO","EN_CURSO"] } },
  { pasajero_id: 1, conductor_id: 1, estado: 1, zona_origen_id: 1, ts_solicitud: 1 }
).sort({ ts_solicitud: -1 })
```

**Viajes SIN_CONDUCTOR y cancelados del día** — colección `viajes`:

```javascript
db.viajes.find(
  { estado: { $in: ["SIN_CONDUCTOR","CANCELADO"] },
    ts_solicitud: { $gte: ISODate("<inicio del día actual>") } },
  { estado: 1, motivo_cancelacion: 1, actor_cancelacion: 1, zona_origen_id: 1 }
).sort({ ts_solicitud: -1 })
```

### Transformación — informes compuestos (etapa Transform del DAG)

| Informe compuesto | Transformación / agregación |
|---|---|
| Tiempo de asignación por zona y franja | Promedio y percentil 95 de los segundos entre solicitud y asignación, agrupado por zona de origen y franja |
| Tasa de cancelación | Cancelados / solicitados, agrupado por motivo, actor, zona y mes; incluye SIN_CONDUCTOR como demanda desatendida |

DAG responsable: `dag_viajes_core` (corrida diaria).

## Dashboard: Panel de Despacho y Demanda

**1 dashboard** (departamento sin división).

**Contenido:**
- KPIs: viajes activos, tiempo de asignación promedio, SIN_CONDUCTOR hoy, tasa de cancelación
- Gráfico: tiempo de asignación por franja horaria (compuesto, ClickHouse)
- Lista: viajes sin conductor / cancelados hoy, con motivo y actor (simple, MongoDB)
- Filtros: zona, franja horaria (diurna/nocturna), rango de fechas

**Patrón de layout recomendado: Z**
Justificación: mismo caso que Captación — 4 KPIs arriba en fila horizontal, gráfico y lista abajo. La decisión operativa aquí es reactiva (¿qué está fallando ahora mismo?), así que el resumen numérico debe capturarse primero antes de profundizar en el gráfico o la lista.
