# Especificación táctica — Coordinación de Flota

Responsable: Coordinador de Flota

## Objetivos tácticos

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT3.1 | Rastreo GPS en tiempo real: controlar los vehículos sin señal y la calidad del posicionamiento | OE2 |
| OT3.2 | Disponibilidad y continuidad del servicio: asegurar cobertura de flota por zona y franja horaria | OE2 |

## Casos de uso tácticos de referencia

- **CU-T05 — Supervisar el rastreo y la disponibilidad de la flota** (OT3.1, OT3.2): incluye "Consultar la ubicación GPS del vehículo"; extiende "Emitir alerta de baja disponibilidad".
- **CU-T06 — Supervisar la reasignación automática de viajes** (OT3.2): incluye "Verificar la disponibilidad del conductor"; extiende de CU-O05 "Asignar conductor (auto-despacho)".

## Informes

| Informe | Tipo | Fuente | Objetivo | Pregunta de negocio |
|---|---|---|---|---|
| Estado y última posición de cada vehículo (tiempo real) | Simple | MongoDB | OT3.1 | ¿Dónde está cada vehículo y en qué estado de servicio? |
| Vehículos sin señal o en alerta | Simple | MongoDB | OT3.1 | ¿Qué vehículos perdieron señal y desde cuándo? |
| % de flota activa por franja horaria y zona | Compuesto | ClickHouse | OT3.2 | ¿Tenemos cobertura suficiente donde y cuando hay demanda? |

### Ejemplo de consulta — informe simple

**Estado y última posición de cada vehículo** — colección `vehiculos`:

```javascript
db.vehiculos.find(
  { estado_habilitacion: "HABILITADO" },
  { placa: 1, estado_servicio: 1, "ultima_posicion.lat": 1,
    "ultima_posicion.lon": 1, "ultima_posicion.ts": 1 }
)
```

**Vehículos sin señal o en alerta** — colección `vehiculos`:

```javascript
db.vehiculos.find(
  { $or: [ { estado_servicio: "SIN_SEÑAL" },
           { "ultima_posicion.precision_baja": true } ] },
  { placa: 1, estado_servicio: 1, "ultima_posicion.ts": 1 }
)
```

### Transformación — informe compuesto (etapa Transform del DAG)

| Informe compuesto | Transformación / agregación |
|---|---|
| % de flota activa | Suma de minutos DISPONIBLE + OCUPADO sobre minutos totales de turno, por vehículo, hora y zona (corrida horaria) |

DAG responsable: `dag_flota_gold` (**corrida horaria**, por la naturaleza en vivo de la disponibilidad — a diferencia del resto de dominios, que corren a diario).

## Dashboard: Panel de Flota en Vivo y Disponibilidad

**1 dashboard** (departamento sin división).

**Contenido:**
- KPIs: en servicio, disponibles, sin señal, % flota activa
- Gráfico: % de flota activa por franja horaria (compuesto, ClickHouse)
- Lista: vehículos sin señal o en alerta, con última señal y zona (simple, MongoDB)
- Filtros: zona, franja horaria

**Patrón de layout recomendado: Z**
Justificación: igual razonamiento que los dashboards anteriores — KPIs de estado inmediato arriba, gráfico de tendencia y lista de alertas activas abajo. El dato en vivo (sin señal) necesita visibilidad inmediata tras el resumen numérico.
