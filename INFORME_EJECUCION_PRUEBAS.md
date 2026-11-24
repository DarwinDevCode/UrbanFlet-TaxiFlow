# Informe de Ejecución de Pruebas — UrbanFleet TaxiFlow

## 1. Introducción

El presente informe documenta la ejecución de las pruebas definidas en el
[Plan de Pruebas](PLAN_DE_PRUEBAS.md) de UrbanFleet TaxiFlow sobre el sistema real, en su entorno
de desarrollo (los tres portales — `web-pasajero`, `web-conductor` y `web-interno` — junto con el
backend, MongoDB, ClickHouse, Redis y el proceso de carga de datos, todos en ejecución simultánea).
Se conservan la estructura, los casos de prueba y los criterios de evaluación del plan original;
este documento registra qué ocurrió al ejecutarlos: el comportamiento observado, si la prueba fue
satisfactoria o generó alguna observación, y las conclusiones de usabilidad, navegación y
funcionamiento que se derivan de esa ejecución.

El informe se organiza en las mismas cuatro partes del plan:

1. Pruebas funcionales para desarrolladores (nivel técnico).
2. Pruebas funcionales para usuarios sin conocimiento técnico (lenguaje simple).
3. Evaluación de usabilidad basada en tareas reales.
4. Análisis final y conclusiones.

Cada caso incluye un espacio identificado para incorporar la evidencia visual correspondiente,
con la indicación precisa de qué debe mostrar esa captura.

### Nota de metodología — Parte 3

Las pruebas de la Parte 2 y la Parte 3 del plan se ejecutaron mediante interacción directa y
repetida con el sistema real: cuentas de prueba reales, solicitudes de red reales, y verificación
cruzada contra el estado real de la base de datos en cada caso. La Parte 3 (evaluación de
usabilidad) se ejecutó como **evaluación heurística**: un recorrido estructurado de cada uno de los
nueve escenarios de tarea definidos en el plan, realizado por un evaluador que examinó
sistemáticamente la interfaz contra los diez criterios de usabilidad establecidos (intuitividad,
facilidad para encontrar opciones, navegación sin perderse, claridad de menús, claridad de nombres,
autonomía, pasos innecesarios, comprensión de mensajes, claridad de pantalla y fluidez). Es un
método de evaluación de usabilidad estándar, distinto de un estudio moderado con usuarios externos,
y así se identifica en cada hallazgo de esa sección.

---

## 2. Resultados — Pruebas funcionales para desarrolladores

### PD-01 — Ciclo de vida completo del viaje

**Qué se evaluó**: que el ciclo completo de un viaje (solicitud, oferta, aceptación, ejecución,
cobro y calificación) transite correctamente por sus ocho estados y que el desglose de tarifa se
calcule y se muestre con exactitud en ambos portales.

**Procedimiento**: con un conductor de vehículo habilitado y turno iniciado, se solicitó un viaje
desde `web-pasajero`, se aceptó la oferta desde `web-conductor`, se avanzó la secuencia completa de
estados hasta la finalización, se registró el cobro en efectivo y se calificó desde ambos lados.

**Comportamiento observado**: el estado avanzó correctamente por la secuencia
`SOLICITADO → OFERTADO → ASIGNADO → EN_CAMINO → EN_CURSO → FINALIZADO → PAGADO`. Al finalizar, ambos
portales mostraron el desglose de tarifa en tres renglones (arrancada, distancia, espera) más el
subtotal; en los viajes de distancia corta el sistema aplicó correctamente la carrera mínima y lo
indicó de forma explícita ("Carrera mínima aplicada"). El viaje quedó disponible de inmediato en
"Mis viajes" de ambas cuentas y en el Historial de viajes de `web-interno`.

**Resultado**: **Satisfactorio**. La consistencia entre el monto mostrado y el monto persistido en
la base de datos fue exacta en todos los casos verificados.

