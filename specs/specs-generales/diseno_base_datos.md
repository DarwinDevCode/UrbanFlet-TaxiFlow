# Diseño de base de datos — UrbanFleet

El modelo soporta los tres niveles organizacionales: el operativo escribe y consulta el transaccional; el táctico consume informes simples (transaccional) y compuestos (columnar); el estratégico consume los KPIs agregados del columnar.

## 1. Modelo lógico (normalizado)

Se diseña primero como modelo relacional en tercera forma normal, independiente del motor. Convenciones: PK = clave primaria, FK = clave foránea; los atributos de dinero son `DECIMAL(10,2)`; los timestamps, UTC.

### 1.1. Personas y acceso

```
USUARIO(usuario_id PK, telefono UNIQUE, email, nombre, hash_password,
        estado, fecha_registro, version_consentimiento, fecha_consentimiento)

ROL(rol_id PK, nombre UNIQUE)
USUARIO_ROL(usuario_id FK, rol_id FK, PK(usuario_id, rol_id))

PASAJERO(pasajero_id PK, usuario_id FK UNIQUE, calificacion_promedio)

CONDUCTOR(conductor_id PK, usuario_id FK UNIQUE, cedula UNIQUE,
          licencia_numero, calificacion_promedio, estado_servicio,
          fecha_alta_socio)
```

Justificación 3FN: los datos de acceso (teléfono, contraseña, consentimiento) dependen del usuario, no del rol de negocio; `PASAJERO` y `CONDUCTOR` son extensiones 1:1 que evitan atributos nulos masivos en `USUARIO` (un pasajero no tiene cédula profesional ni licencia). La calificación promedio es un derivado materializado por rendimiento — decisión declarada, se recalcula desde `CALIFICACION`.

### 1.2. Captación

```
SOLICITUD_CONDUCTOR(solicitud_id PK, usuario_id FK, estado, fecha_envio,
                    fecha_decision, verificador_id FK→USUARIO, motivo_rechazo)

DOCUMENTO(documento_id PK, tipo, propietario_tipo {CONDUCTOR|VEHICULO|SOLICITUD},
          propietario_id, url_objeto, hash_archivo, fecha_emision,
          fecha_vencimiento, estado_verificacion, verificador_id FK, fecha_verificacion)
```

`DOCUMENTO` es una sola entidad para documentos de solicitud, de conductor y de vehículo: el tipo y el vencimiento dependen del documento, no del propietario (evita tres tablas casi idénticas). El par (`propietario_tipo`, `propietario_id`) es una FK polimórfica — se acepta como compromiso consciente y el backend valida la integridad.

### 1.3. Flota y mantenimiento

```
VEHICULO(vehiculo_id PK, placa UNIQUE, marca, modelo, anio, color,
         capacidad, estado_habilitacion, km_acumulado, propietario_id FK→CONDUCTOR)

POSICION(posicion_id PK, vehiculo_id FK, conductor_id FK, lat, lon,
         precision_m, velocidad, rumbo, ts_dispositivo, ts_servidor)

ORDEN_MANTENIMIENTO(orden_id PK, vehiculo_id FK, tipo {PREVENTIVA|CORRECTIVA},
                    estado, descripcion, km_entrada, km_salida, taller,
                    fecha_programada, fecha_cierre, costo_total,
                    orden_madre_id FK→ORDEN_MANTENIMIENTO NULL)

REPUESTO_ORDEN(repuesto_id PK, orden_id FK, descripcion, cantidad, costo_unitario)
```

`REPUESTO_ORDEN` separa el detalle de repuestos (1FN: nada de listas en un campo); `orden_madre_id` modela las órdenes encadenadas de CU-O13 A1.

### 1.4. Viajes y despacho

