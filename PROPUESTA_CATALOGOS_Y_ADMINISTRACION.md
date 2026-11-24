# Propuesta — catálogos nuevos y su administración (Fase 3)

**Fecha:** 2026-08-14 · **Estado:** propuesta, sin implementar · Requiere tu aprobación antes de
definir alcance.

Basado en la evidencia de [AUDITORIA_UX_CATALOGOS.md](AUDITORIA_UX_CATALOGOS.md). Los conteos
citados son mediciones reales sobre la base de desarrollo, no estimaciones.

---

## 1. Punto de partida — qué existe hoy, verificado

El Módulo 3 de Administración del Sistema ya está construido y funcionando:

**Backend** (`backend/src/catalogos/`): CRUD de 3 catálogos (`tipos_documento`,
`motivos_cancelacion`, `talleres`) con creación, listado y edición, cada operación con auditoría
write-ahead (`CATALOGO_CREACION`/`CATALOGO_EDICION`). Sin DELETE por decisión documentada — solo
`activo: false`. Índice único por `nombre` en las 3 colecciones (`core/db_mongo.py:120-124`).
`zonas` vive aparte en `parametros/` por razones históricas ya documentadas.

**Frontend** (`apps/web-interno/src/sections/Catalogos.tsx`): una pantalla con 4 pestañas
(`zonas` · `tipos` · `motivos` · `talleres`), cada una con el patrón WorkPanel estándar
(búsqueda → ActionBar → DataTable → DetailPanel).

**Conclusión de la Fase 3:** la superficie de administración ya existe y es genérica de hecho.
**Todo catálogo nuevo debe entrar como una pestaña más de `Catalogos.tsx` + un bloque más en
`catalogos/service.py`.** No se justifica ninguna sección de administración nueva ni paralela.

---

## 2. Los dos bloqueos que hay que resolver ANTES de cualquier catálogo nuevo

Estos dos puntos no son catálogos nuevos: son condiciones para que cualquier catálogo —incluido el
que ya existe— sirva de algo.

### 2.1 Bloqueo A — RBAC: los consumidores no pueden leer los catálogos

`catalogos/router.py:12` gatea **los 6 endpoints** (incluidos los `GET`) a `admin_sistema`
exclusivamente. Consecuencia concreta: si hoy se pusiera un `<Select>` de talleres en el formulario
de Mantenimiento, `jefe_mantenimiento` recibiría **403** y el formulario quedaría inutilizable.

**Precedente interno que resuelve esto limpio:** `parametros/router.py:100-103` ya hace exactamente
la separación correcta para `zonas` — `GET /parametros/zonas` **no tiene dependencia de rol**
(lectura abierta, se consume con `auth: false` desde `Catalogos.tsx:82`), mientras
`POST`/`PATCH`/`DELETE` exigen `_puede_gestionar_zonas`.

**Propuesta:** replicar esa separación en `catalogos/router.py`.

| Operación | Gate propuesto | Razón |
|---|---|---|
| `GET /catalogos/*` | Cualquier actor autenticado | Un catálogo de referencia no es información sensible; es una lista de nombres de talleres. Lo necesitan `jefe_mantenimiento`, `admin_captacion`, conductores (postulación), etc. |
| `POST`/`PATCH /catalogos/*` | `admin_sistema` (sin cambios) | Escritura sigue siendo alto privilegio, como está hoy. |

Alternativa más conservadora si prefieres no abrir la lectura: OR-gate puntual por endpoint
(`require_roles("admin_sistema", "jefe_mantenimiento")` solo en `GET /catalogos/talleres`), mismo
patrón que ya se usó en `cumplimiento/router.py::listar_documentos_por_vencer` para habilitar
`gerencia`. **Recomiendo la primera** — con la segunda, cada catálogo nuevo obliga a recordar
actualizar su gate, que es justo el tipo de mirror manual que este proyecto ya decidió eliminar.

### 2.2 Bloqueo B — los catálogos están vacíos

Estado real medido: `talleres` = 1 registro ("Taller QA Cache", **inactivo**), `motivos_cancelacion`
= 1 ("Prueba motivo"), `tipos_documento` = 1 ("Prueba documento"), `zonas` = 1 ("Prueba").