**Evidencia recomendada**: captura de la pantalla de finalización del viaje en `web-conductor`
mostrando el desglose de tarifa (arrancada, distancia, espera, subtotal) y, si aplica, la línea de
"Carrera mínima aplicada".

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-02 — Postulación de conductor con documentos y aprobación

**Qué se evaluó**: el flujo completo de postulación con carga real de documentos (licencia y
matrícula) y su revisión y aprobación desde el panel de Captación.

**Procedimiento**: se completó el formulario de postulación en `web-conductor` adjuntando una
imagen real para cada documento requerido y su fecha de caducidad; se revisó la solicitud desde
`web-interno` con la cuenta de Captación, visualizando ambos documentos antes de aprobar.

**Comportamiento observado**: el botón de envío permaneció deshabilitado hasta que ambos archivos y
ambas fechas quedaron completos. El envío se resolvió en la secuencia esperada: creación de la
cuenta, autenticación, carga de los dos archivos y adjunción a la solicitud. En el panel de
revisión, ambas imágenes se visualizaron correctamente junto con su fecha de vencimiento y un
indicador de vigencia (vigente / por vencer / vencido). Al aprobar, el sistema creó automáticamente
el usuario conductor, el vehículo asociado y dos registros reales en la colección de documentos.

**Resultado**: **Satisfactorio**. No se identificó ninguna solicitud que quedara enviada sin sus
documentos adjuntos.

**Evidencia recomendada**: captura del panel de revisión de Captación mostrando los dos documentos
cargados (imagen visible, fecha de caducidad y etiqueta de vigencia).

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-03 — Orden de mantenimiento con todos sus estados

**Qué se evaluó**: la máquina de estados completa de una orden de mantenimiento, incluida la
transición intermedia de espera de repuesto.

**Procedimiento**: se creó una orden nueva sobre un vehículo real, se llevó a taller, se marcó en
espera de repuesto con un motivo, se reanudó y se cerró registrando un costo real distinto del
estimado.

**Comportamiento observado**: la orden recorrió la secuencia
`ABIERTA → EN_TALLER → ESPERANDO_REPUESTO → EN_TALLER → CERRADA` sin errores. Al cerrar, el sistema
mostró la próxima intervención preventiva proyectada en kilómetros y calculó correctamente el
porcentaje de desviación entre el costo estimado y el real. Las transiciones de estado quedaron
registradas automáticamente en la cronología de actividad de la orden, sin que el usuario tuviera
que documentarlas a mano.

**Resultado**: **Satisfactorio**.

**Evidencia recomendada**: captura del mensaje de cierre de la orden mostrando la próxima
intervención proyectada y el porcentaje de desviación de costo.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-04 — Reporte de falla desde los dos orígenes

**Qué se evaluó**: que un reporte de falla creado por el conductor y uno creado por el personal
interno convivan en la misma bandeja sin distinción de trato.

**Procedimiento**: se generó un reporte desde `web-conductor` y otro directamente desde el módulo
de Mantenimiento de `web-interno`, para el mismo tipo de incidencia.

**Comportamiento observado**: ambos reportes aparecieron en la misma bandeja, con las mismas dos
acciones disponibles ("Convertir en orden" y "Descartar"). El reportado por el conductor incluyó su
posición real en el momento del reporte; el creado internamente tomó la última posición conocida
del vehículo. Ninguna marca visual sugería que un origen tuviera más peso que el otro.

**Resultado**: **Satisfactorio**.

**Evidencia recomendada**: captura de la bandeja de "Reportes de falla" mostrando al menos un
registro de cada origen.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-05 — Catálogos: alta, edición y baja lógica

**Qué se evaluó**: que la desactivación de un elemento de catálogo (taller) lo retire de los
selectores activos sin eliminarlo del registro histórico.

**Procedimiento**: se creó un taller, se editó su nombre, se desactivó, y se verificó su
disponibilidad en el selector de taller del formulario de una nueva orden de mantenimiento.

**Comportamiento observado**: tras la desactivación, el taller permaneció visible en el catálogo
con el estado "Inactivo" pero dejó de aparecer como opción en el formulario de nueva orden. El botón
"Eliminar" se mostró deshabilitado, con un texto explicativo al pasar el cursor.

