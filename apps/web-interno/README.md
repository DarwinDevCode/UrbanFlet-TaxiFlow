# web-interno

Portal interno administrativo (React + TypeScript + Vite, SPA responsiva sin PWA). Ver `arquitectura_software.md` para el rol de esta app dentro del stack.

## Antes de dar un cambio por cerrado

Cualquier cambio en este paquete debe pasar limpio por los 3 comandos siguientes (en ese orden, desde la raíz del monorepo):

```bash
npm run build -w @urbanflet/web-interno
npm run lint -w @urbanflet/web-interno
npm run test -w @urbanflet/web-interno
```

- **build**: `tsc -b` (type-check estricto) + `vite build`.
- **lint**: ESLint con la config compartida en `eslint.config.js` (raíz del repo) — mismo set de reglas que web-pasajero/web-conductor/shared-ui.
- **test**: Vitest + React Testing Library (config en el bloque `test` de `vite.config.ts`).

Los 3 deben quedar en verde antes de considerar cerrado un cambio — esto aplica en particular a las pantallas nuevas de "work panel" (Flota/Cumplimiento pendientes) y al nivel táctico: cada pantalla nueva que siga el patrón búsqueda+lista+detalle debería sumar al menos un test siguiendo el ejemplo de `Solicitudes`.

## Tests

`src/App.test.tsx` es una red de seguridad, **no cobertura completa** — cubre, sobre la sección Solicitudes (elegida porque cumple los dos requisitos a la vez: usa el patrón WorkPanel y es donde vive la decisión sobre una postulación):

- El patrón WorkPanel: búsqueda (por cédula), paginación (`Siguiente`/offset), y apertura de detalle por fila.
- Aprobar/rechazar una solicitud de conductor (CU-O01): incluye el caso de "rechazar exige motivo" (botón deshabilitado hasta completar el campo).

Este mismo patrón (búsqueda + `ActionBar` + `DataTable` + `Pagination` + `DetailPanel`) se repite en Mantenimiento, Finanzas y Cumplimiento — al escribir tests para esas pantallas (o para Flota/Cumplimiento cuando adopten el patrón), reusar la misma estructura de `App.test.tsx`.

Decisiones de la infraestructura de test, por si se extiende:

- Esta app no tiene mapa (Leaflet) ni WebSocket, así que no necesita los mocks que sí llevan web-pasajero/web-conductor — `setupTests.ts` solo importa `@testing-library/jest-dom/vitest`.
- **`fetch` se mockea por rutas** (`mockFetch` en el test) — mismo patrón que en las otras 2 apps, para mantener consistencia entre los 3 test suites.
- **Login se simula con un JWT falso** en `localStorage`, con el rol necesario para ver la sección bajo prueba (`admin_captacion` para Solicitudes) — el filtrado de secciones por rol vive en `App.tsx` (`SECCIONES`), así que basta con setear los `roles` del token para aterrizar directo en la pantalla correcta.