**Propuesta:** script de siembra idempotente (mismo patrón que `backend/scripts/seed_*.py` ya
existentes), que crea los valores **derivados de los datos reales**, no inventados:

| Catálogo | Valores a sembrar (derivados de datos reales) | Fuente |
|---|---|---|
| `talleres` | Taller Central, Taller Norte, Lubricadora Express, Taller El Motor, Servicio Rápido Quevedo | Los 5 nombres que concentran 132/134 órdenes |
| `tipos_documento` | LICENCIA_CONDUCIR, MATRICULA_VEHICULAR | Los 2 únicos tipos de los 142 documentos reales — **resuelve la mina latente del §3 de la auditoría** |
| `motivos_cancelacion` (cat. `cancelacion`) | Pasajero ausente (NO_SHOW), Cancelado por el pasajero, Cancelado en camino, Incidencia en ruta, Vehículo averiado | Los motivos que la spec CU-O07 A1-A4 ya nombra |
| `motivos_cancelacion` (cat. `incidencia`) | Avería mecánica, Siniestro/choque, Falla eléctrica, Neumático, Otro | CU-O07 A4 |

Además: borrar los 4 registros "Prueba"/"QA Cache" como parte de la limpieza (mismo criterio que la
limpieza de datos de prueba ya hecha en §8.2 de CLAUDE.md).

**Sin resolver A y B, cablear cualquier selector produce una pantalla rota.** Por eso encabezan la
priorización.

---

## 3. Catálogos propuestos

### 3.1 `talleres` — YA EXISTE, solo falta cablearlo y enriquecerlo

**No se propone crear nada.** Se propone:

1. **Cablear** el `<Select>` en `Mantenimiento.tsx` (crear orden y cerrar orden) contra
   `GET /catalogos/talleres`, reemplazando `<TextField label="Taller">`.
2. **Enriquecer** el schema con los campos que el encargo menciona:

| Campo | Estado | Propuesta |
|---|---|---|
| `nombre` | ✅ existe | — |
| `direccion` | ✅ existe | — |
| `telefono` | ✅ existe | — |
| `activo` | ✅ existe | — |
| **`lat` / `lon`** | ❌ | **Agregar.** Permiten mostrar el taller en el mapa y calcular distancia desde el vehículo. |
| **`url_maps`** | ❌ | **Agregar.** Enlace a Google Maps, tal como pediste. Campo de texto validado como URL; no requiere integración nueva. |
| **`especialidades`** | ❌ | **Opcional** (`list[str]`). Permitiría sugerir el taller según el tipo de falla. **Recomiendo dejarlo fuera de la primera ronda** — no hay dato real que lo respalde todavía. |

**Nota sobre `lat`/`lon`:** el proyecto ya tiene todo lo necesario para capturarlos (Leaflet +
geocoding de Google ya en uso en `web-pasajero`). Pero el formulario de catálogos vive en
`web-interno`, que **no monta ningún mapa hoy**. Capturar lat/lon ahí implicaría llevar Leaflet a
`web-interno` por primera vez. **Recomendación: en la primera ronda, `url_maps` como texto** (el
administrador pega el enlace, que es lo que haría de todos modos), y `lat`/`lon` opcionales
derivables del enlace más adelante. Evita arrastrar una dependencia de mapa a un portal que no la
tiene por un campo secundario.

---

### 3.2 `repuestos` — catálogo nuevo (confianza media, con matiz importante)

**Evidencia honesta:** solo 3 entradas humanas reales (`"Filtro de aceite"`, `"Bujias"`, `"No se"`).
El resto es plantilla de seed. **No puedo afirmar con los datos actuales que los repuestos se
repitan mucho** — sería exactamente el error que el encargo pide evitar.

**Por qué lo propongo igual, con esa salvedad:** las 3 entradas humanas ya muestran los dos
síntomas que el catálogo corrige (ortografía inconsistente y basura), y el dominio (una cooperativa
comprando filtros y bujías para 81 vehículos) hace la repetición casi inevitable en cuanto haya uso
real. **Pero es un candidato de segunda ola, no de la primera** — y la bandeja de solicitudes
(§4.4 de la auditoría) dará la evidencia definitiva sin que haya que adivinar.

