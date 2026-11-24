# UrbanFleet — Documentación organizacional

Este documento describe la organización de la cooperativa UrbanFleet y las funcionalidades que su
sistema ofrece actualmente, ordenadas según los tres niveles organizacionales: operativo, táctico y
estratégico. Su contenido refleja el estado real y verificado del sistema en funcionamiento.

---

## 1. La cooperativa

UrbanFleet es una cooperativa de transporte urbano de pasajeros. Sus socios son los propios
conductores, quienes aportan sus vehículos a una flota común y perciben los ingresos de sus viajes
menos una comisión que sostiene la operación de la cooperativa.

El servicio funciona bajo un modelo de **despacho automático**: el pasajero solicita el viaje desde
la aplicación y el sistema asigna al conductor disponible más adecuado, sin intervención de un
operador humano. Ese modelo obliga a la cooperativa a sostener tres compromisos permanentes:

- Que exista flota disponible en cada franja horaria del día.
- Que cada cobro realizado al pasajero se refleje íntegro en la liquidación del socio.
- Que la documentación de conductores y vehículos se mantenga vigente ante el regulador.

### 1.1 Misión

Movilizar a los pasajeros de la ciudad con un servicio de taxi seguro, disponible y de tarifa
transparente, garantizando a cada socio conductor una liquidación íntegra y verificable de lo que su
trabajo produce, mediante una plataforma propia de despacho automático y control de datos.

### 1.2 Visión

Ser la cooperativa de transporte urbano de referencia en su zona de operación por confiabilidad del
servicio y transparencia con sus socios: cobertura efectiva en todas las franjas horarias,
recaudación conciliada y documentación regulatoria vigente.

### 1.3 Estructura organizacional

La cooperativa se organiza en una dirección general y siete departamentos:

| Unidad | Responsable |
|---|---|
| Dirección General | Gerencia General |
| Captación y Talento | Administrador de Captación |
| Operaciones y Despacho | Coordinador de Operaciones |
| Coordinación de Flota | Coordinador de Flota |
| Mantenimiento | Jefe de Mantenimiento |
| Control Financiero | Administrador Financiero |
| Cumplimiento Regulatorio | Supervisor de Cumplimiento |
| Inteligencia de Negocio y Plataforma | Responsable de Plataforma |

### 1.4 Portales del sistema

El sistema se ofrece a través de tres aplicaciones separadas según el tipo de usuario:

| Portal | Dirigido a | Función principal |
|---|---|---|
| Portal del pasajero | Pasajeros | Solicitar y seguir viajes, consultar su historial |
| Portal del conductor | Socios conductores | Gestionar su turno, atender viajes, reportar fallas, consultar sus liquidaciones |
| Portal interno | Personal de la cooperativa | Operación diaria, paneles de control tácticos y estratégicos, administración |

### 1.5 Fuentes de información

La información se sostiene en dos bases complementarias:

- Una **base operativa** que atiende la operación en tiempo real y responde las consultas directas
  de listado.
- Una **base analítica** que almacena las métricas ya agregadas, calculadas por un proceso de datos
  programado que se ejecuta de forma automática.

Los paneles del sistema identifican en pantalla el origen de cada informe, de modo que el usuario
sabe siempre si está viendo una consulta directa o un indicador agregado.

---

## 2. Cómo se organizan los tres niveles

| Nivel | Horizonte | Pregunta que responde | Quién lo usa |
|---|---|---|---|
| **Operativo** | Diario | ¿Cómo se ejecuta el servicio hoy? | Pasajeros, conductores y personal de cada departamento |
| **Táctico** | Mensual a semestral | ¿Está funcionando bien mi área? | Jefes de departamento |
| **Estratégico** | Anual a plurianual | ¿Hacia dónde va la cooperativa? | Gerencia General |

Cada nivel se apoya en el anterior: la operación diaria genera los datos, el nivel táctico los
controla por área y el nivel estratégico los consolida para la dirección.

### 2.1 Mapa general de objetivos

| Nivel | Código | Objetivo |
|---|---|---|
| Operativo | OP1 | Incorporación de socios conductores y pasajeros |
| Operativo | OP2 | Atención completa de cada solicitud de viaje |
| Operativo | OP3 | Disponibilidad de la flota en servicio |
| Operativo | OP4 | Mantenimiento de los vehículos de la flota |
| Operativo | OP5 | Cobro y liquidación de los viajes |
| Operativo | OP6 | Vigencia documental de socios y vehículos |
| Táctico | OT1 | Rendimiento del proceso de captación |
| Táctico | OT2 | Confiabilidad del despacho y desempeño de los socios |
| Táctico | OT3 | Cobertura y disponibilidad de la flota |
| Táctico | OT4 | Control del plan preventivo y del costo de mantenimiento |
| Táctico | OT5 | Exactitud del cobro y control de la liquidación |
| Táctico | OT6 | Cumplimiento normativo y trazabilidad de la operación |
| Táctico | OT7 | Continuidad y calidad del proceso de datos |
| Estratégico | OE1 | Crecimiento de la base de socios y de la demanda |
| Estratégico | OE2 | Continuidad y calidad del servicio de transporte |
| Estratégico | OE3 | Sostenibilidad de la plataforma y confiabilidad de sus datos |
| Estratégico | OE4 | Decisiones de rentabilidad basadas en datos propios |
| Estratégico | OE5 | Integridad de la recaudación y transparencia con los socios |
| Estratégico | OE6 | Gobernanza de datos y cumplimiento de la normativa |