**Resultado**: **Satisfactorio**. La baja lógica se comportó como está documentada: sin borrado
físico del registro.

**Evidencia recomendada**: captura del catálogo mostrando el taller en estado "Inactivo" junto al
selector de la pantalla de Mantenimiento donde ya no aparece como opción.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-06 — Baja lógica de una cuenta y sus casos borde

**Qué se evaluó**: el comportamiento del sistema al dar de baja una cuenta, incluido el caso borde
de un viaje en curso.

**Procedimiento**: se creó una cuenta de prueba, se dio de baja con un motivo, se intentó iniciar
sesión con ella, y por separado se intentó dar de baja una cuenta con un viaje activo asociado.

**Comportamiento observado**: antes de confirmar, el sistema mostró una advertencia sobre el efecto
de la baja. Tras confirmarla, el inicio de sesión con esa cuenta fue rechazado (401), mientras que
el registro permaneció visible en el sistema con el estado "Baja" y su motivo. El intento de dar de
baja una cuenta con un viaje en curso fue rechazado con un mensaje que identificó explícitamente el
viaje pendiente de cerrar, en lugar de un error genérico.

**Resultado**: **Satisfactorio**.

**Evidencia recomendada**: captura del mensaje de rechazo al intentar dar de baja una cuenta con un
viaje en curso, mostrando la referencia al viaje específico.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-07 — Foto de perfil y preferencias por cuenta

**Qué se evaluó**: que la foto de perfil y las preferencias de interfaz (tema, tamaño de texto,
color de sidebar) se apliquen de inmediato, persistan tras recargar, y sean exclusivas de cada
cuenta.

**Procedimiento**: se cambió la foto, el tema, el tamaño de texto y el color de sidebar en una
cuenta; se recargó la página completa; se inició sesión con una cuenta distinta.

**Comportamiento observado**: los cuatro cambios se reflejaron en la interfaz sin necesidad de
recargar. Tras una recarga completa del navegador, los cuatro valores se mantuvieron. Al iniciar
sesión con una cuenta distinta, esta conservó sus propios valores por defecto, sin ninguna
filtración de la preferencia de la primera cuenta.

**Resultado**: **Satisfactorio**.

**Evidencia recomendada**: dos capturas de la pantalla de Ajustes de dos cuentas distintas, mostrando
valores diferentes de tema y color de sidebar en cada una.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-08 — Orden de las tablas (más reciente primero)

**Qué se evaluó**: que los listados principales del sistema muestren el registro más reciente en
primer lugar.

**Procedimiento**: se revisó la primera fila de las listas de Solicitudes, Órdenes de
mantenimiento, Historial de viajes, "Mis viajes" y "Fallas del vehículo".

**Comportamiento observado**: en todos los listados revisados, el registro más reciente apareció
en la primera posición, ordenado según el campo de fecha correspondiente a cada dominio (fecha de
envío, fecha programada, fecha de solicitud o fecha del reporte, según el caso).

**Resultado**: **Satisfactorio**, con una limitación conocida y documentada: el buscador de
vehículos por placa se ordena alfabéticamente porque la colección de vehículos no registra una
fecha de alta. Esta limitación no se considera un fallo.

**Evidencia recomendada**: no requiere captura — el resultado se limita a la posición relativa de
filas dentro de una tabla.

---

### PD-09 — Mapa del recorrido en el historial, en sus tres estados

**Qué se evaluó**: que el mapa de un viaje en el historial distinga con claridad entre un
recorrido real, una ruta calculada de respaldo y la ausencia total de datos de ruta, sin nunca
presentar una de estas tres situaciones como si fuera otra.

**Procedimiento**: se abrió el detalle de un viaje con traza GPS real, uno real sin traza (con
origen y destino válidos) y uno del dataset histórico importado sin traza.

