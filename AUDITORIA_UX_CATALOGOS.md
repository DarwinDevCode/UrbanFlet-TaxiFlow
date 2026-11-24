# Auditoría de UX — campos de entrada libre y patrón de catálogos

**Fecha:** 2026-08-14 · **Alcance:** los 3 portales (`web-pasajero`, `web-conductor`, `web-interno`)
· **Estado:** auditoría, sin cambios de código.

Documentos hermanos de esta ronda: [PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md](PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md)
(Fase 3) y [PROPUESTA_FLUJO_FALLAS_VEHICULO.md](PROPUESTA_FLUJO_FALLAS_VEHICULO.md) (Fase 4).

---

## 0. Resumen ejecutivo — los 5 hallazgos que cambian el planteamiento

El prompt de esta auditoría partía de premisas tomadas de la especificación. Verificadas contra el
código y los datos reales, **tres de ellas ya no son ciertas y dos lo son pero por una razón
distinta a la esperada**. Esto cambia el alcance de lo que hay que construir.

| # | Hallazgo | Impacto |
|---|---|---|
| **H1** | **El catálogo de talleres YA EXISTE** (`catalogos/`, colección `talleres`, CRUD completo con auditoría, creado en la ronda de usabilidad P3 del 2026-08-07) — pero **nada lo consume**: `OrdenCrearRequest.taller` sigue siendo `str` libre y el formulario sigue siendo `<TextField label="Taller">`. | No hay que construir el catálogo. Hay que **cablearlo**. Esfuerzo mucho menor al previsto. |
| **H2** | **Los 4 catálogos existentes están vacíos de datos reales**: contienen exactamente 1 registro de prueba cada uno (`talleres`: "Taller QA Cache" *inactivo*; `motivos_cancelacion`: "Prueba motivo"; `tipos_documento`: "Prueba documento"; `zonas`: "Prueba"). | **Sembrar los catálogos es prerrequisito de cualquier cableado.** Un `<Select>` conectado hoy mostraría una lista vacía o un registro de QA. |
| **H3** | **Todos los endpoints de catálogo están gateados en exclusiva a `admin_sistema`** (`catalogos/router.py:12`). `jefe_mantenimiento` **no puede ni leer** la lista de talleres → un `<Select>` en Mantenimiento daría **403**. | Blocker de arquitectura. Hay que separar lectura de escritura antes de cablear nada (§4.3 del documento de propuesta). |
| **H4** | **`INCIDENCIA` no existe en el código.** Ni la entidad, ni el endpoint, ni la conversión a pre-orden. Confirmado por triple vía: `service_ejecucion.py:12` declara A4 diferido, `mantenimiento/service.py:9` declara la pre-orden fuera de alcance, y `db.viajes.countDocuments({incidencias:{$exists:true}})` = **0**. | La premisa "el flujo de falla ya tiene una entrada parcial" describe la spec, **no el código**. Ver Fase 4. |
| **H5** | **No existe ninguna capacidad de carga de archivos en el backend.** Cero ocurrencias de `UploadFile`/`multipart` en `backend/src/`. Lo que la spec llama "carga de documentos" es un campo de texto `url_objeto: str` que apunta a un objeto que nadie sube. | La premisa "reusa el mecanismo de carga de archivos que ya existe" **no tiene mecanismo que reusar**. Ver Fase 4, elemento 2. |

**Consecuencia de conjunto:** el trabajo de esta ronda no es mayormente "diseñar catálogos nuevos",
es **terminar de conectar el catálogo que ya se construyó y nunca se enchufó**, y sembrarlo. Eso
mueve el ítem de mayor impacto del proyecto a la casilla de bajo esfuerzo.

---

## 1. Metodología — cómo se midió (no se asumió)

La regla del encargo era explícita: *"un campo que en la práctica nunca se repite no es un buen
candidato aunque conceptualmente parezca una entidad — verifícalo contra los datos existentes"*.

1. **Inventario de formularios**: extracción de todos los `label="…"` de los 3 portales
   (`TextField`/`TextArea`/`Select`), y lectura del componente que arma cada request.
2. **Contraste con el esquema real**: los schemas Pydantic de cada dominio (`str` libre vs. `Literal`
   vs. FK), no la spec.
