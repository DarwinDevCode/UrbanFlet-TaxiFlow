# Propuesta — rediseño del flujo de fallas de vehículo (Fase 4)

**Fecha:** 2026-08-14 · **Estado:** propuesta, sin implementar · Requiere tu aprobación.

Complementa [AUDITORIA_UX_CATALOGOS.md](AUDITORIA_UX_CATALOGOS.md) y
[PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md](PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md).

---

## 1. Corrección de la premisa de partida

El encargo decía: *"El flujo de falla ya tiene una entrada parcial: las incidencias de viaje por
avería (CU-O07 A4) se convierten en 'pre-órdenes' heredando vehículo, descripción y posición"*.

**Eso describe la especificación, no el código.** Verificado por tres vías independientes:

| Evidencia | Resultado |
|---|---|
| `viajes/service_ejecucion.py:12` | *"A4 (incidencia en ruta → notificar al Coordinador de Operaciones): ese rol no está cableado con un canal de notificación propio todavía"* — **diferido** |
| `mantenimiento/service.py:9` | *"la pre-orden por incidencia de viaje (A1 de CU-O12, necesita CU-O07 de Fase 3)"* — **fuera de alcance** |
| Datos reales | `db.viajes.countDocuments({incidencias:{$exists:true}})` = **0**<br>`db.ordenes.countDocuments({orden_madre_id:{$ne:null}})` = **0** |

**No hay entrada parcial. No hay ninguna entrada.** El único camino que existe hoy para que una
falla entre al sistema es que el Jefe de Mantenimiento cree una orden a mano en `web-interno`.

Esto **aumenta** el alcance real respecto de lo que el encargo suponía, y conviene saberlo antes de
decidir qué construir.

---

## 2. El flujo actual, de principio a fin (lo que realmente hay)

```
        ⚠️  La falla ocurre (en ruta o en el patio)
                        │
                        │   ❌ NO existe forma de reportarla desde
                        │      web-conductor. Ni con viaje ni sin viaje.
                        │      El conductor llama por teléfono / avisa de palabra.
                        ▼
   👤 Jefe de Mantenimiento la teclea a mano en web-interno
                        │
                        ▼
              ┌───────────────────┐
              │  ORDEN: ABIERTA   │  ← se crea con: vehículo, tipo, descripción libre,
              └───────────────────┘     km entrada (tecleado), taller (texto libre),
                        │               fecha programada, repuestos estimados
                        │               ▸ opcional: retira el vehículo de servicio
                        │               ▸ notifica al socio propietario ✅
                        ▼
              ┌───────────────────┐
              │     EN_TALLER     │  ← un clic. Sin auditoría (ver §4, hallazgo H8).
              └───────────────────┘     Sin actividades, sin avances, sin fechas.
                        │
                        │   ❌ Entre EN_TALLER y CERRADA no hay NADA.
                        │      Ni un comentario, ni una foto, ni un avance.
                        │      El vehículo puede estar 3 semanas en este limbo.
                        ▼
              ┌───────────────────┐
              │      CERRADA      │  ← trabajos realizados, repuestos consumidos,
              └───────────────────┘     costo total, horas taller, km salida
                                        ▸ opcional: habilita el vehículo
                                        ▸ notifica al socio ✅
```

Volumen real hoy: 134 órdenes — 67 CERRADA, 25 ABIERTA, 22 EN_TALLER, 20 ANULADA.

---

## 3. Clasificación elemento por elemento (lo que pide la Fase 4)

### Elemento 1 — Reporte de falla fuera del contexto de un viaje

**Clasificación: ❌ NO EXISTE — se propone agregar (con matiz).**

No solo falta el reporte *fuera* del viaje: **tampoco existe el reporte dentro del viaje** (CU-O07
A4, ver §1). El conductor no tiene forma alguna de reportar una falla desde su portal.

