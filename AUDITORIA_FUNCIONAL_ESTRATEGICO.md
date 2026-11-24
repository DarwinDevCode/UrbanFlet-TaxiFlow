# Auditoría funcional — Nivel Estratégico

Guía para presentar en voz alta el Tablero Ejecutivo y los 9 dashboards del "Panel Estratégico" de
`web-interno`, ante alguien que no conoce el sistema. Cada indicador responde acá a "¿por qué le
importa esto a alguien que toma decisiones?", no solo "¿de qué es este número?". Todo lo que
aparece ya fue comprobado funcionando con datos reales, con la cuenta `gerencia`
(+593900000010 / `Gerencia123!`) — el único rol que ve los 9 paneles + el Tablero completo. Otros
roles ven solo el panel de su propia área, pero nunca el Tablero, Rentabilidad ni Gobernanza (esos
3 son exclusivos de gerencia).

Regla general de todo el sistema: cuando un dato no existe todavía, el panel muestra "—" en vez de
inventar un número.

**Aviso sobre un nombre engañoso.** El KPI "Conversión de altas" (Crecimiento, y también la
primera tarjeta del Tablero Ejecutivo) suena a "postulantes que llegan a dar su primer viaje", pero
verificado contra el cálculo real, mide otra cosa: qué fracción de las cuentas del sistema
(conductores y pasajeros) no ha sido suspendida ni dada de baja. Es un desajuste real entre el
nombre en pantalla y lo que el sistema calcula — se explica en detalle en el punto 1, y conviene
tenerlo claro porque es la primera cifra que cualquiera va a ver.

---

## 0. Tablero Ejecutivo Consolidado

**¿Qué representa?** Una sola pantalla con la cifra más importante de cada área de la cooperativa,
para detectar en 10 segundos si algo necesita atención antes de entrar al detalle.

**KPI e indicadores**

| Tarjeta | Por qué le importa a gerencia |
|---|---|
| Crecimiento — 98.4% | El nombre dice "conversión", pero mide si las cuentas del sistema (conductores y pasajeros) siguen habilitadas o si se están acumulando suspensiones y bajas — una caída sería señal de un problema (fraude, mal comportamiento) que hay que investigar. |
| Confiabilidad del servicio — 87.8% | Dice si hay suficientes conductores trabajando para atender la demanda en cada momento — si baja, los pasajeros esperan más y empiezan a dejar de usar el servicio. |
| Costo de flota — 100.0% | Un vehículo al que no se le hace mantenimiento a tiempo cuesta más reparar después y es más riesgoso — esta cifra dice si eso se está evitando. |
| Capacidades y plataforma — 1.9% | Si este número sube, significa que los demás datos del sistema (financieros, operativos) se están construyendo sobre información con errores, sin que se note en ninguna otra pantalla. |
| Rentabilidad — 80.0% | Dice cuánto le queda realmente a la cooperativa por cada dólar recaudado, después de comisión y mantenimiento — la diferencia entre facturar mucho y ganar de verdad. |
| Integridad financiera — 100.0% | Dice si se puede confiar en el dinero que los conductores reportan haber cobrado en efectivo — una caída acá es señal de fraude o error de cobro. |
| Cumplimiento normativo — 53.5% | Dice cuánta exposición legal tiene la cooperativa ahora mismo por licencias o matrículas vencidas. |
| Gobernanza de datos — 142 | Confirma que las decisiones administrativas quedan registradas — necesario para poder responder "quién autorizó esto y cuándo" si algo se cuestiona. |

Abajo del todo dice "8 de 8 indicadores con dato publicado" — las 8 tarjetas tienen dato real hoy,
ninguna está caída.

**¿Qué permite entender?** Es el punto de partida para saber a qué área de la cooperativa prestarle
atención primero, sin tener que abrir 8 pantallas. Cada número de acá es exactamente el mismo que
aparece en su panel de detalle — nunca es un cálculo aparte.

**Cómo mostrarlo.** "Panel Estratégico" → "Tablero Ejecutivo" (se abre solo); clic en "Ver
detalle" de cualquier tarjeta salta directo a su panel completo.

---

## 1. Crecimiento Estratégico