3. **Medición de repetición real en MongoDB**: agregaciones `$group` sobre las colecciones vivas del
   entorno de desarrollo. Los conteos de abajo son reales, de la base con 134 órdenes, 81 vehículos,
   142 documentos, 169 solicitudes y ~1.3M viajes.
4. **Separación explícita de artefactos de siembra**: buena parte del volumen viene de scripts de
   seed (`seed_ordenes_mantenimiento_demo.py`, dataset NYC). Cuando un conteo alto es un artefacto
   de plantilla y no evidencia de uso humano, **se dice**, y la conclusión se ajusta.

---

## 2. Fase 1 — Inventario por portal, con evidencia

### 2.1 Clasificación usada

| Clase | Significado |
|---|---|
| **A** | Candidato a catálogo, con evidencia real de repetición |
| **B** | Se queda como texto libre — información genuinamente variable |
| **C** | **No es texto libre: es un input que no existe.** El valor se hardcodea en cliente o servidor y el usuario nunca elige |

La clase **C** no estaba en el encargo y apareció al revisar el código. Es importante porque tres de
los "candidatos a catálogo" del prompt resultaron ser de esta clase: el problema no es que el
usuario escriba mal, es que **no se le pregunta nada**.

---

### 2.2 `web-interno` → Mantenimiento (WorkPanel de órdenes)

Es el formulario con más densidad de entrada libre del sistema y el foco del encargo.

| Campo (label) | Schema backend | Clase | Evidencia real medida |
|---|---|---|---|
| **Taller** | `OrdenCrearRequest.taller: str` | **A** | **134 órdenes → 6 valores distintos.** `Lubricadora Express` 33, `Taller Central` 30, `Taller Norte` 26, `Taller El Motor` 23, `Servicio Rápido Quevedo` 20, y **`"1"` ×2** (basura tipeada a mano). **132/134 = 98.5% de concentración en 5 nombres.** Candidato de libro. |
| **Repuestos → Descripción** | `RepuestoInput.descripcion: str` | **A (media confianza)** | 197 líneas de repuesto, pero 195 son plantilla de seed (`"Repuesto estimado A"` ×130, `"Repuesto consumido A"` ×65). **Las 3 entradas humanas reales son `"Filtro de aceite"`, `"Bujias"` (sin tilde) y `"No se"`.** La muestra humana es demasiado chica para probar repetición, pero ya exhibe los dos síntomas que un catálogo resuelve: ortografía inconsistente y basura. Ver §2.7 para la recomendación matizada. |
| **Descripción** (de la orden) | `OrdenCrearRequest.descripcion: str` | **B** | Máxima repetición = 2, y son basura (`"123"`) o genéricos. El resto son únicos (`"SEED-DEMO-00099: Motor no enciende en frío"`). **Se queda libre.** Pero ver §2.7: el *síntoma* subyacente sí es catalogable aunque la narrativa no. |
| **Trabajos realizados** | `OrdenCerrarRequest.trabajos_realizados: str` | **B** | Aparente repetición alta (12, 11, 10…) que es **100% plantilla de seed**. La única entrada humana repetida es `"Cambio de aceite completado"` ×2. Es una narrativa de lo efectivamente hecho: **variable por naturaleza, se queda libre.** |
| **Motivo del ajuste** (km) | `OrdenCerrarRequest.motivo_ajuste: str \| None` | **B** | 0 usos reales. Justifica una excepción puntual (cambio de odómetro); es una explicación, no una taxonomía. **Se queda libre.** |
| **Motivo** (anulación) | `OrdenAnularRequest.motivo: str` | **A (baja prioridad)** | 20 órdenes anuladas, **1 solo valor distinto** (`"Vehículo dado de baja antes de iniciar el trabajo."`) — pero es seed. Concepto acotado (CU-O12 A4 exige motivo obligatorio). Encaja como categoría nueva del catálogo `motivos` ya existente. |
| Cantidad / Costo unitario / Km / Fechas | numéricos y fechas | — | Fuera de alcance (no son texto libre). |

**Dato de diseño relevante para repuestos:** para `"Repuesto estimado A"` se registraron **130
costos unitarios distintos** (de $10.83 a $79.96). Esto es una señal fuerte de que **el catálogo de
repuestos NO debe llevar precio fijo** — el precio varía por compra y pertenece a la línea de la
orden, no al maestro. Un catálogo de repuestos con `costo_referencial` invitaría a confundirlo con
el precio real.

---