```
ZONA(zona_id PK, nombre, geometria)

VIAJE(viaje_id PK, pasajero_id FK, conductor_id FK NULL, vehiculo_id FK NULL,
      estado, origen_lat, origen_lon, origen_direccion,
      destino_lat NULL, destino_lon NULL, destino_direccion NULL,
      zona_origen_id FK, zona_destino_id FK NULL,
      franja {DIURNA|NOCTURNA}, tarifa_version_id FK,
      ts_solicitud, ts_asignacion, ts_inicio, ts_fin,
      km_recorridos, min_espera, tarifa_estimada, tarifa_final,
      motivo_cancelacion NULL, actor_cancelacion NULL,
      revision_tarifa BOOL, tarifa_parcial BOOL)

OFERTA(oferta_id PK, viaje_id FK, conductor_id FK, ts_emision,
       ts_respuesta NULL, resultado {ACEPTADA|RECHAZADA|EXPIRADA}, radio_m)

TRAZA_PUNTO(viaje_id FK, seq, lat, lon, velocidad, ts, PK(viaje_id, seq))

CALIFICACION(calificacion_id PK, viaje_id FK, emisor_tipo {PASAJERO|CONDUCTOR},
             puntaje, comentario, ts, UNIQUE(viaje_id, emisor_tipo))

INCIDENCIA(incidencia_id PK, viaje_id FK, tipo, descripcion, lat, lon, ts)

PARAMETRO_TARIFA(tarifa_version_id PK, franja, arrancada, costo_km,
                 costo_min_espera, carrera_minima, vigente_desde, vigente_hasta NULL)
```

3FN estricta en el núcleo: la tarifa aplicada no se copia como cuatro columnas en `VIAJE` sino que se referencia por versión (`tarifa_version_id`), eliminando la dependencia transitiva viaje → fecha → parámetros; el desglose siempre es recalculable y auditable. `OFERTA` conserva cada intento de despacho (insumo del informe de cancelaciones). `TRAZA_PUNTO` está en 1FN (un punto por fila), no como array en el viaje — en lo físico esto se revisará (ver §2).

### 1.5. Recaudación y liquidación

```
PARAMETRO_COMISION(comision_version_id PK, porcentaje, vigente_desde, vigente_hasta NULL)

PAGO(pago_id PK, viaje_id FK UNIQUE, metodo {EFECTIVO|ELECTRONICO},
     monto, referencia_externa NULL, estado, ts_registro, ts_confirmacion NULL)

MOVIMIENTO(movimiento_id PK, viaje_id FK, tipo {COMISION|NETO_SOCIO|AJUSTE},
           monto_firmado, comision_version_id FK NULL, motivo NULL,
           autorizador_id FK NULL, ts, liquidacion_id FK NULL)

LIQUIDACION(liquidacion_id PK, conductor_id FK, periodo_inicio, periodo_fin,
            estado, bruto, comisiones, ajustes, neto, saldo,
            ts_emision, ts_aprobacion NULL, ts_pago NULL,
            aprobador_id FK NULL, liquidacion_ref_id FK NULL)

OBSERVACION_LIQUIDACION(observacion_id PK, liquidacion_id FK, motivo,
                        respuesta NULL, ts, ts_respuesta NULL)
```

El patrón contable es de **movimientos inmutables**: la comisión, el neto y cada ajuste son filas de `MOVIMIENTO` con signo; la liquidación agrupa movimientos, y sus totales son derivados verificables (suma de sus movimientos — redundancia declarada para el comprobante). Nada se actualiza tras emitirse: los errores se corrigen con nuevos movimientos (CU-O11 A4), lo que satisface la regla de integridad de OE5.

### 1.6. Auditoría

```
EVENTO_AUDITORIA(evento_id PK, ts, actor_id, rol, accion, entidad, entidad_id,
                 resultado {OK|DENEGADO|ERROR}, ip, dispositivo,
                 datos_previos NULL, datos_posteriores NULL)
```

Solo inserción; sin FK a entidades de negocio (la bitácora sobrevive a anonimizaciones LOPDP con actor seudonimizado).

### 1.7. Dataset histórico NYC (fuente externa)

