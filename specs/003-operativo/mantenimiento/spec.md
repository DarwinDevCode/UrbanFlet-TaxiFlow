# Especificación: Mantenimiento (Nivel Operativo)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_OPERATIVO.md` §4, verificada contra
> `backend/src/mantenimiento/` y `backend/src/reportes_falla/`.

## 1. Objetivo

Gestionar el mantenimiento de la flota de punta a punta: desde que un conductor reporta una falla en
la calle, hasta que el Jefe de Mantenimiento decide si amerita una orden de taller, y esa orden se
trabaja y se cierra con el detalle real de lo hecho y su costo.

## 2. Contexto

Sin este proceso, el Jefe de Mantenimiento solo se entera de una avería si alguien lo llama, y no
hay forma sistemática de saber qué vehículo está en taller, por qué, ni cuánto costó — ni de
proyectar cuándo toca la próxima revisión preventiva.

## 3. Actores

- **`conductor`** — reporta fallas del vehículo, con o sin viaje en curso.
- **`jefe_mantenimiento`** (personal interno) — convierte reportes en órdenes, gestiona el ciclo
  completo de cada orden.

## 4. Requisitos funcionales

### RF-MAN-001 — Reporte de falla por el conductor
El conductor debe poder reportar una falla eligiendo un tipo de un catálogo cerrado, con
descripción y foto opcional, tanto dentro de un viaje en curso ("Registrar incidencia") como fuera
de turno ("Reportar una falla").

### RF-MAN-002 — Bandeja única de reportes
El sistema debe listar en la misma bandeja los reportes que llegan del conductor y los que el propio
Jefe de Mantenimiento crea directamente, sin distinción visual de que uno valga más que el otro.

### RF-MAN-003 — Conversión de reporte a orden
Un reporte `PENDIENTE` debe poder convertirse en orden (kilometraje de entrada, taller, fecha
programada) — siempre `CORRECTIVA`, nunca preventiva — o descartarse con motivo.

### RF-MAN-004 — Ciclo completo de la orden
Una orden debe poder transicionar: `ABIERTA` → `EN_TALLER` → (opcional) `ESPERANDO_REPUESTO` con
motivo obligatorio, registrado automáticamente en la cronología → de vuelta a `EN_TALLER` o directo
a `CERRADA`, con trabajos realizados, costo real, horas de taller, kilometraje de salida y repuestos
consumidos.

### RF-MAN-005 — Proyección de próxima intervención preventiva
Al cerrar una orden, el sistema debe mostrar la próxima intervención preventiva proyectada (en km),
calculada sobre `vehiculos.km_acumulado` real (alimentado por cada viaje finalizado) contra un
umbral global.

### RF-MAN-006 — Desviación de costo
Al cerrar, el sistema debe mostrar el porcentaje de desviación entre el costo estimado (proyectado
al vuelo: mano de obra + repuestos estimados, nunca un valor guardado de antemano) y el costo real.

### RF-MAN-007 — Orden correctiva encadenada
Al cerrar una orden, debe poder abrirse opcionalmente una segunda orden correctiva vinculada
(`orden_madre_id`), heredando el kilometraje de salida de la primera.

### RF-MAN-008 — Ficha del vehículo
El sistema debe mostrar, por vehículo, su kilometraje acumulado real, fecha/km de la última
intervención, y un aviso si le toca preventivo según el umbral global.

### RF-MAN-009 — Catálogo de repuestos con costo sugerido
Los formularios de repuestos deben ofrecer un selector contra el catálogo real (con precio
referencial sugerido, siempre editable) en vez de texto libre.

## 5. Requisitos no funcionales

### RNF-MAN-001 — Catálogo de tipo de falla cerrado por diseño
A diferencia de otros catálogos del sistema (que ofrecen "Otro"), el tipo de falla de un reporte es
un catálogo cerrado — el backend lo valida y rechaza un valor libre.

### RNF-MAN-002 — Cronología insert-only por orden
Cada orden mantiene su propia bitácora de actividad (comentarios, avances, transiciones
automáticas) — insert-only, distinta de la bitácora global de auditoría.