### 2.3 `web-conductor` → formulario de postulación (CU-O01)

| Campo | Schema | Clase | Evidencia real medida |
|---|---|---|---|
| **Marca** | `str` libre | **A** | 81 vehículos → 6 marcas reales (`Kia` 21, `Toyota` 18, `Chevrolet` 13, `Nissan` 11, `Hyundai` 8, `Suzuki` 8) **+ basura: `"X"` y `"123"`**. Conjunto acotado y estable del mundo real. |
| **Color** | `str` libre | **A** | 81 vehículos → 7 colores reales (`Blanco` 16, `Negro` 15, `Azul` 14, `Rojo` 12, `Plata` 11, `Gris` 7, `Amarillo` 4) **+ basura: `"Z"` y `"123"`**. Conjunto cerrado por naturaleza. |
| **Modelo** | `str` libre | **A + bug de datos** | **Hallazgo no anticipado: el campo `modelo` está lleno de AÑOS** (`2022` ×10, `2024` ×9, `2018` ×9, `2020` ×8, `2021` ×8…). Solo 5 de 81 registros tienen algo parecido a un modelo real: `"Yaris"` ×3 y **`"Yirus"` ×2 — que es "Yaris" mal escrito**. El formulario tiene `Año` y `Modelo` contiguos y **la gente los confunde sistemáticamente**. |
| **Nombre completo / Cédula / Licencia / Placa** | `str` | **B** | Identificadores únicos por persona/vehículo. **Se quedan libres** (con validación de formato, no catálogo). |
| Capacidad / Año | numéricos | — | Fuera de alcance. |

`"Yirus"` vs `"Yaris"` es la demostración más limpia de toda la auditoría de por qué un selector
importa: con n=5 ya hay una variante corrupta que rompe cualquier agrupación futura por modelo.

**Nota de alcance:** `Modelo` como catálogo depende de `Marca` (es una jerarquía marca→modelo). Eso
lo hace más caro que `Marca`/`Color`. Ver priorización en el documento de propuesta.

---

### 2.4 `web-conductor` → viaje activo

| Campo | Schema | Clase | Evidencia |
|---|---|---|---|
| **Motivo de cancelación del conductor** | `CancelarConductorRequest.motivo: str` | **C — input inexistente** | El backend acepta un motivo, pero el cliente lo **hardcodea**: `body: { motivo: "cancelado por el conductor" }` (`web-conductor/src/App.tsx:418`). El conductor nunca elige ni escribe nada. **La spec CU-O07 A3 exige literalmente "con selección obligatoria de motivo"** → esto es un incumplimiento de spec, no una mejora opcional. |
| **Registrar incidencia** (avería/siniestro) | — | **C — no existe** | CU-O07 A4 pide un botón "Registrar incidencia" con selección de tipo. No existe botón, ni endpoint, ni entidad. Ver Fase 4. |
| **Comentario** (calificación) | `str \| None` | **B** | Opinión libre sobre un viaje puntual. **Se queda libre.** |
| **Monto cobrado en efectivo** | numérico | — | Fuera de alcance. |

---

### 2.5 `web-pasajero`

| Campo | Clase | Evidencia |
|---|---|---|
| **Motivo de cancelación del pasajero** | **C — input inexistente** | `viajes/service.py:305-318` **hardcodea** `"Cancelado por el pasajero"`. 93,094 viajes con ese valor idéntico. Al pasajero nunca se le pregunta por qué cancela. La spec (CU-O07 A1/A2) distingue `NO_SHOW_PASAJERO` / `CANCELADO_PASAJERO_EN_CAMINO` / `INCIDENCIA` — **el sistema no puede distinguirlos porque no los captura**. Impacto directo: `rpt_tasa_cancelacion` agrupa "por motivo" sobre un campo que solo tiene un valor. |
| **Referencia de origen** (opcional) | **B** | Indicación puntual al conductor ("casa portón negro"). Variable por definición. **Libre.** |
| **Destino** | **B** | Resuelto por mapa/geocoding, no tecleado como taxonomía. **Libre.** |
| **Etiqueta** (dirección favorita) | **B** | Ya está acotado en la UI con chips Casa/Trabajo/Otro. Datos reales: 3 registros (`Trabajo` ×2, `Otro` ×1). **No amerita catálogo administrable** — es un enum de 3 valores de la UI. |
| **Comentario** (calificación) | **B** | Igual que en conductor. **Libre.** |