---

# 3. Nivel operativo

Ejecuta las tareas diarias que hacen posible el servicio. Es el nivel donde ocurre el negocio: se
incorporan socios, se prestan viajes, se cobra, se mantiene la flota y se controlan los documentos.

## OP1 — Incorporación de socios conductores y pasajeros

**Departamento:** Captación y Talento · **Responsable:** Administrador de Captación

- **Qué representa.** La puerta de entrada al sistema, tanto del lado de la oferta (conductores que
  aportan su vehículo) como del lado de la demanda (pasajeros que solicitan viajes).
- **Propósito.** Incorporar nuevos participantes con el control de calidad que corresponde a cada
  caso: revisión documental para los conductores, alta inmediata para los pasajeros.
- **Necesidad que cubre.** Sin socios habilitados no hay flota que despachar; sin pasajeros
  registrados no hay demanda que atender.

### CU-O01 — Alta de socios conductores

**Actores:** Postulante a socio conductor · Administrador de Captación
**Objetivo que respalda:** OP1

Cubre el proceso completo por el que una persona interesada pasa de postulante a socio conductor
habilitado:

- El postulante completa desde el portal del conductor sus datos personales, los del vehículo
  (placa, marca, modelo, año, color, capacidad) y adjunta la documentación exigida con su fecha de
  caducidad.
- El Administrador de Captación toma la solicitud desde el portal interno, revisa los documentos
  adjuntos —que se visualizan en pantalla junto a un indicador de vigencia calculado contra la fecha
  actual— y decide.
- La decisión puede ser aprobar, observar (solicitando una corrección con motivo escrito) o
  rechazar.
- Al aprobar, el sistema crea automáticamente la cuenta del conductor, registra su vehículo en la
  flota e incorpora sus documentos al control de vigencia.

### CU-O02 — Registro de pasajeros

**Actor:** Pasajero
**Objetivo que respalda:** OP1

Permite que cualquier persona cree su propia cuenta desde el portal del pasajero en un solo paso,
indicando su nombre, un teléfono o correo como identificador y una contraseña. El sistema inicia la
sesión de forma automática al completarse el registro, de modo que el pasajero puede solicitar un
viaje de inmediato.

---

## OP2 — Atención completa de cada solicitud de viaje

**Departamento:** Operaciones y Despacho · **Responsable:** Coordinador de Operaciones

- **Qué representa.** El proceso central del negocio: llevar a un pasajero desde su origen hasta su
  destino, cobrando la tarifa correspondiente.
- **Propósito.** Atender cada solicitud con asignación automática de conductor y mantener
  consistente el estado del viaje de principio a fin, incluyendo los caminos alternos que pueden
  presentarse.
- **Necesidad que cubre.** Es la razón de ser de la cooperativa; todo lo demás existe para
  sostenerlo.

### CU-O03 — Gestión del ciclo de vida del viaje

**Actores:** Pasajero · Conductor · Sistema
**Objetivo que respalda:** OP2

Agrupa, como un solo proceso continuo, todas las etapas de un viaje:

| Etapa | Qué ocurre |
|---|---|
| Turno del conductor | El conductor inicia su turno y el sistema comienza a recibir su posición |
| Solicitud | El pasajero marca su destino en el mapa —o lo selecciona de sus direcciones favoritas— y recibe la distancia, duración y tarifa estimadas antes de confirmar |
| Despacho automático | El sistema ofrece el viaje al conductor disponible más cercano; si no responde a tiempo, lo ofrece al siguiente |
| Seguimiento | El conductor avanza por los estados "en camino", "ha llegado" e "inicia el viaje", y el pasajero ve cada cambio junto a los datos del conductor asignado |
| Finalización | El sistema calcula la tarifa final y la muestra desglosada a ambas partes: arrancada, distancia recorrida, tiempo de espera y carrera mínima cuando corresponde |
| Cobro | El conductor registra el monto recibido en efectivo; si no coincide con la tarifa calculada, el viaje queda señalado para revisión financiera |
| Calificación | Pasajero y conductor se califican mutuamente de 1 a 5 estrellas, con un comentario opcional |