**¿Qué representa?** Si la cooperativa está sumando socios conductores de forma sana, o si se está
perdiendo gente por el camino antes de aportar valor real al negocio.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Conversión de altas — 98.4% | A pesar del nombre, no mide si el conductor ya dio su primer viaje — mide si su cuenta sigue habilitada (no suspendida ni dada de baja). Sirve para detectar una ola de suspensiones, no para saber si la captación está funcionando. |
| Retención a 90 días — 0.0% | Diría si los socios que entran se quedan trabajando más de 3 meses o se van rápido — hoy da cero porque todavía ningún socio lleva esos 90 días, no porque se estén yendo. |
| Altas de socios (período) — 183 | Dice si la cooperativa está atrayendo conductores al ritmo que necesita para cubrir la demanda. El período anterior tuvo apenas 7 altas, por eso el salto se ve como +2514% — es real, pero comparado contra muy pocos casos. |

**Nota (ronda de correcciones, agosto 2026):** el KPI "Crecimiento de demanda" que aparecía acá se
quitó de la interfaz — nunca tuvo dato real detrás (no existe ninguna fuente que registre viajes
solicitados por mes de forma consolidable, ver `CLAUDE.md`) y se decidió no ocupar espacio con un
indicador que nunca va a poder mostrar un número. El panel ahora muestra 3 KPIs en vez de 4.

**Gráficos y tablas**

- Tendencia de altas y solicitudes: si las solicitudes suben pero las altas no, hay un cuello de botella en la aprobación, no falta de interesados.
- Conversión de altas en el tiempo: si la salud de la base de cuentas mejora o empeora mes a mes.
- Conversión por canal en el tiempo: qué canal (web, app, referido) trae mejores candidatos.
- Conversión por canal (tabla): esta sí es la conversión real de solicitud a socio aprobado — la
  columna "Conversión" acá mide algo distinto del KPI de arriba, ver "¿Qué permite entender?".

**¿Qué permite entender?** Este panel tiene dos números llamados "conversión" que no miden lo
mismo: el KPI de arriba mide cuentas activas; la tabla de canales mide qué porcentaje de
solicitudes termina aprobada. Si preguntan por la conversión real de postulante a socio, la
respuesta está en la tabla, no en el KPI de cabecera.

**Cómo mostrarlo.** "Panel Estratégico" → "Crecimiento"; probar el filtro de canal en la tabla de
abajo.

---

## 2. Confiabilidad y Disponibilidad del Servicio

**¿Qué representa?** Si el servicio responde rápido y sin fallas para el pasajero — un servicio
lento o con muchas cancelaciones pierde clientes aunque el negocio crezca en socios.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Tiempo de asignación promedio — 0.0s | Mide cuánto espera un pasajero desde que pide el viaje hasta que le confirman conductor — la razón número uno por la que alguien deja de usar la app. Da 0.0s porque en este entorno de prueba la asignación es instantánea, no porque el sistema falle. |
| Tasa de cancelación — 78.3% | Qué proporción de los viajes solicitados en el período termina cancelándose (por el pasajero, por el conductor, o sin conductor disponible). Corregido en la ronda de agosto 2026 — ver nota abajo. |
| Cancelaciones del período — 47 | Cada cancelación es un pasajero que no llegó a destino o un conductor que perdió un viaje. Mientras más bajo, mejor. |
| Flota activa promedio — 87.8% | Si baja, hay menos conductores disponibles para atender la demanda, lo que empeora directamente el tiempo de asignación de arriba. |
| Franja con menor cobertura — 00-06 | Dice en qué horario conviene incentivar más conductores si se quiere mejorar el servicio nocturno — es normal que sea de madrugada, no una alerta. |

**Gráficos y tablas**

- Tiempo de asignación en el tiempo: si el servicio viene tardando más o menos mes a mes.
- Cancelaciones y demanda sin atender: distingue un problema de calidad de servicio (la gente cancela) de uno de falta de oferta (no hay quién atienda).
- Flota activa (%) en el tiempo: si la cobertura de vehículos mejora o empeora.
- Franjas con menor disponibilidad: dónde reforzar la oferta de conductores primero.
- Tiempo de asignación por franja diurna/nocturna: si de noche se tarda más que de día en asignar.