---

### 2.6 `web-interno` → resto de WorkPanels

| Pantalla / campo | Clase | Evidencia real |
|---|---|---|
| Solicitudes → **Motivo de rechazo** | **A parcial + B** | 45 solicitudes con motivo, 2 valores distintos (25 y 20) — **ambos de seed**. El *tipo* de rechazo es acotado ("documento ilegible", "vehículo no cumple"), el *detalle* no. Recomendación: **selector de categoría + texto libre complementario**, no uno u otro. |
| Usuarios → **Motivo suspensión/baja** | **A parcial + B** | Solo 2 usos humanos reales: `"Suspención de prueba"` (mal escrito) y `"Esta es una prueba"`. Muestra insuficiente para probar repetición; misma recomendación híbrida que arriba. |
| Cumplimiento → **Motivo (obligatorio)** al observar | **B** | Ya se corrigió en una ronda previa para que el supervisor escriba el suyo (antes era hardcodeado). Es una observación puntual sobre un documento concreto. **Libre.** |
| Cumplimiento → **Tipo de documento** (filtro) | **A — ya resuelto parcialmente** | 142 documentos, **exactamente 2 valores** (`LICENCIA_CONDUCIR` ×71, `MATRICULA_VEHICULAR` ×71). El catálogo `tipos_documento` ya existe y `captacion/service.py:165-173` **ya valida contra él**. Ver la mina latente en §3. |
| Integraciones → Nombre / Alcance | **B** | Nombre propio de una credencial de una sola vez. **Libre.** |
| Catálogos → Nombre / Descripción / Dirección / Teléfono | **B** | Son los campos *del propio catálogo*. **Libres por definición.** |

---

### 2.7 Campos que se quedan como texto libre — declaración explícita

El encargo pide documentar esto, no solo lo que se convierte. **No se convierten a selector:**