El mismo caso de uso contempla las variantes que pueden presentarse durante el proceso:

- **Programación anticipada.** El pasajero puede solicitar el viaje para una fecha y hora futuras;
  el sistema lo despacha automáticamente cuando llega el momento.
- **Reintento de búsqueda.** Si ningún conductor está disponible, el pasajero puede reintentar
  conservando el mismo origen y destino.
- **Compartir el viaje.** El pasajero genera un enlace público que permite a un tercero seguir el
  viaje en curso sin necesidad de cuenta; el enlace se invalida al terminar el viaje.
- **Cancelación.** Cualquiera de las dos partes puede cancelar antes de finalizar, indicando un
  motivo del catálogo.
- **Incidencia en ruta.** El conductor puede registrar una avería durante el viaje; si indica que
  no puede continuar, el sistema cancela ese viaje y genera automáticamente una nueva solicitud para
  el pasajero desde la posición del incidente.

### CU-O04 — Consulta del historial propio de viajes

**Actores:** Pasajero · Conductor
**Objetivo que respalda:** OP2

Permite a cada usuario revisar sus viajes anteriores con fecha, destino, tarifa y estado. El detalle
de cada viaje muestra el desglose de la tarifa, la calificación intercambiada y un mapa con el
recorrido realizado. El conductor accede únicamente al nombre de pila y la calificación del
pasajero, nunca a sus datos de contacto.

---

## OP3 — Disponibilidad de la flota en servicio

**Departamento:** Coordinación de Flota · **Responsable:** Coordinador de Flota

- **Qué representa.** El conocimiento en tiempo real de qué vehículos están trabajando, dónde se
  encuentran y en qué estado.
- **Propósito.** Sostener la base sobre la que opera el despacho automático y dar visibilidad
  inmediata de la cobertura disponible.
- **Necesidad que cubre.** El sistema no puede asignar un viaje a un vehículo del que desconoce su
  posición y disponibilidad.

### CU-O05 — Gestión del turno y reporte de posición

**Actores:** Conductor · Sistema
**Objetivo que respalda:** OP3

El conductor inicia y finaliza su turno desde su portal. Mientras el turno está activo, el
dispositivo reporta la posición del vehículo de forma continua y el sistema actualiza su estado
—disponible, ocupado o sin señal—. El sistema valida cada reporte y descarta aquellos que impliquen
un desplazamiento geográficamente imposible entre dos lecturas consecutivas.

### CU-O06 — Supervisión del tablero de flota en vivo

**Actor:** Coordinador de Flota
**Objetivo que respalda:** OP3

Presenta en el portal interno la lista de vehículos con turno activo, con su conductor, estado,
posición y hora de última actualización. La vista se actualiza automáticamente y admite filtros por
placa, conductor o estado.

---

## OP4 — Mantenimiento de los vehículos de la flota

**Departamento:** Mantenimiento · **Responsable:** Jefe de Mantenimiento

- **Qué representa.** El ciclo completo de atención de un desperfecto, desde que se detecta hasta
  que el vehículo vuelve a estar habilitado.
- **Propósito.** Mantener la flota en condiciones de operar y llevar registro del costo real de cada
  intervención.
- **Necesidad que cubre.** Un vehículo con falla no puede prestar servicio, y sin registro de
  intervenciones no hay forma de conocer el costo de sostener la flota.

### CU-O07 — Gestión de fallas y órdenes de mantenimiento

**Actores:** Conductor · Jefe de Mantenimiento
**Objetivo que respalda:** OP4

Reúne las tres etapas del proceso en un solo flujo:

1. **Reporte de la falla.** El conductor informa el desperfecto desde su portal, eligiendo el tipo
   de falla, describiéndolo y adjuntando una fotografía si lo considera necesario. El sistema
   notifica al Jefe de Mantenimiento y al Coordinador de Operaciones.
2. **Evaluación del reporte.** El Jefe de Mantenimiento revisa el reporte y decide si amerita una
   orden de taller —heredando el vehículo, la descripción y la evidencia fotográfica— o lo descarta
   indicando el motivo.
3. **Ciclo de la orden.** La orden avanza por sus estados: abierta, en taller, en espera de repuesto
   (con el motivo registrado) y cerrada. Al cerrarla se registran los trabajos realizados, el costo
   total, las horas de taller, el kilometraje de salida y los repuestos consumidos. El sistema
   muestra entonces la desviación entre el costo estimado y el real, proyecta la próxima
   intervención preventiva y permite abrir de inmediato una orden encadenada si se detectó algo
   adicional durante el trabajo.

El kilometraje acumulado de cada vehículo se alimenta de los viajes realizados, lo que permite
proyectar cuándo corresponde su siguiente mantenimiento preventivo.

---

