# Plan técnico (retroactivo): Operaciones y Despacho

## Backend

- `backend/src/viajes/`: `router_trips.py` (solicitar, historial, estimación de ruta),
  `router_dispatch.py` (auto-despacho, ofertas), `router_ejecucion.py` (transiciones de estado,
  traza, recálculo de ruta), `router_finalizacion.py` (finalizar, calificar), `router_publico.py`
  (vista pública de compartir viaje) — separados por responsabilidad, no un único router monolítico.
- `service_dispatch.py`: auto-despacho por radios crecientes, con `RADIOS_M`/
  `OFERTA_EXPIRA_SEGUNDOS` leídos en caliente de `configuracion.service` (no constantes fijas).
- `service_ejecucion.py`: `registrar_punto_traza` acumula la traza GPS punto a punto; `TRAZA_MAX_PUNTOS`
  acota el crecimiento del documento.
- `service_historial.py`: `simplificar_traza` — muestreo uniforme que conserva siempre primer y
  último punto, nunca interpola.
- `service_compartir.py`: token de 256 bits (`secrets.token_urlsafe(32)`), rate limiting de 20
  fallos/15min por IP, 404 genérico sin distinguir causa (mismo criterio anti-enumeración que el
  login).
- Colecciones: `viajes` (documento único por viaje con toda su vida), `pagos`.

## Frontend

- `apps/web-pasajero/src/App.tsx` (`RideMap`, `PanelSolicitar`, `PanelViajeActivo`,
  `CalificarConductorForm`, `VistaCompartida`).
- `apps/web-conductor/src/App.tsx` (`DriverMap`, `PantallaTurno`, flujo de ejecución,
  `ReportarFallaForm`).
- `apps/shared-ui/src/components/MapaRutaViaje.tsx` — mapa del historial (traza real / sin traza /
  sin destino), compartido por los 3 portales.
- `apps/shared-ui/src/components/MapOverlayCard.tsx` — el panel flotante sobre el mapa persistente,
  ancla abajo-izquierda (RN-DES-001).

## Decisión de arquitectura: por qué la calificación vive dentro del mismo overlay que "Tu viaje"

Corrección real reciente: la tarjeta de calificación vivía como bloque separado debajo del mapa,
compitiendo por altura en el mismo contenedor flex que el mapa (`flex:1`) — lo que lo achicaba
visualmente y la dejaba centrada en vez de alineada con el resto del overlay. Se movió dentro del
mismo `MapOverlayCard` que ya muestra el resumen del viaje finalizado, con el propio scroll interno
del overlay absorbiendo el alto extra.

## Decisión de arquitectura: por qué el mapa del historial nunca dibuja una ruta inventada

Antes de la corrección, el detalle de un viaje cerrado unía origen y destino con una línea recta
pasada como si fuera la ruta — indistinguible visualmente de una ruta real. Se reemplazó por
`MapaRutaViaje`, que solo dibuja la traza GPS real acumulada; sin traza, muestra únicamente los 2
marcadores con una nota explícita de que no hay dato real.
