# Auditoría funcional — Nivel Operativo

Guía de demostración en vivo para UrbanFleet TaxiFlow. Cada funcionalidad de este documento fue
ejecutada personalmente, en el navegador, contra el stack real corriendo en este equipo (no
inferida del código ni copiada de `CLAUDE.md`), con datos reales del entorno de desarrollo y con
una cuenta real del rol correspondiente. Donde el resultado no coincidió con lo esperado, o donde
solo se pudo confirmar parcialmente, se dice explícitamente en el campo 9 de esa entrada.

**Alcance de este documento**: solo procesos de negocio propios de una cooperativa de taxis —
captación de socios, gestión del ciclo de vida del viaje, gestión de flota, mantenimiento de
vehículos, cobro y liquidación, control documental. Cada entrada agrupa el proceso completo, con
sus etapas explicadas adentro — no se fragmenta cada paso de un mismo flujo en una entrada aparte.
Lo que sostiene a estos procesos pero no es en sí mismo una operación de la cooperativa (bitácora
de auditoría, notificaciones, catálogo de informes, autoservicio de cuenta, y los 8 módulos de
Administración del Sistema) vive en `FUNCIONALIDADES_TRANSVERSALES.md`.

**Cómo levantar el entorno antes de la demo**: `docker compose up -d` (backend, Mongo, Redis,
ClickHouse, Airflow, PocketBase) + `npm run dev` en `web-pasajero` (5173), `web-conductor` (5174)
y `web-interno` (5175). Ver §8.6 de `CLAUDE.md` para el detalle completo y las credenciales de
demo (§8.7) — se reutilizan las mismas cuentas en esta auditoría.

---

## 1. Captación de socios

### 1.1 Alta de socios conductores (postulación → verificación → decisión)

**Qué hace y propósito.** El proceso completo por el que una persona interesada en manejar para la
cooperativa pasa de postulante a socio conductor habilitado: envía su solicitud con sus datos y
los del vehículo, el equipo de Captación la revisa, y decide aprobarla, observarla (pedir una
corrección) o rechazarla.

**Por qué existe.** Es la puerta de entrada de nuevos conductores a la flota, con control de
calidad de por medio — la cooperativa no puede aceptar automáticamente a cualquiera que se
postule, alguien tiene que verificar los datos antes de dejarlo operar.

