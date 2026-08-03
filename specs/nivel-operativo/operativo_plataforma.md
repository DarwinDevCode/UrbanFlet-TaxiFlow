# Especificación operativa — Inteligencia de Negocio y Plataforma

Paquete: `pkg-bi` · Objetivo: OP4.1 (procesar diariamente los datos de la operación y publicar los indicadores) · OE4

El departamento opera el pipeline que transforma los datos transaccionales en los informes compuestos que consumen los niveles táctico y estratégico, bajo el patrón Medallion (Bronze → Silver → Gold) orquestado por Apache Airflow. Los informes simples no pasan por aquí: se consultan directo de la base relacional.

DAGs y frecuencias:

| DAG | Dominio | Frecuencia | Tablas Gold que produce |
|---|---|---|---|
| `dag_viajes_core` | Viajes | Diaria (02:00) | `fact_viaje`, `dim_zona`, `dim_tiempo` |
| `dag_flota_gold` | Flota | Horaria | `fact_ubicacion_flota` |
| `dag_finanzas_gold` | Recaudación | Diaria (03:00) | `fact_recaudacion`, `fact_liquidacion` |
| `dag_captacion_gold` | Captación | Diaria (03:30) | `fact_registro_usuario` |
| `dag_cumplimiento_gold` | Cumplimiento | Diaria (04:00) | `fact_cumplimiento_documental`, `fact_integracion_api` |
| `dag_historico_nyc` | Dataset histórico yellow taxi | Bajo demanda | `fact_viaje_historico` |

---

## CU-O15 — Ejecutar el proceso de transformación de datos

**Actores:** Sistema (Airflow); Responsable de Plataforma (receptor de alertas)

**Precondiciones:**
- Fuentes transaccionales accesibles.
- No hay otra corrida del mismo DAG y la misma fecha lógica en ejecución.

**Flujo principal:**
1. **Bronze — extracción:** el DAG extrae de las fuentes transaccionales los registros del periodo (fecha lógica de la corrida) y los aterriza sin transformación en las tablas de staging, con `lote_id` y timestamp de extracción.
2. **Silver — validación y limpieza:** cada registro pasa las reglas de validación del dominio. Para viajes:

   | Regla | Condición | Flag de rechazo |
   |---|---|---|
   | Distancia válida | `distancia_km > 0` | `DISTANCIA_CERO` |
   | Duración coherente | `fin > inicio` y `duracion < 1440 min` | `FECHAS_INVALIDAS` |
   | Integridad financiera | `monto_pagado == tarifa_final` (o discrepancia ya resuelta con ajuste) | `ERROR_MONTO` |
   | Zona válida | origen y destino resuelven a una zona del catálogo | `ZONA_INVALIDA` |
   | No duplicado | `viaje_id` único en el lote y en Gold | descarte silencioso + contador |

3. **Cuarentena:** todo registro rechazado se inserta en la tabla de cuarentena del dominio con `viaje_id`/id de origen, flag, valores originales, `lote_id` y timestamp. **El pipeline nunca se detiene por un registro inválido:** continúa con el resto del lote.
4. **Gold — agregación:** los registros válidos se transforman al modelo dimensional y se cargan.
5. **Carga idempotente:** antes de insertar, el DAG elimina de Gold las particiones de la fecha lógica que va a cargar (`DELETE ... WHERE fecha = fecha_lote`) y luego inserta. Re-ejecutar una corrida produce exactamente el mismo resultado.
6. Al finalizar, el DAG publica las métricas de la corrida: registros extraídos, válidos, en cuarentena, % de calidad y duración por etapa.

**Flujos alternos:**
- **A1 — Fuente inaccesible:** reintento con backoff (3 intentos, 5/15/45 min); agotados, la corrida queda `FAILED` con alerta inmediata al Responsable de Plataforma. La corrida del día siguiente incluye el backfill del día perdido.
- **A2 — % de cuarentena > 1% del lote:** la corrida termina pero se marca `WARN` y dispara alerta: un pico de rechazos indica un problema aguas arriba (bug de app, regla desalineada), no datos "malos" normales.
- **A3 — Reproceso de un lote en cuarentena:** resuelto el problema de origen, el Responsable relanza la corrida de esa fecha lógica desde Airflow; la idempotencia del paso 5 garantiza que no haya duplicados.
- **A4 — Corrida que excede su ventana (solapa con la siguiente):** el sensor de no-concurrencia encola la siguiente; dos encolamientos consecutivos generan alerta de capacidad.
- **A5 — Carga del dataset histórico NYC:** `dag_historico_nyc` procesa el CSV crudo de yellow taxi por lotes con las mismas reglas Silver (adaptadas a los campos del dataset: la validación financiera compara `total_amount` contra la suma de sus componentes) y carga `fact_viaje_historico`, separado de la operación propia. Un registro corrupto no detiene el lote.

**Postcondiciones:** particiones Gold de la fecha lógica cargadas de forma idempotente; cuarentena poblada con los rechazos; métricas de calidad publicadas; alertas emitidas si aplica.

---

## CU-O16 — Publicar los indicadores para los informes de las áreas

**Actores:** Sistema; jefes de área (consumidores)

**Precondiciones:** corrida Gold del dominio finalizada `OK` o `WARN`.

**Flujo principal:**
1. Con la carga Gold confirmada, el sistema refresca las vistas materializadas que alimentan cada informe compuesto (definidas por informe táctico: % de flota activa por franja y zona, tasa de discrepancias, margen de comisión, conversión de onboarding, documentación vigente por tipo, uso de integraciones por endpoint).
2. El catálogo de informes marca cada informe con su timestamp de datos ("datos al ..."), visible para el consumidor.
3. Los tableros de los jefes de área consultan exclusivamente estas vistas; nunca las tablas transaccionales.

**Flujos alternos:**
- **A1 — Carga fallida del dominio:** los informes del dominio siguen sirviendo la última versión buena, marcada "datos al día anterior"; el catálogo muestra el aviso de retraso. Nunca se publica un informe parcial.
- **A2 — Vista materializada corrupta o inconsistente:** el Responsable puede regenerarla desde Gold sin re-ejecutar el DAG (las vistas son derivadas, no fuente).
- **A3 — Informe consultado durante el refresco:** el refresco es atómico (swap de vista); el consumidor ve la versión anterior o la nueva, nunca un estado intermedio.

**Postcondiciones:** vistas publicadas con marca temporal; consumidores notificados del retraso cuando aplica; la frescura de cada informe es siempre verificable.