## 6. Reglas de negocio

### RN-MAN-001
El umbral de proyección de preventivo es **global** (mismo valor para toda la flota) — no existe
ninguna diferenciación por antigüedad del vehículo en el sistema real, pese a que la spec original
lo sugería como ejemplo; documentado como simplificación deliberada, no un olvido.

### RN-MAN-002
Un reporte convertido en orden siempre es `CORRECTIVA` — una falla reportada nunca se reclasifica
como preventiva.

### RN-MAN-003
Marcar "En taller" (transición operativa frecuente) queda auditado igual que crear/cerrar/anular —
hallazgo real corregido en una ronda posterior (antes esta transición específica no se auditaba).

## 7. Entradas

- Conductor: tipo de falla (catálogo cerrado), descripción, foto opcional, "no puedo continuar"
  (solo con viaje activo).
- Jefe de Mantenimiento: kilometraje, taller, fecha, mano de obra/repuestos estimados; al cerrar:
  trabajos realizados, costo real, horas, km de salida, repuestos consumidos.

## 8. Salidas

- Reporte de falla listado en la bandeja única.
- Orden con su ciclo de vida completo.
- Mensaje real de próxima preventiva proyectada + desviación de costo al cerrar.
- Vehículo habilitado de nuevo tras el cierre.

## 9. Estados posibles

Orden: `ABIERTA` → `EN_TALLER` ⇄ `ESPERANDO_REPUESTO` → `CERRADA` / `ANULADA`.
Reporte de falla: `PENDIENTE` → `CONVERTIDO_A_ORDEN` / `DESCARTADO`.

## 10. Escenarios

### Escenario 1: Reporte del conductor convertido en orden y cerrado con encadenada
Dado que un conductor reporta una avería mecánica con foto
Cuando el Jefe de Mantenimiento la convierte en orden, la lleva a `EN_TALLER`, espera un repuesto,
reanuda, y cierra con costo real distinto al estimado, marcando "abrir correctiva encadenada"
Entonces la orden queda `CERRADA` con la desviación real mostrada, existe una segunda orden
`CORRECTIVA` nueva con el kilometraje heredado, y el vehículo vuelve a `HABILITADO`.

### Escenario 2: Reporte descartado
Dado que un reporte no amerita una orden
Cuando el Jefe de Mantenimiento pulsa "Descartar" con un motivo
Entonces el reporte queda `DESCARTADO`, sin crear ninguna orden.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md`:
- **PD-03** — Orden con todos sus estados, incluida la desviación de costo.
- **PD-04** — Reporte de falla desde los 2 orígenes, misma bandeja.
- **PU-04**/**PU-05** — Versión en lenguaje simple.
- **TU-05** — Conductor reporta una falla sin instrucciones (mide si la reubicación reciente del
  botón fue realmente intuitiva).
- **TU-06** — Mantenimiento convierte un reporte real en orden sin instrucciones (mide si las
  pestañas de la pantalla se descubren solas).

### CA-MAN-001
Cerrar una orden con costo real distinto al estimado muestra el porcentaje de desviación correcto.

### CA-MAN-002
Un reporte del conductor y uno creado internamente aparecen en la misma bandeja, sin distinción
visual de origen que sugiera prioridad distinta.

## 12. Dependencias

- **003-operativo/operaciones-y-despacho** — alimenta `km_acumulado` con cada viaje finalizado.
- **004-transversal/administracion-del-sistema** (Catálogos) — talleres, tipos de falla, repuestos.
- **004-transversal/notificaciones** — la creación de una orden dispara aviso al conductor
  correspondiente.

## 13. Fuera de alcance

- **Corrección automática por umbral de kilometraje**: existe la proyección informativa, pero no
  genera una pre-orden automática (CU-O12 A2 no implementado, decisión ya tomada).
- **Diferenciación del umbral preventivo por antigüedad del vehículo** — umbral único global.
- **Validación externa de talleres** (que el taller esté realmente habilitado legalmente) — el
  catálogo es de referencia interna, sin validación externa.