**Dónde se encuentra.** Etapa 1 (postulación) en `web-conductor` (http://localhost:5174), pantalla
de login → "¿Eres postulante nuevo? Postula aquí". Etapas 2-3 (verificación y decisión) en
`web-interno` (http://localhost:5175) → sección "Solicitudes".

**Quién puede usarla.** La postulación (etapa 1) la hace cualquier persona sin cuenta previa. La
verificación y decisión (etapas 2-3) las hace el rol `admin_captacion` (la cuenta de demo
`staff-verificacion` lo incluye).

**Pasos para reproducirla en vivo, por etapa.**

1. **Postulación** (`web-conductor`): clic en "Postula aquí" → completar nombre completo,
   teléfono, contraseña (mínimo 8 caracteres), cédula, número de licencia, placa, año, marca
   (selector con "Otro" para valor libre), modelo, color (selector con "Otro"), capacidad → "Enviar
   solicitud". Confirma con "Solicitud enviada — Te contactaremos por teléfono cuando la
   revisemos."
2. **Tomar la solicitud** (`web-interno` → Solicitudes): buscar la fila en estado `ENVIADA` → "Ver"
   → "Tomar" — el estado pasa a `EN_VERIFICACION` y aparece el bloque de decisión.
3. **Decidir** (mismo panel): elegir "Aprobar" (o "Rechazar"/"Observar" — "Observar" exige un
   motivo de texto libre, no un selector genérico) → "Aceptar decisión".

**Flujo completo / estado previo.** No requiere nada preparado de antemano para la etapa 1 (alta
desde cero, con cédula/teléfono no usados antes). Para demostrar la etapa 2-3 en el mismo bloque de
la demo, conviene crear la postulación unos minutos antes.

**Qué muestra al completarse.** El estado de la solicitud cambia a `APROBADA` (o `RECHAZADA`/
`OBSERVADA`). Al aprobar, el sistema crea automáticamente el usuario conductor y el vehículo
asociado — confirmable de inmediato en la Bitácora de auditoría (ver
`FUNCIONALIDADES_TRANSVERSALES.md`): aparecen los eventos `SOLICITUD_CONDUCTOR_DECISION` y
`VEHICULO_HABILITACION` con la misma marca de tiempo.

**Qué debe saber Darwin.** La carga de documentos (licencia, matrícula, SOAT) está fuera de
alcance a propósito — el aviso en pantalla lo dice explícitamente al postular, no es una carencia
oculta. La aprobación es el efecto real que habilita al conductor a iniciar sesión con la
contraseña que definió al postular — si se quiere demostrar el ciclo completo, después de aprobar
se puede loguear en `web-conductor` con esas credenciales y encadenar directo con el proceso de
"Gestión del ciclo de vida del viaje" (sección 2).

---

### 1.2 Registro de pasajeros

**Qué hace y propósito.** Permite que cualquier persona cree su propia cuenta de pasajero y
empiece a pedir viajes de inmediato — a diferencia del alta de conductores, es un único paso sin
revisión posterior.

**Por qué existe.** Es el alta de usuarios del lado de la demanda — sin cuenta no se puede
solicitar un taxi.

**Dónde se encuentra.** `web-pasajero` (http://localhost:5173), pantalla de login → "¿No tienes
cuenta? Regístrate".

**Quién puede usarla.** Cualquier persona, sin cuenta previa.

**Pasos para reproducirla en vivo.**
1. Clic en "Regístrate".
2. Completar: nombre, elegir "Teléfono" o "Correo" como identificador, el valor correspondiente,
   contraseña (mínimo 8 caracteres), aceptar el checkbox de términos.
3. Clic en "Crear cuenta".

**Flujo completo / estado previo.** Ninguno — alta desde cero. El teléfono/correo debe ser nuevo.

**Qué muestra al completarse.** Inicia sesión automáticamente y lleva directo a la pantalla
"¿A dónde vamos?" (la app pide permiso de ubicación del navegador en este punto — es un permiso del
navegador, no un error del sistema).

**Qué debe saber Darwin.** No hay verificación de OTP ni de correo — el diseño original la
contemplaba pero se abandonó en favor de usuario+contraseña simple (decisión de arquitectura ya
tomada, no mostrarlo como una carencia). El registro dispara login automático — no hace falta un
segundo paso de "iniciar sesión" después de crear la cuenta. La cuenta recién creada puede encadenar
directo con "Gestión del ciclo de vida del viaje" (sección 2).

---

## 2. Gestión del ciclo de vida del viaje

Este es el proceso central del sistema — sin esto no hay negocio. Cubre, como un solo flujo, desde
que el pasajero pide un taxi hasta que ambos se califican al final. Conviene demostrarlo con dos
pestañas del navegador abiertas en simultáneo (una con `web-pasajero`, otra con `web-conductor`)
para que la audiencia vea ambos lados reaccionar en tiempo real.

### 2.1 El ciclo completo: solicitar, despachar, ejecutar y cerrar un viaje

**Qué hace y propósito.** De principio a fin: el pasajero pide un taxi, el sistema lo ofrece al
conductor disponible más cercano, el conductor lo atiende (va, llega, inicia el viaje), lo
finaliza con el cobro correspondiente, y ambas partes se califican mutuamente. Incluye las
variantes y caminos alternos que pueden ocurrir en cualquier punto del camino (nadie disponible,
cancelación, avería del vehículo, compartir el seguimiento con un tercero).

**Por qué existe.** Es el caso de uso central de toda la cooperativa — la razón de ser del
sistema.

**Dónde se encuentra.** `web-pasajero` para el lado del pasajero, `web-conductor` para el lado del
conductor. Todo el ciclo de vida del viaje (desde "¿A dónde vamos?" hasta calificar al final) es un
**overlay sobre el mismo mapa persistente en ambas apps** — nunca navega a otra pantalla, solo
cambia el panel flotante encima del mapa. Es una decisión de diseño deliberada, no un flujo
inconcluso.

**Quién puede usarla.** El rol `pasajero` solicita, cancela, comparte, califica y paga (recibe el
cobro el conductor); el rol `conductor` acepta, ejecuta, finaliza y también califica. Ambos deben
tener cuenta (ver sección 1).

**Pasos para reproducirla en vivo, por etapa.**

**Etapa 0 — Turno del conductor (prerrequisito).** En `web-conductor` → "Mi turno" → "Iniciar
turno" (pide permiso de ubicación) → el estado pasa a `DISPONIBLE` y se ve "Posición reportada —
hh:mm:ss" actualizándose. Sin al menos un conductor `DISPONIBLE`, ningún viaje puede asignarse.

**Etapa 1 — Solicitar (pasajero).** En `web-pasajero`, con el mapa centrado en la ubicación del
pasajero, tocar el mapa para marcar el destino (o usar un chip de dirección favorita ya guardada —
ver "Guardar como favorita" bajo el campo de destino) → el sistema muestra distancia, duración y
tarifa estimadas → "Solicitar taxi". *Variante*: en vez de "Ahora", elegir el toggle "Programar" y
una fecha/hora entre 15 minutos y 7 días en el futuro — el viaje queda en estado `PROGRAMADO` y un
proceso automático (Airflow, cada 2 minutos) lo despacha solo cuando llega la hora, reusando el
mismo mecanismo de auto-despacho de la Etapa 2 sin duplicar lógica. Para una demo en vivo sin
esperar el ciclo de 2 minutos, mostrar solo hasta la confirmación "Viaje programado" es suficiente
y honesto.

**Etapa 2 — Auto-despacho y aceptación (conductor).** En cuanto el pasajero solicita, en
`web-conductor` aparece "Nuevo viaje — Ns" con la distancia hasta el origen y los botones
"Rechazar"/"Aceptar". Clic en "Aceptar". Si el conductor no responde a tiempo, la oferta expira y
el sistema ofrece a otro conductor disponible. *Camino alterno*: si nadie está disponible, el
pasajero ve "No se encontró conductor disponible" con un botón "Reintentar búsqueda" — con al menos
un conductor `DISPONIBLE`, reintentar reusa el mismo origen/destino sin pedir los datos de nuevo
(confirmado en vivo con datos reales: sin conductor en línea → `SIN_CONDUCTOR` → conductor puesto
en línea → reintentar → oferta real generada y aceptada).

**Etapa 3 — Seguimiento hasta iniciar (conductor).** En `web-conductor`: "Voy en camino" → "He
llegado" → "Iniciar viaje". En `web-pasajero`, la tarjeta refleja cada cambio ("El conductor va en
camino", "Viaje en curso") sin ninguna acción propia, y muestra los datos del conductor asignado
(foto, nombre, placa). Al iniciar, aparece un contador de "Distancia recorrida" en vivo a partir de
las posiciones reales reportadas.

**Etapa 3a — Compartir el viaje (opcional, pasajero).** Mientras el viaje está `EN_CAMINO` o
`EN_CURSO`, botón "Compartir viaje" genera un enlace público (`/compartido/<token>`) que cualquiera
puede abrir sin sesión ni cuenta — verificado en esta sesión abriendo el enlace real en una pestaña
sin ninguna cookie ni token guardado, mostrando estado del viaje, conductor, placa y mapa. El
enlace se invalida automáticamente al finalizar o cancelarse el viaje; uno inventado o vencido
siempre devuelve el mismo mensaje genérico (protección contra intentos de adivinar tokens).

**Etapa 3b — Cancelar (opcional, cualquiera de los dos).** Botón "Cancelar solicitud"/"Cancelar
viaje" en cualquier punto antes de finalizar → elegir un motivo del catálogo (Cancelado en camino,
Cancelado por el pasajero, Incidencia en ruta, Pasajero ausente, Vehículo averiado, u "Otro" con
texto libre) → "Confirmar cancelación". El viaje queda `CANCELADO` con el motivo registrado.

**Etapa 3c — Registrar incidencia/avería (opcional, conductor, solo con viaje `EN_CURSO`).** Botón
"Registrar incidencia" → elegir tipo de falla (catálogo cerrado, sin "Otro" — a diferencia del
catálogo de motivos de cancelación, este es intencionalmente cerrado porque el backend lo valida)
→ describir → marcar "No puedo continuar" si corresponde. Si se marca, el sistema cancela ese viaje
y dispara automáticamente uno nuevo para el pasajero desde la posición del incidente, sin que el
pasajero tenga que volver a pedirlo — y notifica en vivo al Coordinador de Operaciones.

**Etapa 4 — Finalización con desglose de tarifa (conductor).** Con el viaje `EN_CURSO`, "Finalizar
viaje" → el sistema calcula y muestra a ambos la tarifa final desglosada:

```
Arrancada:               $0.50
Distancia (X.X km):      $X.XX
Espera (X min):          $X.XX
                          ------
Subtotal:                 $X.XX
Carrera mínima aplicada:  $X.XX   [solo si el subtotal no alcanzaba el mínimo]
```

La línea de "Carrera mínima aplicada" solo aparece cuando el piso realmente se activó — verificado
con un viaje corto (piso aplicado) y con un viaje de distancia real simulada (~3.3 km moviendo la
posición del conductor en pasos), donde el subtotal por sí solo ya superaba el mínimo y la línea
correctamente no aparece.

**Etapa 5 — Cobro en efectivo (conductor).** Ingresar el monto cobrado → "Confirmar pago recibido"
→ el viaje pasa a `PAGADO`. Si el monto no coincide con la tarifa final, el viaje entra a la
bandeja de discrepancias del proceso de Cobro y Liquidación (sección 5) — no hace falta generarlo
en vivo, ya hay un caso real cargado en el entorno.

**Etapa 6 — Calificación mutua (ambos).** Tanto pasajero como conductor eligen de 1 a 5 estrellas y
un comentario opcional a la otra parte → "Enviar calificación" (o "Omitir", que existe a propósito
— calificar no es obligatorio para seguir usando la app).

**Después del proceso — consultar el historial propio.** En cualquiera de las 2 apps, sección "Mis
viajes": lista de viajes propios con fecha, destino, tarifa y estado; el detalle agrega el desglose
de tarifa, la calificación recibida y la foto de la contraparte. El conductor solo ve nombre de
pila y calificación del pasajero (nunca teléfono ni ubicación) — la foto respeta ese mismo límite,
es el mismo tipo de dato de identidad visual, no uno nuevo.

**Flujo completo / estado previo.** El único prerrequisito real es la Etapa 0 (un conductor
`DISPONIBLE`) antes de solicitar. Todo lo demás se desprende del propio flujo — no hace falta
preparar datos aparte.

**Qué muestra al completarse.** Un viaje real `PAGADO`, con calificación en ambos sentidos, visible
de inmediato en "Mis viajes" de ambas cuentas y en el Historial global (nivel táctico).

**Qué debe saber Darwin.** Cada transición del viaje queda registrada en la bitácora de auditoría
con actor y hora exactos (ver `FUNCIONALIDADES_TRANSVERSALES.md`) — buen cierre de demo, volver a
esa pantalla después de un viaje completo y mostrar los eventos recién generados. El acumulado de
kilómetros de cada viaje alimenta `vehiculos.km_acumulado`, usado para proyectar el próximo
mantenimiento preventivo (sección 4). El sistema detecta y rechaza reportes de posición que
impliquen un salto geográfico imposible entre dos lecturas consecutivas (protección
anti-suplantación de GPS) — no es relevante para la demo salvo que pregunten específicamente por
seguridad. En un entorno de solo 5-8 conductores de prueba, el mismo conductor que reportó una
incidencia puede recibir la re-oferta de su propio viaje reasignado — si pasa en la demo, basta con
rechazarla.

---

## 3. Coordinación de Flota

### 3.1 Tablero de flota en vivo

**Qué hace y propósito.** Muestra, en tiempo real, qué vehículos tienen turno activo, su estado
(disponible/ocupado/sin señal) y su posición.

**Por qué existe.** Le da al coordinador de flota visibilidad operativa inmediata de toda la
cooperativa sin tener que preguntar a cada conductor.

**Dónde se encuentra.** `web-interno` → sección "Flota".

**Quién puede usarla.** Rol `coordinador_flota`.

**Pasos para reproducirla en vivo.** Abrir "Flota" — la lista se refresca sola cada 10 segundos. Se
puede filtrar por placa/conductor o por estado.

**Flujo completo / estado previo.** Para ver un vehículo como "Disponible", ese conductor debe
tener el turno iniciado (Etapa 0 de la sección 2) en ese momento.

**Qué muestra al completarse.** Lista de vehículos con turno activo, su conductor, estado, posición
y hora de última actualización; el detalle de cada fila es de solo lectura.

**Qué debe saber Darwin.** Solo lista vehículos con turno activo en ese instante — un vehículo sin
turno simplemente no aparece, no figura como "inactivo" en la tabla. El filtro por zona existe en
la pantalla pero está deshabilitado con una nota, porque la dimensión de zona geográfica no está
resuelta todavía en los datos reales de viajes — es una limitación conocida, no un botón roto.

---

## 4. Mantenimiento de vehículos

### 4.1 Gestión de fallas y órdenes de mantenimiento

**Qué hace y propósito.** El proceso completo de mantenimiento de un vehículo: desde que un
conductor reporta una falla en la calle, hasta que el Jefe de Mantenimiento decide si amerita una
orden de taller, y esa orden se abre, se trabaja (con espera de repuestos si hace falta) y se
cierra con el detalle real de lo hecho y su costo.

**Por qué existe.** Control de mantenimiento de la flota — sin esto no hay forma de saber qué
vehículo está en taller, por qué, ni cuánto costó; y sin el reporte de fallas, el Jefe de
Mantenimiento solo se entera de una avería si alguien lo llama.

**Dónde se encuentra.** Etapa 1 (reporte) en `web-conductor` → "Fallas del vehículo". Etapas 2-3
(conversión y ciclo de la orden) en `web-interno` → "Mantenimiento" (pestañas "Reportes de falla" y
"Órdenes").

**Quién puede usarla.** La etapa 1 la hace el rol `conductor`; las etapas 2-3 el rol
`jefe_mantenimiento`.

**Pasos para reproducirla en vivo, por etapa.**

1. **Reportar una falla** (`web-conductor` → "Fallas del vehículo" → "Reportar una falla" — o,
   dentro de un viaje en curso, "Registrar incidencia", ver sección 2): elegir tipo de falla
   (catálogo cerrado), descripción, foto opcional → enviar. Queda listado con estado "En revisión".
2. **Convertir el reporte en orden** (`web-interno` → Mantenimiento → "Reportes de falla"): abrir
   un reporte `PENDIENTE` → "Convertir en orden" → completar kilometraje de entrada, taller y
   fecha programada (campo obligatorio aunque no lleva asterisco — si "Crear orden" queda
   deshabilitado, revisar ese campo primero) → confirmar. (Alternativa: "Descartar" con motivo, si
   no amerita una orden.) El tipo siempre queda `CORRECTIVA` — una falla reportada nunca es
   preventiva.
3. **Ciclo de la orden** (`web-interno` → Mantenimiento → "Órdenes"): abrir una orden `ABIERTA` →
   "En taller" (pasa a `EN_TALLER`) → si falta un repuesto, "Esperar repuesto" con motivo (pasa a
   `ESPERANDO_REPUESTO`, registrado automáticamente en la cronología de actividad de la orden;
   desde ahí se puede volver a taller o cerrar directo) → "Cerrar" con trabajos realizados, costo
   total, horas de taller, kilometraje de salida, repuestos consumidos, y opcionalmente "Abrir una
   orden correctiva encadenada al cerrar" si se detectó algo más durante el trabajo.

**Flujo completo / estado previo.** Ninguno especial para la etapa 1. La etapa 3 puede arrancar
directo de una orden `ABIERTA` ya existente (hay 130+ en el entorno de desarrollo) sin pasar por
las etapas 1-2 si solo se quiere mostrar el ciclo de la orden.

**Qué muestra al completarse.** Al cerrar: mensaje real con la próxima intervención preventiva
proyectada (en km), el porcentaje de desviación entre costo estimado y costo real, y confirmación
de si se abrió una orden encadenada — verificado en vivo con un cierre real ($26.17 estimado vs.
$34.50 real → "+31.8%") con orden correctiva encadenada real creada. El vehículo queda habilitado
de nuevo.

**Qué debe saber Darwin.** Las 3 etapas se verificaron en vivo de punta a punta en esta sesión,
incluyendo el paso intermedio de "Esperando repuesto" y el cierre con orden encadenada. El costo
estimado que se muestra antes de cerrar es siempre una proyección calculada al vuelo (mano de obra
estimada + repuestos estimados) — nunca un valor fijo guardado de antemano. El tipo de falla del
reporte es un catálogo cerrado por diseño (a diferencia de otros catálogos del sistema, no ofrece
"Otro") — el backend lo valida y rechazaría un valor libre.

---

## 5. Control Financiero

### 5.1 Conciliación y liquidación de pagos a socios

**Qué hace y propósito.** El proceso completo de cierre financiero semanal: detectar y resolver
discrepancias entre lo cobrado y la tarifa real de cada viaje, generar el lote de liquidaciones de
la semana cerrada, y aprobarlas/pagarlas — con una vista de alerta para socios que acumulan varios
periodos en rojo.

**Por qué existe.** Es el mecanismo real de pago a los socios y de control de exactitud del cobro
en efectivo — sin esto no hay forma sistemática de saldar cuentas semana a semana ni de detectar
cuando algo no cuadra.

**Dónde se encuentra.** `web-interno` → "Finanzas".

**Quién puede usarla.** Rol `admin_financiero`.

**Pasos para reproducirla en vivo, por etapa.**

1. **Discrepancias de pago**: la tabla "Pagos en discrepancia" ya muestra cualquier caso real
   existente (tarifa final, monto cobrado, diferencia) con un botón "Resolver" por fila. Debajo,
   "Viajes finalizados sin pago (+24h)" es solo informativo — no tiene acción de resolución
   todavía.
2. **Generar liquidaciones**: botón "Generar liquidaciones del periodo cerrado" — genera el lote de
   la semana viernes-a-viernes más reciente ya cerrada; volver a pulsarlo no duplica lo ya emitido.
3. **Aprobar y pagar**: abrir cualquier liquidación de la lista → aprobar/observar/marcar pagada
   según su estado actual (`EMITIDA` → `OBSERVADA`/`APROBADA` → `PAGADA`).
4. **Alertas de saldo negativo** (monitoreo, sin acción propia): tabla aparte con los socios que
   llevan 2+ periodos consecutivos con saldo negativo sin regularizar.

**Flujo completo / estado previo.** El entorno ya tiene una discrepancia real ($0.50), 3 viajes sin
pago, 9 socios con alerta de saldo negativo, y 71 liquidaciones repartidas en varios periodos y
estados — no hace falta generar nada nuevo para mostrar la variedad completa del proceso.

**Qué muestra al completarse.** Discrepancias con su diferencia exacta; liquidaciones con
conductor, periodo, estado, neto en mano y saldo, con el detalle de cada una desglosando los
movimientos que la componen.

**Qué debe saber Darwin.** No consumir en vivo la única discrepancia real disponible — mostrarla es
más valioso que resolverla, porque no hay forma sencilla de generar una nueva discrepancia real sin
rehacer un viaje completo con un monto distinto al cobrado (el formulario de resolución se
confirmó real y funcional sin necesidad de enviarlo). Un socio sin viajes pagados en el periodo
simplemente no genera liquidación — no es un error si algunos conductores no aparecen en un periodo
dado. La suspensión de turno para los casos de saldo negativo no está automatizada, es puramente
informativo. La corrección de una liquidación ya `PAGADA` mediante nota de ajuste está fuera de
alcance por decisión consciente.

---

## 6. Cumplimiento

### 6.1 Control de vigencia documental

**Qué hace y propósito.** Revisa la vigencia de los documentos de los socios (licencia, matrícula)
y marca cuáles están vencidos o próximos a vencer, para gestionar su renovación.

**Por qué existe.** Cumplimiento normativo — un conductor con licencia vencida no debería seguir
operando.

**Dónde se encuentra.** `web-interno` → "Cumplimiento".

**Quién puede usarla.** Rol `supervisor_cumplimiento`.

**Pasos para reproducirla en vivo.** Botón "Ejecutar control de vigencia" (en producción corre solo
a las 06:00; este botón lo dispara bajo demanda) — confirmado en vivo con un resultado real:
"Revisados: 160 · Por vencer notificados: 2 · Vencidos nuevos: 2".

**Flujo completo / estado previo.** Ninguno — hay 142 documentos reales cargados en el entorno.

**Qué muestra al completarse.** Un mensaje con la cantidad de documentos revisados, cuántos se
notificaron por estar por vencer, y cuántos vencidos nuevos se detectaron en esta corrida.

**Qué debe saber Darwin — investigado a fondo el hallazgo de la ronda anterior, con causa
confirmada.** La misma pantalla incluye una bandeja "Buscar renovaciones pendientes", que se
observó vacía incluso justo después de que el control reportara "Vencidos nuevos: 2". **No es un
filtro que ajustar — es un defecto real de cobertura, confirmado leyendo el código y reproducido en
vivo**: esa bandeja no muestra documentos vencidos, muestra documentos donde un conductor o
propietario **ya subió una renovación** y está pendiente de que Cumplimiento la apruebe (existe un
endpoint de backend para subir una renovación, `POST
/cumplimiento/documentos/{id}/renovacion`). El problema es que **ninguna pantalla de ninguna de las
3 apps llama a ese endpoint** — no hay ningún botón "Subir mi renovación" en `web-conductor` ni en
ningún otro lugar. La propia pantalla lo reconoce indirectamente: el botón "Nuevo" de esa bandeja
está deshabilitado con el tooltip "No aplica: las renovaciones las suben los propios
conductores/propietarios, no el personal interno." Como no existe ningún camino para que un
conductor suba esa renovación, la bandeja **siempre estará vacía en este entorno, sin importar
cuántos documentos venzan** — no es que falte sembrar datos ni ajustar un filtro. Recomendación
para la demo: mostrar únicamente "Ejecutar control de vigencia" (real y funcional) y, si se quiere
ver el detalle de vencidos/por vencer con datos reales, usar el panel táctico "Vigencia Documental"
(que sí lista 67+ documentos vencidos reales por una vía distinta) en vez de la bandeja de
renovaciones — evitar abrir esa bandeja sin explicar de antemano por qué está vacía.

---

## Notas de cierre para Darwin

- **Orden sugerido de presentación**: Captación (alta de conductor + registro de pasajero) → un
  ciclo completo de viaje (pasajero + conductor en paralelo, incluyendo compartir viaje y el
  desglose de tarifa) → Mantenimiento (ciclo completo de una orden) → Finanzas → Cumplimiento.
  Este orden hace que cada sección "explique" la anterior con datos frescos en vez de datos viejos
  del seed.
- **Preparar con antelación**: la postulación de conductor conviene hacerla un rato antes si se
  quiere mostrar también su aprobación sin depender de cambiar de pestaña en vivo bajo presión de
  tiempo.
- **No consumir en vivo**: la única discrepancia de pago real (sección 5) — mostrarla es más
  valioso que resolverla.
- **No abrir sin explicar**: la bandeja de "renovaciones pendientes" de Cumplimiento (sección 6) —
  siempre está vacía por un gap real de cobertura, no por falta de datos.
- Para todo lo que sostiene a estos 6 procesos pero no es en sí mismo una operación de la
  cooperativa (bitácora, notificaciones, catálogo de informes, autoservicio de cuenta, y la
  Administración del Sistema completa), ver `FUNCIONALIDADES_TRANSVERSALES.md`.