## OP5 — Cobro y liquidación de los viajes

**Departamento:** Control Financiero · **Responsable:** Administrador Financiero

- **Qué representa.** El cierre económico de la operación: verificar que lo cobrado sea correcto y
  pagar a cada socio lo que le corresponde.
- **Propósito.** Convertir los viajes realizados en liquidaciones verificables, aplicando la
  comisión que sostiene a la cooperativa.
- **Necesidad que cubre.** Es el compromiso central con los socios: que cada viaje trabajado se
  refleje íntegro en su pago.

### CU-O08 — Conciliación de pagos y liquidación a socios

**Actores:** Administrador Financiero · Sistema
**Objetivo que respalda:** OP5

Comprende el cierre financiero completo:

- **Revisión de discrepancias.** El sistema presenta los pagos donde el monto cobrado no coincide
  con la tarifa calculada del viaje, con la diferencia exacta, para que el Administrador Financiero
  los resuelva.
- **Generación del lote semanal.** Con una sola acción se emiten las liquidaciones del período
  semanal ya cerrado, consolidando los viajes pagados de cada socio y aplicando la comisión vigente.
  Repetir la acción no duplica lo ya emitido.
- **Ciclo de aprobación.** Cada liquidación avanza por sus estados —emitida, observada, aprobada y
  pagada— y su detalle muestra los movimientos que la componen.
- **Alertas de saldo negativo.** Una vista aparte identifica a los socios que acumulan dos o más
  períodos consecutivos con saldo negativo, para su seguimiento.

---

## OP6 — Vigencia documental de socios y vehículos

**Departamento:** Cumplimiento Regulatorio · **Responsable:** Supervisor de Cumplimiento

- **Qué representa.** El control de que la documentación habilitante de conductores y vehículos siga
  siendo válida.
- **Propósito.** Anticipar los vencimientos y avisar a tiempo a quien debe renovar.
- **Necesidad que cubre.** Operar con documentación vencida expone legalmente a la cooperativa; el
  control debe ser sistemático, no depender de que alguien lo recuerde.

### CU-O09 — Control de vigencia documental

**Actores:** Supervisor de Cumplimiento · Sistema
**Objetivo que respalda:** OP6

El sistema revisa la fecha de vencimiento de todos los documentos registrados y clasifica cada uno
como vigente, próximo a vencer o vencido. La revisión se ejecuta de forma programada cada día y
también puede dispararse manualmente desde el portal interno, informando cuántos documentos se
revisaron, cuántos se notificaron por proximidad de vencimiento y cuántos vencimientos nuevos se
detectaron. Los titulares afectados reciben la notificación correspondiente.

El resultado se consulta de dos formas complementarias: como listado de documentos vencidos y por
vencer con su titular y días restantes, y como estado documental individual de un socio determinado
desde su ficha en el portal interno.

---

# 4. Nivel táctico

Cada jefe de departamento supervisa el rendimiento de su área mediante paneles de control que
combinan consultas directas sobre la operación con indicadores agregados por el proceso de datos.
Todos los paneles residen en el portal interno y son accesibles únicamente al rol responsable del
área correspondiente.

## OT1 — Rendimiento del proceso de captación

**Departamento:** Captación y Talento · **Responsable:** Administrador de Captación
**Respalda al objetivo estratégico:** OE1

- **Qué representa.** La medición del embudo de incorporación de socios, no solo de su volumen.
- **Propósito.** Detectar dónde se frena el proceso de alta: si faltan interesados o si se acumulan
  solicitudes sin decidir.
- **Necesidad que cubre.** El crecimiento de la base de socios depende de que el proceso de
  verificación no se convierta en un cuello de botella.

### CU-T01 — Análisis del embudo de captación y altas

**Actor:** Administrador de Captación
**Objetivo que respalda:** OT1

Presenta el estado del proceso de incorporación: solicitudes pendientes de verificación, porcentaje
de conversión del período, tiempo promedio hasta la decisión y retención de los socios incorporados.
Incluye la conversión de altas por canal de captación y el listado de referidos registrados. Los
datos pueden filtrarse por canal de origen.

---

## OT2 — Confiabilidad del despacho y desempeño de los socios

**Departamento:** Operaciones y Despacho · **Responsable:** Coordinador de Operaciones
**Respalda al objetivo estratégico:** OE2

- **Qué representa.** El pulso operativo del negocio: si las solicitudes se atienden con rapidez y
  si los socios están prestando un buen servicio.
- **Propósito.** Detectar problemas de cobertura o de desempeño antes de que se traduzcan en quejas
  de los pasajeros.
- **Necesidad que cubre.** En un modelo de despacho automático, un tiempo de asignación creciente o
  una tasa de cancelación alta son las primeras señales de que el servicio se está deteriorando.

