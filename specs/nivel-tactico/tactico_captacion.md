# Especificación táctica — Captación y Talento

Responsable: Administrador de Captación

## Objetivos tácticos

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT1.1 | Onboarding digital autoservicio: sostener el plazo de 5 días hábiles de aprobación y elevar la conversión de solicitudes | OE1 |
| OT1.2 | Captación y retención de socios conductores y pasajeros por canal | OE1 |

## Casos de uso tácticos de referencia

- **CU-T01 — Gestionar el onboarding de conductores y pasajeros** (OT1.1): incluye "Verificar los documentos del postulante"; extiende "Rechazar la solicitud".
- **CU-T02 — Gestionar campañas de captación y referidos** (OT1.2): incluye "Validar la elegibilidad del referido"; extiende "Segmentar la audiencia por comportamiento".

## Informes

| Informe | Tipo | Fuente | Objetivo | Pregunta de negocio |
|---|---|---|---|---|
| Solicitudes pendientes de verificación con semáforo de plazo | Simple | MongoDB | OT1.1 | ¿Qué solicitudes están por incumplir el plazo de 5 días? |
| Referidos y estado de su incentivo | Simple | MongoDB | OT1.2 | ¿Qué referidos están activos y a quiénes debemos el incentivo? |
| Conversión y tiempo de aprobación por mes y canal | Compuesto | ClickHouse | OT1.1 | ¿Qué proporción de postulantes se convierte en socio y cuánto tardamos en aprobarlos? |
| Altas y retención de socios por canal y mes | Compuesto | ClickHouse | OT1.2 | ¿Qué canal trae socios que permanecen activos? |

### Ejemplo de consulta — informe simple

**Solicitudes pendientes de verificación** — colección `solicitudes`:

```javascript
db.solicitudes.find(
  { estado: "ENVIADA" },
  { usuario_id: 1, canal: 1, fecha_envio: 1 }
).sort({ fecha_envio: 1 })
// El semáforo de plazo se deriva en el dashboard a partir de fecha_envio:
// verde < 3 días, ámbar 3-5, rojo > 5.
```

**Referidos y estado de su incentivo** — colección `referidos`:

```javascript
db.referidos.find(
  { estado_incentivo: { $in: ["PENDIENTE", "ACREDITADO"] } },
  { referente_id: 1, referido_id: 1, canal: 1, estado_incentivo: 1 }
).sort({ fecha: -1 })
```

### Transformación — informes compuestos (etapa Transform del DAG)

| Informe compuesto | Transformación / agregación |
|---|---|
| Conversión y tiempo de aprobación | Conteo de solicitudes por estado terminal y promedio de días entre envío y decisión, agrupado por mes y canal |
| Altas y retención por canal | Conteo de altas por canal/mes y proporción de socios con actividad a 90 días del alta |

DAG responsable: `dag_captacion_gold` (corrida diaria).

## Dashboard: Panel de Captación y Onboarding

**1 dashboard** (departamento sin división, un único proceso y audiencia).

**Contenido:**
- KPIs (tarjetas superiores): solicitudes pendientes, conversión del mes, tiempo promedio de aprobación, retención a 90 días
- Gráfico: conversión de onboarding por canal (compuesto, ClickHouse)
- Lista: solicitudes pendientes de verificación con semáforo de plazo (simple, MongoDB)
- Filtros: rango de fechas, canal (App/Web/Referido/Campaña)

**Patrón de layout recomendado: Z**
Justificación: 4 tarjetas KPI en la fila superior (lectura horizontal izquierda→derecha) seguidas de dos bloques (gráfico + lista) en la fila inferior (lectura izquierda→derecha de nuevo) — el trazo natural del ojo dibuja una Z. Encaja porque el usuario necesita primero el resumen numérico antes de decidir a cuál de los dos bloques de detalle prestar atención.
