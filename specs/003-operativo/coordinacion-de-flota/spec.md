# Especificación: Coordinación de Flota (Nivel Operativo)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_OPERATIVO.md` §3, verificada contra
> `backend/src/flota/`.

## 1. Objetivo

Dar visibilidad en tiempo real de qué vehículos tienen turno activo, su estado y su posición, sin
que el coordinador tenga que preguntar a cada conductor.

## 2. Contexto

La posición y disponibilidad de la flota cambia constantemente durante el día — sin una vista
centralizada, saber "¿tenemos cobertura ahora mismo?" requeriría llamar conductor por conductor.

## 3. Actores

- **`coordinador_flota`** (personal interno) — consulta el tablero.
- **`conductor`** — genera los datos (posición, estado de servicio) simplemente usando su turno,
  sin ninguna acción dirigida a este módulo.

## 4. Requisitos funcionales

### RF-FLO-001 — Tablero de flota en vivo
El sistema debe mostrar la lista de vehículos con turno activo en este momento, con conductor,
estado (disponible/ocupado/sin señal) y posición, actualizada sola cada 10 segundos.

### RF-FLO-002 — Filtro por placa/conductor y por estado
El tablero debe permitir buscar por placa/conductor y filtrar por estado.

### RF-FLO-003 — Detección de "sin señal"
Un vehículo con turno activo pero sin reporte de posición reciente debe marcarse como "sin señal",
no simplemente desaparecer de la lista.

## 5. Requisitos no funcionales

### RNF-FLO-001 — Solo lectura
El módulo no tiene ningún verbo de edición sobre vehículos — es exclusivamente de consulta.

### RNF-FLO-002 — Sin paginación de servidor
`GET /flota/tablero` no pagina ni filtra en servidor — es un tablero en vivo, no un listado CRUD; la
búsqueda/paginación de la pantalla son client-side sobre el snapshot que igual se refresca cada 10s.

## 6. Reglas de negocio

### RN-FLO-001
Solo lista vehículos con turno activo en ese instante — un vehículo sin turno iniciado simplemente
no aparece, no figura como "inactivo" en la tabla.

## 7. Entradas

- Filtro de búsqueda por placa/conductor (client-side).
- Filtro por estado (client-side).

## 8. Salidas

- Lista de vehículos en servicio con conductor, estado, posición y hora de última actualización.

## 9. Estados posibles

Estado de servicio del conductor (`usuarios.conductor.estado_servicio`): `FUERA_DE_LINEA`,
`DISPONIBLE`, `OCUPADO`. No es una máquina de estados propia de este módulo — se gestiona en
Operaciones y Despacho (turno) y se refleja aquí como consulta.

## 10. Escenarios

### Escenario 1: Consulta de cobertura actual
Dado que 3 conductores tienen turno iniciado
Cuando `coordinador_flota` abre el tablero
Entonces ve los 3 vehículos con su estado y posición real, actualizándose solos cada 10 segundos.

### Escenario 2: Vehículo sin señal
Dado que un conductor con turno activo deja de reportar posición
Cuando pasa el umbral de tiempo esperado
Entonces su fila se marca "Sin señal" en vez de desaparecer.

## 11. Criterios de aceptación

### CA-FLO-001
El tablero muestra únicamente vehículos con turno activo — un vehículo sin turno no aparece en
ninguna fila.

### CA-FLO-002
El filtro por zona aparece deshabilitado con una nota visible, nunca oculto ni simulado.

## 12. Dependencias

- **003-operativo/operaciones-y-despacho** — fuente real de las posiciones y el estado de servicio.
- **002-tactico/coordinacion-de-flota** — agrega este mismo dato en el panel táctico.

## 13. Fuera de alcance

- **Filtro por zona geográfica** — deshabilitado, la dimensión de zona nunca se resuelve en los
  datos reales de posición (gap heredado, documentado en varios niveles).
- **Cualquier verbo de edición** sobre un vehículo desde este módulo (existe en Mantenimiento, no
  acá).
