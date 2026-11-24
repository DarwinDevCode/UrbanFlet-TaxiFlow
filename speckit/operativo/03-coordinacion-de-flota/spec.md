# Especificación: Departamento de Coordinación de Flota

**Nivel:** Operativo · **Objetivo que respalda:** OP3 — Disponibilidad de la flota en servicio ·
**Responsable:** Coordinador de Flota

## 1. Objetivo

Conocer en tiempo real qué vehículos están trabajando, dónde se encuentran y en qué estado, para
sostener la base sobre la que opera el despacho automático.

## 2. Contexto

El sistema no puede asignar un viaje a un vehículo del que desconoce su posición y disponibilidad.
La gestión del turno del conductor y el reporte continuo de posición son, por eso, un requisito de
funcionamiento del despacho, no solo un dato de supervisión.

## 3. Usuarios o actores

- **Socio conductor** — inicia/finaliza turno, su dispositivo reporta posición.
- **Coordinador de Flota** — supervisa el tablero en vivo desde el portal interno.
- **Sistema** — valida cada reporte de posición y actualiza el estado del vehículo.

## 4. Funcionalidad 1 — Gestión del turno y reporte de posición (CU-O05)

### 4.1 Requisitos funcionales

- **RF-FLOT-001**: El sistema debe permitir al conductor iniciar y finalizar su turno desde su
  portal.
- **RF-FLOT-002**: Mientras el turno está activo, el sistema debe recibir reportes periódicos de la
  posición del vehículo y mantener actualizado su estado: disponible, ocupado, o sin señal.
- **RF-FLOT-003**: El sistema debe marcar automáticamente como "sin señal" a un vehículo que no
  reporta posición durante más de 60 segundos, sin que nadie tenga que marcarlo a mano.
- **RF-FLOT-004**: El sistema debe rechazar como inválido cualquier reporte de posición que implique
  un desplazamiento geográficamente imposible respecto del último reporte válido (más de 3 km en el
  intervalo entre dos lecturas consecutivas), y debe generar una alerta de seguridad cuando esto
  ocurre.

### 4.2 Reglas de negocio

- **RN-FLOT-001**: Un conductor no puede iniciar turno si su vehículo no está habilitado (por
  ejemplo, si está retirado por mantenimiento).
- **RN-FLOT-002**: Un conductor no puede finalizar su turno mientras tiene un viaje activo asignado.
- **RN-FLOT-003**: Un salto de posición que supera el umbral de desplazamiento imposible no se
  aplica al estado del vehículo, pero sí queda registrado como evento de seguridad.

### 4.3 Entradas

Coordenadas de posición, marca de tiempo del reporte.

### 4.4 Salidas

Estado del vehículo actualizado (disponible/ocupado/sin señal/fuera de línea); alerta de seguridad
cuando corresponde.

### 4.5 Escenarios

**Escenario: turno normal**
Dado que un conductor con vehículo habilitado inicia su turno
Cuando su dispositivo reporta posición de forma continua
Entonces el vehículo queda "disponible" para recibir ofertas de viaje.

**Escenario: pérdida de señal**
Dado que un conductor con turno activo deja de reportar posición
Cuando pasan más de 60 segundos sin un nuevo reporte
Entonces el sistema marca el vehículo como "sin señal" automáticamente.

**Escenario: salto de posición imposible**
Dado que la última posición válida de un vehículo está a cierta distancia
Cuando llega un reporte nuevo que implicaría un desplazamiento de más de 3 km en el intervalo
transcurrido
Entonces el sistema descarta ese reporte para el estado del vehículo y genera una alerta de
seguridad.

### 4.6 Criterios de aceptación

- **CA-FLOT-001**: Un vehículo sin reportes por más de 60 segundos aparece como "sin señal" sin
  intervención manual.
- **CA-FLOT-002**: Un reporte de posición geográficamente imposible no mueve el marcador del
  vehículo y queda registrado en la bitácora de seguridad.
- **CA-FLOT-003**: Un conductor con un viaje activo no puede finalizar su turno.

## 5. Funcionalidad 2 — Supervisión del tablero de flota en vivo (CU-O06)

### 5.1 Requisitos funcionales

- **RF-FLOT-005**: El sistema debe presentar en el portal interno la lista de vehículos con turno
  activo: conductor, estado, posición y hora de la última actualización.
- **RF-FLOT-006**: El sistema debe actualizar el tablero de forma automática, sin que el Coordinador
  de Flota tenga que recargar la pantalla.
- **RF-FLOT-007**: El sistema debe permitir filtrar el tablero por placa, conductor o estado.

### 5.2 Entradas

Filtro de placa, conductor o estado.

### 5.3 Salidas

Lista en vivo de vehículos en turno, con su posición en un mapa.

### 5.4 Escenarios

**Escenario: consulta en vivo**
Dado que hay varios vehículos con turno activo
Cuando el Coordinador de Flota abre el tablero
Entonces ve la lista completa con su estado y posición actualizada, sin necesidad de recargar la
página para ver cambios posteriores.

### 5.5 Criterios de aceptación

- **CA-FLOT-004**: El tablero refleja un cambio de estado de un vehículo (por ejemplo, de
  disponible a ocupado al aceptar un viaje) sin recargar la página.
- **CA-FLOT-005**: El filtro por estado reduce la lista a exactamente los vehículos en ese estado.

## 6. Requisitos no funcionales

- **RNF-FLOT-001 (seguridad)**: Todo salto de posición geográficamente imposible se registra como
  evento de seguridad, no solo se descarta en silencio.

## 7. Dependencias

- Captación y Talento: un vehículo debe existir y estar habilitado (creado al aprobar una
  postulación) antes de poder reportar turno.
- Operaciones y Despacho: el estado "disponible"/"ocupado" del vehículo es lo que el despacho
  automático consulta para ofrecer un viaje.
- Mantenimiento: un vehículo retirado por una orden de taller no puede iniciar turno.

## 8. Fuera de alcance

- Filtro del tablero por zona geográfica — el dato de zona no se resuelve todavía en la posición
  reportada.
- Envío de instrucciones de navegación al conductor por parte del Coordinador de Flota.

---

**Trazabilidad**: Nivel Operativo → Departamento Coordinación de Flota → OP3 → CU-O05/CU-O06 →
`web-conductor` (pantalla "Mi turno"), `web-interno` → Flota → `backend/src/flota/`.