**Nota (ronda de correcciones, agosto 2026):** hasta esta ronda, "Tasa de cancelación" se mostraba
como "—" porque el cálculo de origen (`rpt_tasa_cancelacion`) contaba mal el denominador — el
número de "viajes solicitados" se calculaba con el mismo agrupamiento que separa los cancelados
por motivo, así que terminaba siendo igual al número de cancelados y la tasa daba siempre 100%.
Corregido de raíz calculando el universo real de viajes solicitados por separado; verificado
contra un conteo manual directo en Mongo para 3 períodos reales. El panel de Despacho (nivel
táctico) tenía el mismo defecto y también se corrigió.

**Cómo mostrarlo.** "Panel Estratégico" → "Confiabilidad del servicio"; probar el filtro de
franja horaria.

---

## 3. Estado y Costo de Flota

**¿Qué representa?** Cuánto le cuesta a la cooperativa mantener la flota funcionando, y si ese
mantenimiento se hace antes de que un vehículo falle.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Cumplimiento preventivo — 100.0% | Un vehículo al que no se le hace mantenimiento a tiempo tiene más riesgo de fallar en medio de un viaje, y reparar después de una falla cuesta más que prevenir. Da 100% porque ese mes hubo pocas revisiones programadas y todas se hicieron a tiempo. |
| Costo del último período — $1.681,90 | Es el gasto real que la cooperativa tuvo que cubrir ese mes — dice si el presupuesto de flota alcanza. |
| Costo acumulado — $1.681,90 | Es la base para decidir si conviene seguir reparando la flota actual o empezar a pensar en renovar vehículos — hoy coincide con el anterior porque solo hay un mes con datos. |

**Gráficos y tablas**

- Costo de mantenimiento por mes: si el gasto se dispara en algún mes puntual.
- Cumplimiento del plan preventivo en el tiempo: si el mantenimiento a tiempo mejora o empeora.
- Vehículos candidatos a reemplazo: qué vehículos ya cuestan más de lo que valdría reemplazarlos
  (no incluye kilómetros recorridos — ese dato no está disponible en este panel).

**Cómo mostrarlo.** "Panel Estratégico" → "Estado y costo de flota"; buscar un vehículo por placa
en la tabla de candidatos a reemplazo.

---

## 4. Capacidades y Plataforma

**¿Qué representa?** Si se puede confiar en los datos que alimentan a todo el sistema — si este
proceso falla, los demás paneles (tácticos y estratégicos) empiezan a mostrar información vieja o
incorrecta sin que nadie lo note.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Registros rechazados (global) — 1.94% | Si este número sube, significa que los demás números del sistema (financieros, operativos) se están construyendo sobre datos con errores, sin que se note en ninguna otra pantalla. Mientras más bajo, mejor. |
| Dominio más afectado — cumplimiento_gold | Dice qué parte del sistema revisar primero si se quiere mejorar la calidad general de los datos. |
| Corridas OK — 161 | Confirma que el proceso de carga de datos viene funcionando con la regularidad esperada. |
| Corridas fallidas — 0 | Si un proceso de carga falla, los reportes de esa área quedan desactualizados sin que se note hasta que alguien pregunta por qué un número "no cuadra". Mientras más bajo, mejor. |

**Nota (ronda de correcciones, agosto 2026):** el KPI "Avance de capacitación" que aparecía acá se
quitó de la interfaz — no existe ningún módulo de capacitación en el sistema y se decidió no
ocupar espacio con un indicador que nunca va a poder mostrar un número. El panel ahora muestra 4
KPIs en vez de 5.

**Gráficos y tablas**

- Tendencia de % de registros rechazados: si la calidad de los datos mejora o empeora en el tiempo.
- Registros rechazados por proceso: qué proceso rechaza más datos, comparado con los demás.
- Calidad de datos por proceso: el detalle de cada uno de los 7 procesos.

**Cómo mostrarlo.** "Panel Estratégico" → "Capacidades y plataforma"; filtrar la tabla por
proceso.

---

## 5. Rentabilidad y Demanda