### CU-T02 — Supervisión del despacho y la demanda no atendida

**Actor:** Coordinador de Operaciones
**Objetivo que respalda:** OT2

Muestra cuántos viajes están activos en el momento, cuánto tarda en promedio asignar un conductor,
cuántas solicitudes quedaron sin atender y qué proporción de los viajes solicitados termina
cancelándose. Complementa esos indicadores con el tiempo de asignación desagregado por franja
horaria y con el listado de viajes cancelados o sin conductor, indicando el motivo de cada uno.

### CU-T03 — Evaluación comparativa del desempeño de los conductores

**Actor:** Coordinador de Operaciones
**Objetivo que respalda:** OT2

Compara a los socios conductores entre sí dentro de una ventana de tiempo seleccionable: viajes
completados, viajes cancelados, porcentaje de éxito, calificación promedio e ingreso neto. Permite
reconocer a los socios más activos y detectar caídas de desempeño que ameriten seguimiento.

### CU-T04 — Consulta del historial global de viajes

**Actores:** Coordinador de Operaciones · Supervisor de Cumplimiento · Gerencia General
**Objetivo que respalda:** OT2

Permite buscar cualquier viaje de la cooperativa por nombre de pasajero o conductor, estado o rango
de fechas. El detalle de cada viaje incluye sus participantes, el desglose de la tarifa y el mapa
del recorrido. Es una consulta de solo lectura: un viaje cerrado no se modifica desde esta vista.

---

## OT3 — Cobertura y disponibilidad de la flota

**Departamento:** Coordinación de Flota · **Responsable:** Coordinador de Flota
**Respalda al objetivo estratégico:** OE2

- **Qué representa.** La visión agregada de cuánta flota está efectivamente disponible para atender
  la demanda.
- **Propósito.** Responder con una sola mirada si la cooperativa tiene cobertura suficiente en este
  momento y en cada franja horaria.
- **Necesidad que cubre.** Revisar vehículo por vehículo no permite decidir con rapidez; el
  coordinador necesita el total y su distribución horaria.

### CU-T05 — Supervisión agregada de la disponibilidad de flota

**Actor:** Coordinador de Flota
**Objetivo que respalda:** OT3

Resume cuántos vehículos están en servicio, cuántos libres para recibir un viaje y cuántos dejaron
de reportar posición. Incluye el porcentaje de flota activa por franja horaria y el listado de
vehículos sin señal o en alerta, para su seguimiento directo.

---

## OT4 — Control del plan preventivo y del costo de mantenimiento

**Departamento:** Mantenimiento · **Responsable:** Jefe de Mantenimiento
**Respalda al objetivo estratégico:** OE2

- **Qué representa.** El control de gestión del área de mantenimiento: cuánto se gasta y si el
  mantenimiento se hace a tiempo.
- **Propósito.** Sostener el cumplimiento del plan preventivo y vigilar qué vehículos concentran el
  gasto.
- **Necesidad que cubre.** Reparar después de una falla cuesta más que prevenirla, y sin el costo
  consolidado por vehículo no hay base para decidir una renovación.

### CU-T06 — Análisis de mantenimiento y costos por vehículo

**Actor:** Jefe de Mantenimiento
**Objetivo que respalda:** OT4

Presenta cuántas órdenes están abiertas, cuántos vehículos se encuentran retirados de servicio por
mantenimiento, el nivel de cumplimiento del plan preventivo y el costo acumulado de los vehículos
más gravosos. Incluye la evolución mensual del cumplimiento preventivo y el listado de órdenes
abiertas, filtrable por tipo de orden, vehículo y rango de fechas.

---

## OT5 — Exactitud del cobro y control de la liquidación

**Departamento:** Control Financiero · **Responsable:** Administrador Financiero
**Respalda al objetivo estratégico:** OE5

- **Qué representa.** La vigilancia agregada de dos riesgos financieros distintos: que el cobro no
  coincida con lo debido, y que la comisión retenida no sea la correcta.
- **Propósito.** Detectar desviaciones sistemáticas que no se aprecian revisando caso por caso.
- **Necesidad que cubre.** Diferencias pequeñas y repetidas pasan inadvertidas en la operación
  diaria pero son significativas al acumularse.

### CU-T07 — Control de la conciliación de pagos

**Actor:** Administrador Financiero
**Objetivo que respalda:** OT5

Muestra cuántos pagos tienen una discrepancia sin resolver, el monto total en disputa, el porcentaje
de pagos que concilian correctamente y los viajes finalizados sin cobro registrado. Incluye la
evolución mensual de la tasa de discrepancias por método de pago.

### CU-T08 — Control de la liquidación y del margen de comisión

**Actor:** Administrador Financiero
**Objetivo que respalda:** OT5