**Comportamiento observado**: el viaje con traza real mostró una línea sólida junto con la
cantidad exacta de puntos registrados. El viaje real sin traza mostró una ruta calculada entre
origen y destino sobre calles reales, mediante el mismo mecanismo de cálculo de ruta que usa el
flujo de solicitud, mostrada en un estilo visual deliberadamente distinto (línea punteada, tono
desaturado) acompañada de una nota que aclaró que se trataba de una ruta calculada y no del
recorrido efectivo. El viaje del dataset histórico se mantuvo sin ninguna línea trazada, con la
nota original que explica la ausencia de dato real, sin disparar ningún cálculo de ruta.

**Resultado**: **Satisfactorio**. Los tres estados se distinguieron con claridad visual y textual
en todos los casos verificados.

**Evidencia recomendada**: tres capturas — una por cada estado del mapa (recorrido real, ruta
calculada punteada, y solo marcadores sin línea) — mostrando en cada una la nota explicativa
correspondiente debajo del mapa.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

### PD-10 — Documentación del socio de punta a punta

**Qué se evaluó**: la consistencia de la información documental de un socio entre las distintas
pantallas que la consumen, y el aviso de documentación vencida sin bloqueo de operación.

**Procedimiento**: se revisó la ficha de un socio en Usuarios, se ejecutó el control de vigencia
documental, y se consultó "Mis documentos" desde la cuenta del propio conductor.

**Comportamiento observado**: la fecha de caducidad y el estado de vigencia coincidieron en las
tres pantallas. El control de vigencia incrementó su contador de revisados al incorporar los
documentos de una postulación recién aprobada, sin intervención manual adicional. Al forzar una
fecha de vencimiento pasada, apareció un aviso visible en ambas pantallas (la del conductor y la
del personal interno) que aclaró explícitamente que ninguna operación quedaba bloqueada por ese
motivo.

**Resultado**: **Satisfactorio**.

**Evidencia recomendada**: captura del aviso de documentación vencida en la ficha de Usuarios,
mostrando el texto que aclara que no hay bloqueo de operaciones.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

## 3. Resultados — Pruebas funcionales para usuarios sin conocimiento técnico

Estas pruebas se ejecutaron siguiendo el guion en lenguaje simple del plan, sin desviarse de los
pasos indicados. El resultado de cada una se resume en la tabla siguiente y se detalla después.

| Prueba | Resultado | Observación principal |
|---|---|---|
| PU-01 — Pedir un taxi de principio a fin | Satisfactorio | El estado avanzó solo, sin intervención manual, en ambas ventanas |
| PU-02 — Cobrar el viaje y calificar | Satisfactorio | El viaje quedó primero en la lista, con precio y calificación correctos |
| PU-03 — Inscribirse como conductor y ser aprobado | Satisfactorio | Las dos imágenes se visualizaron antes de la decisión |
| PU-04 — Llevar un vehículo al taller | Satisfactorio | El mensaje de cierre incluyó la próxima intervención y la desviación de costo |
| PU-05 — Reportar que el vehículo falló | Satisfactorio | El reporte y su foto llegaron a la bandeja de Mantenimiento |
| PU-06 — Cambiar cómo se ve el sistema | Satisfactorio | Los ajustes sobrevivieron a la recarga y no afectaron a otra cuenta |
| PU-07 — Marcar las secciones que más usa | Satisfactorio | Las secciones marcadas se duplicaron en "Favoritos" sin desaparecer de su grupo original |
| PU-08 — Dar de baja a una persona | Satisfactorio | El aviso previo fue legible y el bloqueo de acceso fue inmediato |
| PU-09 — Ver por dónde pasó un viaje | Satisfactorio | La diferencia entre "con recorrido" y "sin recorrido" fue clara sin explicación adicional |

**Observaciones de detalle**:

- En **PU-01**, el cambio de "Buscando conductor…" a la información del conductor asignado ocurrió
  sin que la persona ejecutando la prueba tuviera que refrescar la pantalla ni realizar ninguna
  acción — la actualización llegó por sí sola.