**¿Qué representa?** Cuánto le queda realmente a la cooperativa después de pagar comisión y
mantenimiento, separado por turno diurno y nocturno — para decidir dónde reforzar flota o ajustar
tarifas.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Margen promedio — 80.0% | Es la diferencia entre facturar mucho y ganar de verdad — de cada dólar recaudado, cuánto queda después de comisión y mantenimiento. Da lo mismo en ambas franjas porque ese mes no hubo gasto de mantenimiento que restar: sin ese gasto, lo que queda es solo la recaudación menos la comisión fija del 20%. |
| Franja menos rentable — NOCTURNA | Dice si conviene ajustar la tarifa nocturna o reforzar la flota diurna, según dónde se está perdiendo margen. |
| Margen de esa franja — 80.0% | El margen exacto del turno nocturno — igual al promedio por la misma razón de arriba. |
| Recaudación último trimestre — $30,00 | Es la facturación real de la cooperativa en dólares — bajo porque este es un entorno de prueba con poco volumen real todavía. |

**Gráficos y tablas**

- Demanda de largo plazo: se usa la recaudación como aproximación, porque todavía no se puede
  contar cuántos viajes se piden por trimestre.
- Resumen por franja: cuál turno deja más margen real.
- Matriz de rentabilidad por mes y franja: el detalle completo para auditar mes por mes.

**¿Qué permite entender?** Sirve para decidir en qué franja horaria conviene invertir más flota o
ajustar incentivos, según cuál realmente deja más ganancia neta, no solo más facturación. El
filtro por zona geográfica está deshabilitado porque ese dato todavía no existe en el sistema.

**Cómo mostrarlo.** "Panel Estratégico" → "Rentabilidad y demanda"; filtrar la matriz por franja.

---

## 6. Integridad Financiera

**¿Qué representa?** Si el dinero que se cobra está bien registrado y si la comisión que retiene
la cooperativa es la que corresponde — control financiero antes de que un problema chico se
vuelva grande.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Conciliado — 100.0% | Dice si se puede confiar en que el dinero que los conductores reportan haber cobrado en efectivo coincide con lo que debían cobrar — clave para detectar fraude o error de cobro antes de que crezca. |
| Tasa de discrepancias — 0.0% | Cuenta en cuántos pagos individuales hubo algún problema, aunque el monto total siga cuadrando — dice cuántos casos hay que revisar uno por uno. Mientras más bajo, mejor. |
| Margen de comisión promedio — 20.0% | Confirma que la cooperativa está cobrando la comisión que le corresponde, sin fugas ni descuentos no autorizados. |

**Gráficos y tablas**

- Conciliación y discrepancias en el tiempo: cómo evolucionan ambos indicadores mes a mes.
- Margen de comisión en el tiempo: si la comisión real se mantiene estable en 20%.
- Composición del margen: de lo recaudado, cuánto se va en comisión y cuánto queda neto.
- Períodos con discrepancia relevante: en qué meses hubo pagos con diferencias que revisar.
- Comparación entre años: al comparar 2021 con 2026 hay que aclarar que 2021 es un conjunto de
  datos de prueba histórico, no operación real de la cooperativa.

**¿Qué permite entender?** "Conciliado" y "Tasa de discrepancias" pueden parecer contradictorios,
pero responden preguntas distintas: uno dice cuánto DINERO está bien cobrado, el otro dice cuántos
PAGOS individuales tienen algún problema. Que uno sea alto y el otro también no es un error — son
dos formas distintas de vigilar lo mismo.

**Cómo mostrarlo.** "Panel Estratégico" → "Integridad financiera"; filtrar el gráfico de
comparación por año 2026, para dejar fuera el dato histórico de prueba.

---

## 7. Cumplimiento Normativo

**¿Qué representa?** Si los conductores y vehículos de la cooperativa están habilitados
legalmente para operar — un riesgo real, no solo un trámite pendiente.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Documentación vigente — 53.5% | Operar con licencias o matrículas vencidas es una exposición legal directa para la cooperativa — puede traer sanciones o dejar sin cobertura si pasa un accidente. Mientras más alto, mejor. |
| Documentos vencidos — 66 | Es la lista concreta de a quién contactar antes de que ese riesgo se convierta en un problema real. Se puede hacer clic para ver el detalle. Mientras más bajo, mejor. |
| Tipo más expuesto — LICENCIA CONDUCIR | Dice qué campaña de renovación priorizar primero. |

**Gráficos y tablas**