- **Descripción de la orden de mantenimiento** y **trabajos realizados** — narrativa del caso
  concreto. Convertirlos empobrecería el registro.
  *Matiz que sí vale la pena*: aunque la narrativa es libre, el **síntoma** ("motor no enciende en
  frío", "fuga de líquido de frenos", "ruido en suspensión") sí se repite en los datos. La
  recomendación no es reemplazar la descripción, sino **añadir junto a ella un `tipo_falla`
  seleccionable**, dejando la descripción intacta. Ver Fase 4.
- **Motivo del ajuste de kilometraje** — excepción justificada, por definición narrativa.
- **Comentarios de calificación** (ambos sentidos) — opinión libre.
- **Referencia de origen** del pasajero — indicación puntual.
- **Nombre, cédula, licencia, placa** — identificadores únicos.
- **Nombre/descripción de los propios catálogos** y de credenciales de integración.
- **Etiqueta de dirección favorita** — ya acotada en la UI, volumen trivial (3 registros).

---

## 3. Mina latente detectada (no es un bug hoy, lo será mañana)

`captacion/service.py:165-173` valida `documentos[].tipo` contra `tipos_documento` con `activo:True`
y lanza **422 `TIPO_DOCUMENTO_INVALIDO`** si no encuentra el tipo.

El catálogo contiene **únicamente "Prueba documento"**. Los 142 documentos reales del sistema son
`LICENCIA_CONDUCIR` y `MATRICULA_VEHICULAR`, **ninguno de los cuales está en el catálogo**.

Hoy no explota porque el formulario de postulación envía `documentos: []` (línea 92 de
`web-conductor/src/App.tsx`) y la validación está dentro de un `if documentos:`. **En el momento en
que se habilite la carga de documentos —que es justo lo que propone la Fase 4 para las fotos de
avería— toda postulación con un tipo real fallará con 422.**

Es el ejemplo perfecto del riesgo de H2: **un catálogo vacío no es neutro cuando algo ya valida
contra él.** Sembrarlo es parte del trabajo, no un extra.

---

## 4. Fase 2 — Diseño del patrón "selector + Otro + notificación"

### 4.1 Comportamiento en la UI

```
┌─ Taller ──────────────────────────────┐
│ [ Taller Central              ▾ ]     │
│   · Taller Central                    │
│   · Taller Norte                      │
│   · Lubricadora Express               │
│   ─────────────────                   │
│   · Otro (no está en la lista)…       │
└───────────────────────────────────────┘
        ↓ al elegir "Otro"
┌───────────────────────────────────────┐
│ Nombre del taller *  [____________]   │
│ ⓘ Se registrará y quedará pendiente   │
│   de que el administrador lo agregue  │
│   al catálogo.                        │
└───────────────────────────────────────┘
```

Reglas de comportamiento:

1. **El trabajo del usuario nunca se bloquea.** Elegir "Otro" y escribir el valor permite guardar la
   orden igual. El valor se persiste tal cual en el campo destino (`ordenes.taller`), exactamente
   como hoy — el catálogo no cambia la forma del dato en el registro de negocio.
2. **Se guarda el texto, no una FK.** Decisión deliberada y consistente con lo que el propio
   `catalogos/service.py:1-14` ya documentó para `tipos_documento`/`motivos_cancelacion`: son
   taxonomías de referencia, no claves foráneas. Migrar 134 órdenes históricas a FK es un trabajo
   aparte y no aporta a este objetivo.
3. **El selector precarga solo valores `activo: true`**; los inactivos siguen visibles en registros
   históricos pero no se pueden elegir de nuevo.
4. **Coexistencia con lo histórico:** si una orden vieja tiene `taller: "1"`, al abrirla en modo
   consulta se muestra tal cual. Al editarla, el selector aparece sin valor y obliga a elegir uno
   válido o "Otro". No se reescriben datos históricos en silencio.

### 4.2 Registro de la solicitud — tabla genérica, no una por catálogo

El encargo pide justificar la elección. **Recomendación: una sola colección genérica
`solicitudes_catalogo`**, no una por catálogo.

| Criterio | Tabla genérica ✅ | Tabla por catálogo ❌ |
|---|---|---|
| Bandeja del administrador | Una sola vista, un solo endpoint, un solo componente | N vistas casi idénticas |
| Catálogo nuevo en el futuro | Cero código nuevo de bandeja | Otra tabla + otra vista + otro endpoint |
| Conteo de repeticiones (§4.4) | Una sola agregación `$group` | Repetida N veces |
| Consistencia con el proyecto | Igual criterio que `AccionAuditoria` (un catálogo de acciones, `entidad` distingue) y que `CATALOGO_CREACION` (una acción genérica para los 3 catálogos, `entidad` distingue cuál) | Rompe un patrón ya establecido y validado |

El precedente interno es explícito: `core/audit.py:84-90` decidió exactamente esto para las acciones
de catálogo — *"genéricas para las 3 tablas maestras; `entidad` distingue cuál catálogo cambió, no
hace falta una acción por catálogo"*. La bandeja de solicitudes debe seguir el mismo criterio.

**Forma propuesta del documento:**

```
solicitudes_catalogo {
  _id,
  catalogo:        "talleres" | "repuestos" | "motivos" | "tipos_documento" | …
  valor_propuesto: str          // lo que el usuario escribió, normalizado
  valor_original:  str          // tal cual lo tecleó, para no perder evidencia
  solicitante_id:  str
  rol_solicitante: str
  contexto: { entidad: "ordenes", entidad_id: "<orden_id>" }   // trazabilidad
  veces_solicitado: int         // ver §4.4
  primera_solicitud_ts, ultima_solicitud_ts
  estado:          "PENDIENTE" | "APROBADA" | "RECHAZADA"
  resuelto_por, resuelto_ts, motivo_resolucion
}
```

`contexto` es lo que hace útil la bandeja: el administrador puede abrir la orden que originó la
solicitud antes de decidir, en vez de aprobar un nombre a ciegas.

### 4.3 Notificación al administrador — reusar, no construir

Ya existe el mecanismo exacto que hace falta: `notificaciones/service.py::disparar_alerta`, con
configuración por tipo de alerta (canal, destinatarios adicionales, activo/inactivo), rol
destinatario por defecto, y persistencia en la bandeja in-app (`notificaciones_usuario`, visible en
la campana `NotificacionesBell` de las 3 apps).

**Propuesta:** agregar `"catalogo_solicitud_pendiente"` a `TIPOS_ALERTA`
(`notificaciones/service.py:43`) y a `ROL_DEFAULT_POR_ALERTA` con destinatario `admin_sistema`.

Ventajas de reusar esto en vez de inventar un canal:
- Aparece automáticamente en la pantalla de **Configuración de alertas** (Módulo 6.3) sin código de
  UI nuevo — el administrador puede silenciarla o añadir destinatarios.
- Queda auditada igual que el resto (`ALERTA_CONFIG_CAMBIO` al cambiarla).
- Entrega real por el único canal que de verdad entrega en este sistema (`web_push` in-app).

**Anti-recomendación explícita:** no notificar por correo. No hay envío de correo en todo el
codebase, y el propio schema de alertas ya rechaza `"correo"` como valor por ser *"un selector que
promete algo que no ocurre"* (`notificaciones/schemas.py:19-22`). Mantener esa disciplina.

### 4.4 Repetición del mismo valor libre

**Recomendación: sí contarlo, y es barato.**

Al registrar una solicitud, hacer `update_one` con `upsert` sobre la clave
`(catalogo, valor_normalizado)` con `$inc: {veces_solicitado: 1}`, donde `valor_normalizado` =
minúsculas + sin tildes + espacios colapsados. Así `"Taller del Norte"`, `"taller del norte"` y
`"TALLER DEL NORTE "` cuentan como una sola solicitud con `veces_solicitado: 3`, en vez de tres
filas casi idénticas.

Consecuencias directas:
- La bandeja se ordena por `veces_solicitado` desc → el administrador ve primero lo que más gente
  pidió, que es la mejor señal de que el catálogo tiene un hueco real.
- **Se dispara una sola notificación en la primera solicitud**, no una por repetición. Sin esto, un
  taller nuevo usado por 10 conductores genera 10 alertas idénticas y la campana se vuelve ruido.
- El conteo es también la métrica que justifica (o descarta) el catálogo a futuro: si un valor libre
  nunca se repite, la bandeja lo demuestra con datos en vez de con intuición.

Costo: un `update_one` con upsert. **Es trivial y se recomienda incluirlo desde la primera
implementación**, no diferirlo.

### 4.5 Qué pasa al aprobar

Aprobar desde la bandeja debe **crear el registro en el catálogo destino reusando el servicio ya
existente** (`catalogos/service.py::crear_taller`, etc.) — no un `insert_one` paralelo. Así la
creación queda auditada con `CATALOGO_CREACION` igual que si se hubiera creado a mano, y el
administrador puede completar los campos que el solicitante no conocía (dirección y teléfono del
taller, por ejemplo).

**Decisión pendiente de tu aprobación:** al aprobar, ¿se reescriben los registros históricos que
usaron el valor libre para normalizarlos al nombre del catálogo? **Recomendación: no.** Reescribir
`ordenes.taller` en registros ya cerrados altera datos de negocio históricos por una razón
cosmética. El catálogo gobierna de aquí en adelante; lo viejo se queda como está y se resuelve por
`valor_normalizado` si alguna vez hace falta agrupar.

---

## 5. Resumen de la Fase 1 en una tabla

| Campo | Portal | Clase | ¿Catálogo existe? | Acción propuesta |
|---|---|---|---|---|
| Taller | interno | A | **Sí, sin usar** | Cablear + sembrar |
| Repuesto (descripción) | interno | A media | No | Catálogo nuevo, sin precio |
| Motivo anulación orden | interno | A baja | Parcial (`motivos`) | Categoría nueva |
| Marca vehículo | conductor | A | No | Catálogo nuevo |
| Color vehículo | conductor | A | No | Catálogo nuevo |
| Modelo vehículo | conductor | A + bug | No | Catálogo jerárquico (caro) — o arreglar el bug primero |
| Tipo de documento | interno/conductor | A | **Sí, vacío** | Sembrar (urgente, §3) |
| Motivo cancelación conductor | conductor | **C** | Parcial (`motivos`) | Exponer el input que falta |
| Motivo cancelación pasajero | pasajero | **C** | Parcial (`motivos`) | Exponer el input que falta |
| Tipo de incidencia | conductor | **C** | Parcial (`motivos` cat. `incidencia`) | Ver Fase 4 |
| Motivo rechazo solicitud | interno | A parcial | No | Categoría + detalle libre |
| Motivo suspensión usuario | interno | A parcial | No | Categoría + detalle libre |
| Descripción orden / trabajos / comentarios / referencia / identificadores | todos | **B** | — | **Se quedan libres** |

Priorización y esfuerzo: ver [PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md](PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md).