- En **PU-03**, al llegar al paso de revisión en `web-interno`, ambos documentos (licencia y
  matrícula) se visualizaron como imagen, con su fecha de caducidad, antes de tomar la decisión de
  aprobación.
- En **PU-09**, al abrir un viaje sin conductor asignado (por lo tanto sin recorrido), el mapa
  mostró únicamente los dos puntos de referencia y una frase explícita indicando que no existía
  dato real de recorrido, en vez de una línea recta que pudiera confundirse con una ruta real.

**Evidencia recomendada para esta sección**: captura de la pantalla de "Mis viajes" tras completar
PU-02, mostrando el viaje recién finalizado en la primera fila con su precio y calificación.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

## 4. Resultados — Evaluación de usabilidad (evaluación heurística)

Se ejecutó un recorrido estructurado sobre cada uno de los nueve escenarios de tarea definidos en
el plan, evaluando en cada uno los diez criterios de usabilidad establecidos: intuitividad,
facilidad para encontrar opciones, navegación sin perderse, claridad de organización de menús,
claridad de nombres, autonomía, pasos innecesarios, comprensión de mensajes y estados, claridad de
qué hacer en cada pantalla, y fluidez general.

### 4.1 Resumen por escenario

| # | Escenario | Resultado del recorrido | Observación principal |
|---|---|---|---|
| TU-01 | Pasajero: pedir un taxi por primera vez | Tarea completable en un único intento de navegación | El destino se fija tocando el mapa; no hay un campo de texto alternativo, lo que exige entender esa convención sin indicación previa en pantalla |
| TU-02 | Pasajero: cancelar y reintentar | Tarea completable | El motivo de cancelación es obligatorio antes de confirmar; la opción "Reintentar búsqueda" reutiliza el mismo origen/destino sin pedirlos de nuevo |
| TU-03 | Pasajero: encontrar un viaje en el historial | Tarea completable con una limitación real de la interfaz | No existe campo de búsqueda por texto ni por destino en el historial del pasajero; solo hay filtro por estado y por rango de fechas |
| TU-04 | Conductor: turno completo hasta el cobro | Tarea completable, con un punto de fricción temporal real | La oferta entrante expira a los 20 segundos (valor configurable), un margen ajustado para quien ve la pantalla por primera vez |
| TU-05 | Conductor: reportar una falla sin indicación previa | Tarea completable desde su ubicación actual en el menú | La función tiene sección propia en el menú ("Fallas del vehículo"), separada de la pantalla de turno, tras la reubicación de una ronda de rediseño anterior |
| TU-06 | Mantenimiento: convertir un reporte en orden | Tarea completable | La pantalla de Mantenimiento abre por defecto en la pestaña "Órdenes"; el reporte de falla vive en una pestaña separada ("Reportes de falla") |
| TU-07 | Captación: revisar documentos y decidir | Tarea completable con un paso intermedio obligatorio | Una solicitud recién enviada solo ofrece el botón "Tomar"; los botones de decisión (Aprobar/Rechazar/Observar) aparecen recién después de ese paso |
| TU-08 | Gerencia: comprender un indicador estratégico | Indicador localizable y sus cifras interpretables sin ambigüedad | El panel distingue con claridad el porcentaje vigente, el conteo de vencidos y el tipo de documento más expuesto |
| TU-09 | Personal interno: reconstruir un viaje con datos incompletos | Tarea completable | Cuando el viaje no tiene destino registrado, la interfaz lo declara explícitamente en vez de mostrar un mapa vacío o incompleto sin explicación |

### 4.2 Hallazgos por criterio

- **Intuitividad general**: la navegación por menú lateral agrupado (Operación / Panel Táctico /
  Panel Estratégico / Administración) permitió ubicar la sección correspondiente a cada escenario
  sin necesidad de recorrer el sistema completo. La jerarquía de los tres niveles organizacionales
  se distingue visualmente en el menú, no solo por el texto del encabezado.
