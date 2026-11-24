# Checklist de validación: Operaciones y Despacho

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PD-01** — Ciclo completo, verificado en Mongo (`estado:"PAGADO"`, `desglose_tarifa`
  poblado, ambas calificaciones).
- [ ] **PD-09** — Mapa del historial en sus 3 estados (con recorrido / sin recorrido / sin
  destino), confirmando que la traza nunca viaja en la lista, solo en el detalle.
- [ ] **PU-01**/**PU-02** — Versión en lenguaje simple.
- [ ] **PU-09** — Interpretación honesta de un viaje sin recorrido registrado.
- [ ] **TU-01** — Pasajero pide un taxi sin instrucciones, en menos de 2 minutos, hasta calificar.
- [ ] **TU-02** — Cancelar con motivo obligatorio + reintentar reutilizando origen/destino.
- [ ] **TU-03** — Buscar un viaje en el historial (expone la carencia de búsqueda por texto).
- [ ] **TU-04** — Conductor completa un turno sin instrucciones (nota: la oferta expira en 20s por
  defecto, margen ajustado para alguien que ve la pantalla por primera vez).

## Funcional (nuevos)

- [ ] **CHK-DES-001** — "Carrera mínima aplicada" solo aparece cuando el subtotal real no alcanza
  el piso — confirmar con un viaje corto (aparece) y uno con distancia real simulada (no aparece).
- [ ] **CHK-DES-002** — El enlace de "Compartir viaje" abierto sin sesión devuelve 200 con los
  datos reales; el mismo enlace tras finalizar el viaje devuelve el 404 genérico.
- [ ] **CHK-DES-003** — Marcar "No puedo continuar" en una incidencia cancela el viaje `EN_CURSO` y
  genera uno nuevo automáticamente para el mismo pasajero.
- [ ] **CHK-DES-004** — `GET /viajes/{id}` (traza) solo responde 200 al propio pasajero/conductor
  del viaje; `GET /viajes/historial-global/{id}` solo a los 4 roles internos autorizados.

## Automatizado

- [ ] `backend/tests/viajes/` (múltiples archivos) — incluye `test_historial_global.py` (RBAC de
  traza, 21 casos).
- [ ] `npm run test -w @urbanflet/web-pasajero` y `-w @urbanflet/web-conductor`.

## No verificable automáticamente

- [ ] Ciclo real con 2 pestañas simultáneas (pasajero + conductor) reaccionando en tiempo real.
- [ ] Recorrido real dibujado en el mapa con `getComputedStyle`/conteo de puntos SVG.
