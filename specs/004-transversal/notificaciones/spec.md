# Especificación: Notificaciones (Transversal)

> Documento retroactivo. Fuente principal: `FUNCIONALIDADES_TRANSVERSALES.md` §2, verificada contra
> `backend/src/notificaciones/`.

## 1. Objetivo

Mantener informado a cada usuario de eventos relevantes de su propio rol, sin depender de un canal
externo (correo, SMS).

## 2. Contexto

Los 3 niveles y los 6 departamentos operativos generan eventos que alguien necesita saber (nueva
solicitud, documento vencido, orden creada, incidencia en curso) — sin un centro de notificaciones,
cada rol tendría que revisar activamente cada pantalla para enterarse.

## 3. Actores

- **Cualquier usuario autenticado**, en cualquiera de los 3 portales.

## 4. Requisitos funcionales

### RF-NOT-001 — Campana con contador
Cada portal debe mostrar una campana (ícono real, no emoji) con el número de no leídas, con las
últimas 20 y un enlace "Ver todas".

### RF-NOT-002 — Sección completa en el sidebar
Debe existir una sección propia "Notificaciones" con listado completo, filtros (tipo/estado/rango de
fecha) y detalle.

### RF-NOT-003 — Marcar como leída
Abrir el detalle debe marcarla como leída automáticamente; debe existir además un botón explícito
"Marcar leída" sin necesidad de abrir el detalle.

### RF-NOT-004 — Acción rápida por tipo
Cuando el tipo tiene una pantalla de destino real, un botón debe llevar directo ahí (ej. "Nueva
solicitud de conductor" → Solicitudes).

### RF-NOT-005 — Preferencias por categoría
Las categorías de notificación push (captación, cumplimiento, mantenimiento, viaje) deben poder
activarse/desactivarse por separado en Ajustes — la de seguridad nunca es desactivable.

## 5. Requisitos no funcionales

### RNF-NOT-001 — Consistencia entre campana y sidebar
El contador debe verse idéntico en ambos lugares a la vez, sin necesidad de recargar la página.

## 6. Reglas de negocio

### RN-NOT-001
`no_leidas` se calcula siempre sin filtro (global) — filtrar la lista visible no debe hacer parecer
que la bandeja está al día si hay otras notificaciones sin leer fuera del filtro actual.

### RN-NOT-002
No todos los tipos tienen acción rápida — un tipo sin pantalla de destino real queda como
informativo, sin fabricar un destino que no existe.

## 7. Entradas

- Filtros: tipo, estado (leída/no leída), rango de fecha.
- Cambio de preferencia de categoría en Ajustes.

## 8. Salidas

- Contador consistente en campana + sidebar.
- Listado filtrable con detalle y acción rápida cuando aplica.

## 9. Estados posibles

Notificación: leída / no leída.

## 10. Escenarios

### Escenario 1: Notificación real con acción rápida
Dado que se crea una orden de mantenimiento sobre el vehículo de un conductor logueado en otra
pestaña
Cuando el conductor revisa su campana
Entonces ve la notificación real, y al abrirla queda marcada como leída y el contador baja en los 2
lugares a la vez.

### Escenario 2: Filtro global no engaña sobre pendientes
Dado que hay notificaciones sin leer de varios tipos
Cuando se filtra la lista visible a un solo tipo
Entonces el contador de no leídas sigue reflejando el total real, no solo lo visible.

## 11. Criterios de aceptación

### CA-NOT-001
El contador baja de forma consistente en campana y sidebar al marcar como leída, sin recargar.

### CA-NOT-002
Un tipo con pantalla de destino real navega correctamente sin recargar la página.

## 12. Dependencias

- Consumida por los 6 departamentos operativos y por Administración del Sistema (configuración de
  alertas) — cualquier dominio puede disparar una notificación real.

## 13. Fuera de alcance

- **Canal de entrega distinto de web push** — no hay envío de correo ni SMS en ningún flujo.
- **Acción rápida fabricada** para un tipo sin pantalla de destino real (ej. los 6 tipos que recibe
  el conductor sin ninguna pantalla propia de detalle en ese portal) — quedan informativos a
  propósito.