Resume cuántas liquidaciones se emitieron, cuántas siguen pendientes de aprobación, el margen de
comisión real de la cooperativa y el tiempo promedio hasta el pago. Presenta la evolución mensual
del margen y su composición —monto bruto, comisión retenida y neto entregado al socio— junto al
listado de liquidaciones por socio y período.

---

## OT6 — Cumplimiento normativo y trazabilidad de la operación

**Departamento:** Cumplimiento Regulatorio · **Responsable:** Supervisor de Cumplimiento
**Respalda al objetivo estratégico:** OE6

- **Qué representa.** El control de dos frentes: la habilitación legal de socios y vehículos, y la
  trazabilidad de lo que ocurre dentro del sistema.
- **Propósito.** Anticipar la exposición regulatoria y poder reconstruir cualquier acción realizada.
- **Necesidad que cubre.** Ante una revisión externa, la cooperativa debe poder demostrar tanto que
  sus socios están habilitados como quién hizo cada cosa y cuándo.

### CU-T09 — Análisis de vigencia documental

**Actor:** Supervisor de Cumplimiento
**Objetivo que respalda:** OT6

Cuantifica cuántos documentos están vencidos, cuántos vencen dentro de los próximos treinta días y
qué porcentaje del total se mantiene vigente. Presenta el detalle por tipo de documento y la
tendencia mensual de vigencia, junto al listado completo filtrable por tipo y rango de vencimiento.

### CU-T10 — Supervisión de la actividad y los accesos del sistema

**Actor:** Supervisor de Cumplimiento
**Objetivo que respalda:** OT6

Combina el registro cronológico completo de acciones del sistema con indicadores de uso: cuántos
eventos se produjeron en el día, cuántos accesos fueron denegados y qué operaciones concentran la
mayor actividad. El registro puede filtrarse por actor, acción y resultado.

---

## OT7 — Continuidad y calidad del proceso de datos

**Departamento:** Inteligencia de Negocio y Plataforma · **Responsable:** Responsable de Plataforma
**Respalda al objetivo estratégico:** OE3

- **Qué representa.** La supervisión del proceso automático que alimenta con datos a todos los
  paneles tácticos y estratégicos.
- **Propósito.** Confirmar que los indicadores que consume el resto de la organización se están
  actualizando y que los datos que los componen son confiables.
- **Necesidad que cubre.** Si este proceso se detiene o degrada, los demás paneles muestran
  información desactualizada sin que resulte evidente.

### CU-T11 — Supervisión de la salud del proceso de datos

**Actor:** Responsable de Plataforma
**Objetivo que respalda:** OT7

Informa cuántas ejecuciones del proceso se completaron correctamente, qué porcentaje de registros se
rechazó por no cumplir las reglas de calidad y cuándo se ejecutó el último proceso. Desglosa el
rechazo por dominio de negocio y presenta el historial de ejecuciones con su estado, filtrable por
dominio y fecha.

---

# 5. Nivel estratégico

Consolida la información de todas las áreas para la Dirección General. Se compone de un tablero
ejecutivo y nueve paneles de análisis. El acceso completo corresponde a la Gerencia General; los
responsables de área acceden al panel estratégico de su propio dominio.

### CU-E01 — Consulta del Tablero Ejecutivo Consolidado

**Actor:** Gerencia General
**Objetivos que respalda:** OE1, OE2, OE3, OE4, OE5, OE6

Presenta en una sola pantalla el indicador principal de cada área de la cooperativa, con su
tendencia reciente, permitiendo identificar en pocos segundos qué frente requiere atención. Cada
tarjeta enlaza directamente al panel de detalle correspondiente, y el valor mostrado es exactamente
el mismo que aparece en ese panel, nunca un cálculo distinto.

---

## OE1 — Crecimiento de la base de socios y de la demanda

- **Qué representa.** La capacidad de la cooperativa de sumar socios conductores de forma sostenida
  y de conservarlos.
- **Propósito.** Verificar que la base de socios crece al ritmo necesario para cubrir la demanda y
  que las cuentas se mantienen habilitadas.
- **Necesidad que cubre.** Sin crecimiento de la oferta, la cooperativa no puede sostener ni ampliar
  su cobertura.

### CU-E02 — Análisis del crecimiento estratégico

**Actores:** Gerencia General · Administrador de Captación
**Objetivo que respalda:** OE1

Analiza la evolución de las altas de socios por período, la proporción de cuentas que se mantienen
habilitadas y la retención de los socios incorporados. Contrasta la tendencia de solicitudes
recibidas contra la de altas efectivas —lo que permite distinguir un problema de captación de uno de
aprobación— y desagrega la conversión por canal de origen.

---

## OE2 — Continuidad y calidad del servicio de transporte

- **Qué representa.** El compromiso de prestar un servicio disponible, rápido y confiable en toda la
  zona de operación.
