# Auditoría previa — Segundo rediseño visual (Fase 0)

Continuación del rediseño ya aprobado en [`PLAN_REDISENO_VISUAL.md`](PLAN_REDISENO_VISUAL.md) /
[`AUDITORIA_DISENO_ACTUAL.md`](AUDITORIA_DISENO_ACTUAL.md) (agosto 2026) — no repite lo ya resuelto
ahí (paleta cálida base, tipografía Barlow + Big Shoulders, franja de ruta signature), solo lo que
esta ronda nueva encuentra y debe decidir.

## 1. Estado real del sidebar — confirmado antes de tocarlo

`apps/shared-ui/src/tokens.css:119-131`. Los tokens `--color-sidebar-*` se definen **una sola vez**
en `:root` y **nunca se sobrescriben** en el bloque `[data-theme="dark"]`. El propio comentario en
el código lo deja explícito:

> *"sidebar oscura FIJA, independiente del tema claro/oscuro del contenido (no se sobreescribe en
> el bloque `[data-theme="dark"]` de abajo, es la misma decisión que ya regía)"*

Confirmado: es una decisión deliberada, tomada y re-confirmada en la ronda anterior. Esta ronda la
revierte por instrucción explícita — ver Fase 1 §3 del plan de paleta para el diseño concreto.

**Efecto colateral real que esto obliga a resolver** (no es opcional, es una consecuencia directa):
el estado de foco de teclado del sidebar (`tokens.css:296-301`) usa `--color-accent` brillante
**porque asumía sidebar oscuro fijo** — verificado con la fórmula WCAG real: ese mismo ámbar da
solo **1.65:1** contra un fondo de sidebar claro (fallando el mínimo de 3:1 para componentes no
textuales), mientras que `--color-accent-deep` da **5.39:1** contra el mismo fondo claro. Lo mismo
aplica al indicador de rail activo del ítem de menú seleccionado (mismo ámbar brillante hoy). **Los
dos necesitan volverse condicionales al tono de sidebar elegido**, no solo el color de fondo — se
detalla en el plan de paleta.

## 2. Inventario de emojis (búsqueda exhaustiva por rango Unicode, no por memoria)

Escaneados todos los `.ts`/`.tsx`/`.css`/`.html` de `apps/*` (sin `node_modules`/`dist`) contra los
rangos Unicode reales de emoji, dingbats y símbolos misceláneos. Resultado: **9 archivos, 13
glifos únicos**.

### 2.1 Iconos funcionales — reemplazo directo, sin ambigüedad

| Glifo | Archivo:línea | Uso |
|---|---|---|
| `☰` | `AppShell.tsx:308` | Botón "Abrir menú" (hamburguesa) |
| `✕` | `Lightbox.tsx:81` | Botón "Cerrar" de la imagen ampliada |
| `★`/`☆` | `AppShell.tsx:268` | Botón de alternar favorito de una sección del sidebar |
| `☆` | `web-pasajero/App.tsx:536,1809` | Botón/texto de ayuda "☆ Guardar como favorita" (dirección) |
| `📷` | `web-conductor/App.tsx:922` | Indicador de "tiene evidencia" en una celda de tabla |
| `▲`/`▼` | `web-pasajero/App.tsx:811` | Texto de expandir/colapsar "Ver detalle del conductor ▼" |

### 2.2 Notación de calificación — juicio a confirmar, no decidido en silencio

`★` como sufijo de número (`"4.5★"`, `"5★"`) aparece **14 veces** repartidas en
`web-pasajero/App.tsx` (5), `web-conductor/App.tsx` (3), `HistorialGlobal.tsx` (2),
`PanelDesempenoConductores.tsx` (1), `PanelRendimientoConductores.tsx` (5). No son botones ni
navegación — es notación de contenido (igual que "$" para moneda). Mi recomendación es **dejarlos
como están**, con el mismo criterio de la ronda anterior (ningún emoji de contenido/dato se tocó
entonces): sustituirlos por un ícono de estrella + número exige rediseñar el layout de ~14 puntos
distintos (celdas de tabla, encabezados de KPI, texto de párrafo) por una notación que ya es
universal y legible. Lo marco explícitamente porque la instrucción dice "sin excepciones" — si
preferís que también se reemplacen, lo hago en Fase 2, pero quería que la decisión fuera tuya, no
mía.

### 2.3 No es un hallazgo real

