## 1. Backend — autoservicio de la ficha

- [x] 1.1 En `backend/src/mantenimiento/service.py`, agregar `VehiculoConductorNoAsignadoError` (404,
      junto a `VehiculoNoEncontradoError` en la línea 33) y verificar que el mensaje es claro
      ("no tenés un vehículo asignado" o equivalente).
- [x] 1.2 En el mismo archivo, agregar `obtener_ficha_de_mi_vehiculo(db, *, conductor_id)` que
      resuelve `db.vehiculos.find_one({"propietario_id": conductor_id})`, lanza
      `VehiculoConductorNoAsignadoError` si no hay vehículo, y delega en
      `obtener_ficha_vehiculo(db, vehiculo_id=vehiculo["_id"])` ya existente — verificar que no
      duplica ningún cálculo de `obtener_ficha_vehiculo`.
- [x] 1.3 En `backend/src/mantenimiento/router.py`, agregar `_conductor = require_roles("conductor")`
      junto a `_jefe_mantenimiento` (línea 11) y el endpoint nuevo
      `GET /mantenimiento/vehiculos/mio/ficha` (gateado a `_conductor`, usando `actor.usuario_id`,
      nunca un `vehiculo_id` del cliente), reusando `schemas.FichaVehiculoOut` tal cual — verificar
      que la ruta no colisiona con `GET /vehiculos/{vehiculo_id}/ficha` (declarar `/mio/ficha` antes
      que la ruta con parámetro, o confirmar con una llamada real que FastAPI la resuelve bien).
- [x] 1.4 Tests nuevos en `backend/tests/mantenimiento/test_mantenimiento.py` (o archivo dedicado):
      conductor con vehículo propio recibe 200 con la ficha real; conductor sin vehículo recibe 404;
      un `jefe_mantenimiento` (sin rol `conductor`) recibe 403 en `/vehiculos/mio/ficha`; un
      `conductor` recibe 403 en `GET /vehiculos/{id}/ficha` (el endpoint existente sigue exclusivo
      de `jefe_mantenimiento`) — verificar con `pytest backend/tests/mantenimiento/` en verde.
- [x] 1.5 Correr `ruff check src/ tests/` dentro de `backend/` y confirmar 0 hallazgos nuevos.

## 2. Frontend (`web-conductor`) — pantalla "Mi vehículo"

- [x] 2.1 Agregar el tipo `MiFichaVehiculo` (o reusar/derivar el shape de `FichaVehiculoOut`) y una
      función `FichaVehiculoView()` en `apps/web-conductor/src/App.tsx`, siguiendo el patrón de
      `MisDocumentosView` (líneas 1099+): `apiFetch<T>("/mantenimiento/vehiculos/mio/ficha")` en un
      `useEffect`, manejo de `ApiError`, estado de carga — verificar que compila con `tsc -b`.
- [x] 2.2 Renderizar la ficha con `KpiCard` (`escala`/`referencia` para km acumulado vs. próxima
      preventiva, ver design.md D5) + `Card` con fecha/km de última intervención + `Alert
      tono="advertencia"` cuando `le_toca_preventivo` es verdadero, mismo lenguaje visual que
      `MisDocumentosView` — verificar visualmente en el navegador (ver tarea 4.1).
- [x] 2.3 Manejar el estado "sin vehículo asignado" (404 de 1.1) con un mensaje claro en vez de un
      error genérico — verificar simulando la respuesta 404 o con una cuenta de conductor real sin
      vehículo si existe una en el entorno de datos de demo.
- [x] 2.4 Agregar `"vehiculo"` a `VistaConductor` (línea 1914-1923) y la entrada
      `{ id: "vehiculo", label: "Mi vehículo", group: "Operación" }` en `navItemsConductor` (después
      de "Fallas del vehículo"/"Mis documentos", línea ~1946-1947) y el `else if (vista ===
      "vehiculo")` que renderiza `<FichaVehiculoView />` (junto a los demás `else if` de vista,
      ~línea 2289-2292) — verificar que "Mi turno"/"Mis viajes"/"Mis liquidaciones" del riel inferior
      no cambian de posición.
- [x] 2.5 En `resolverAccionRapida` (~línea 2297-2306), agregar la rama para
      `ORDEN_MANTENIMIENTO_REGISTRADA`/`ORDEN_MANTENIMIENTO_CERRADA` → `{ etiqueta: "Ver mi
      vehículo", onClick: () => setVista("vehiculo") }`, junto a la rama ya existente de
      `DOCUMENTO_VENCIDO`/`DOCUMENTO_POR_VENCER` — verificar que el comentario que documentaba el
      gap ("siguen sin pantalla propia...") se actualiza o se retira, ya no es cierto.
- [x] 2.6 Actualizar el mock de `App.test.tsx` (`web-conductor`) para incluir el handler nuevo de
      `GET /mantenimiento/vehiculos/mio/ficha` (mismo patrón que el resto de handlers por defecto),
      y sumar al menos un test que abra "Mi vehículo" desde la navegación y confirme que muestra el
      kilometraje/próxima preventiva del mock — verificar con `npm run test -w @urbanflet/web-conductor`.
- [x] 2.7 Correr `npm run build -w @urbanflet/web-conductor` y `npm run lint -w @urbanflet/web-conductor`
      y confirmar 0 errores nuevos (los 3 warnings preexistentes de `useEffect` en otras apps no
      aplican a `web-conductor`).

## 3. Documentación

- [ ] 3.1 Actualizar `CLAUDE.md` (sección de estado por CU / pendientes) con el cierre de este punto,
      siguiendo el mismo formato ya usado para rondas anteriores — solo si el usuario pide dejar
      constancia en ese archivo antes de cerrar la sesión (regla de cierre del proyecto, `CLAUDE.md`
      encabezado).

## 4. Verificación end-to-end en navegador (regla de cierre del proyecto)

- [ ] 4.1 Con una cuenta real de conductor con vehículo propio (ver credenciales documentadas en
      `CLAUDE.md` §8.7/§22), abrir "Mi vehículo" desde la navegación y confirmar en pantalla el
      kilometraje acumulado, la última intervención y la próxima preventiva reales — no simulados.
- [ ] 4.2 Generar una notificación real de `ORDEN_MANTENIMIENTO_REGISTRADA` (crear una orden real
      sobre el vehículo de esa cuenta desde `jefe_mantenimiento`) y confirmar que la acción rápida
      "Ver mi vehículo" navega a la pantalla nueva. Repetir para `ORDEN_MANTENIMIENTO_CERRADA`
      (cerrar esa orden) y confirmar que el kilometraje/próxima preventiva mostrados reflejan el
      cierre.
- [ ] 4.3 Confirmar que un `jefe_mantenimiento` real sigue sin ver "Mi vehículo" (rol no incluido) y
      que el endpoint existente `/vehiculos/{id}/ficha` sigue funcionando para ese rol sin cambios.