```
NYC_RAW_TRIP(fila_id PK, tpep_pickup_datetime, tpep_dropoff_datetime,
             passenger_count, trip_distance, pu_location_id, do_location_id,
             fare_amount, mta_tax, improvement_surcharge, congestion_surcharge,
             tolls_amount, tip_amount, total_amount, payment_type, lote_carga)
```

Se conserva crudo, sin normalizar: es una fuente externa de solo lectura; la limpieza ocurre en el pipeline, nunca sobre el origen.

## 2. Implementación física

### 2.1. Reparto por motor

| Entidad lógica | Motor | Estructura física | Justificación |
|---|---|---|---|
| USUARIO, ROL, PASAJERO, CONDUCTOR | MongoDB | Colección `usuarios` (rol y extensión embebidos) | El perfil se lee siempre completo en cada autorización (CU-O18 A3); un documento por usuario evita 3 joins por petición |
| SOLICITUD_CONDUCTOR + sus DOCUMENTO | MongoDB | `solicitudes` con array de documentos embebido | La solicitud se procesa como agregado: se envía, verifica y decide entera |
| DOCUMENTO de conductor/vehículo vigentes | MongoDB | `documentos` (colección propia) | Los consulta el job diario de vencimientos transversalmente, fuera del ciclo de la solicitud |
| VEHICULO, ORDEN_MANTENIMIENTO + REPUESTO_ORDEN | MongoDB | `vehiculos`, `ordenes` (repuestos embebidos) | Los repuestos solo existen dentro de su orden |
| VIAJE + TRAZA_PUNTO + CALIFICACION + INCIDENCIA | MongoDB | `viajes` con traza, calificaciones e incidencias embebidas | El viaje es el agregado central: se escribe incrementalmente y se lee entero (detalle, comprobante). La traza embebida (array acotado: viaje < 24 h ⇒ < ~17 000 puntos) evita una colección de miles de millones de filas |
| OFERTA | MongoDB | `ofertas` | Vive fuera de `viajes` porque se consulta por conductor (métricas de rechazo) |
| POSICION (histórico) | MongoDB | `posiciones` con TTL de 7 días | Solo sirve para reconstrucción reciente y para la extracción horaria del DAG de flota; el histórico agregado vive en ClickHouse |
| Última posición (tiempo real) | Redis | clave `pos:{vehiculo_id}`, TTL 60 s | Lectura por el mapa y el despacho a frecuencia alta; su expiración implementa la detección de sin señal |
| PAGO, MOVIMIENTO, LIQUIDACION, OBSERVACION | MongoDB | `pagos`, `movimientos`, `liquidaciones` | Movimientos como colección propia (no embebidos): se consultan por periodo y por liquidación, y su inmutabilidad se protege con permisos de solo inserción |
| PARAMETRO_TARIFA, PARAMETRO_COMISION, ZONA | MongoDB | `parametros`, `zonas` | Pocos documentos, versionados, cacheados en memoria del backend |
| EVENTO_AUDITORIA | MongoDB | `bitacora` (solo inserción) | Write-ahead desde el mismo backend; sin update/delete en ninguna API |
| NYC_RAW_TRIP | **PocketBase** | Colección `raw_trips` | Mandato de arquitectura: el dataset crudo de yellow taxi vive en PocketBase, aislado del OLTP propio; el DAG histórico lo lee por su API |
| Hechos y dimensiones (§2.2) | **ClickHouse** | Tablas MergeTree particionadas por fecha | Agregaciones por zona/franja/periodo para informes compuestos y KPIs |

Índices mínimos en MongoDB: `usuarios.telefono` (unique), `viajes.{pasajero_id, ts_solicitud}`, `viajes.{conductor_id, ts_solicitud}`, `viajes.estado` (parcial, solo estados activos), `ofertas.{conductor_id, ts_emision}`, `pagos.viaje_id` (unique), `movimientos.liquidacion_id`, `documentos.fecha_vencimiento`, `bitacora.{actor_id, ts}`, `posiciones.{vehiculo_id, ts}` + índice TTL.

