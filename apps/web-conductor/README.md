# web-conductor

PWA del conductor (React + TypeScript + Vite). Ver `arquitectura_software.md` para el rol de esta app dentro del stack.

## Antes de dar un cambio por cerrado

Cualquier cambio en este paquete debe pasar limpio por los 3 comandos siguientes (en ese orden, desde la raíz del monorepo):

```bash
npm run build -w @urbanflet/web-conductor
npm run lint -w @urbanflet/web-conductor
npm run test -w @urbanflet/web-conductor
```

- **build**: `tsc -b` (type-check estricto) + `vite build`.
- **lint**: ESLint con la config compartida en `eslint.config.js` (raíz del repo) — mismo set de reglas que web-pasajero/web-interno/shared-ui.
- **test**: Vitest + React Testing Library (config en el bloque `test` de `vite.config.ts`).

Los 3 deben quedar en verde antes de considerar cerrado un cambio.

## Tests

`src/App.test.tsx` es una red de seguridad, **no cobertura completa** — cubre los flujos ya verificados manualmente en navegador real:

- Iniciar/terminar turno (CU-O07).
- Aceptar/rechazar oferta (CU-O06).

Decisiones de la infraestructura de test, por si se extiende:

- **`DriverMap` se mockea** (`vi.mock("./DriverMap")`): mismo motivo que `RideMap` en web-pasajero — Leaflet no funciona bien en jsdom, y el mapa ya se verificó visualmente.
- **`fetch` se mockea por rutas** (`mockFetch` en el test), con defaults silenciosos para las llamadas de fondo (reporte de posición periódico, poll de oferta cuando el test no lo declara explícitamente).
- **Login se simula con un JWT falso** en `localStorage`, igual que en web-pasajero.
- A diferencia de web-pasajero, **esta app no usa WebSocket todavía** (ver comentario en `App.tsx`: "sin WebSocket del lado del conductor"), así que `setupTests.ts` no necesita un stub para eso.