`🚕`/`🚖` en `MarcadorVehiculo.tsx:6` — están **solo en un comentario de código** ("el taxi genérico
que usaban antes"), nunca se renderizan. No requiere acción.

## 3. Inventario de texto de desarrollador (los 3 niveles, los 3 portales)

Encontrado buscando referencias a `CLAUDE.md`/specs, códigos `CU-O*`/`CU-T*`/`CU-E*`, jerga de
infraestructura (`endpoint`, `API`, `webhook`, `backend`, `pipeline`), e identificadores crudos de
base de datos. Cada hallazgo se clasifica según la regla que diste: **la sustancia honesta se
queda, el envoltorio técnico se saca.**

### 3.1 Referencias directas a `CLAUDE.md` / "backlog consciente" — quitar la referencia, quedarse con el hecho

| Archivo:línea | Texto actual | Qué se queda / qué se saca |
|---|---|---|
| `PanelDocumentacion.tsx:205` | *"...carga de documentos de postulación es backlog consciente, ver CLAUDE.md)."* | **Nota real: ya no aplica** — la carga de documentos de postulación se cerró en una ronda posterior (ver `CLAUDE.md` §26.3), este texto quedó desactualizado. Se corrige el mensaje al estado real, no solo el envoltorio. |
| `PanelFlota.tsx:168` | *"Filtro por zona no disponible todavía... (ver nota en CLAUDE.md)."* | Se queda: "no disponible todavía, el dato no se calcula por zona". Se saca: "(ver nota en CLAUDE.md)". |
| `PanelAuditoria.tsx:209-210` | *"'% error API' no disponible... (backlog consciente); el gráfico usa solo conteo de solicitudes por endpoint..."* | Se queda: no existe ese dato todavía. Se saca: "backlog consciente", "endpoint". |
| `PanelPlataforma.tsx:133` | *"'Capacitación' no disponible... (backlog consciente)."* | Se queda: no existe ese dominio. Se saca: "backlog consciente" (jerga ágil). |

### 3.2 "API"/"endpoint" expuestos como texto de interfaz (`PanelAuditoria.tsx`, panel de Auditoría e Integraciones)

- KPI "Endpoints activos" (descripción: "Rutas del sistema usadas al menos una vez en el periodo")
- KPI "% error API"
- Encabezado `<h3>Uso de API por endpoint</h3>`
- El eje del gráfico usa como `categoria` el campo `endpoint`, que trae la **ruta real** (ej.
  `/viajes/estimacion-ruta`) — a diferencia de los demás, esto no es jerga sobrante, es el dato en
  sí (qué ruta se llamó). Recomiendo mantenerlo como dato de eje (igual que `FuenteBadge` mantiene
  "MongoDB/ClickHouse": transparencia técnica, no descuido), pero renombrar los rótulos que sí son
  puro envoltorio ("Endpoints activos" → algo como "Integraciones usadas"; "% error API" → "% de
  errores de integración"; el `<h3>` → "Uso de integraciones por ruta").

### 3.3 Códigos de caso de uso (`CU-O*`/`CU-T*`/`CU-E*`) visibles en pantalla — quitar el código, quedarse con la frase

| Archivo:línea | Dónde aparece |
|---|---|
| `ConfiguracionAlertas.tsx:14` | Etiqueta de tipo de alerta: "Denegaciones de permisos repetidas (CU-O18 A4)" |
| `Flota.tsx:139` | `title` de botón deshabilitado: "...al aprobarse la postulación de su conductor (CU-O01), no desde acá." |
| `Indicadores.tsx:110` | Encabezado `<h2>Catálogo de informes (CU-O16)</h2>` |
| `ParametrosGlobales.tsx:118` | Párrafo: "...gobiernan el auto-despacho de viajes (CU-O05): el primer valor..." |
| `PoliticasSeguridad.tsx:119` | Encabezado `<h3>Suspensión por denegaciones de permisos (CU-O18 A4)</h3>` |
| `Usuarios.tsx:355` | Párrafo: "...se autorregistran desde las apps públicas (CU-O01/CU-O02)..." |
| `Usuarios.tsx:586` | `title` (tooltip real, visible al pasar el cursor): "...son roles de autorregistro (CU-O01/CU-O02) — el backend no permite reasignarlos..." — este también dice **"el backend"**, doble jerga en la misma frase |

En los 7, la frase en español ya explica el comportamiento sin el código entre paréntesis — se
elimina el código, la frase se queda igual o casi igual.

### 3.4 Jerga de infraestructura cruda — reescritura completa, no solo recorte

`ConfiguracionAlertas.tsx:23`, nota sobre la alerta de "Corrida de proceso de datos fallida":

> *"Configurable, pero sin disparo real todavía: el proceso de carga de datos (Airflow) no tiene un
> webhook hacia este backend, solo escribe en ClickHouse y en su propio log. La configuración
> queda lista para el día en que se agregue ese enlace."*

Esto es jerga de implementación de punta a punta (Airflow, webhook, backend, log). La sustancia
honesta que hay que conservar es una sola frase: **esta alerta se puede configurar pero todavía no
se dispara sola**. Propongo en Fase 2: *"Configurable, pero todavía no se dispara automáticamente:
falta conectar el aviso al proceso que corre los reportes. Mientras tanto, esta alerta no genera
notificaciones por sí sola."*

### 3.5 Identificadores crudos de backend mostrados como dato — necesita diccionario de etiquetas, no solo texto

Los "dominios" que ve el personal interno (`gerencia`, `admin_plataforma`, `responsable_plataforma`)
son en realidad los `dag_id` reales de Airflow. Verificado contra ClickHouse los 7 valores reales
que existen hoy: `dag_captacion_gold`, `dag_cumplimiento_gold`, `dag_finanzas_gold`,
`dag_flota_gold`, `dag_historico_nyc`, `dag_mantenimiento_gold`, `dag_viajes_core`.

| Archivo:línea | Qué muestra hoy |
|---|---|
| `PanelPlataforma.tsx:55` (columna de tabla) | El `dag_id` **completo y crudo**: "dag_viajes_core" |
| `PanelPlataforma.tsx:170` (filtro desplegable) | Mismo crudo, como valor y como etiqueta |
| `PanelPlataforma.tsx:145` (eje de gráfico) | Recorta `dag_`/`_gold` a mano → queda "viajes_core", sigue en snake_case |
| `PanelCapacidades.tsx:137,180` (KPI y gráfico) | Mismo recorte parcial → "viajes_core", "flota", etc. |

Ninguno de los 4 usa un nombre legible real. Propongo en Fase 2 un diccionario compartido (mismo
patrón que `ETIQUETA_TIPO_DOCUMENTO`/`nombreRol()` ya existentes): Captación, Cumplimiento,
Finanzas, Flota, Histórico (dataset de calibración), Mantenimiento, Viajes — aplicado en los 4
lugares a la vez.

**Mismo problema, con roles**: `ConfiguracionAlertas.tsx:106,135` muestra
`rol_destinatario_default` crudo ("supervisor_cumplimiento") en vez de pasarlo por `nombreRol()`
(ya existe y ya se usa en `Usuarios.tsx`/`FeatureFlags.tsx`/`PerfilPropio.tsx` desde la ronda de
unificación de lenguaje). `GobernanzaDatos.tsx:124` tiene el mismo gap:
`u.roles.join(", ")` sin pasar por `nombreRol()` — quedó afuera de esa ronda anterior. Los dos se
corrigen igual: usar la función que ya existe, no crear una nueva.

### 3.6 Historia de desarrollo sin ninguna sustancia que conservar — se elimina, no se reescribe

`PanelPlataforma.tsx:161-162`:

> *"Servido desde ClickHouse (tabla `corridas`) — la colección Mongo `corridas_etl` que pide el
> spec no existe; el seguimiento del proceso de datos vive en ClickHouse desde el diseño
> original."*

A diferencia de los anteriores, esto **no es una declaración honesta de un dato faltante** — es la
explicación de por qué la implementación difiere de la spec original. Ningún usuario, técnico o no,
necesita saber que existió una spec que pedía una colección Mongo que nunca se construyó. Propongo
eliminar el párrafo completo (no reemplazarlo por nada, el encabezado de la sección ya dice de qué
se trata).

### 3.7 Nombres de motor (MongoDB/ClickHouse) en pantallas técnicas — juicio: se quedan, mismo criterio que `FuenteBadge`

`Monitoreo.tsx` (salud de infraestructura: "Mongo — conexiones activas", "ClickHouse — consultas
activas"...) y `Respaldos.tsx` ("Respaldo/restauración de prueba de MongoDB y ClickHouse..."). Estas
2 pantallas son, por diseño, herramientas técnicas para `admin_sistema` — el motor de base de datos
**es** el objeto que se está monitoreando o respaldando, no jerga decorativa alrededor de otra cosa.
Mismo argumento ya aceptado para `FuenteBadge` en la ronda anterior ("recurso de transparencia
técnica deliberado"). Recomiendo **no tocarlas**, pero las señalo para que la decisión sea explícita
y no un descuido.

Dentro de `Respaldos.tsx:466` sí hay un recorte menor real: *"...plan de recuperación ante desastres
(DR)."* — el acrónimo en inglés no aporta nada, la frase en español ya está completa sin él. Se
quita solo el `(DR)`.

`Respaldos.tsx` también usa **RTO/RPO** (con su traducción al lado: "Tiempo objetivo de
recuperación (RTO)"), términos estándar de continuidad de TI — igual criterio, se quedan, ya vienen
con su explicación en español al lado.

### 3.8 Dos términos aislados, juicio a confirmar

- `Monitoreo.tsx:194` — encabezado `<h2>Monitoreo y observabilidad</h2>`. "Observabilidad" es jerga
  de ingeniería (SRE) que no aporta claridad ni siquiera para un administrador técnico en español.
  Propongo "Monitoreo del sistema".
- `ConfiguracionAlertas.tsx:15` — `"Posible GPS spoofing"` como nombre de un tipo de alerta de
  seguridad real (detección de falsificación de posición). Es un término de seguridad reconocible,
  pero en inglés dentro de una interfaz en español. Propongo "Posible falsificación de ubicación
  GPS" — mismo hecho, sin el anglicismo.

## 4. Auditoría de componentes `shared-ui`

- **Modales: ya centralizados, sin nada que migrar.** Los únicos 3 componentes con
  `position: "fixed"` en todo el frontend son `DetailPanel`, `KpiDetalleModal` y `Lightbox`, los 3
  en `shared-ui`. Ninguna pantalla construye un modal a mano.
- **Botones, tarjetas, campos, tabla, badges: ya centralizados.** Un `grep` de definiciones locales
  de `Button`/`Badge`/`Card`/`TextField`/`Select` en las 3 apps no encuentra ninguna — todo se
  consume de `shared-ui`.
- **`TabButton`: duplicado 4 veces, byte por byte idéntico.** `Catalogos.tsx`, `Integraciones.tsx`,
  `Mantenimiento.tsx` y `Respaldos.tsx` (los 4 en `web-interno`) definen exactamente el mismo
  componente local, mismo estilo inline, mismas 20 líneas. Candidato claro a un `Tabs`/`TabButton`
  compartido.
- **No existe ningún componente de alerta/aviso compartido.** Los 2 avisos rojos de "documentación
  vencida" que se agregaron en una ronda anterior (`web-conductor/App.tsx:1123` y
  `Usuarios.tsx:613`) están hechos a mano, con los mismos tokens de color repetidos en los dos
  lugares (uno es un `<div>`, el otro un `<p>`, mismo estilo). Candidato a un `Alert` compartido
  (tono: éxito/advertencia/peligro/informativo — el último es nuevo, ver plan de paleta).
- **No hay librería de íconos instalada** (confirmado: ningún `package.json` de las 4 apps declara
  `lucide`/`react-icons`/similar). El patrón ya establecido (`NotificacionesBell.tsx`) es SVG
  dibujado a mano (`stroke="currentColor"`, `viewBox="0 0 24 24"`, estilo tipo Feather) — los
  reemplazos de emoji de la Fase 2 van a seguir ese mismo patrón, sin agregar una dependencia nueva.

## 5. Bloqueador real — el logo nuevo

No tengo forma de extraer los bytes de la imagen que compartiste en el chat: mi herramienta de
archivos solo lee rutas del repositorio, no adjuntos pegados en la conversación. El
`logo_urbanflet.png` que hoy vive en la raíz del repo es el logo **anterior** (sin cambios desde el
7 de agosto), no el nuevo.

**Para desbloquear esto**: guardá el archivo de imagen en el repo (por ejemplo, sobrescribiendo
`logo_urbanflet.png` en la raíz, mismo lugar de siempre) y avisame la ruta — desde ahí puedo
recortar las 2 variantes que ya usa el sistema (`logo-urbanflet-icon.png`, cuadrada, para el
sidebar; `logo-urbanflet-full.png`, con el texto, para las 3 pantallas de login) exactamente como
se hizo con el logo anterior.
