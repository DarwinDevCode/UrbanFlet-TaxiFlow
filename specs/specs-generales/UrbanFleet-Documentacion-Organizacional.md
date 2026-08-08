# UrbanFleet — Documentación organizacional

## 1. Introducción

UrbanFleet es una cooperativa de transporte urbano de pasajeros. Sus socios son los propios conductores, quienes aportan sus vehículos a una flota común y perciben los ingresos de sus viajes menos una comisión que sostiene la operación de la cooperativa.

El servicio funciona bajo un modelo de despacho automático: el pasajero solicita el viaje desde la aplicación y el sistema asigna al conductor disponible más adecuado sin intervención de un operador humano. Esto obliga a la cooperativa a sostener tres compromisos permanentes: que haya flota disponible en cada zona y franja horaria, que cada peso cobrado al pasajero se refleje íntegro en la liquidación del socio, y que la documentación de conductores y vehículos esté siempre vigente ante el regulador.

La cooperativa se organiza en siete departamentos:

| Departamento | Responsable |
|---|---|
| Dirección General | Junta de Socios y Gerencia General |
| Captación y Talento | Administrador de Captación |
| Operaciones y Despacho | Coordinador de Operaciones |
| Coordinación de Flota | Coordinador de Flota |
| Mantenimiento | Jefe de Mantenimiento |
| Control Financiero | Administrador Financiero |
| Cumplimiento Regulatorio | Supervisor de Cumplimiento |
| Inteligencia de Negocio y Plataforma | Responsable de Plataforma |

La información de la cooperativa se sostiene en dos bases complementarias: una base relacional que atiende la operación en tiempo real y responde las consultas directas, y una base columnar que almacena las métricas agregadas ya calculadas por un pipeline de datos programado. Los informes de listado se obtienen de la primera; los informes de indicadores, de la segunda.

## 2. Misión

Movilizar a los pasajeros de la ciudad con un servicio de taxi seguro, disponible y de tarifa transparente, garantizando a cada socio conductor una liquidación íntegra y verificable de lo que su trabajo produce, mediante una plataforma propia de despacho automático y control de datos.

## 3. Visión

Ser la cooperativa de transporte urbano de referencia en su zona de operación por confiabilidad del servicio y transparencia con sus socios: cobertura efectiva en todas las zonas y franjas horarias de la ciudad, recaudación conciliada al cien por ciento y documentación regulatoria vigente sin excepciones.

---

# 4. Objetivos y casos de uso

## 4.1. Nivel estratégico

Horizonte de tres a cinco años. Define qué quiere lograr la cooperativa.

### Dirección General

**Responsable:** Junta de Socios y Gerencia General

| Código | Objetivo estratégico |
|---|---|
| OE1 | Crecimiento sostenido de la base de socios conductores y de la demanda de pasajeros |
| OE2 | Continuidad y calidad del servicio de transporte en toda la zona de operación |
| OE3 | Capacidades propias: una plataforma tecnológica sostenible y personas formadas para usarla |
| OE4 | Decisiones de demanda, tarifa y rentabilidad basadas en datos de la propia operación |
| OE5 | Integridad de la recaudación y transparencia en la liquidación a los socios |
| OE6 | Gobernanza de los datos y cumplimiento de la normativa de transporte |

**Casos de uso**

**CU-E01 — Consultar el tablero de indicadores de la cooperativa**
Actor: Gerente General · Objetivos: OE1, OE2, OE3, OE4, OE5, OE6
- «include» Consolidar los indicadores de cada perspectiva del periodo
- «extend» Exportar el tablero para la junta de socios

**CU-E02 — Analizar la rentabilidad por zona y franja horaria**
Actor: Gerente General · Objetivo: OE4
- «include» Consultar el margen por viaje del periodo
- «extend» Comparar contra el mismo periodo del año anterior

**CU-E03 — Definir la política tarifaria**
Actor: Junta de Socios · Objetivo: OE4
- «include» Revisar la demanda histórica por zona y franja
- «extend» Aprobar un ajuste tarifario por franja de alta demanda

**CU-E04 — Auditar la integridad de la recaudación**
Actor: Junta de Socios · Objetivo: OE5
- «include» Verificar la conciliación del periodo
- «extend» Ordenar la investigación de una discrepancia

**CU-E05 — Supervisar la gobernanza de datos y los accesos**
Actor: Gerente General · Objetivo: OE6
- «include» Revisar el registro de auditoría del periodo
- «extend» Revocar un acceso comprometido

## 4.2. Nivel táctico

Horizonte de seis a dieciocho meses. Cada jefe de departamento traduce la estrategia en planes y controles para su área.

### Captación y Talento

**Responsable:** Administrador de Captación

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT1.1 | Onboarding digital autoservicio de conductores y pasajeros | OE1 |
| OT1.2 | Captación y retención de socios conductores y pasajeros | OE1 |

**CU-T01 — Gestionar el onboarding de conductores y pasajeros** · OT1.1
Actor: Administrador de Captación
- «include» Verificar los documentos del postulante
- «extend» Rechazar la solicitud

