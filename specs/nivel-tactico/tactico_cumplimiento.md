# Especificación táctica — Cumplimiento Regulatorio

Responsable: Supervisor de Cumplimiento

## Objetivos tácticos

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT6.1 | Cumplimiento de la normativa: cero conductores o vehículos operando con documentación vencida | OE6 |
| OT6.2 | Trazabilidad y auditoría de toda operación sensible | OE6 |
| OT2.1 | Integraciones externas documentadas y controladas por credencial | OE3 |

## Casos de uso tácticos de referencia

- **CU-T10 — Controlar la vigencia documental** (OT6.1, OT6.2): incluye "Verificar las fechas de vencimiento"; extiende "Bloquear al conductor o al vehículo".
- **CU-T13 — Consultar el registro de auditoría** (OT6.2): incluye "Filtrar los eventos por actor y periodo"; extiende "Exportar la evidencia para el regulador".
- **CU-T03 — Administrar las integraciones externas** (OT2.1): incluye "Registrar la credencial de integración"; extiende "Revocar la credencial de integración".

## Informes

| Informe | Tipo | Fuente | Objetivo | Pregunta de negocio |
|---|---|---|---|---|
| Documentos vencidos y por vencer (≤ 30 días) | Simple | MongoDB | OT6.1 | ¿Qué documentos hay que renovar ya y qué bloqueos siguen activos? |
| Consulta filtrada de la bitácora de auditoría | Simple | MongoDB | OT6.2 | ¿Quién hizo qué, cuándo y con qué resultado? |
| Documentación vigente por tipo y tendencia mensual | Compuesto | ClickHouse | OT6.1 | ¿La vigencia documental de la flota mejora o se deteriora? |
| Uso de integraciones por credencial y endpoint: solicitudes, error, latencia | Compuesto | ClickHouse | OT2.1 | ¿Qué integración externa falla o abusa del servicio? |

### Ejemplo de consulta — informe simple

**Documentos vencidos y por vencer** — colección `documentos`:

```javascript
db.documentos.find(
  { fecha_vencimiento: { $lte: ISODate("<hoy + 30 días>") } },
  { tipo: 1, propietario_tipo: 1, propietario_id: 1,
    fecha_vencimiento: 1, estado_verificacion: 1 }
).sort({ fecha_vencimiento: 1 })
```

**Consulta filtrada de la bitácora de auditoría** — colección `bitacora`:

```javascript
db.bitacora.find(
  { resultado: "DENEGADO", ts: { $gte: ISODate("<inicio del rango>") } },
  { actor_id: 1, rol: 1, accion: 1, entidad: 1, resultado: 1, ts: 1 }
).sort({ ts: -1 })
```

### Transformación — informes compuestos (etapa Transform del DAG)

| Informe compuesto | Transformación / agregación |
|---|---|
| Documentación vigente | Conteo de documentos por estado (vigente / por vencer / vencido) y tipo, en cortes diarios para la tendencia mensual |
| Uso de integraciones | Conteo de solicitudes, tasa de error y latencia p95 por credencial, endpoint y hora |

DAG responsable: `dag_cumplimiento_gold` (corrida diaria).

## Dashboards (2 — se divide por proceso y audiencia distintos)

### 1. Panel de Vigencia Documental (OT6.1)

**Contenido:**
- KPIs: vencidos, por vencer (≤30d), % vigente, bloqueados
- Gráfico: documentación por estado, tipo dona/pie (compuesto, ClickHouse)
- Lista: documentos vencidos y por vencer, con propietario y días restantes (simple, MongoDB)
- Filtros: tipo de documento, rango de vencimiento

**Patrón de layout recomendado: Z**
Justificación: 4 KPIs + 1 gráfico + 1 lista, misma estructura de resumen-antes-que-detalle que el resto de dashboards operativos de estado.

### 2. Panel de Auditoría e Integraciones (OT6.2 / OT2.1)

**Contenido:**
- KPIs: eventos hoy, accesos denegados, endpoints activos, % error API
- Gráfico: uso de API por endpoint (compuesto, ClickHouse)
- Lista: bitácora — accesos denegados, con actor/acción/resultado/hora (simple, MongoDB)
- Filtros: actor, rango de fechas, tipo de acción/resultado

**Patrón de layout recomendado: F**
Justificación: a diferencia de los demás, este panel es fundamentalmente una herramienta de **investigación/escaneo de registros** (bitácora de auditoría), no un tablero de estado resumido. El patrón F favorece la lectura vertical rápida de filas de eventos — el Supervisor escanea la lista buscando anomalías, no solo lee 4 números y decide. Los KPIs quedan como franja superior de contexto, pero el peso visual y de interacción principal debe estar en la tabla de eventos, optimizada para escaneo descendente.
