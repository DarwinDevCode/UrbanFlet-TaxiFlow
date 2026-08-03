# Especificación táctica — Inteligencia de Negocio y Plataforma

Responsable: Responsable de Plataforma

## Objetivos tácticos

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT8.1 | Informes de indicadores disponibles y oportunos para cada área | OE4 |
| OT8.2 | Formación de socios y personal en el uso de la plataforma | OE3 |

## Casos de uso tácticos de referencia

- **CU-T14 — Operar el pipeline de informes de indicadores** (OT8.1): incluye "Ejecutar el proceso programado del dominio"; extiende "Reprocesar un lote en cuarentena".
- **CU-T15 — Gestionar la capacitación en el uso de la plataforma** (OT8.2): incluye "Registrar el avance de la capacitación"; extiende "Reasignar una capacitación pendiente".

## Informes

| Informe | Tipo | Fuente | Objetivo | Pregunta de negocio |
|---|---|---|---|---|
| Estado de las corridas del pipeline y % de cuarentena por lote | Simple | MongoDB | OT8.1 | ¿Qué corrida falló o degradó la calidad de datos hoy? |
| Avance de capacitación por área | Simple | MongoDB | OT8.2 | ¿Quiénes tienen la capacitación pendiente? |
| % de cuarentena por dominio y corrida | Compuesto | ClickHouse | OT8.1 | ¿Qué dominio concentra los rechazos del pipeline y su calidad de datos empeora? |

### Ejemplo de consulta — informe simple

**Estado de las corridas del pipeline** — colección `corridas_etl`:

```javascript
db.corridas_etl.find(
  { fecha_logica: ISODate("<fecha lógica>") },
  { dag: 1, estado: 1, registros: 1, en_cuarentena: 1, pct_cuarentena: 1, ts_fin: 1 }
).sort({ ts_fin: -1 })
```

**Avance de capacitación por área** — colección `capacitaciones`:

```javascript
db.capacitaciones.find(
  { estado: { $in: ["PENDIENTE","EN_CURSO"] } },
  { area: 1, usuario_id: 1, curso: 1, avance_pct: 1, estado: 1 }
).sort({ area: 1 })
```

### Transformación — informe compuesto (etapa Transform del DAG)

| Informe compuesto | Transformación / agregación |
|---|---|
| % de cuarentena por dominio | Registros en cuarentena / registros extraídos, por dominio (DAG) y fecha de corrida, calculado al cierre de cada ejecución |

DAG responsable: `dag_publicar_indicadores` (métricas propias del pipeline, alimentadas por las corridas de los 6 DAGs de dominio).

## Dashboard: Panel de Salud del Pipeline y Capacitación

**1 dashboard** (departamento sin división).

**Contenido:**
- KPIs: corridas OK hoy, % cuarentena, última corrida, capacitación (%)
- Gráfico: % de cuarentena por dominio (compuesto, ClickHouse)
- Lista: estado de corridas del pipeline por DAG, con % cuarentena y hora (simple, MongoDB)
- Filtros: dominio/DAG, fecha lógica

**Patrón de layout recomendado: Z**
Justificación: mismo patrón de resumen-antes-que-detalle — el Responsable de Plataforma necesita primero saber si algo falló hoy (KPIs), luego dónde concentra el problema (gráfico) y cuál corrida específica revisar (lista).