**CU-T02 — Gestionar campañas de captación y referidos** · OT1.2
Actor: Administrador de Captación
- «include» Validar la elegibilidad del referido
- «extend» Segmentar la audiencia por comportamiento

### Operaciones y Despacho

**Responsable:** Coordinador de Operaciones

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT4.1 | Confiabilidad del despacho automático | OE2 |
| OT4.2 | Reducción de viajes no atendidos y cancelaciones | OE2 |

**CU-T07 — Supervisar el desempeño del despacho automático** · OT4.1
Actor: Coordinador de Operaciones
- «include» Consultar los tiempos de asignación por zona y hora
- «extend» Ajustar el radio de búsqueda de conductores

**CU-T08 — Analizar cancelaciones y viajes sin conductor asignado** · OT4.2
Actor: Coordinador de Operaciones
- «include» Clasificar el motivo de cancelación
- «extend» Emitir alerta de zona desatendida

### Coordinación de Flota

**Responsable:** Coordinador de Flota

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT3.1 | Rastreo GPS de la flota en tiempo real | OE2 |
| OT3.2 | Disponibilidad y continuidad del servicio | OE2 |

**CU-T05 — Supervisar el rastreo y la disponibilidad de la flota** · OT3.1, OT3.2
Actor: Coordinador de Flota
- «include» Consultar la ubicación GPS del vehículo
- «extend» Emitir alerta de baja disponibilidad

**CU-T06 — Supervisar la reasignación automática de viajes** · OT3.2
Actor: Coordinador de Flota
- «include» Verificar la disponibilidad del conductor
- «extend» de CU-O05 Asignar conductor (auto-despacho)

### Mantenimiento

**Responsable:** Jefe de Mantenimiento

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT7.1 | Cumplimiento del plan de mantenimiento preventivo | OE2 |
| OT7.2 | Control del costo de mantenimiento por vehículo | OE2 |

**CU-T04 — Planificar y controlar el mantenimiento de la flota** · OT7.1
Actor: Jefe de Mantenimiento
- «include» Consultar el kilometraje y la última intervención del vehículo
- «extend» Retirar el vehículo de servicio

**CU-T11 — Analizar el costo de mantenimiento por vehículo y periodo** · OT7.2
Actor: Jefe de Mantenimiento
- «include» Consolidar las órdenes de trabajo del periodo
- «extend» Marcar el vehículo como candidato a reemplazo

### Control Financiero

**Responsable:** Administrador Financiero

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT5.1 | Conciliación de los pagos de viajes | OE5 |
| OT5.2 | Control de la liquidación de comisiones a los socios | OE5 |

**CU-T09 — Conciliar pagos y comisiones** · OT5.1, OT5.2
Actor: Administrador Financiero
- «include» Detectar discrepancias entre viajes y pagos
- «extend» Generar un ajuste financiero

**CU-T12 — Controlar la liquidación de comisiones del periodo** · OT5.2
Actor: Administrador Financiero
- «include» Calcular la comisión retenida del periodo
- «extend» Reprocesar una liquidación observada por el socio

### Cumplimiento Regulatorio

**Responsable:** Supervisor de Cumplimiento

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT6.1 | Cumplimiento de la normativa de transporte | OE6 |
| OT6.2 | Trazabilidad y auditoría de la operación | OE6 |
| OT2.1 | Integraciones externas documentadas y controladas | OE3 |

**CU-T10 — Controlar la vigencia documental** · OT6.1, OT6.2
Actor: Supervisor de Cumplimiento
- «include» Verificar las fechas de vencimiento
- «extend» Bloquear al conductor o al vehículo

**CU-T13 — Consultar el registro de auditoría** · OT6.2
Actor: Supervisor de Cumplimiento
- «include» Filtrar los eventos por actor y periodo
- «extend» Exportar la evidencia para el regulador

**CU-T03 — Administrar las integraciones externas** · OT2.1
Actor: Supervisor de Cumplimiento
- «include» Registrar la credencial de integración
- «extend» Revocar la credencial de integración

### Inteligencia de Negocio y Plataforma

**Responsable:** Responsable de Plataforma

| Código | Objetivo táctico | Objetivo estratégico |
|---|---|---|
| OT8.1 | Informes de indicadores disponibles y oportunos para cada área | OE4 |
| OT8.2 | Formación de socios y personal en el uso de la plataforma | OE3 |

**CU-T14 — Operar el pipeline de informes de indicadores** · OT8.1
Actor: Responsable de Plataforma
- «include» Ejecutar el proceso programado del dominio
- «extend» Reprocesar un lote en cuarentena

**CU-T15 — Gestionar la capacitación en el uso de la plataforma** · OT8.2
Actor: Responsable de Plataforma
- «include» Registrar el avance de la capacitación
- «extend» Reasignar una capacitación pendiente

## 4.3. Nivel operativo

Horizonte diario a mensual. Ejecuta las tareas que hacen posible el servicio.

### Captación y Talento

| Código | Objetivo operativo | Objetivo estratégico |
|---|---|---|
| OP1.1 | Registrar y verificar las solicitudes de conductores y pasajeros | OE1 |