| Campo | Tipo | Nota |
|---|---|---|
| `nombre` | str, único | "Filtro de aceite", "Bujía" |
| `categoria` | str | Motor / Frenos / Eléctrico / Suspensión / Neumáticos / Otro |
| `unidad` | str | unidad / litro / juego |
| `activo` | bool | — |
| ~~`costo_referencial`~~ | — | **Deliberadamente NO incluido.** Los datos muestran 130 costos unitarios distintos para la misma descripción. Un precio en el maestro se confundiría con el precio real de compra, que pertenece a la línea de la orden. |

El campo `costo_unitario` **se queda en la línea de la orden**, donde ya está.

---

### 3.3 `motivos` — extender el catálogo existente, no crear uno nuevo

`motivos_cancelacion` ya existe con `categoria: Literal["cancelacion", "incidencia"]`. **La
categoría `incidencia` no tiene un solo consumidor hoy** — se construyó anticipando CU-O07 A4, que
nunca se implementó.

**Propuesta:** ampliar el `Literal` a `["cancelacion", "incidencia", "anulacion_orden", "rechazo_solicitud", "suspension_usuario"]`
y usar el mismo catálogo para los cinco casos. Un solo maestro, `categoria` distingue el uso —
exactamente el criterio que `core/audit.py:84-90` ya estableció para las acciones de catálogo.

**Alcance recortado recomendado para la primera ronda:** cablear solo `cancelacion` e `incidencia`
(que son incumplimientos de spec, ver §2.4/2.5 de la auditoría). Las otras tres categorías
(anulación, rechazo, suspensión) son mejoras de calidad de dato sin incumplimiento asociado y
pueden esperar.

---

### 3.4 `marcas_vehiculo` y `colores_vehiculo` — catálogos nuevos, evidencia sólida

Evidencia real: 6 marcas y 7 colores cubren los 81 vehículos, **más basura en ambos** (`"X"`,
`"123"`, `"Z"`). Conjuntos cerrados y estables.

| Catálogo | Campos | Nota |
|---|---|---|
| `marcas_vehiculo` | `nombre` (único), `activo` | Simplísimo |
| `colores_vehiculo` | `nombre` (único), `activo` | Podría llevar `hex` para mostrar una muestra de color en la tabla de Flota — opcional, agradable, no esencial |

**Consumidor:** el formulario de postulación en `web-conductor` (público, sin sesión). Esto refuerza
la recomendación del §2.1: la lectura del catálogo debe ser accesible sin ser `admin_sistema` — en
este caso concreto, **incluso sin autenticación**, igual que `GET /parametros/zonas` hoy.

### 3.5 `modelos_vehiculo` — **recomiendo NO construirlo todavía**

Es el único candidato que **descarto explícitamente para esta ronda**, y no por falta de valor sino
por secuencia:

1. El campo `modelo` hoy contiene **años** en 76 de 81 vehículos. Un catálogo de modelos sobre datos
   así no tiene de dónde sembrarse.
2. Requiere jerarquía marca→modelo (selector dependiente), que es sensiblemente más caro que un
   selector plano.
3. **El arreglo de UX que de verdad importa acá es otro**: el formulario pone `Año` y `Modelo`
   contiguos con etiquetas ambiguas y la gente los confunde. Cambiar la etiqueta a
   *"Modelo (ej. Yaris, Sail)"* con placeholder, y validar que `modelo` no sea un número de 4
   dígitos, resuelve el 90% del problema con el 5% del esfuerzo.

**Propuesta: arreglar el formulario ahora, catálogo de modelos después**, cuando `marcas_vehiculo`
esté en uso y haya datos limpios de los que derivarlo.

---

## 4. Priorización — impacto vs. esfuerzo

### Ola 0 — prerrequisitos (sin esto, nada de lo demás funciona)

| # | Ítem | Esfuerzo | Impacto |
|---|---|---|---|
| 0.1 | Separar lectura/escritura en `catalogos/router.py` (§2.1) | **Muy bajo** — 6 líneas | **Bloqueante** |
| 0.2 | Sembrar los 4 catálogos con valores reales + borrar los de prueba (§2.2) | **Bajo** — 1 script idempotente | **Bloqueante** + resuelve la mina latente del 422 |

### Ola 1 — alto impacto / bajo esfuerzo