Respondiendo a la pregunta explícita del encargo (*"¿debería el Jefe de Mantenimiento o el propio
conductor poder reportar una falla directamente?"*):

**Recomendación: el conductor, sí; el Jefe, ya puede.** El Jefe ya crea órdenes directamente — darle
un "reporte de falla" separado sería una segunda puerta al mismo sitio. Quien no tiene puerta es el
conductor, que es justamente **quien detecta la falla**.

**Restricción de modelo de datos que condiciona el diseño:** `diseno_base_datos.md:144` decidió que
`INCIDENCIA` va **embebida en el documento del viaje** (*"`viajes` con traza, calificaciones e
incidencias embebidas"*). Eso funciona para una falla en ruta, pero **no puede alojar una falla sin
viaje** — no hay documento donde embeberla.

**Propuesta: una sola colección `reportes_falla`, con `viaje_id` opcional.**

```
reportes_falla {
  _id, vehiculo_id, conductor_id,
  viaje_id: str | None,        ← None = reporte fuera de viaje (patio, revisión, fin de turno)
  tipo_falla: str,             ← del catálogo `motivos`, categoría `incidencia`
  descripcion: str,            ← texto libre (clase B, ver auditoría §2.7)
  lat, lon, ts,
  impide_continuar: bool,      ← si true y hay viaje → CU-O07 A4: cancela y redespacha
  estado: "PENDIENTE" | "CONVERTIDO_A_ORDEN" | "DESCARTADO",
  orden_id: str | None,        ← trazabilidad al convertirlo
  evidencias: [ … ]            ← ver elemento 2
}
```

**Por qué una colección propia en vez de embeberla en el viaje**, apartándome de la nota del diseño:
una falla sin viaje no tiene dónde embeberse, y el consumidor principal (la bandeja del Jefe de
Mantenimiento) necesita consultar *"todos los reportes pendientes de todos los vehículos"* — una
consulta transversal que sobre un array embebido en 1.3M viajes es inviable. Es el mismo
razonamiento que el propio diseño aplicó a `OFERTA` (*"vive fuera de `viajes` porque se consulta por
conductor"*) y a `DOCUMENTO` (*"los consulta el job diario transversalmente, fuera del ciclo de la
solicitud"*). **Es una desviación deliberada del diseño original, con el mismo criterio que el
diseño ya usó dos veces.**

Con esto, A1 de CU-O12 (pre-orden) se vuelve implementable: la bandeja lista los `PENDIENTE` y el
Jefe convierte con un clic, heredando vehículo, descripción y posición.

---

### Elemento 2 — Adjuntar fotos / evidencia

**Clasificación: ❌ NO EXISTE, y el mecanismo que el encargo asumía reusable tampoco existe.**

El encargo decía: *"verifica si el sistema ya tiene capacidad de carga de archivos en algún otro
flujo (documentos de solicitud ya la usan, según la spec) y reusa ese mecanismo"*.

**Verificado: no hay ninguna capacidad de carga de archivos en el backend.** Cero ocurrencias de
`UploadFile`, `multipart` o `File(` en todo `backend/src/`. Lo que existe es:

| Campo | Qué es realmente |
|---|---|
| `documentos.url_objeto: str` | Un **string** que apunta a un objeto que ningún endpoint sube |
| `usuarios.conductor.foto_url: str` | Un **campo de URL** que el conductor pega a mano (ver `PerfilPropio`) |

Y la carga de documentos de postulación está declarada **backlog consciente** en CLAUDE.md §3.1 y
§8.3. El formulario de postulación envía `documentos: []` literalmente.

**Por lo tanto: no hay mecanismo que reusar. Hay que decidir si se construye uno.** Es la decisión
más cara de esta Fase 4 y la presento con opciones en vez de elegir por ti:

| Opción | Qué implica | Costo | Consecuencia |
|---|---|---|---|
| **A — Campo `url_foto` de texto** (patrón `foto_url` ya existente) | El conductor pega una URL | **Muy bajo** | Consistente con lo que ya hace el proyecto, pero **irreal para un conductor en la carretera con una avería** — nadie va a subir una foto a otro lado y pegar el enlace |
| **B — Carga real con almacenamiento local** | `UploadFile` + volumen en disco + endpoint de servido | **Medio-alto** | Primer mecanismo de archivos del proyecto. Sirve también para desbloquear la carga de documentos de postulación (backlog) |
| **C — Carga real a almacenamiento de objetos** (S3/MinIO) | Lo anterior + infraestructura nueva | **Alto** | Correcto para producción, desproporcionado para un proyecto académico con el stack ya en 7GB de límite |
| **D — Aplazarlo** | Reporte de falla sin fotos en la primera ronda | **Cero** | El flujo funciona igual; la evidencia fotográfica se suma después |

**Mi recomendación: D para la primera ronda, luego B.** El valor del rediseño del flujo de fallas
(reporte del conductor → pre-orden → seguimiento) **no depende de las fotos**, y meter el primer
mecanismo de carga de archivos del proyecto dentro de esta misma ronda mezcla dos trabajos de
naturaleza y riesgo muy distintos. Si prefieres las fotos desde el día uno, la opción es **B**, no
A — un campo de URL en una pantalla de emergencia es un selector que promete algo que no ocurre.

---

### Elemento 3 — Seguimiento de actividades / estado de la reparación

**Clasificación: ❌ NO EXISTE — se propone agregar. Es el hueco más grande del flujo actual.**

Hoy entre `EN_TALLER` y `CERRADA` no hay absolutamente nada: ni comentarios, ni avances, ni fechas
intermedias, ni quién hizo qué. Con 22 órdenes reales en `EN_TALLER` ahora mismo, no hay forma de
saber si alguna lleva un día o tres semanas.

Además, la propia spec pide dos cosas que hoy no tienen dónde vivir:
- **CU-O12 A3**: *"la orden puede quedar `ABIERTA` en espera de repuesto, **con el motivo visible**"*
  → no hay campo ni estado para "esperando repuesto".
- **CU-O13 A1**: cerrar la original y **abrir una correctiva encadenada** → `orden_madre_id` existe
  en el esquema y en el código… pero **nunca se asigna** (`crear_orden` lo pone `None` siempre) y
  hay **0 órdenes encadenadas** en los datos. Es un campo vestigial.

**Propuesta A — bitácora de actividades embebida en la orden** (recomendada):

```
ordenes.actividades: [
  { ts, actor_id, rol, tipo: "COMENTARIO" | "AVANCE" | "ESPERA_REPUESTO" |
                            "REPUESTO_RECIBIDO" | "CAMBIO_ESTADO",
    detalle: str, evidencias: [...] }
]
```

Embebida (no colección aparte) porque se lee **siempre junto con su orden** y nunca de forma
transversal — es el mismo criterio con el que el diseño embebió los repuestos (*"los repuestos solo
existen dentro de su orden"*). El volumen es acotado: unas pocas entradas por orden.

**Propuesta B — un estado nuevo `ESPERANDO_REPUESTO`**, entre `EN_TALLER` y `CERRADA`:

```
ABIERTA → EN_TALLER ⇄ ESPERANDO_REPUESTO → CERRADA
   └────────────────→ ANULADA
```

Esto satisface CU-O12 A3 de forma explícita y hace visible en la bandeja *por qué* un vehículo lleva
semanas parado. **Advertencia de impacto:** agregar un estado toca
`EstadoOrden` (schema), la máquina de estados, el panel táctico de Mantenimiento, los filtros de la
UI y **el DAG `dag_mantenimiento_gold`** (que extrae órdenes `CERRADA` — no se rompería, pero el
informe de "órdenes abiertas" del panel táctico sí necesitaría incluir el estado nuevo). Es
perfectamente factible, pero **no es un cambio cosmético** y conviene decidirlo explícitamente.

**Propuesta C — cablear `orden_madre_id`**: al cerrar una orden, opción *"abrir correctiva
encadenada"* que crea la orden hija con la referencia. Bajo esfuerzo (el campo ya existe en el
esquema, el schema de salida ya lo expone) y cierra CU-O13 A1.

---

### Elemento 4 — Costo estimado vs. costo real

**Clasificación: 🟡 EXISTE PARCIAL — falta la comparación, no el dato.**

Verificado en el código:

| Concepto | Estado real |
|---|---|
| Costo estimado a nivel de orden | ❌ **No existe.** `ORDEN_MANTENIMIENTO` no tiene `costo_estimado` (ni en la spec de datos ni en el código) |
| Costo estimado de repuestos | ✅ **Existe** — `repuestos_estimados[].costo_unitario` × `cantidad` es derivable |
| Costo real | ✅ Existe — `costo_total`, obligatorio al cerrar (`Field(gt=0)`), + `repuestos_consumidos[]` con costos reales |
| **Comparación estimado vs. real** | ❌ **No existe en ninguna parte** — ni en el backend, ni en la UI, ni en los informes |

Es decir: **el dato para comparar ya está casi todo ahí y nadie lo compara.** Hoy el Jefe registra
repuestos estimados con costos al abrir, y repuestos consumidos con costos al cerrar, y el sistema
nunca pone las dos cifras una al lado de la otra.

**Propuesta (bajo esfuerzo, alto valor):**
1. Calcular y mostrar **`costo_estimado`** derivado de `repuestos_estimados` (suma), sin campo nuevo
   en la base.
2. Agregar **`mano_obra_estimada`** opcional al crear la orden — sin esto, el estimado solo cubre
   repuestos y la comparación es engañosa.
3. En el panel de cierre, mostrar **estimado vs. real con la desviación en %**.
4. Registrar la desviación en la bitácora al cerrar (mismo evento `ORDEN_MANTENIMIENTO_CIERRE`, que
   ya se escribe — solo se le suman los campos).

Esto alimentaría de forma natural el panel táctico de Mantenimiento y el estratégico de Estado y
Costo de Flota, que hoy solo ven costo real.

---

### Elementos adicionales encontrados en la auditoría (no estaban en la lista original)

| # | Hallazgo | Clasificación |
|---|---|---|
| **H6** | **CU-O12 P1 no se cumple**: la spec pide que el Jefe vea la ficha del vehículo con *"kilometraje acumulado, fecha y km de la última intervención, y el plan preventivo aplicable"*. El formulario solo pide buscar por placa y **teclear el km a mano**. | ❌ No existe |
| **H7** | **`vehiculos.km_acumulado` = 0 en los 81 vehículos.** El campo existe pero **nada lo alimenta**, pese a que el sistema acumula `km_recorridos` por viaje. Por eso CU-O12 A2 (pre-orden automática por umbral de km) es imposible hoy: no hay km contra el cual comparar. | ❌ No existe (bug de datos real) |
| **H8** | **`marcar_en_taller` no escribe evento de auditoría**, a diferencia de crear/cerrar/anular, que sí lo hacen. Es una transición de estado de una entidad de negocio sin rastro en bitácora — inconsistente con el contrato write-ahead de CU-O17 que el resto del módulo respeta. | 🟡 Gap de auditoría |
| **H9** | **CU-O13 P2 no se cumple**: *"el sistema recalcula la fecha/kilometraje de la próxima intervención preventiva"*. No existe ningún campo ni cálculo de próxima intervención. | ❌ No existe |
| **H10** | El **taller** de la orden es texto libre pese a existir el catálogo (ver auditoría H1). | 🟡 Catálogo sin cablear |

**H7 es la más importante de las cinco**: sin `km_acumulado` alimentado, ni la ficha del vehículo
(H6), ni la pre-orden automática por umbral (CU-O12 A2), ni la próxima intervención preventiva (H9)
pueden existir. Es un solo dato que desbloquea tres requisitos de spec.

---

## 4. Flujo propuesto de principio a fin

```
  ⚠️ Falla detectada
        │
        ├─── 🚗 En ruta (con viaje activo) ──────┐
        │    Conductor → "Registrar incidencia"  │
        │    · tipo (selector, catálogo)         │
        │    · descripción (libre)               │
        │    · posición (automática)             │
        │    · ¿impide continuar? ──── sí ──▶ viaje CANCELADO motivo=INCIDENCIA
        │                                         + redespacho automático (CU-O07 A4)
        │                                        │
        ├─── 🅿️ Sin viaje (patio, fin de turno) ─┤
        │    Conductor → "Reportar falla"        │
        │    (mismo formulario, sin viaje_id)    │
        │                                        │
        └─── 👤 Jefe la registra directamente ───┤
                                                 ▼
                                    ┌────────────────────────┐
                                    │  reportes_falla        │
                                    │  estado: PENDIENTE     │
                                    └────────────────────────┘
                                                 │
                                    🔔 notifica al Jefe (reusa disparar_alerta)
                                                 │
                                                 ▼
                                   Bandeja de reportes pendientes
                                   (nueva pestaña en Mantenimiento)
                                                 │
                          ┌──────────────────────┴─────────────┐
                          ▼                                    ▼
                  "Convertir en orden"                    "Descartar"
                  (hereda vehículo, tipo,                 (con motivo)
                   descripción, posición)
                          │
                          ▼
              ┌───────────────────────┐
              │   ORDEN: ABIERTA      │  + taller por SELECTOR (catálogo)
              └───────────────────────┘  + costo estimado calculado
                          │              + notifica al socio ✅ (ya existe)
                          ▼
              ┌───────────────────────┐
              │      EN_TALLER        │◀────┐  + evento de auditoría (corrige H8)
              └───────────────────────┘     │
                          │                 │
                          │   📋 ACTIVIDADES (nuevo): comentarios,
                          │      avances, quién y cuándo
                          │                 │
                          ▼                 │
              ┌───────────────────────┐     │
              │  ESPERANDO_REPUESTO   │─────┘  (CU-O12 A3, motivo visible)
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │       CERRADA         │  + estimado vs. real con desviación %
              └───────────────────────┘  + notifica al socio ✅ (ya existe)
                          │
                          └──▶ opcional: correctiva encadenada (orden_madre_id, CU-O13 A1)
```

---

## 5. Resumen de clasificación

| Elemento | Clasificación | Esfuerzo |
|---|---|---|
| Reporte de falla **en** viaje (CU-O07 A4) | ❌ No existe → **agregar** | Medio |
| Reporte de falla **fuera** de viaje | ❌ No existe → **agregar** (misma colección) | Bajo (incremental sobre lo anterior) |
| Conversión reporte → pre-orden (CU-O12 A1) | ❌ No existe → **agregar** | Bajo |
| Fotos / evidencia | ❌ No existe **ni el mecanismo** → **decisión tuya** (A/B/C/D) | Muy bajo a alto |
| Seguimiento de actividades | ❌ No existe → **agregar** (embebido) | Medio |
| Estado `ESPERANDO_REPUESTO` (CU-O12 A3) | ❌ No existe → **agregar** (con impacto en panel táctico) | Medio |
| Órdenes encadenadas (CU-O13 A1) | 🟡 Campo existe, sin uso → **cablear** | Bajo |
| Costo estimado vs. real | 🟡 Datos existen, falta comparar → **calcular y mostrar** | Bajo |
| Taller como selector | 🟡 Catálogo existe, sin cablear → **cablear** | Bajo |
| Auditoría de `EN_TALLER` (H8) | 🟡 Gap → **corregir** | Muy bajo |
| `km_acumulado` alimentado (H7) | ❌ No existe → **agregar** (desbloquea H6, H9, CU-O12 A2) | Medio |
| Ficha del vehículo (H6, CU-O12 P1) | ❌ No existe → **agregar** (depende de H7) | Medio |
| Próxima intervención preventiva (H9, CU-O13 P2) | ❌ No existe → **agregar** (depende de H7) | Medio |
| Pre-orden automática por umbral (CU-O12 A2) | ❌ No existe → **descartado por ahora** | Alto (depende de H7 + scheduler) |

**Único elemento que descarto explícitamente:** la **pre-orden automática por umbral de kilometraje**
(CU-O12 A2). Requiere `km_acumulado` alimentado *y* un proceso periódico que evalúe umbrales. El
proyecto ya tomó la decisión equivalente en el Módulo 5 de Monitoreo (*"evaluación bajo demanda, no
vigilancia continua — no hay worker/cron apto en este stack sin agregar infraestructura nueva"*).
Alternativa barata si quieres el valor sin la infraestructura: **calcular el umbral al abrir la
ficha del vehículo** y mostrar un aviso *"le toca preventivo"*, en vez de crear la pre-orden sola.

---

## 6. Decisiones que necesito de ti

1. **Fotos (elemento 2)** — ¿opción **D** (aplazar, recomendada), **B** (construir carga real de
   archivos), o **A** (campo de URL)? Es la decisión de mayor impacto en esfuerzo de esta fase.
2. **Estado `ESPERANDO_REPUESTO`** — ¿lo agregamos (toca máquina de estados, panel táctico y
   filtros), o lo modelamos solo como una actividad dentro de `EN_TALLER` (más barato, menos
   visible en la bandeja)?
3. **`reportes_falla` como colección propia** — ¿apruebas la desviación del diseño original (que
   embebía `INCIDENCIA` en el viaje), por las razones de §3 elemento 1?
4. **H7 (`km_acumulado`)** — ¿entra en esta ronda? Desbloquea tres requisitos de spec, pero es un
   trabajo con identidad propia (alimentar el acumulado desde los viajes ya cerrados + mantenerlo).
5. **Alcance de la primera implementación.** Sugerencia de bloque coherente y verificable de punta a
   punta: **reporte de falla del conductor (con y sin viaje) → bandeja → conversión a orden →
   actividades → taller por selector → estimado vs. real**, dejando fotos, `km_acumulado` y el
   estado nuevo para una segunda ronda.
