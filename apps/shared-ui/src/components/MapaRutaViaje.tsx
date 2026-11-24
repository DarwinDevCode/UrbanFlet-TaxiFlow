import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./MapaRutaViaje.css";
import { useEffect, useState } from "react";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";
import { estimarRuta } from "../api/rutas";

export interface PuntoMapa {
  lat: number;
  lon: number;
}

export interface MapaRutaViajeProps {
  /** Id real del viaje -- se usa solo para reconocer los viajes sembrados del
   * dataset histórico NYC (ver `esViajeHistoricoNyc` más abajo), nunca se
   * muestra. */
  viajeId: string;
  origen: PuntoMapa | null;
  destino: PuntoMapa | null;
  /** Traza GPS REAL del viaje (`ViajeOut.traza`), tal como la acumuló el
   * backend punto a punto durante el recorrido. `null`/vacío cuando el viaje
   * nunca la acumuló -- en ese caso, si además es un viaje real (no del
   * dataset histórico) con origen y destino válidos, se calcula una ruta de
   * respaldo (ver `rutaCalculada` abajo); si no, no se dibuja ninguna línea. */
  traza?: [number, number][] | null;
  origenDireccion?: string | null;
  destinoDireccion?: string | null;
  alto?: number;
}

// Los ~1.3M viajes sembrados desde el dataset histórico NYC 2021 (ver
// `analytics/scripts/seed_viajes_nyc.py`) usan `_id` con este prefijo
// (`f"viaje-nyc-{numero_fila:09d}"`) -- verificado contra Mongo antes de
// escribir esto, no asumido: los 1,334,748 documentos con este prefijo son
// exactamente los que trae la siembra (0 excepciones), y ninguno tiene traza
// real (se insertan con `"traza": []` a propósito, recalcular una ruta ahí no
// tiene sentido -- son coordenadas sintéticas anclas a Quevedo, no un
// recorrido real de 2021). Los viajes reales del sistema usan
// `str(uuid.uuid4())` como `_id` (`viajes/service.py::solicitar_viaje`),
// nunca este prefijo -- no hay colisión posible.
function esViajeHistoricoNyc(viajeId: string): boolean {
  return viajeId.startsWith("viaje-nyc-");
}

// Mismas medidas/formas que `puntoOrigenStyle`/`puntoDestinoStyle` de la
// franja de ruta de web-pasajero, un poco más grandes para que se lean sobre
// las tiles. Se usan divIcons y no el pin PNG de Leaflet a propósito: evita
// el parche de assets del bundler que RideMap necesita y, sobre todo, deja el
// mismo lenguaje visual del sistema en el mapa.
const iconoOrigen = L.divIcon({
  className: "",
  html: '<div class="uf-marcador-ruta uf-marcador-ruta--origen" style="width:16px;height:16px"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const iconoDestino = L.divIcon({
  className: "",
  html: '<div class="uf-marcador-ruta uf-marcador-ruta--destino" style="width:14px;height:14px"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

/** Encuadra el mapa sobre todo lo que hay que mostrar. Sin esto, un viaje
 * cuyo destino queda fuera del zoom inicial mostraría solo el origen. */
function Encuadrar({ puntos }: { puntos: [number, number][] }) {
  const map = useMap();
  const clave = JSON.stringify(puntos[0]) + JSON.stringify(puntos[puntos.length - 1]) + puntos.length;
  useEffect(() => {
    if (puntos.length === 1) {
      map.setView(puntos[0], 15);
      return;
    }
    map.fitBounds(L.latLngBounds(puntos), { padding: [28, 28], maxZoom: 16 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave]);
  return null;
}

function Leyenda({ origen, destino }: { origen: string; destino: string | null }) {
  const texto = {
    fontSize: "var(--font-size-sm)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
    minWidth: 0,
  };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-1)", minWidth: 0 }}>
      <span
        aria-hidden="true"
        style={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          border: "2px solid var(--color-accent-deep)",
          background: "var(--color-surface)",
          flexShrink: 0,
        }}
      />
      <span style={{ ...texto, flex: "1 1 0" }}>{origen}</span>
      <span aria-hidden="true" style={{ flexShrink: 0, width: 18, borderTop: "2px dashed var(--color-accent-deep)" }} />
      <span style={{ ...texto, flex: "1 1 0", fontWeight: 600 }}>{destino ?? "Sin destino registrado"}</span>
      <span
        aria-hidden="true"
        style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--color-text)", flexShrink: 0 }}
      />
    </div>
  );
}

function EstadoSinDatos({ mensaje, alto }: { mensaje: string; alto: number }) {
  return (
    <div
      style={{
        height: alto,
        borderRadius: "var(--radius-md)",
        border: "1px dashed var(--color-border)",
        background: "var(--color-surface-muted, var(--color-surface))",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "var(--space-3)",
        color: "var(--color-text-muted)",
        fontSize: "var(--font-size-sm)",
      }}
    >
      {mensaje}
    </div>
  );
}