- **Propósito.** Vigilar que la experiencia del pasajero se mantenga en niveles aceptables y que la
  flota esté en condiciones de sostenerla.
- **Necesidad que cubre.** Un servicio lento o con muchas cancelaciones pierde pasajeros aunque la
  cooperativa siga creciendo en número de socios.

### CU-E03 — Análisis de la confiabilidad y disponibilidad del servicio

**Actores:** Gerencia General · Coordinador de Operaciones
**Objetivo que respalda:** OE2

Evalúa cuánto espera un pasajero desde que solicita el viaje hasta que se le confirma conductor, qué
proporción de las solicitudes termina cancelándose, cuánta flota está activa en promedio y en qué
franja horaria la cobertura es menor. Presenta la evolución de cada indicador en el tiempo y
distingue las cancelaciones por decisión de las partes de la demanda que quedó sin atender por falta
de oferta.

### CU-E04 — Análisis del estado y costo de la flota

**Actores:** Gerencia General · Jefe de Mantenimiento
**Objetivo que respalda:** OE2

Consolida cuánto cuesta sostener la flota y con qué rigor se cumple el plan preventivo. Presenta el
costo de mantenimiento por período, su evolución en el tiempo y el listado de vehículos cuyo costo
acumulado los convierte en candidatos a reemplazo.

### CU-E05 — Evaluación del desempeño de los socios conductores

**Actor:** Gerencia General
**Objetivo que respalda:** OE2

Compara a los socios conductores a lo largo de varios trimestres según viajes completados,
cancelaciones, calificación recibida e ingreso generado. Sirve para reconocer a los socios más
activos y para identificar caídas sostenidas de desempeño.

---

## OE3 — Sostenibilidad de la plataforma y confiabilidad de sus datos

- **Qué representa.** La solidez de la plataforma tecnológica propia sobre la que descansa toda la
  operación.
- **Propósito.** Garantizar que las decisiones de la cooperativa se toman sobre datos correctos y
  actualizados.
- **Necesidad que cubre.** Un deterioro en la calidad de los datos se propaga silenciosamente a
  todos los indicadores financieros y operativos.

### CU-E06 — Evaluación de capacidades y calidad de datos de la plataforma

**Actores:** Gerencia General · Responsable de Plataforma
**Objetivo que respalda:** OE3

Mide qué porcentaje de los registros procesados se rechaza por no cumplir las reglas de calidad, qué
dominio concentra ese rechazo y con qué regularidad se completan los procesos de carga. Presenta la
tendencia de calidad en el tiempo y el detalle por proceso.

---

## OE4 — Decisiones de rentabilidad basadas en datos propios

- **Qué representa.** La capacidad de la Dirección de decidir sobre la base de la operación real de
  la cooperativa y no de estimaciones.
- **Propósito.** Conocer cuánto queda efectivamente para la cooperativa después de la comisión
  entregada al socio y del costo de mantener la flota.
- **Necesidad que cubre.** Facturar mucho no equivale a ganar: la decisión de dónde reforzar flota o
  ajustar incentivos requiere el margen real, no la recaudación bruta.

### CU-E07 — Análisis de rentabilidad y demanda

**Actor:** Gerencia General
**Objetivo que respalda:** OE4

Calcula el margen que le queda a la cooperativa por franja horaria y período, descontando de la
recaudación la comisión entregada al socio y el costo de mantenimiento asociado. Identifica la
franja menos rentable, presenta la evolución de la demanda de largo plazo y ofrece una matriz de
rentabilidad por mes y franja para el análisis detallado.

---

## OE5 — Integridad de la recaudación y transparencia con los socios

- **Qué representa.** La confianza en que el dinero cobrado está correctamente registrado y en que
  la comisión retenida es la que corresponde.
- **Propósito.** Sostener ante los socios la promesa de una liquidación íntegra y verificable.
- **Necesidad que cubre.** El modelo cooperativo depende de la confianza de los socios en que su
  liquidación refleja exactamente su trabajo.

### CU-E08 — Auditoría de la integridad financiera

**Actores:** Gerencia General · Administrador Financiero
**Objetivo que respalda:** OE5

Verifica qué proporción del dinero cobrado concilia correctamente, en cuántos pagos individuales se
detectó alguna diferencia y si el margen de comisión se mantiene en el nivel establecido. Presenta
la evolución de la conciliación y del margen en el tiempo, la composición del margen entre comisión
y neto del socio, y la comparación entre períodos anuales.

---

## OE6 — Gobernanza de datos y cumplimiento de la normativa

- **Qué representa.** La responsabilidad de la cooperativa frente al regulador y frente al uso
  correcto de su propio sistema.
- **Propósito.** Mantener acotada la exposición legal por documentación y poder rendir cuentas de
  toda decisión administrativa.