| # | Ítem | Esfuerzo | Impacto | Nota |
|---|---|---|---|---|
| 1.1 | **Cablear `<Select>` de talleres** en Mantenimiento | **Bajo** — el catálogo y el CRUD ya existen | **Alto** — 98.5% de concentración, elimina la basura tipo `"1"` | El mejor ratio de toda la auditoría |
| 1.2 | Agregar `url_maps` (+ `lat`/`lon` opcionales) a `talleres` | Bajo | Medio | Lo que pediste explícitamente |
| 1.3 | **Exponer el motivo de cancelación del conductor** (selector, categoría `cancelacion`) | Bajo | **Alto** — cierra un incumplimiento de spec (CU-O07 A3 exige "selección obligatoria") | El endpoint ya acepta `motivo`; hoy el cliente lo hardcodea |
| 1.4 | Selectores de **marca** y **color** en postulación | Bajo | Medio-alto | Elimina `"X"`/`"123"`/`"Z"` en origen |
| 1.5 | Arreglar etiqueta/validación de **Modelo** (sin catálogo) | **Muy bajo** | Medio | Corrige un bug de datos real (76/81 con año en vez de modelo) |

### Ola 2 — patrón "Otro" completo

| # | Ítem | Esfuerzo | Impacto |
|---|---|---|---|
| 2.1 | Colección `solicitudes_catalogo` + endpoints + conteo de repetición | **Medio** | Alto — es la infraestructura que hace sostenibles todos los catálogos |
| 2.2 | Bandeja del administrador (5ª pestaña en `Catalogos.tsx`) | Medio | Alto |
| 2.3 | Alerta `catalogo_solicitud_pendiente` (reusa `disparar_alerta`) | **Bajo** | Medio |

### Ola 3 — requiere más modelo de datos o más evidencia

| # | Ítem | Esfuerzo | Impacto | Nota |
|---|---|---|---|---|
| 3.1 | Catálogo `repuestos` | Medio | Medio | Esperar evidencia de la bandeja (§3.2) |
| 3.2 | Motivo de cancelación **del pasajero** | Medio | **Alto para analítica** | Desbloquea `rpt_tasa_cancelacion` real; hoy 93,094 viajes con un solo motivo. Es medio porque toca el flujo del pasajero y la deuda técnica ya conocida de esa tabla |
| 3.3 | Categorías `anulacion_orden` / `rechazo_solicitud` / `suspension_usuario` | Medio | Bajo-medio | Selector de categoría + detalle libre |
| 3.4 | Catálogo `modelos_vehiculo` jerárquico | **Alto** | Bajo hoy | Solo después de 1.4 + 1.5 |

---

## 5. Lo que esta propuesta deliberadamente NO hace

- **No migra a claves foráneas.** Los catálogos gobiernan la *entrada* de datos; los registros
  siguen guardando el texto. Es la decisión que `catalogos/service.py:1-14` ya tomó y documentó, y
  cambiarla ahora implicaría migrar 134 órdenes, 81 vehículos y 1.3M viajes sin beneficio claro.
- **No reescribe datos históricos.** `taller: "1"` se queda como está.
- **No crea una superficie de administración nueva.** Todo entra en `Catalogos.tsx` como pestaña.
- **No agrega precio al catálogo de repuestos** (evidencia: 130 costos distintos por descripción).
- **No propone notificación por correo** (no existe envío de correo en el codebase).
- **No convierte a selector** ninguno de los campos clasificados **B** en la auditoría
  (descripciones, trabajos realizados, comentarios, identificadores).

---

## 6. Decisiones que necesito de ti antes de implementar

1. **§2.1** — ¿lectura de catálogos abierta a cualquier autenticado (recomendado), o OR-gate puntual
   por endpoint?
2. **§2.2** — ¿apruebas sembrar los catálogos con los valores derivados de los datos reales, y
   borrar los 4 registros de prueba?
3. **§3.1** — ¿`url_maps` como texto en esta ronda (recomendado), o quieres captura de `lat`/`lon`
   con mapa en `web-interno` desde ya?
4. **§3.5** — ¿de acuerdo con posponer el catálogo de modelos y arreglar primero el formulario?
5. **§4.5 de la auditoría** — al aprobar una solicitud de "Otro", ¿confirmas que **no** se reescriben
   los registros históricos?
6. **Alcance de la primera implementación**: ¿Ola 0 + Ola 1 (recomendado como bloque coherente y
   verificable), o incluir también la Ola 2?