/**
 * Mapa de un viaje YA CERRADO, para el detalle del historial en los 3
 * portales (CU-O14 paso 3, "mapa con la ruta recorrida"). De solo lectura:
 * sin clics de "elegir destino", sin control de geolocalización, sin
 * seguimiento en vivo -- eso es `RideMap`/`DriverMap`, que siguen siendo los
 * mapas del viaje en curso.
 *
 * Regla de honestidad del dato, que es lo que gobierna todo este componente:
 * la línea que se dibuja siempre declara qué es. La traza GPS real (cuando
 * existe) se pinta sólida y se etiqueta como "recorrido real". Cuando un
 * viaje REAL (no del dataset histórico NYC) se quedó sin traza -- ej. un
 * problema de permisos durante la prueba, no porque el viaje no haya
 * ocurrido -- se calcula una ruta de respaldo con el mismo motor que ya usa
 * el flujo de solicitud (`estimarRuta`, sobre calles reales vía Directions)
 * y se dibuja con un estilo deliberadamente distinto (punteada, tono más
 * claro) más una nota que aclara que es una ruta calculada, no el recorrido
 * efectivo. Para los viajes del dataset histórico (recalcular una ruta ahí
 * no tiene sentido real, ver `esViajeHistoricoNyc`) y para cualquier viaje
 * sin destino, se mantiene el criterio anterior: solo los marcadores, sin
 * ninguna línea, con la nota explicando por qué.
 */
export function MapaRutaViaje({
  viajeId,
  origen,
  destino,
  traza = null,
  origenDireccion = null,
  destinoDireccion = null,
  alto = 280,
}: MapaRutaViajeProps) {
  const trazaValida = traza && traza.length > 1 ? traza : null;
  const necesitaCalculo = !trazaValida && Boolean(origen) && Boolean(destino) && !esViajeHistoricoNyc(viajeId);

  const [rutaCalculada, setRutaCalculada] = useState<[number, number][] | null>(null);

  useEffect(() => {
    if (!necesitaCalculo || !origen || !destino) {
      setRutaCalculada(null);
      return;
    }
    let cancelado = false;
    setRutaCalculada(null);
    estimarRuta({ lat: origen.lat, lon: origen.lon }, { lat: destino.lat, lon: destino.lon }).then((r) => {
      if (!cancelado) setRutaCalculada(r.ruta);
    });
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [necesitaCalculo, origen?.lat, origen?.lon, destino?.lat, destino?.lon]);

  if (!origen) {
    return (
      <EstadoSinDatos
        alto={alto}
        mensaje="Este viaje no tiene datos de ubicación registrados, así que no se puede mostrar en el mapa."
      />
    );
  }

  const puntos: [number, number][] = trazaValida ? [...trazaValida] : [[origen.lat, origen.lon]];
  if (!trazaValida) {
    if (destino) puntos.push([destino.lat, destino.lon]);
  } else {
    puntos.unshift([origen.lat, origen.lon]);
    if (destino) puntos.push([destino.lat, destino.lon]);
  }

  const nota = trazaValida
    ? `Recorrido real del vehículo según su traza GPS (${trazaValida.length} ${
        trazaValida.length === 1 ? "punto registrado" : "puntos registrados"
      }).`
    : necesitaCalculo
      ? "Este viaje no dejó traza GPS real — se muestra la ruta calculada entre origen y destino, no el recorrido efectivamente realizado."
      : destino
        ? "Este viaje no dejó traza GPS, así que se muestran solo el punto de recogida y el destino: no hay dato real de por dónde circuló el vehículo, y no se dibuja una ruta inventada."
        : "Este viaje no registró destino ni traza GPS: se muestra solo el punto de recogida.";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <div style={{ height: alto, borderRadius: "var(--radius-md)", overflow: "hidden" }}>
        <MapContainer
          center={[origen.lat, origen.lon]}
          zoom={15}
          style={{ height: "100%", width: "100%" }}
          scrollWheelZoom={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Encuadrar puntos={puntos} />
          {trazaValida && (
            <Polyline positions={trazaValida} pathOptions={{ className: "uf-traza-viaje", weight: 4, opacity: 0.9 }} />
          )}
          {!trazaValida && rutaCalculada && rutaCalculada.length > 1 && (
            <Polyline
              positions={rutaCalculada}
              pathOptions={{ className: "uf-ruta-calculada", weight: 4, opacity: 0.85, dashArray: "2 10" }}
            />
          )}
          <Marker position={[origen.lat, origen.lon]} icon={iconoOrigen} title="Punto de recogida" />
          {destino && <Marker position={[destino.lat, destino.lon]} icon={iconoDestino} title="Destino" />}
        </MapContainer>
      </div>
      <Leyenda origen={origenDireccion ?? "Origen"} destino={destinoDireccion} />
      <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "var(--font-size-xs)" }}>{nota}</p>
    </div>
  );
}
