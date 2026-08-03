# web-pasajero

PWA del pasajero (React + TypeScript + Vite). Ver `arquitectura_software.md` para el rol de esta app dentro del stack.

## Antes de dar un cambio por cerrado

Cualquier cambio en este paquete debe pasar limpio por los 3 comandos siguientes (en ese orden, desde la raíz del monorepo):

```bash
npm run build -w @urbanflet/web-pasajero
npm run lint -w @urbanflet/web-pasajero
npm run test -w @urbanflet/web-pasajero
```

- **build**: `tsc -b` (type-check estricto) + `vite build`. Si falla, hay un error de tipos o de bundling.
- **lint**: ESLint con la config compartida en `eslint.config.js` (raíz del repo) — mismo set de reglas que web-conductor/web-interno/shared-ui. `eslint.config.js` no se duplica por app: ESLint busca el archivo subiendo desde el directorio de la app hasta encontrarlo.
- **test**: Vitest + React Testing Library. `vitest.config` vive en `vite.config.ts` (bloque `test`), no en un archivo aparte.

Los 3 deben quedar en verde — no se cierra un cambio con el linter en rojo ni tests rotos, aunque el resto del comando falle silenciosamente en warnings (ver `no-unused-vars` con prefijo `_` como única excepción tolerada).

## Tests

`src/App.test.tsx` es una red de seguridad, **no cobertura completa** — cubre los flujos ya verificados manualmente en navegador real y que no deben romperse en silencio:

- Solicitar viaje: flujo principal (A1), error de geolocalización (A2), `TRIP_ALREADY_ACTIVE` (A3, CU-O04).
- Cancelar solicitud (CU-O04 A4).
- Reintentar búsqueda tras `SIN_CONDUCTOR` (CU-O05 A3).

Decisiones de la infraestructura de test, por si se extiende:

- **`RideMap` se mockea** (`vi.mock("./RideMap")`): usa Leaflet, que no funciona bien en jsdom (tiles, `ResizeObserver`, medición de layout). El mapa en sí se verifica visualmente en navegador, no acá.
- **`fetch` se mockea por rutas** (`mockFetch` en el test): cada test declara los endpoints que le importan; las llamadas de fondo (tarifa vigente, taxis cercanos) tienen un default silencioso para no tener que declararlas en cada test.
- **Login se simula con un JWT falso** en `localStorage` (`AuthProvider` decodifica el payload sin verificar firma en el cliente — la autorización real vive en el backend) — no hay que pasar por el formulario de login para probar flujos autenticados.
- **`WebSocket` se stubea en `src/setupTests.ts`**: la app abre un socket a `${getApiBaseUrl()}/ws/pasajero/{id}` mientras el viaje puede cambiar en vivo; en tests no hay `configureApiClient`, así que la URL queda relativa y el `WebSocket` real de jsdom la rechaza. El polling de respaldo (que sí se ejercita) cubre las mismas transiciones.