- **Necesidad que cubre.** Tanto una sanción regulatoria como un uso indebido interno son riesgos
  que deben vigilarse de forma permanente, no revisarse cuando ya ocurrieron.

### CU-E09 — Evaluación del cumplimiento normativo documental

**Actores:** Gerencia General · Supervisor de Cumplimiento
**Objetivo que respalda:** OE6

Cuantifica el porcentaje de documentación vigente de la flota y de los socios, el número de
documentos vencidos y qué tipo de documento concentra la mayor exposición. Presenta la tendencia de
vigencia en el tiempo y permite acceder al listado detallado de los documentos vencidos desde el
propio indicador.

### CU-E10 — Supervisión de la gobernanza de datos y la seguridad

**Actor:** Gerencia General
**Objetivo que respalda:** OE6

Consolida cuántas decisiones administrativas se registraron en el período, cuántos intentos de
acceso fueron denegados y cuántas alertas de seguridad se generaron. Permite revisar la evolución
conjunta de estos indicadores —donde un incremento aislado de uno solo es la señal más relevante— y
consultar el listado completo de eventos administrativos, filtrable por acción y resultado.

---

# 6. Capa transversal de soporte

Las funcionalidades descritas a continuación **no constituyen objetivos organizacionales de ningún
nivel**: ningún departamento existe para ejecutarlas y ningún socio o pasajero es su destinatario
final. Son la plataforma que sostiene a los tres niveles y hace posible que sus procesos operen de
forma segura, trazable y configurable. Se documentan aparte por esa razón.

| Capacidad | Qué aporta al sistema |
|---|---|
| **Bitácora de auditoría** | Registra de forma cronológica cada acción relevante —quién, qué, cuándo, sobre qué y con qué resultado—. Es la base sobre la que se apoyan los casos de uso de trazabilidad de los niveles táctico y estratégico. |
| **Control de acceso por rol** | Valida el rol del actor antes de permitir cualquier operación y registra los intentos denegados. Determina qué secciones ve cada usuario en su portal. |
| **Centro de notificaciones** | Informa a cada usuario de los eventos relevantes para su rol, con bandeja propia, filtros y acceso directo a la pantalla correspondiente. |
| **Autoservicio de cuenta** | Permite a cada usuario editar sus datos de contacto, cambiar su foto de perfil, revisar sus sesiones activas y ajustar la apariencia del portal. |
| **Proceso de datos y catálogo de informes** | Ejecuta de forma programada la transformación de los datos de la operación, valida y descarta los registros que no cumplen las reglas de calidad, y publica los indicadores que consumen los niveles táctico y estratégico. El catálogo muestra cada informe publicado con su fecha de datos. |
| **Administración del sistema** | Ocho módulos reservados al administrador del sistema: gestión de identidades y accesos, configuración general y funcionalidades activables, catálogos de negocio, integraciones externas, monitoreo de infraestructura, políticas de seguridad y alertas, respaldos y continuidad, y gobernanza de datos. |

---

# 7. Trazabilidad entre niveles

La siguiente tabla resume cómo los objetivos de cada nivel se apoyan entre sí.

| Objetivo estratégico | Objetivos tácticos que lo sostienen | Objetivos operativos que lo alimentan |
|---|---|---|
| OE1 — Crecimiento de la base de socios | OT1 | OP1 |
| OE2 — Continuidad y calidad del servicio | OT2, OT3, OT4 | OP2, OP3, OP4 |
| OE3 — Sostenibilidad de la plataforma | OT7 | — |
| OE4 — Decisiones de rentabilidad | OT5, OT4 | OP5, OP4 |
| OE5 — Integridad de la recaudación | OT5 | OP5 |
| OE6 — Gobernanza y cumplimiento | OT6 | OP6 |

---

# 8. Actores del sistema

| Actor | Nivel donde interviene | Portal |
|---|---|---|
| Pasajero | Operativo | Portal del pasajero |
| Socio conductor | Operativo | Portal del conductor |
| Administrador de Captación | Operativo y táctico | Portal interno |
| Coordinador de Operaciones | Táctico | Portal interno |
| Coordinador de Flota | Operativo y táctico | Portal interno |
| Jefe de Mantenimiento | Operativo y táctico | Portal interno |
| Administrador Financiero | Operativo y táctico | Portal interno |
| Supervisor de Cumplimiento | Operativo y táctico | Portal interno |
| Responsable de Plataforma | Táctico | Portal interno |
| Gerencia General | Estratégico | Portal interno |
| Administrador del Sistema | Transversal | Portal interno |
| Sistema | Operativo | — |

El actor **Sistema** interviene de forma autónoma en el despacho automático de viajes, el disparo de
los viajes programados, el cálculo de tarifas y comisiones, el control diario de vigencia documental
y la ejecución del proceso de datos.