- Tendencia de vigencia documental: si el riesgo legal viene creciendo o achicándose.
- Vigencia por tipo de documento: licencias comparadas con matrículas.
- Tabla de exposición por tipo: el detalle numérico detrás del gráfico.

**Cómo mostrarlo.** "Panel Estratégico" → "Cumplimiento normativo"; clic en "Documentos vencidos"
para ver el listado completo sin salir de la pantalla.

---

## 8. Gobernanza de Datos y Seguridad

**¿Qué representa?** Si el sistema se está usando y protegiendo correctamente — rendición de
cuentas al más alto nivel, sin tener que revisar el registro técnico completo.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Eventos administrativos — 142 | Sirve para poder responder "quién tomó esta decisión y cuándo" si alguna vez se cuestiona una acción administrativa. Se puede hacer clic para ver el detalle. |
| Accesos denegados — 22 | Cada intento denegado es alguien tratando de hacer algo para lo que no tiene permiso — vigilarlo ayuda a detectar mal uso interno antes de que cause un daño real. Mientras más bajo, mejor. |
| Alertas de seguridad — 241 | Son señales tempranas de posibles intentos de entrar sin autorización o de falsear la ubicación de un vehículo — ignorarlas es el tipo de descuido que termina en un incidente real. Mientras más bajo, mejor. |

**Gráficos y tablas**

- Tendencia de gobernanza: si la actividad administrativa y de seguridad sube o baja junta, o si
  algo se dispara solo (la señal más preocupante).
- Eventos administrativos consolidados: el listado completo, filtrable por tipo y resultado.

**Cómo mostrarlo.** "Panel Estratégico" → "Gobernanza de datos"; filtrar la tabla por acción o
por resultado (OK / denegado).

---

## 9. Desempeño de Conductores

**¿Qué representa?** Compara a los socios conductores entre sí a lo largo de varios trimestres —
útil para reconocer a los más activos o detectar a los que bajan su desempeño.

**KPI e indicadores**

| Indicador | Por qué le importa a gerencia |
|---|---|
| Socios en la ventana — 5 | Dice sobre cuántos conductores hay información real para evaluar en este período. |
| Viajes completados (ventana) — 1.241.663 | En una operación real, mostraría el volumen de trabajo real de la flota de socios. Acá el número es tan alto porque se cargó un histórico grande de prueba para poder demostrar los paneles, no porque 5 conductores hicieran ese volumen real. |
| Ingreso neto (ventana) — $0,00 | En una operación real, mostraría cuánto se les está pagando a los socios. Da cero porque ese histórico grande nunca pasó por el proceso real de pago — un grupo pequeño de viajes nuevos, aparte, sí generó pagos reales y no cae en esta ventana. |

**Gráficos y tablas**

- Top 10 por viajes completados: quién tiene más viajes en el período.
- Detalle por socio y trimestre: viajes, cancelaciones, calificación e ingreso de cada socio.

**¿Qué permite entender?** Con datos reales de operación, sirve para reconocer a los socios más
activos o revisar a los que bajan su desempeño. Hoy, con solo 5 conductores acumulando cientos de
miles de viajes cada uno por el volumen de prueba cargado, cualquier "top" que se vea acá refleja
cómo se cargaron los datos de prueba, no mérito real — conviene decirlo en voz alta si se muestra
este panel. Elegir "Últimos 2 trimestres" en el filtro reduce este efecto.

**Cómo mostrarlo.** "Panel Estratégico" → "Desempeño de conductores"; usar el filtro de "Últimos
2 trimestres" antes de mostrarlo.

---

## Antes de presentar

- Un rol sin permiso de gerencia (ej. `staff-verificacion`) no ve el Tablero Ejecutivo, Rentabilidad
  ni Gobernanza en su menú — está bloqueado de verdad, no solo oculto.
- Orden sugerido: Tablero Ejecutivo primero, luego un panel limpio (Cumplimiento Normativo o
  Integridad Financiera) y uno con matices (Confiabilidad del servicio, por la tasa de
  cancelación), y cerrar con Gobernanza de Datos.
- El dato que más preguntas puede generar es "Conversión de altas" en Crecimiento (punto 1): el
  nombre suena a "postulante que empieza a trabajar", pero mide cuentas activas. Es la primera
  cifra del Tablero Ejecutivo — conviene tenerlo claro de entrada.