**CU-O01 — Registrar la solicitud de un conductor**
Actor: Postulante a socio conductor
- «include» Cargar los documentos del vehículo y de la licencia
- «extend» Guardar la solicitud como incompleta

**CU-O02 — Registrar un pasajero**
Actor: Pasajero
- «include» Validar el contacto del pasajero
- «extend» Completar el perfil en una segunda etapa

**CU-O03 — Verificar la documentación del postulante**
Actor: Administrador de Captación
- «include» Registrar el resultado de la verificación
- «extend» Solicitar la corrección de un documento

### Operaciones y Despacho

| Código | Objetivo operativo | Objetivo estratégico |
|---|---|---|
| OP2.1 | Atender cada solicitud de viaje con asignación automática | OE2 |
| OP2.2 | Mantener consistente el estado de cada viaje de principio a fin | OE2 |

**CU-O04 — Solicitar un viaje**
Actor: Pasajero
- «include» Calcular la tarifa estimada del recorrido
- «extend» Cancelar la solicitud antes de la asignación

**CU-O05 — Asignar conductor (auto-despacho)**
Actor: Sistema
- «include» Seleccionar al conductor candidato más cercano disponible
- «extend» Ofrecer el viaje al siguiente conductor de la lista

**CU-O06 — Ofrecer el viaje al conductor**
Actor: Conductor
- «include» Registrar la respuesta del conductor
- «extend» Expirar la oferta por falta de respuesta

**CU-O07 — Ejecutar el viaje**
Actor: Conductor
- «include» Actualizar el estado del viaje en cada transición
- «extend» Registrar una incidencia en ruta

**CU-O08 — Finalizar el viaje**
Actor: Conductor
- «include» Calcular la tarifa final del recorrido
- «extend» Registrar la calificación del pasajero

**CU-O14 — Consultar el historial de viajes**
Actor: Pasajero, Conductor
- «include» Filtrar los viajes por periodo
- «extend» Emitir el comprobante de un viaje

### Coordinación de Flota

| Código | Objetivo operativo | Objetivo estratégico |
|---|---|---|
| OP2.3 | Registrar la posición y el estado de cada vehículo en servicio | OE2 |

**CU-O19 — Reportar la posición y el estado del vehículo**
Actor: Conductor, Sistema
- «include» Actualizar la ubicación del vehículo
- «extend» Marcar el vehículo como sin señal

### Mantenimiento

| Código | Objetivo operativo | Objetivo estratégico |
|---|---|---|
| OP2.4 | Ejecutar y registrar las órdenes de mantenimiento de la flota | OE2 |

**CU-O12 — Registrar una orden de mantenimiento**
Actor: Jefe de Mantenimiento
- «include» Registrar el kilometraje del vehículo
- «extend» Solicitar un repuesto

**CU-O13 — Cerrar la orden y habilitar el vehículo**
Actor: Jefe de Mantenimiento
- «include» Registrar el costo y el tiempo de la intervención
- «extend» Prolongar el retiro de servicio del vehículo

### Control Financiero

| Código | Objetivo operativo | Objetivo estratégico |
|---|---|---|
| OP5.1 | Registrar y validar cada pago de viaje | OE5 |
| OP5.2 | Calcular la comisión y emitir la liquidación de cada socio | OE5 |

**CU-O09 — Registrar el pago del viaje**
Actor: Sistema, Pasajero
- «include» Validar la consistencia del monto cobrado
- «extend» Marcar el pago en discrepancia

**CU-O10 — Calcular la comisión de la cooperativa**
Actor: Sistema
- «include» Aplicar el porcentaje de comisión vigente
- «extend» Aplicar un ajuste autorizado

**CU-O11 — Generar la liquidación del socio conductor**
Actor: Sistema
- «include» Consolidar los viajes del periodo del socio
- «extend» Emitir una nota de ajuste

### Cumplimiento Regulatorio

| Código | Objetivo operativo | Objetivo estratégico |
|---|---|---|
| OP6.1 | Registrar todo evento sensible en la bitácora de auditoría | OE6 |
| OP6.2 | Controlar cada operación según el rol del actor | OE6 |

**CU-O17 — Registrar un evento en la bitácora de auditoría**
Actor: Sistema
- «include» Sellar el evento con actor, fecha, acción y resultado
- «extend» Disparar una alerta de seguridad

**CU-O18 — Controlar el acceso por rol**
Actor: Sistema
- «include» Validar el rol del actor antes de la transición de estado
- «extend» Bloquear y registrar la operación no autorizada

### Inteligencia de Negocio y Plataforma

| Código | Objetivo operativo | Objetivo estratégico |
|---|---|---|
| OP4.1 | Procesar diariamente los datos de la operación y publicar los indicadores | OE4 |

**CU-O15 — Ejecutar el proceso de transformación de datos**
Actor: Sistema
- «include» Validar y poner en cuarentena los registros inválidos
- «extend» Reprocesar el lote de forma idempotente

**CU-O16 — Publicar los indicadores para los informes de las áreas**
Actor: Sistema
- «include» Cargar el modelo de hechos y dimensiones
- «extend» Notificar una carga fallida al Responsable de Plataforma
