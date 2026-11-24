# Constitución — reglas generales del sistema

Reglas que **todo** módulo, de cualquier nivel, respeta hoy. No son aspiraciones: cada una está
verificada contra el código real y se cita su ubicación. Una especificación de departamento nunca
repite estas reglas — las referencia por su código (`RG-NNN`).

## RG-001 — Autenticación por contraseña, sin OTP

El acceso a los 3 portales (pasajero, conductor, personal interno) es por teléfono-o-correo +
contraseña. No existe verificación por código enviado por SMS/correo en ningún punto del sistema.
*(`backend/src/auth/`)*

## RG-002 — Bloqueo por intentos fallidos

Login, renovación de sesión y denegaciones de permiso comparten el mismo mecanismo de bloqueo
temporal: 5 fallos en 15 minutos bloquean el recurso por 15 minutos, con las claves de conteo en
Redis. *(`backend/src/core/`)*

## RG-003 — Control de acceso por rol (RBAC)

Cada endpoint del backend declara explícitamente qué rol o combinación de roles puede invocarlo. Un
actor sin el rol requerido recibe un error de autorización y el intento queda registrado en la
bitácora. Los roles no son exclusivos entre sí: una misma cuenta de personal interno puede acumular
varios roles a la vez (p. ej. Jefe de Mantenimiento y Coordinador de Flota). *(`backend/src/core/rbac.py`)*

## RG-004 — Bitácora de auditoría write-ahead

Toda acción que cambia un estado de negocio relevante (decisión sobre una solicitud, transición de
un viaje, cierre de una orden, emisión de una liquidación, cambio de vigencia documental) se
registra en la bitácora **antes** de aplicar el cambio, con actor, rol, entidad afectada y
resultado. *(`backend/src/core/audit.py`)*

## RG-005 — Mapa: siempre Leaflet + OpenStreetMap

Ningún mapa del sistema usa el SDK de Google Maps. Google se usa exclusivamente para geocodificación
y cálculo de ruta, siempre a través del backend (nunca llamado directo desde el navegador, porque la
API de rutas de Google no admite solicitudes desde el cliente). *(`apps/*/src/*Map.tsx`)*

## RG-006 — El ciclo de vida del viaje es un overlay sobre un mapa persistente

En los portales de pasajero y conductor, desde que se elige un destino hasta que se califica al
finalizar, el componente de mapa se monta una sola vez; solo cambia el panel flotante que se le
superpone. Nunca se navega a una pantalla distinta durante ese ciclo. *(`apps/web-pasajero/src/App.tsx`,
`apps/web-conductor/src/App.tsx`)*

## RG-007 — Ninguna decisión, baja o cancelación se ejecuta sin motivo

Rechazar una solicitud, observar una liquidación, descartar un reporte, cancelar un viaje o dar de
baja una cuenta exige un motivo explícito. El control que ejecuta la acción permanece inhabilitado
hasta que el motivo está presente.

## RG-008 — Baja lógica, nunca borrado físico

Ninguna entidad de negocio (cuenta, vehículo, documento, catálogo) se elimina de la base de datos.
Se desactiva o se marca como dada de baja, conservando su historial y su trazabilidad.

## RG-009 — Los datos agregados provienen de un proceso de datos propio, nunca de cálculos en el
frontend

Ningún panel del sistema calcula una agregación (promedio, tendencia, porcentaje) en el navegador.
Los indicadores compuestos se publican por un proceso de datos programado (Bronze → Silver → Gold)
que corre fuera de la aplicación web; el frontend solo los consulta y los muestra, identificando
siempre si el dato es una consulta directa o un indicador ya agregado.