- **Facilidad para encontrar opciones**: en ocho de los nueve escenarios, la opción requerida se
  ubicó desde la sección de menú más directamente asociada a la tarea. La excepción es TU-06, donde
  la ubicación del reporte de falla dentro de una pestaña separada de "Órdenes" no es evidente sin
  explorar la pantalla.
- **Navegación sin perderse**: no se registraron casos en los que completar una tarea exigiera
  salir de la sección de trabajo y volver a entrar; el patrón de panel de detalle sobre la misma
  pantalla (sin cambiar de vista) se mantuvo consistente en los nueve escenarios.
- **Claridad de organización de menús**: la agrupación del menú lateral en zona funcional y zona
  personal ("Mi cuenta") permite distinguir configuración propia de la operación diaria.
- **Claridad de nombres de botones y formularios**: la mayoría de las etiquetas describen la acción
  con precisión ("Convertir en orden", "Reportar una falla", "Confirmar pago recibido"). La
  excepción real identificada es el botón **"Tomar"** (TU-07): la palabra por sí sola no anticipa
  que es el paso previo obligatorio para habilitar la decisión sobre una solicitud.
- **Autonomía sin instrucciones constantes**: los nueve escenarios se completaron sin necesitar más
  de un paso de exploración adicional al previsto por el flujo principal de cada pantalla.
- **Pasos innecesarios**: no se identificaron pasos sobrantes en los flujos de negocio (crear
  orden, aprobar solicitud, reportar falla). Sí se identificó una **espera implícita** no señalada
  como paso (TU-07): antes de "Tomar", ningún botón de decisión existe en pantalla, lo cual puede
  leerse como un paso "faltante" antes de descubrir que es, en realidad, un requisito previo.
- **Comprensión de mensajes y estados del sistema**: los mensajes de estado (`Buscando conductor…`,
  `Viaje pagado`, avisos de documentación vencida, ausencia de recorrido) se presentaron en lenguaje
  llano, sin códigos internos ni terminología técnica.
- **Claridad de qué hacer en cada pantalla**: las pantallas con datos incompletos (viaje sin
  destino) declaran explícitamente la ausencia del dato en lugar de dejar un espacio vacío sin
  explicación, lo cual reduce la posibilidad de que se interprete como una falla del sistema. Los
  indicadores que nunca iban a tener dato real (crecimiento de demanda, avance de capacitación, y
  "% error" de Auditoría) se retiraron directamente de la interfaz en rondas posteriores, en vez de
  mantenerlos como espacio vacío permanente.
- **Fluidez general**: el punto de fricción más consistente en los nueve escenarios fue el límite
  de 20 segundos de la oferta al conductor (TU-04), que exige una respuesta rápida en la primera
  interacción con esa pantalla.

**Evidencia recomendada**: captura de la pantalla de Solicitudes en el estado `ENVIADA` (antes de
pulsar "Tomar"), mostrando que los botones de decisión todavía no están disponibles.

Evidencia de la prueba:
[Insertar aquí captura de pantalla]

---

## 5. Análisis final

### 5.1 Aspectos que funcionaron correctamente

- El ciclo completo de un viaje, desde la solicitud hasta el cobro y la calificación, se ejecutó
  sin intervención manual adicional a la prevista, con actualización de estado en tiempo real en
  ambos portales.
- Los tres mecanismos de baja lógica verificados (catálogos, cuentas de usuario, y la propia
  advertencia previa a la anonimización) preservaron el historial y explicaron con claridad el
  efecto de la acción antes de confirmarla.
- Las preferencias de interfaz (tema, tamaño de texto, color de sidebar) se aplicaron de inmediato,
  persistieron tras recargar la página y se mantuvieron exclusivas de cada cuenta.
- El mapa del historial de viajes distinguió con claridad sus tres estados posibles (recorrido
  real, ruta calculada, y ausencia de dato), sin presentar ninguno de ellos como si fuera otro.
- Los mensajes de estado del sistema se presentaron en lenguaje simple y sin terminología técnica
  en las pantallas orientadas al usuario final.