### 2.2. Modelo dimensional en ClickHouse (Gold)

Dimensiones:

```
dim_tiempo(fecha_id, fecha, dia, semana, mes, trimestre, anio, franja, dia_semana)
dim_zona(zona_id, nombre, distrito)
dim_conductor(conductor_id, antiguedad_meses, tipo_licencia)   -- SCD tipo 1, sin datos personales
dim_metodo_pago(metodo_id, nombre)
dim_canal(canal_id, nombre)                                    -- app, web, referido, campaña
dim_documento(tipo_documento_id, nombre)
```

Hechos (motor `MergeTree`, `PARTITION BY toYYYYMM(fecha)`, `ORDER BY` según el patrón de consulta indicado):

| Tabla | Grano | Métricas | ORDER BY | Informes que alimenta |
|---|---|---|---|---|
| `fact_viaje` | un viaje finalizado o cancelado | km, min_espera, duracion_min, tarifa, seg_asignacion, cancelado (0/1) | (fecha, zona_origen_id, franja) | Tiempo de asignación por zona/hora; demanda; cancelaciones; rentabilidad por zona (OE4, CU-E02) |
| `fact_ubicacion_flota` | vehículo × hora | min_disponible, min_ocupado, min_sin_senal | (fecha, hora, zona_id) | % de flota activa por franja y zona |
| `fact_recaudacion` | un pago | monto, comision, neto, discrepancia (0/1) | (fecha, metodo_id) | Tasa de discrepancias; % conciliado mensual; KPI OE5 |
| `fact_liquidacion` | una liquidación | bruto, comisiones, ajustes, neto, horas_hasta_pago | (periodo_fin, conductor_id) | Margen de comisión; tiempo promedio de liquidación |
| `fact_registro_usuario` | una solicitud/alta | dias_aprobacion, convertido (0/1) | (fecha, canal_id) | Conversión de onboarding; efectividad de campañas |
| `fact_cumplimiento_documental` | documento × día de corte | vigente (0/1), dias_para_vencer | (fecha, tipo_documento_id) | Documentación vigente por tipo y tendencia |
| `fact_integracion_api` | credencial × endpoint × hora | solicitudes, errores, latencia_p95 | (fecha, endpoint) | Uso de integraciones externas |
| `fact_viaje_historico` | un viaje del dataset NYC validado | distancia, duracion, componentes de tarifa | (fecha, pu_location_id) | Calibración tarifaria y de demanda (referencia externa) |

Las dimensiones no llevan datos personales (nombre, teléfono, cédula): los informes tácticos y estratégicos operan sobre identificadores; el detalle nominal se consulta, con rol, en el transaccional. Cada tabla de cuarentena (`rejected_*`) replica el esquema de su staging más `flag_rechazo`, `lote_id` y `ts`.

### 2.3. Reglas contra la duplicación entre motores

1. **Un dato maestro vive en un solo motor.** Perfiles, viajes, pagos y órdenes existen solo en MongoDB; ClickHouse guarda derivados agregados con identificadores, nunca la copia del documento.
2. **Duplicaciones justificadas y declaradas:** (a) la última posición en Redis es una réplica efímera (TTL 60 s) de la cola de `posiciones`, por latencia del despacho; (b) los totales de `LIQUIDACION` son derivados de sus movimientos, materializados para el comprobante del socio; (c) `fact_viaje` re-expresa atributos del viaje al grano analítico — es transformación, no réplica.
3. **El dataset NYC nunca se copia a MongoDB:** PocketBase → (validación en pipeline) → `fact_viaje_historico` en ClickHouse. La operación propia y el histórico externo no se mezclan en ninguna tabla.
4. **Sentido único del flujo analítico:** MongoDB/PocketBase → Airflow → ClickHouse. Nada escrito en ClickHouse regresa a los motores operativos.