### 5.2 Aspectos que presentaron dificultades

- El historial de viajes del pasajero no ofrece búsqueda por texto ni por destino, solo filtro por
  estado y por rango de fechas — una limitación real para localizar un viaje específico sin conocer
  su fecha aproximada.
- El botón **"Tomar"**, único disponible al abrir una solicitud recién enviada, no comunica por sí
  mismo que es el paso previo obligatorio para habilitar la decisión sobre esa solicitud.
- La ventana de 20 segundos para responder a una oferta de viaje es ajustada para una primera
  interacción con esa pantalla.
- La ubicación de los reportes de falla en una pestaña separada de "Órdenes" (que es la pestaña que
  abre por defecto) no resulta evidente sin explorar la pantalla de Mantenimiento.

### 5.3 Qué tan intuitiva resulta la interfaz

La interfaz permitió completar la generalidad de las tareas evaluadas ubicando la sección correcta
desde el menú lateral, sin necesidad de recorrer el sistema completo. La agrupación por nivel
organizacional (operativo, táctico, estratégico) y la separación de la zona personal del menú
contribuyen a esa orientación. Los puntos de fricción identificados son puntuales y no impidieron
completar ninguna de las tareas evaluadas.

### 5.4 Qué tan fácil resulta navegar por el sistema

La navegación no exigió, en ningún escenario evaluado, salir de una sección para completar una
tarea y volver a entrar — el patrón de panel de detalle sobre la misma pantalla se mantuvo
consistente. La jerarquía visual del menú lateral resultó suficiente para distinguir entre los
distintos niveles de la organización sin depender únicamente del texto.

### 5.5 Qué tan sencillo es completar las tareas habituales

Las tareas de uso diario evaluadas (pedir un viaje, aceptar una oferta, cerrar una orden de
mantenimiento, revisar una postulación) se completaron sin pasos sobrantes respecto del flujo de
negocio que cada una representa. Las excepciones identificadas son puntuales: el paso implícito de
"Tomar" antes de decidir una solicitud, y el margen de tiempo ajustado para responder a una oferta.

### 5.6 Mejoras que podrían ser necesarias

A partir de las observaciones registradas en este informe, se identifican las siguientes mejoras
como pertinentes:

- Incorporar un campo de búsqueda por texto o por destino en el historial de viajes del pasajero.
- Reforzar la etiqueta o agregar una indicación visual junto al botón "Tomar" que anticipe que
  habilita la decisión sobre la solicitud.
- Evaluar si el margen de 20 segundos de la oferta al conductor es suficiente para una primera
  interacción, sin modificar el comportamiento para conductores ya familiarizados con el sistema.
- Considerar un indicador visual en la pestaña "Órdenes" de Mantenimiento cuando existan reportes
  de falla pendientes de revisión, para reducir la dependencia de que el usuario explore las
  pestañas por su cuenta.

Estas conclusiones se derivan directamente de las pruebas documentadas en este informe y no
incorporan funcionalidades ni problemas fuera del alcance evaluado.

---

## 6. Índice de evidencia pendiente de incorporar

| Sección | Evidencia a capturar |
|---|---|
| PD-01 | Desglose de tarifa al finalizar un viaje |
| PD-02 | Documentos visualizados en el panel de revisión de Captación |
| PD-03 | Mensaje de cierre de orden con desviación de costo |
| PD-04 | Bandeja de reportes de falla con ambos orígenes |
| PD-05 | Catálogo con un taller inactivo y el selector donde ya no aparece |
| PD-06 | Rechazo de baja por viaje en curso |
| PD-07 | Ajustes de dos cuentas con valores distintos |
| PD-09 | Los tres estados del mapa de historial (recorrido real, ruta calculada, sin datos) |
| PD-10 | Aviso de documentación vencida sin bloqueo |
| Parte 3 | "Mis viajes" con el viaje recién finalizado en primera fila |
| Parte 4 | Solicitud en estado `ENVIADA` antes de "Tomar" |
