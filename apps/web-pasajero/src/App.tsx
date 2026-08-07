import {
  AjustesPropios,
  ApiError,
  AppShell,
  Badge,
  Button,
  Card,
  CentroAyuda,
  DataTable,
  DetailField,
  DetailPanel,
  NotificacionesBell,
  PerfilPropio,
  Select,
  TextArea,
  TextField,
  apiFetch,
  getApiBaseUrl,
  tokenStorage,
  useAuth,
  type PreguntaFrecuente,
} from "@urbanflet/shared-ui";
import { useEffect, useState, type CSSProperties } from "react";
import { ALTO_MAPA, RideMap } from "./RideMap";
import { estimarRuta, geocodificarInverso } from "./rutas";

const VERSION_CONSENTIMIENTO = "v1-2026-07";

const TELEFONO_VALIDO = /^\+\d{7,15}$/;
const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function LoginCard() {
  const { registrar, login } = useAuth();
  const [modo, setModo] = useState<"login" | "registro">("login");
  const [tipoIdentificador, setTipoIdentificador] = useState<"telefono" | "email">("telefono");
  const [nombre, setNombre] = useState("");
  const [identificadorLogin, setIdentificadorLogin] = useState("");
  const [identificadorRegistro, setIdentificadorRegistro] = useState("");
  const [password, setPassword] = useState("");
  const [aceptaConsentimiento, setAceptaConsentimiento] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const identificadorRegistroValido =
    tipoIdentificador === "telefono"
      ? TELEFONO_VALIDO.test(identificadorRegistro)
      : EMAIL_VALIDO.test(identificadorRegistro);

  const entrar = async () => {
    setError(null);
    setCargando(true);
    try {
      await login(identificadorLogin, password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo iniciar sesión");
    } finally {
      setCargando(false);
    }
  };

  const crearCuenta = async () => {
    setError(null);
    setCargando(true);
    try {
      await registrar({
        nombre,
        telefono: tipoIdentificador === "telefono" ? identificadorRegistro : undefined,
        email: tipoIdentificador === "email" ? identificadorRegistro : undefined,
        password,
        versionConsentimiento: VERSION_CONSENTIMIENTO,
      });
      // La cuenta queda ACTIVA de inmediato (no hay paso de verificación
      // externo) — se entra directo con las mismas credenciales recién
      // creadas en vez de pedírselas de nuevo.
      await login(identificadorRegistro, password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear la cuenta");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-4)" }}>
        {modo === "login" ? "Ingresa a tu cuenta" : "Crea tu cuenta"}
      </h1>

      {modo === "login" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <TextField
            label="Teléfono o correo"
            value={identificadorLogin}
            onChange={(e) => setIdentificadorLogin(e.target.value)}
          />
          <TextField
            label="Contraseña"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
          <Button onClick={entrar} loading={cargando} disabled={!identificadorLogin || !password}>
            Entrar
          </Button>
          <button
            type="button"
            onClick={() => {
              setModo("registro");
              setError(null);
            }}
            style={{ background: "none", border: "none", color: "var(--color-accent)", cursor: "pointer" }}
          >
            ¿No tienes cuenta? Regístrate
          </button>
        </div>
      )}

      {modo === "registro" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />

          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button
              variant={tipoIdentificador === "telefono" ? "primary" : "secondary"}
              onClick={() => {
                setTipoIdentificador("telefono");
                setIdentificadorRegistro("");
              }}
            >
              Teléfono
            </Button>
            <Button
              variant={tipoIdentificador === "email" ? "primary" : "secondary"}
              onClick={() => {
                setTipoIdentificador("email");
                setIdentificadorRegistro("");
              }}
            >
              Correo
            </Button>
          </div>

          {tipoIdentificador === "telefono" ? (
            <TextField
              label="Teléfono"
              type="tel"
              placeholder="+593..."
              value={identificadorRegistro}
              onChange={(e) => setIdentificadorRegistro(e.target.value)}
            />
          ) : (
            <TextField
              label="Correo"
              type="email"
              placeholder="tu@correo.com"
              value={identificadorRegistro}
              onChange={(e) => setIdentificadorRegistro(e.target.value)}
            />
          )}
          {identificadorRegistro && !identificadorRegistroValido && (
            <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>
              {tipoIdentificador === "telefono" ? "Formato inválido, usa +código país" : "Correo inválido"}
            </span>
          )}

          <TextField
            label="Contraseña (mínimo 8 caracteres)"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <label
            style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)", alignItems: "flex-start" }}
          >
            <input
              type="checkbox"
              checked={aceptaConsentimiento}
              onChange={(e) => setAceptaConsentimiento(e.target.checked)}
            />
            Acepto los términos y la política de tratamiento de datos de la cooperativa.
          </label>
          {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
          <Button
            onClick={crearCuenta}
            loading={cargando}
            disabled={
              !nombre || !identificadorRegistroValido || password.length < 8 || !aceptaConsentimiento
            }
          >
            Crear cuenta
          </Button>
          <button
            type="button"
            onClick={() => {
              setModo("login");
              setError(null);
            }}
            style={{ background: "none", border: "none", color: "var(--color-accent)", cursor: "pointer" }}
          >
            Ya tengo cuenta
          </button>
        </div>
      )}
    </Card>
  );
}

type EstadoViaje =
  | "PROGRAMADO"
  | "SOLICITADO"
  | "OFERTADO"
  | "ASIGNADO"
  | "EN_CAMINO"
  | "EN_CURSO"
  | "FINALIZADO"
  | "PAGADO"
  | "CANCELADO"
  | "SIN_CONDUCTOR";

interface DireccionFavorita {
  id: string;
  etiqueta: "Casa" | "Trabajo" | "Otro";
  direccion: string;
  lat: number;
  lon: number;
}

interface Viaje {
  id: string;
  estado: EstadoViaje;
  conductor_id: string | null;
  origen_lat: number;
  origen_lon: number;
  origen_direccion: string;
  destino_lat: number | null;
  destino_lon: number | null;
  destino_direccion: string | null;
  tarifa_estimada: number | null;
  tarifa_final: number | null;
  conductor_nombre: string | null;
  conductor_calificacion: number | null;
  vehiculo_placa: string | null;
  vehiculo_marca: string | null;
  vehiculo_color: string | null;
  ts_solicitud: string;
  ts_programado: string | null;
  ts_llegada_origen: string | null;
  calificacion_pasajero_a_conductor: { puntaje: number } | null;
}

// CU-O05: el conductor está "asignado y localizable" en estos tres estados —
// mismo conjunto que ESTADOS_VIAJE_CON_CONDUCTOR_VISIBLE del backend
// (backend/src/flota/service.py), que es lo que autoriza GET
// /flota/posicion/{conductor_id} para el pasajero de este viaje.
const ESTADOS_CON_CONDUCTOR_LOCALIZABLE: EstadoViaje[] = ["ASIGNADO", "EN_CAMINO", "EN_CURSO"];
// CU-O05: mientras se busca conductor, mostramos un indicador de tiempo
// transcurrido sobre el propio mapa (no una pantalla aparte).
const ESTADOS_BUSCANDO_CONDUCTOR: EstadoViaje[] = ["SOLICITADO", "OFERTADO"];

const ESTADO_TONO: Record<EstadoViaje, "neutral" | "exito" | "advertencia" | "peligro"> = {
  PROGRAMADO: "neutral",
  SOLICITADO: "neutral",
  OFERTADO: "advertencia",
  ASIGNADO: "exito",
  EN_CAMINO: "exito",
  EN_CURSO: "exito",
  FINALIZADO: "exito",
  PAGADO: "exito",
  CANCELADO: "peligro",
  SIN_CONDUCTOR: "peligro",
};

const ESTADO_TEXTO: Record<EstadoViaje, string> = {
  PROGRAMADO: "Viaje programado",
  SOLICITADO: "Buscando conductor…",
  OFERTADO: "Ofrecido a un conductor…",
  ASIGNADO: "Conductor asignado",
  EN_CAMINO: "El conductor va en camino",
  EN_CURSO: "Viaje en curso",
  FINALIZADO: "Viaje finalizado",
  PAGADO: "Viaje pagado",
  CANCELADO: "Viaje cancelado",
  SIN_CONDUCTOR: "No se encontró conductor disponible",
};

// Aproximación cliente de la franja horaria (mismos límites por defecto que
// core/config.py:franja_diurna_desde_hora/hasta_hora en el backend) — solo
// para que la vista previa de tarifa en el cliente sea razonable, la franja
// real que se cobra la resuelve el servidor con su propia zona horaria de
// operación al crear el viaje.
function resolverFranjaAproximada(): "DIURNA" | "NOCTURNA" {
  const hora = new Date().getHours();
  return hora >= 5 && hora < 22 ? "DIURNA" : "NOCTURNA";
}

// Sección 1.5: mismo margen mínimo que MARGEN_MINIMO_PROGRAMACION_MINUTOS
// en backend/src/viajes/service.py -- solo para fijar el `min` del input de
// fecha/hora en el cliente (evita que el usuario elija algo que el backend
// va a rechazar de todos modos); la validación real sigue siendo del
// servidor. Formato "YYYY-MM-DDTHH:mm" en hora LOCAL, el que espera
// <input type="datetime-local">.
function minimoProgramacionLocal(): string {
  const fecha = new Date(Date.now() + 15 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${fecha.getFullYear()}-${pad(fecha.getMonth() + 1)}-${pad(fecha.getDate())}T${pad(fecha.getHours())}:${pad(fecha.getMinutes())}`;
}

interface TarifaVigente {
  arrancada: number;
  costo_km: number;
  carrera_minima: number;
}

// Panel flotante que se superpone al mapa (nunca lo reemplaza) — usado tanto
// para "¿A dónde vamos?" como para el estado del viaje activo. Se ancla
// abajo del mapa para no tapar los controles propios de Leaflet (zoom
// arriba-izquierda, "ir a mi ubicación" arriba-derecha).
// Compacto a propósito: el mapa es el elemento principal de la pantalla, el
// panel es un overlay que se le agrega encima, no una segunda pantalla que
// lo tapa. Ancho acotado (no left+right = todo el ancho) y alto reducido —
// corregido tras hallazgo en pruebas reales: la versión anterior llegaba a
// cubrir ~87% del alto del mapa (420px de 480px totales).
const overlayPanelStyle: CSSProperties = {
  position: "absolute",
  left: "var(--space-3)",
  bottom: "var(--space-3)",
  width: "min(340px, calc(100% - 2 * var(--space-3)))",
  maxHeight: "min(45%, 260px)",
  overflowY: "auto",
  zIndex: 500,
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-md)",
  boxShadow: "0 4px 16px rgba(0, 0, 0, 0.28)",
  padding: "var(--space-3)",
};

interface PanelSolicitarProps {
  origenLat: number | null;
  origenLon: number | null;
  ubicando: boolean;
  errorUbicacion: string | null;
  solicitarUbicacion: () => void;
  origenDireccion: string;
  setOrigenDireccion: (v: string) => void;
  destinoLat: number | null;
  destinoDireccion: string;
  setDestinoDireccion: (v: string) => void;
  geocodificando: boolean;
  estimacion: { distanciaKm: number; duracionMin: number } | null;
  tarifaEstimadaCliente: number | null;
  errorSolicitar: string | null;
  viajeActivoExistente: boolean;
  cargando: boolean;
  solicitar: () => void;
  favoritas: DireccionFavorita[];
  onSeleccionarFavorita: (fav: DireccionFavorita) => void;
  onGuardarFavorita: (etiqueta: DireccionFavorita["etiqueta"]) => void;
  guardandoFavorita: boolean;
  // Sección 1.5 de ux_complementaria.md: "Ahora" (comportamiento de
  // siempre) vs. "Programar" (hora futura, valor crudo de un
  // <input type="datetime-local">, en hora LOCAL del navegador -- se
  // convierte a ISO/UTC recién al enviar, ver `solicitar()`).
  modo: "ahora" | "programar";
  setModo: (v: "ahora" | "programar") => void;
  tsProgramadoLocal: string;
  setTsProgramadoLocal: (v: string) => void;
}

// Contenido del panel "¿A dónde vamos?" — el mapa en sí (con el marcador de
// origen, el click para elegir destino y los taxis anónimos cercanos) ahora
// vive en el componente padre (VistaViaje), que lo mantiene montado también
// mientras el viaje ya está en curso; este panel solo aporta los controles
// que van flotando encima.
function PanelSolicitar({
  origenLat,
  origenLon,
  ubicando,
  errorUbicacion,
  solicitarUbicacion,
  origenDireccion,
  setOrigenDireccion,
  destinoLat,
  destinoDireccion,
  setDestinoDireccion,
  geocodificando,
  estimacion,
  tarifaEstimadaCliente,
  errorSolicitar,
  viajeActivoExistente,
  cargando,
  solicitar,
  favoritas,
  onSeleccionarFavorita,
  onGuardarFavorita,
  guardandoFavorita,
  modo,
  setModo,
  tsProgramadoLocal,
  setTsProgramadoLocal,
}: PanelSolicitarProps) {
  const [mostrandoGuardar, setMostrandoGuardar] = useState(false);
  const [etiquetaNueva, setEtiquetaNueva] = useState<DireccionFavorita["etiqueta"]>("Otro");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0 }}>¿A dónde vamos?</h1>
      {origenLat !== null && origenLon !== null ? (
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
          Origen: {origenLat.toFixed(5)}, {origenLon.toFixed(5)} — toca el mapa para elegir tu destino.
        </p>
      ) : (
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
          {ubicando ? "Centrando el mapa en tu ubicación…" : "No se pudo centrar el mapa en tu ubicación."}
        </p>
      )}
      {/* CU-O04 A2: reintento explícito solo cuando el permiso quedó
          denegado o falló — no es el mecanismo normal para ver el mapa. */}
      {origenLat === null && !ubicando && (
        <Button variant="secondary" onClick={solicitarUbicacion}>
          Reintentar ubicación
        </Button>
      )}
      <TextField
        label="Referencia de origen (opcional)"
        value={origenDireccion}
        onChange={(e) => setOrigenDireccion(e.target.value)}
      />
      {favoritas.length > 0 && (
        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
          {favoritas.map((fav) => (
            <button
              key={fav.id}
              type="button"
              onClick={() => onSeleccionarFavorita(fav)}
              title={fav.direccion}
              style={{
                border: "1px solid var(--color-border)",
                background: "var(--color-surface)",
                color: "var(--color-text)",
                borderRadius: "999px",
                padding: "4px 12px",
                fontSize: "var(--font-size-sm)",
                cursor: "pointer",
              }}
            >
              {fav.etiqueta}
            </button>
          ))}
        </div>
      )}
      <TextField
        label="Destino"
        value={geocodificando ? "Buscando dirección…" : destinoDireccion}
        onChange={(e) => setDestinoDireccion(e.target.value)}
        placeholder={destinoLat === null ? "Toca el mapa para elegir un destino" : undefined}
      />
      {destinoLat !== null && !geocodificando && (
        <div>
          {!mostrandoGuardar ? (
            <Button variant="secondary" onClick={() => setMostrandoGuardar(true)}>
              ☆ Guardar como favorita
            </Button>
          ) : (
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end", flexWrap: "wrap" }}>
              <div style={{ minWidth: 140 }}>
                <Select
                  label="Etiqueta"
                  value={etiquetaNueva}
                  onChange={(e) => setEtiquetaNueva(e.target.value as DireccionFavorita["etiqueta"])}
                  options={[
                    { value: "Casa", label: "Casa" },
                    { value: "Trabajo", label: "Trabajo" },
                    { value: "Otro", label: "Otro" },
                  ]}
                />
              </div>
              <div style={{ minWidth: 100 }}>
                <Button
                  variant="secondary"
                  loading={guardandoFavorita}
                  onClick={() => {
                    onGuardarFavorita(etiquetaNueva);
                    setMostrandoGuardar(false);
                  }}
                >
                  Guardar
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      {estimacion && (
        <div
          style={{
            background: "var(--color-bg)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          <p style={{ margin: 0 }}>Distancia estimada: {estimacion.distanciaKm.toFixed(1)} km</p>
          <p style={{ margin: 0 }}>Duración estimada: {Math.round(estimacion.duracionMin)} min</p>
          {tarifaEstimadaCliente !== null && (
            <p style={{ margin: 0, fontWeight: 600 }}>
              Tarifa estimada: ${tarifaEstimadaCliente.toFixed(2)} (aproximada, se confirma al solicitar)
            </p>
          )}
        </div>
      )}
      {(errorUbicacion || errorSolicitar) && (
        <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>
          {errorSolicitar ?? errorUbicacion}
        </span>
      )}
      {viajeActivoExistente && (
        <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Ya tenías un viaje en curso — te llevamos a él.
        </span>
      )}
      {/* Sección 1.5 de ux_complementaria.md: "Ahora" vs. "Programar" —
          nueva opción en el flujo de solicitud, junto al botón final. */}
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Button
          variant={modo === "ahora" ? "primary" : "secondary"}
          onClick={() => setModo("ahora")}
          style={{ width: "auto", flex: 1 }}
        >
          Ahora
        </Button>
        <Button
          variant={modo === "programar" ? "primary" : "secondary"}
          onClick={() => setModo("programar")}
          style={{ width: "auto", flex: 1 }}
        >
          Programar
        </Button>
      </div>
      {modo === "programar" && (
        <TextField
          label="Fecha y hora"
          type="datetime-local"
          value={tsProgramadoLocal}
          min={minimoProgramacionLocal()}
          onChange={(e) => setTsProgramadoLocal(e.target.value)}
        />
      )}
      <Button
        onClick={solicitar}
        loading={cargando}
        disabled={origenLat === null || (modo === "programar" && !tsProgramadoLocal)}
      >
        {modo === "programar" ? "Programar viaje" : "Solicitar taxi"}
      </Button>
    </div>
  );
}

// CU-O04 A4: cancelar solo tiene sentido antes de que haya un conductor
// confirmado — coincide con ESTADOS_CANCELABLES_PASAJERO en el backend
// (backend/src/viajes/service.py). A partir de ASIGNADO es CU-O07 A2, fuera
// de alcance de este slice. PROGRAMADO (Sección 1.5) se agrega por el mismo
// motivo: con más razón es cancelable antes de disparar el despacho.
const ESTADOS_CANCELABLES_PASAJERO: EstadoViaje[] = ["PROGRAMADO", "SOLICITADO", "OFERTADO"];

// Contenido del panel del viaje activo — igual que PanelSolicitar, flota
// sobre el mapa persistente en vez de reemplazarlo. Además de lo que ya
// mostraba ViajeActivoCard, agrega el contador de tiempo buscando conductor
// (CU-O05) y un "Ver detalle" plegable para los datos del conductor asignado.
function PanelViajeActivo({
  viaje,
  onCancelado,
  elapsedSeconds,
  onReintentar,
}: {
  viaje: Viaje;
  onCancelado: () => void;
  elapsedSeconds: number;
  onReintentar: () => void;
}) {
  const [cancelando, setCancelando] = useState(false);
  const [errorCancelar, setErrorCancelar] = useState<string | null>(null);
  const [detalleAbierto, setDetalleAbierto] = useState(false);
  const [reintentando, setReintentando] = useState(false);
  const [errorReintentar, setErrorReintentar] = useState<string | null>(null);
  const [compartiendo, setCompartiendo] = useState(false);
  const [errorCompartir, setErrorCompartir] = useState<string | null>(null);
  const [enlaceCompartir, setEnlaceCompartir] = useState<string | null>(null);
  const [enlaceCopiado, setEnlaceCopiado] = useState(false);

  const compartir = async () => {
    setErrorCompartir(null);
    setCompartiendo(true);
    try {
      const { token } = await apiFetch<{ token: string }>("/viajes/activo/compartir", { method: "POST" });
      setEnlaceCompartir(`${window.location.origin}/compartido/${token}`);
      setEnlaceCopiado(false);
    } catch (e) {
      setErrorCompartir(e instanceof ApiError ? e.message : "No se pudo generar el enlace para compartir");
    } finally {
      setCompartiendo(false);
    }
  };

  const copiarEnlace = async () => {
    if (!enlaceCompartir) return;
    try {
      await navigator.clipboard.writeText(enlaceCompartir);
      setEnlaceCopiado(true);
    } catch {
      // Sin permiso de portapapeles: el enlace ya está visible en el campo
      // de texto de abajo para copiar a mano, no bloquea nada.
    }
  };

  const reintentar = async () => {
    setErrorReintentar(null);
    setReintentando(true);
    try {
      await onReintentar();
    } catch (e) {
      setErrorReintentar(e instanceof ApiError ? e.message : "No se pudo reintentar la búsqueda");
    } finally {
      setReintentando(false);
    }
  };

  const texto =
    viaje.estado === "EN_CAMINO" && viaje.ts_llegada_origen
      ? "El conductor te está esperando"
      : ESTADO_TEXTO[viaje.estado];

  const buscandoConductor = ESTADOS_BUSCANDO_CONDUCTOR.includes(viaje.estado);

  const cancelar = async () => {
    setErrorCancelar(null);
    setCancelando(true);
    try {
      await apiFetch("/viajes/activo/cancelar", { method: "POST" });
      onCancelado();
    } catch (e) {
      // Caso borde explícito (CU-O04 A4): el conductor se asignó justo
      // cuando el pasajero pulsó cancelar — el servidor rechaza y se lo
      // mostramos en vez de romper la UI.
      setErrorCancelar(e instanceof ApiError ? e.message : "No se pudo cancelar el viaje");
    } finally {
      setCancelando(false);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>Tu viaje</h1>
      <div style={{ marginBottom: "var(--space-2)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <Badge texto={texto} tono={ESTADO_TONO[viaje.estado]} />
        {/* CU-O05: indicador de tiempo transcurrido buscando conductor,
            sobre el propio mapa — no una pantalla aparte. */}
        {buscandoConductor && (
          <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            {elapsedSeconds}s buscando…
          </span>
        )}
      </div>
      {/* Sección 1.5 de ux_complementaria.md: mientras PROGRAMADO, la hora
          pedida es el dato más relevante del panel -- el auto-despacho
          todavía no arrancó. */}
      {viaje.estado === "PROGRAMADO" && viaje.ts_programado && (
        <p style={{ margin: "var(--space-1) 0" }}>
          Programado para: {new Date(viaje.ts_programado).toLocaleString()}
        </p>
      )}
      <p style={{ color: "var(--color-text-muted)", margin: "var(--space-1) 0" }}>Origen: {viaje.origen_direccion}</p>
      {viaje.destino_direccion && (
        <p style={{ color: "var(--color-text-muted)", margin: "var(--space-1) 0" }}>Destino: {viaje.destino_direccion}</p>
      )}
      {viaje.estado === "FINALIZADO" && viaje.tarifa_final !== null ? (
        <p style={{ margin: "var(--space-1) 0" }}>Tarifa final: ${viaje.tarifa_final.toFixed(2)}</p>
      ) : (
        viaje.tarifa_estimada !== null && (
          <p style={{ margin: "var(--space-1) 0" }}>Tarifa estimada: ${viaje.tarifa_estimada.toFixed(2)}</p>
        )
      )}
      {viaje.conductor_nombre && (
        <div style={{ margin: "var(--space-1) 0" }}>
          <button
            type="button"
            onClick={() => setDetalleAbierto((v) => !v)}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              color: "var(--color-accent)",
              cursor: "pointer",
              fontSize: "var(--font-size-sm)",
            }}
          >
            {detalleAbierto ? "Ocultar detalle del conductor ▲" : "Ver detalle del conductor ▼"}
          </button>
          {detalleAbierto && (
            <div style={{ marginTop: "var(--space-1)" }}>
              <p style={{ margin: 0 }}>Conductor: {viaje.conductor_nombre}</p>
              {viaje.conductor_calificacion !== null && (
                <p style={{ margin: 0 }}>Calificación: {viaje.conductor_calificacion.toFixed(1)}★</p>
              )}
              {viaje.vehiculo_placa && <p style={{ margin: 0 }}>Placa: {viaje.vehiculo_placa}</p>}
              {(viaje.vehiculo_marca || viaje.vehiculo_color) && (
                <p style={{ margin: 0 }}>
                  Vehículo: {viaje.vehiculo_marca ?? "—"} · {viaje.vehiculo_color ?? "—"}
                </p>
              )}
            </div>
          )}
        </div>
      )}
      {/* Sección 1.2 de ux_complementaria.md: solo tiene sentido compartir
          mientras el vehículo se mueve — antes de EN_CAMINO no hay nada que
          seguir en vivo, y después de EN_CURSO el viaje ya terminó. */}
      {(viaje.estado === "EN_CAMINO" || viaje.estado === "EN_CURSO") && (
        <div style={{ margin: "var(--space-2) 0" }}>
          {errorCompartir && (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{errorCompartir}</p>
          )}
          {enlaceCompartir ? (
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end", flexWrap: "wrap" }}>
              <TextField label="Enlace para compartir" value={enlaceCompartir} readOnly onChange={() => {}} />
              <Button variant="secondary" onClick={copiarEnlace}>
                {enlaceCopiado ? "¡Copiado!" : "Copiar enlace"}
              </Button>
            </div>
          ) : (
            <Button variant="secondary" onClick={compartir} loading={compartiendo}>
              Compartir viaje
            </Button>
          )}
        </div>
      )}
      {ESTADOS_CANCELABLES_PASAJERO.includes(viaje.estado) && (
        <div style={{ marginTop: "var(--space-3)" }}>
          {errorCancelar && (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{errorCancelar}</p>
          )}
          <Button variant="danger" onClick={cancelar} loading={cancelando}>
            Cancelar solicitud
          </Button>
        </div>
      )}
      {/* CU-O05 A3: se agotaron todos los radios de despacho sin encontrar
          conductor — en vez de dejar al pasajero varado en este estado, se
          le ofrece reintentar con una nueva solicitud que reusa el mismo
          origen/destino. SIN_CONDUCTOR no es cancelable (no está en
          ESTADOS_CANCELABLES_PASAJERO), así que este botón vive aparte. */}
      {viaje.estado === "SIN_CONDUCTOR" && (
        <div style={{ marginTop: "var(--space-3)" }}>
          {errorReintentar && (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{errorReintentar}</p>
          )}
          <Button onClick={reintentar} loading={reintentando}>
            Reintentar búsqueda
          </Button>
        </div>
      )}
    </div>
  );
}

interface PosicionConductor {
  lat: number;
  lon: number;
  ts_servidor: string;
}

// Dueño del mapa persistente de la pestaña "Viaje": el mapa se monta una
// sola vez aquí y se mantiene montado sin importar si el pasajero todavía
// está eligiendo destino o ya tiene un viaje en curso — todo lo demás
// (formulario de solicitud, estado del viaje, calificación) se dibuja como
// panel flotante encima o, en el caso de la calificación, debajo, pero nunca
// desmontando el mapa. Solo cambiar a la pestaña "Mis viajes" desmonta este
// árbol (decisión explícita de navegación, fuera de alcance de este slice).
function VistaViaje({ viaje, setViaje }: { viaje: Viaje | null; setViaje: (v: Viaje | null) => void }) {
  const [origenLat, setOrigenLat] = useState<number | null>(null);
  const [origenLon, setOrigenLon] = useState<number | null>(null);
  const [ubicando, setUbicando] = useState(false);
  const [errorUbicacion, setErrorUbicacion] = useState<string | null>(null);

  const [origenDireccion, setOrigenDireccion] = useState("");
  const [destinoLat, setDestinoLat] = useState<number | null>(null);
  const [destinoLon, setDestinoLon] = useState<number | null>(null);
  const [destinoDireccion, setDestinoDireccion] = useState("");
  const [geocodificando, setGeocodificando] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [errorSolicitar, setErrorSolicitar] = useState<string | null>(null);
  const [cercanos, setCercanos] = useState<{ lat: number; lon: number }[]>([]);
  const [ruta, setRuta] = useState<[number, number][] | null>(null);
  const [estimacion, setEstimacion] = useState<{ distanciaKm: number; duracionMin: number } | null>(null);
  const [tarifaVigente, setTarifaVigente] = useState<TarifaVigente | null>(null);
  const [viajeActivoExistente, setViajeActivoExistente] = useState<Viaje | null>(null);
  const [conductorPos, setConductorPos] = useState<{ lat: number; lon: number } | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [favoritas, setFavoritas] = useState<DireccionFavorita[]>([]);
  // Sección 1.5 de ux_complementaria.md: "Ahora" vs. "Programar".
  const [modoSolicitud, setModoSolicitud] = useState<"ahora" | "programar">("ahora");
  const [tsProgramadoLocal, setTsProgramadoLocal] = useState("");

  // Se reinicia a los valores por defecto cada vez que no hay un viaje en
  // curso (cubre los 4 puntos donde el viaje vuelve a null: cancelar,
  // calificar, SIN_CONDUCTOR resuelto, error de refresco) sin tener que
  // tocar cada uno de esos call sites por separado.
  useEffect(() => {
    if (viaje === null) {
      setModoSolicitud("ahora");
      setTsProgramadoLocal("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viaje === null]);

  // Sección 1.1 de ux_complementaria.md: accesos rápidos sobre el buscador
  // de destino -- solo tiene sentido cargarlas mientras no hay un viaje ya
  // en curso (el destino ya está fijado en ese caso).
  useEffect(() => {
    if (viaje) return;
    apiFetch<DireccionFavorita[]>("/direcciones")
      .then(setFavoritas)
      .catch(() => setFavoritas([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viaje === null]);

  // CU-O04 paso 1: la ubicación se pide como parte de cargar esta pantalla,
  // no detrás de un botón — el mapa debe aparecer ya centrado apenas el
  // pasajero abre el portal. CU-O04 A2: mensaje accionable, no el error
  // crudo del navegador, para el caso en que el permiso se niegue.
  const solicitarUbicacion = () => {
    if (!("geolocation" in navigator)) {
      setErrorUbicacion("Este navegador no soporta geolocalización. Ingresa tu ubicación manualmente no está disponible aún.");
      return;
    }
    setErrorUbicacion(null);
    setUbicando(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOrigenLat(pos.coords.latitude);
        setOrigenLon(pos.coords.longitude);
        setUbicando(false);
      },
      (err) => {
        const mensaje =
          err.code === err.PERMISSION_DENIED
            ? "Activa el permiso de ubicación en tu navegador para continuar: usualmente está en el ícono de candado/información junto a la barra de direcciones → Permisos del sitio → Ubicación."
            : "No se pudo obtener tu ubicación — verifica que el GPS esté activado e inténtalo de nuevo.";
        setErrorUbicacion(mensaje);
        setUbicando(false);
      },
      { enableHighAccuracy: true },
    );
  };

  // Dispara el pedido de permiso/ubicación automáticamente al montar esta
  // pantalla (CU-O04 flujo principal paso 1) — solo tiene sentido mientras
  // no hay ya un viaje (el origen del mapa pasa a ser el del propio viaje).
  useEffect(() => {
    if (!viaje) solicitarUbicacion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Carga la tarifa vigente aproximada una sola vez, para poder mostrar una
  // vista previa de tarifa razonable antes de solicitar (CU-O04 P3). Si no
  // hay una tarifa vigente configurada, la vista previa simplemente no se
  // muestra — no bloquea el flujo.
  useEffect(() => {
    apiFetch<{ valores: TarifaVigente }>(
      `/parametros/vigente?tipo=tarifa&franja=${resolverFranjaAproximada()}`,
    )
      .then((r) => setTarifaVigente(r.valores))
      .catch(() => setTarifaVigente(null));
  }, []);

  // Taxis cercanos anónimos (CU-O04 P1) — solo tienen sentido mientras
  // todavía no hay un conductor asignado (eligiendo destino, o ya
  // solicitado/ofertado pero sin asignar): una vez ASIGNADO, el mapa muestra
  // al conductor real en vez de íconos anónimos (ver el efecto de abajo).
  useEffect(() => {
    if (viaje && !ESTADOS_BUSCANDO_CONDUCTOR.includes(viaje.estado)) {
      setCercanos([]);
      return;
    }
    const lat = viaje ? viaje.origen_lat : origenLat;
    const lon = viaje ? viaje.origen_lon : origenLon;
    if (lat === null || lon === null) return;
    let cancelado = false;
    const cargar = () => {
      apiFetch<{ lat: number; lon: number }[]>(`/flota/cercanos?lat=${lat}&lon=${lon}&radio_m=300`)
        .then((r) => {
          if (!cancelado) setCercanos(r);
        })
        .catch(() => {
          if (!cancelado) setCercanos([]);
        });
    };
    cargar();
    const id = setInterval(cargar, 15000);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
    // Deps deliberadamente acotadas a los campos usados en vez de `viaje`
    // completo — el objeto cambia de identidad en cada poll aunque estos
    // campos sigan iguales, y eso reiniciaría el timer sin necesidad.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viaje?.estado, viaje?.origen_lat, viaje?.origen_lon, origenLat, origenLon]);

  // Ruta + distancia/duración estimadas (CU-O04 P3) mientras se elige
  // destino, antes de solicitar — Directions API con fallback a línea recta.
  useEffect(() => {
    if (viaje) return;
    if (origenLat === null || origenLon === null || destinoLat === null || destinoLon === null) {
      setRuta(null);
      setEstimacion(null);
      return;
    }
    let cancelado = false;
    estimarRuta({ lat: origenLat, lon: origenLon }, { lat: destinoLat, lon: destinoLon }).then((r) => {
      if (cancelado) return;
      setRuta(r.ruta);
      setEstimacion({ distanciaKm: r.distanciaKm, duracionMin: r.duracionMin });
    });
    return () => {
      cancelado = true;
    };
  }, [viaje, origenLat, origenLon, destinoLat, destinoLon]);

  // Una vez que el viaje ya tiene destino fijado, la ruta se recalcula sobre
  // esas coordenadas fijas (origen/destino del propio viaje), no sobre el
  // estado local de "elegir destino" — así la línea sigue en el mapa
  // persistente durante todo el viaje.
  useEffect(() => {
    if (!viaje || viaje.destino_lat === null || viaje.destino_lon === null) return;
    let cancelado = false;
    estimarRuta(
      { lat: viaje.origen_lat, lon: viaje.origen_lon },
      { lat: viaje.destino_lat, lon: viaje.destino_lon },
    ).then((r) => {
      if (!cancelado) setRuta(r.ruta);
    });
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viaje?.id, viaje?.destino_lat, viaje?.destino_lon]);

  // Posición del conductor ya asignado (punto 3 de la tarea): se consulta el
  // endpoint dedicado GET /flota/posicion/{conductor_id} — no /flota/cercanos,
  // que es anónimo — con la misma cadencia de 15s que el resto de polling de
  // posiciones en este slice. Deja de pedirse fuera de
  // ASIGNADO/EN_CAMINO/EN_CURSO o si por algún motivo no hay conductor_id.
  useEffect(() => {
    if (!viaje || !viaje.conductor_id || !ESTADOS_CON_CONDUCTOR_LOCALIZABLE.includes(viaje.estado)) {
      setConductorPos(null);
      return;
    }
    let cancelado = false;
    const cargar = () => {
      apiFetch<PosicionConductor>(`/flota/posicion/${viaje.conductor_id}`)
        .then((r) => {
          if (!cancelado) setConductorPos({ lat: r.lat, lon: r.lon });
        })
        .catch(() => {
          if (!cancelado) setConductorPos(null);
        });
    };
    cargar();
    const id = setInterval(cargar, 15000);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
    // Deps acotadas al mismo criterio que el efecto de "cercanos" arriba.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viaje?.conductor_id, viaje?.estado]);

  // CU-O05: segundos transcurridos desde que se pidió el viaje, mientras
  // sigue en SOLICITADO/OFERTADO — se muestra sobre el mapa en
  // PanelViajeActivo, no en una pantalla aparte.
  useEffect(() => {
    if (!viaje || !ESTADOS_BUSCANDO_CONDUCTOR.includes(viaje.estado)) {
      setElapsedSeconds(0);
      return;
    }
    const inicioMs = new Date(viaje.ts_solicitud).getTime();
    const tick = () => setElapsedSeconds(Math.max(0, Math.floor((Date.now() - inicioMs) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viaje?.id, viaje?.estado, viaje?.ts_solicitud]);

  const manejarClickMapa = (lat: number, lon: number) => {
    if (viaje) return; // destino ya fijado por el viaje en curso, el mapa no acepta más clics (ver clicksHabilitados)
    setDestinoLat(lat);
    setDestinoLon(lon);
    setDestinoDireccion("");
    setGeocodificando(true);
    geocodificarInverso(lat, lon)
      .then((direccion) => {
        if (direccion) setDestinoDireccion(direccion);
      })
      .finally(() => setGeocodificando(false));
  };

  // Sección 1.1: un toque sobre una dirección favorita fija el destino
  // directo (sin geocodificación, ya viene con lat/lon guardados) -- mismo
  // resultado final que un clic en el mapa, sin tocar el mapa.
  const seleccionarFavorita = (fav: DireccionFavorita) => {
    if (viaje) return;
    setDestinoLat(fav.lat);
    setDestinoLon(fav.lon);
    setDestinoDireccion(fav.direccion);
  };

  const [guardandoFavorita, setGuardandoFavorita] = useState(false);

  const guardarFavorita = async (etiqueta: DireccionFavorita["etiqueta"]) => {
    if (destinoLat === null || destinoLon === null || !destinoDireccion) return;
    setGuardandoFavorita(true);
    try {
      const nueva = await apiFetch<DireccionFavorita>("/direcciones", {
        method: "POST",
        body: { etiqueta, direccion: destinoDireccion, lat: destinoLat, lon: destinoLon },
      });
      setFavoritas((prev) => [...prev, nueva]);
    } catch {
      /* silencioso -- no bloquea el flujo de solicitar el viaje */
    } finally {
      setGuardandoFavorita(false);
    }
  };

  const tarifaEstimadaCliente =
    tarifaVigente && estimacion
      ? Math.max(tarifaVigente.arrancada + tarifaVigente.costo_km * estimacion.distanciaKm, tarifaVigente.carrera_minima)
      : null;

  const solicitar = async () => {
    if (origenLat === null || origenLon === null) return;
    setErrorSolicitar(null);
    setCargando(true);
    try {
      const tieneDestino = destinoLat !== null && destinoLon !== null;
      const nuevoViaje = await apiFetch<Viaje>("/viajes", {
        method: "POST",
        body: {
          origen_lat: origenLat,
          origen_lon: origenLon,
          origen_direccion: origenDireccion || "Ubicación actual",
          ...(tieneDestino
            ? {
                destino_lat: destinoLat,
                destino_lon: destinoLon,
                destino_direccion: destinoDireccion || null,
              }
            : {}),
          ...(modoSolicitud === "programar" && tsProgramadoLocal
            ? { ts_programado: new Date(tsProgramadoLocal).toISOString() }
            : {}),
        },
      });
      setViaje(nuevoViaje);
    } catch (e) {
      // CU-O04 A3: en vez de dejar al usuario en un mensaje de error muerto,
      // si ya tiene un viaje activo se trae ese viaje y se muestra tal cual.
      if (e instanceof ApiError && e.code === "TRIP_ALREADY_ACTIVE") {
        try {
          // GET /viajes/activo responde 200 con cuerpo vacío (null) cuando no
          // hay viaje activo — ya no 404. Aquí ese caso es una carrera real
          // (el viaje se resolvió entre el POST y este GET); cae al mensaje
          // de error genérico en vez de mostrar una recuperación fantasma.
          const activo = await apiFetch<Viaje | null>("/viajes/activo");
          if (activo) {
            setViajeActivoExistente(activo);
            setViaje(activo);
            return;
          }
        } catch {
          // si tampoco se pudo traer el activo, cae al mensaje de error genérico abajo
        }
      }
      setErrorSolicitar(e instanceof ApiError ? e.message : "No se pudo solicitar el viaje");
    } finally {
      setCargando(false);
    }
  };

  // CU-O05 A3: reintento tras SIN_CONDUCTOR — reusa el origen/destino del
  // propio viaje agotado (no el estado local del formulario, que puede
  // haber cambiado o estar vacío) para pedir un viaje nuevo. Mismo manejo de
  // TRIP_ALREADY_ACTIVE que `solicitar` arriba, por si el viaje se resolvió
  // (p. ej. otro dispositivo) justo antes de este reintento.
  const reintentarBusqueda = async (viajeAgotado: Viaje) => {
    const tieneDestino = viajeAgotado.destino_lat !== null && viajeAgotado.destino_lon !== null;
    try {
      const nuevoViaje = await apiFetch<Viaje>("/viajes", {
        method: "POST",
        body: {
          origen_lat: viajeAgotado.origen_lat,
          origen_lon: viajeAgotado.origen_lon,
          origen_direccion: viajeAgotado.origen_direccion,
          ...(tieneDestino
            ? {
                destino_lat: viajeAgotado.destino_lat,
                destino_lon: viajeAgotado.destino_lon,
                destino_direccion: viajeAgotado.destino_direccion,
              }
            : {}),
        },
      });
      setViaje(nuevoViaje);
    } catch (e) {
      if (e instanceof ApiError && e.code === "TRIP_ALREADY_ACTIVE") {
        const activo = await apiFetch<Viaje | null>("/viajes/activo");
        if (activo) {
          setViaje(activo);
          return;
        }
      }
      throw e;
    }
  };

  const mapaOrigen = viaje
    ? { lat: viaje.origen_lat, lon: viaje.origen_lon }
    : origenLat !== null && origenLon !== null
      ? { lat: origenLat, lon: origenLon }
      : null;
  const mapaDestino = viaje
    ? viaje.destino_lat !== null && viaje.destino_lon !== null
      ? { lat: viaje.destino_lat, lon: viaje.destino_lon }
      : null
    : destinoLat !== null && destinoLon !== null
      ? { lat: destinoLat, lon: destinoLon }
      : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {/* CU-O04 paso 1: el mapa está siempre presente en esta pantalla —
          mientras se resuelve el permiso/la posición se muestra un estado de
          carga en el mismo lugar. Una vez que hay un viaje, sigue siendo el
          mismo elemento montado: solo cambian los marcadores/overlay. */}
      <div style={{ position: "relative" }}>
        {mapaOrigen ? (
          <RideMap
            origen={mapaOrigen}
            destino={mapaDestino}
            ruta={ruta}
            cercanos={cercanos}
            conductor={conductorPos}
            clicksHabilitados={!viaje}
            onMapaClick={manejarClickMapa}
            onUbicacionEncontrada={(lat, lon) => {
              if (viaje) return;
              setOrigenLat(lat);
              setOrigenLon(lon);
              setErrorUbicacion(null);
              setUbicando(false);
            }}
            onUbicacionError={(mensaje) => {
              setErrorUbicacion(mensaje);
              setUbicando(false);
            }}
          />
        ) : (
          <div
            style={{
              height: ALTO_MAPA,
              borderRadius: "var(--radius-md)",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-text-muted)",
              fontSize: "var(--font-size-sm)",
              textAlign: "center",
              padding: "var(--space-4)",
            }}
          >
            {ubicando ? "Centrando el mapa en tu ubicación…" : "No se pudo centrar el mapa en tu ubicación."}
          </div>
        )}
        <div style={overlayPanelStyle}>
          {viaje ? (
            <PanelViajeActivo
              viaje={viaje}
              onCancelado={() => setViaje(null)}
              elapsedSeconds={elapsedSeconds}
              onReintentar={() => reintentarBusqueda(viaje)}
            />
          ) : (
            <PanelSolicitar
              origenLat={origenLat}
              origenLon={origenLon}
              ubicando={ubicando}
              errorUbicacion={errorUbicacion}
              solicitarUbicacion={solicitarUbicacion}
              origenDireccion={origenDireccion}
              setOrigenDireccion={setOrigenDireccion}
              destinoLat={destinoLat}
              destinoDireccion={destinoDireccion}
              setDestinoDireccion={setDestinoDireccion}
              geocodificando={geocodificando}
              estimacion={estimacion}
              tarifaEstimadaCliente={tarifaEstimadaCliente}
              errorSolicitar={errorSolicitar}
              viajeActivoExistente={viajeActivoExistente !== null}
              cargando={cargando}
              solicitar={solicitar}
              favoritas={favoritas}
              onSeleccionarFavorita={seleccionarFavorita}
              onGuardarFavorita={guardarFavorita}
              guardandoFavorita={guardandoFavorita}
              modo={modoSolicitud}
              setModo={setModoSolicitud}
              tsProgramadoLocal={tsProgramadoLocal}
              setTsProgramadoLocal={setTsProgramadoLocal}
            />
          )}
        </div>
      </div>
      {viaje?.estado === "FINALIZADO" && !viaje.calificacion_pasajero_a_conductor && (
        <CalificarConductorForm viajeId={viaje.id} onListo={() => setViaje(null)} />
      )}
    </div>
  );
}

function CalificarConductorForm({ viajeId, onListo }: { viajeId: string; onListo: () => void }) {
  const [puntaje, setPuntaje] = useState(5);
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enviar = async () => {
    setEnviando(true);
    setError(null);
    try {
      await apiFetch(`/viajes/${viajeId}/calificar`, {
        method: "POST",
        body: { puntaje, comentario: comentario.trim() || undefined },
      });
      onListo();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo enviar la calificación");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>Califica al conductor</h1>
      <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setPuntaje(n)}
            style={{
              fontSize: "var(--font-size-lg)",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: n <= puntaje ? "var(--color-accent)" : "var(--color-border)",
            }}
          >
            ★
          </button>
        ))}
      </div>
      <div style={{ marginBottom: "var(--space-3)" }}>
        <TextArea
          label="Comentario (opcional)"
          value={comentario}
          onChange={(e) => setComentario(e.target.value)}
        />
      </div>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <div style={{ display: "flex", gap: "var(--space-3)" }}>
        <Button onClick={enviar} loading={enviando}>
          Enviar calificación
        </Button>
        <Button variant="secondary" onClick={onListo}>
          Omitir
        </Button>
      </div>
    </Card>
  );
}

interface HistorialItem {
  id: string;
  ts_solicitud: string;
  origen_direccion: string;
  destino_direccion: string | null;
  estado: EstadoViaje;
  tarifa_final: number | null;
  conductor_nombre: string | null;
  calificacion_pasajero_a_conductor: { puntaje: number } | null;
}

// CU-O14 paso 3: detalle de un viaje puntual del historial, obtenido de GET
// /viajes/{id} al hacer clic en una fila — el mismo endpoint que ya usa
// VistaViaje para seguir el viaje activo, reutilizado aquí para el caso de
// un viaje ya cerrado.
interface ViajeDetalle {
  id: string;
  origen_lat: number;
  origen_lon: number;
  origen_direccion: string;
  destino_lat: number | null;
  destino_lon: number | null;
  destino_direccion: string | null;
  estado: EstadoViaje;
  tarifa_final: number | null;
  tarifa_estimada: number | null;
  conductor_nombre: string | null;
  conductor_calificacion: number | null;
}

// CU-O14 paso 2: filtrar por estado (finalizados / cancelados) — solo esos
// dos son filtrables por diseño del backend (SIN_CONDUCTOR/PAGADO no son
// estados que la spec pida como filtro explícito, aunque igual aparecen
// listados sin filtro).
const OPCIONES_ESTADO = [
  { value: "", label: "Todos" },
  { value: "FINALIZADO", label: "Finalizados" },
  { value: "CANCELADO", label: "Cancelados" },
];

function HistorialView({ onVolver }: { onVolver: () => void }) {
  const [items, setItems] = useState<HistorialItem[]>([]);
  const [total, setTotal] = useState(0);
  const [estado, setEstado] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [pagina, setPagina] = useState(1);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detalleAbierto, setDetalleAbierto] = useState(false);
  const [seleccionado, setSeleccionado] = useState<ViajeDetalle | null>(null);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);
  const [errorDetalle, setErrorDetalle] = useState<string | null>(null);
  const limite = 10;

  useEffect(() => {
    setCargando(true);
    setError(null);
    const params = new URLSearchParams({ rol: "pasajero", pagina: String(pagina), limite: String(limite) });
    if (estado) params.set("estado", estado);
    // CU-O14 paso 2: rango de fechas — el backend espera datetimes ISO en
    // desde/hasta; a partir de un <input type="date"> (YYYY-MM-DD) se arma
    // el inicio y el fin del día para no perder ninguno de los dos extremos.
    if (desde) params.set("desde", `${desde}T00:00:00`);
    if (hasta) params.set("hasta", `${hasta}T23:59:59`);
    apiFetch<{ viajes: HistorialItem[]; total: number }>(`/viajes?${params}`)
      .then((r) => {
        setItems(r.viajes);
        setTotal(r.total);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar el historial"))
      .finally(() => setCargando(false));
  }, [estado, desde, hasta, pagina]);

  // CU-O14 paso 3: al hacer clic en una fila se pide el detalle completo por
  // id — la fila de la tabla ya trae lo esencial, pero el detalle confirma
  // tarifa/estado/contraparte desde la fuente autoritativa.
  const abrirDetalle = (id: string) => {
    setErrorDetalle(null);
    setSeleccionado(null);
    setDetalleAbierto(true);
    setCargandoDetalle(true);
    apiFetch<ViajeDetalle>(`/viajes/${id}`)
      .then(setSeleccionado)
      .catch((e) => setErrorDetalle(e instanceof ApiError ? e.message : "No se pudo cargar el detalle del viaje"))
      .finally(() => setCargandoDetalle(false));
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-4)" }}>Mis viajes</h1>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Estado"
            value={estado}
            onChange={(e) => {
              setEstado(e.target.value);
              setPagina(1);
            }}
            options={OPCIONES_ESTADO}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <TextField
            label="Desde"
            type="date"
            value={desde}
            onChange={(e) => {
              setDesde(e.target.value);
              setPagina(1);
            }}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <TextField
            label="Hasta"
            type="date"
            value={hasta}
            onChange={(e) => {
              setHasta(e.target.value);
              setPagina(1);
            }}
          />
        </div>
      </div>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      {cargando ? (
        <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
      ) : (
        <DataTable
          rows={items}
          keyField={(v) => v.id}
          vacio="Todavía no tienes viajes en este filtro."
          columns={[
            { header: "Fecha", render: (v) => new Date(v.ts_solicitud).toLocaleString() },
            { header: "Origen → Destino", render: (v) => `${v.origen_direccion} → ${v.destino_direccion ?? "—"}` },
            { header: "Conductor", render: (v) => v.conductor_nombre ?? "—" },
            { header: "Tarifa", render: (v) => (v.tarifa_final !== null ? `$${v.tarifa_final.toFixed(2)}` : "—") },
            { header: "Estado", render: (v) => <Badge texto={ESTADO_TEXTO[v.estado]} tono={ESTADO_TONO[v.estado]} /> },
            {
              header: "Calificación",
              render: (v) => (v.calificacion_pasajero_a_conductor ? `${v.calificacion_pasajero_a_conductor.puntaje}★` : "—"),
            },
            {
              header: "Detalle",
              render: (v) => (
                <Button variant="secondary" onClick={() => abrirDetalle(v.id)}>
                  Ver
                </Button>
              ),
            },
          ]}
        />
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-3)" }}>
        <Button variant="secondary" onClick={() => setPagina((p) => Math.max(1, p - 1))} disabled={pagina === 1}>
          Anterior
        </Button>
        <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Página {pagina} de {Math.max(1, Math.ceil(total / limite))}
        </span>
        <Button variant="secondary" onClick={() => setPagina((p) => p + 1)} disabled={pagina * limite >= total}>
          Siguiente
        </Button>
      </div>
      <Button variant="secondary" onClick={onVolver} style={{ marginTop: "var(--space-3)" }}>
        Volver
      </Button>

      {detalleAbierto && (
        <DetailPanel
          titulo="Detalle del viaje"
          modo="consulta"
          onSalir={() => setDetalleAbierto(false)}
        >
          {errorDetalle ? (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{errorDetalle}</p>
          ) : cargandoDetalle || !seleccionado ? (
            <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {/* CU-O14 paso 3: mapa/ruta del viaje ya cerrado — mismo
                  RideMap del viaje en curso, en modo solo-lectura (sin
                  clics, sin control de geolocalización activo) y con la
                  línea recta origen→destino como proxy de ruta, igual que
                  el resto de la app (sin motor de ruteo en el stack). */}
              <RideMap
                origen={{ lat: seleccionado.origen_lat, lon: seleccionado.origen_lon }}
                destino={
                  seleccionado.destino_lat !== null && seleccionado.destino_lon !== null
                    ? { lat: seleccionado.destino_lat, lon: seleccionado.destino_lon }
                    : null
                }
                ruta={
                  seleccionado.destino_lat !== null && seleccionado.destino_lon !== null
                    ? [
                        [seleccionado.origen_lat, seleccionado.origen_lon],
                        [seleccionado.destino_lat, seleccionado.destino_lon],
                      ]
                    : null
                }
                cercanos={[]}
                onMapaClick={() => {}}
                onUbicacionEncontrada={() => {}}
                onUbicacionError={() => {}}
                clicksHabilitados={false}
              />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
                <DetailField label="Origen" value={seleccionado.origen_direccion} />
                <DetailField label="Destino" value={seleccionado.destino_direccion ?? "—"} />
                <DetailField
                  label="Conductor"
                  value={
                    seleccionado.conductor_nombre
                      ? `${seleccionado.conductor_nombre}${seleccionado.conductor_calificacion !== null ? ` (${seleccionado.conductor_calificacion.toFixed(1)}★)` : ""}`
                      : "—"
                  }
                />
                <DetailField
                  label="Tarifa estimada"
                  value={seleccionado.tarifa_estimada !== null ? `$${seleccionado.tarifa_estimada.toFixed(2)}` : "—"}
                />
                <DetailField
                  label="Tarifa final"
                  value={seleccionado.tarifa_final !== null ? `$${seleccionado.tarifa_final.toFixed(2)}` : "—"}
                />
                <DetailField label="Estado" value={<Badge texto={ESTADO_TEXTO[seleccionado.estado]} tono={ESTADO_TONO[seleccionado.estado]} />} />
              </div>
            </div>
          )}
        </DetailPanel>
      )}
    </Card>
  );
}

// Sección 1.1 de ux_complementaria.md: gestión (ver/eliminar) de
// direcciones favoritas, dentro de "Mi perfil" (slot `extra` de
// `PerfilPropio`). Agregar una nueva se hace desde el flujo de solicitud
// ("Guardar como favorita" junto al destino elegido en el mapa) -- no
// desde aquí, para no pedirle lat/lon a mano sin un mapa a la vista.
function GestionDireccionesFavoritas() {
  const [favoritas, setFavoritas] = useState<DireccionFavorita[]>([]);
  const [error, setError] = useState<string | null>(null);

  const cargar = () =>
    apiFetch<DireccionFavorita[]>("/direcciones")
      .then(setFavoritas)
      .catch(() => setError("No se pudieron cargar tus direcciones favoritas"));

  useEffect(() => {
    cargar();
  }, []);

  const eliminar = async (id: string) => {
    setError(null);
    try {
      await apiFetch(`/direcciones/${id}`, { method: "DELETE" });
      setFavoritas((prev) => prev.filter((f) => f.id !== id));
    } catch {
      setError("No se pudo eliminar la dirección");
    }
  };

  return (
    <Card>
      <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Direcciones favoritas</h3>
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
        Se agregan desde la pantalla de viaje, con el botón "☆ Guardar como favorita" junto al destino elegido.
      </p>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      {favoritas.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Todavía no guardaste ninguna dirección favorita.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {favoritas.map((f) => (
            <div
              key={f.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "var(--space-2)",
                padding: "var(--space-2) var(--space-3)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
              }}
            >
              <div>
                <div style={{ fontSize: "var(--font-size-sm)", fontWeight: 600 }}>{f.etiqueta}</div>
                <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>{f.direccion}</div>
              </div>
              <div style={{ minWidth: 90 }}>
                <Button variant="danger" onClick={() => eliminar(f.id)}>
                  Eliminar
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

const NAV_ITEMS_PASAJERO: { id: "viaje" | "historial" | "perfil" | "ajustes" | "ayuda"; label: string }[] = [
  { id: "viaje", label: "Viaje" },
  { id: "historial", label: "Mis viajes" },
  { id: "perfil", label: "Mi perfil" },
  { id: "ajustes", label: "Ajustes" },
  { id: "ayuda", label: "Ayuda" },
];

const PREGUNTAS_FRECUENTES_PASAJERO: PreguntaFrecuente[] = [
  {
    pregunta: "¿Cómo cancelo un viaje que ya pedí?",
    respuesta: "Desde la pantalla de viaje activo, usa el botón \"Cancelar solicitud\" mientras el estado sea SOLICITADO.",
  },
  {
    pregunta: "¿Por qué no encuentra conductor?",
    respuesta: "Puede que no haya socios disponibles cerca en este momento. Puedes reintentar la búsqueda con el mismo origen y destino.",
  },
  {
    pregunta: "¿Cómo cambio mi contraseña?",
    respuesta: "Entra a \"Mi perfil\" y edita tus datos con tu contraseña actual.",
  },
];

function InicioAutenticado() {
  const [viaje, setViaje] = useState<Viaje | null | undefined>(undefined);
  const [vista, setVista] = useState<"viaje" | "historial" | "perfil" | "ajustes" | "ayuda">("viaje");

  useEffect(() => {
    let cancelado = false;
    // 200 con cuerpo vacío cuando no hay viaje activo — no es un error, es
    // el estado normal la mayoría del tiempo (corregido tras hallazgo en
    // pruebas reales: antes era 404, y este catch lo trataba igual que
    // cualquier otro fallo real de red).
    apiFetch<Viaje | null>("/viajes/activo")
      .then((v) => {
        if (!cancelado) setViaje(v);
      })
      .catch(() => {
        if (!cancelado) setViaje(null);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  // Refresca el viaje cada 5s — sigue siendo necesario como respaldo (si el
  // WebSocket de abajo no conecta, o para transiciones que este slice no
  // empuja en vivo todavía, como SIN_CONDUCTOR). Una vez que ya se conoce el
  // id, se usa GET /viajes/{id} en vez de /viajes/activo: ese último solo
  // devuelve viajes en un estado ACTIVO por diseño, así que un viaje
  // FINALIZADO desaparecería de ahí — el cliente nunca podría enterarse de
  // esa transición y se quedaría en un 404 permanente justo cuando más
  // importa (mostrar tarifa final y habilitar la calificación).
  useEffect(() => {
    if (!viaje || viaje.estado === "FINALIZADO") return;
    const id = setInterval(() => {
      apiFetch<Viaje>(`/viajes/${viaje.id}`)
        .then(setViaje)
        .catch(() => setViaje(null));
    }, 5000);
    return () => clearInterval(id);
  }, [viaje]);

  // Notificación en vivo (CU-O05 paso 5, CU-O07/O08): en vez de esperar
  // hasta 5s de polling para ver una transición, cualquier evento en el
  // canal del viaje dispara un refetch inmediato por id — una sola fuente
  // de verdad, sin duplicar el mapeo de campos por evento en el cliente. El
  // socket vive mientras el viaje siga en un estado que aún puede cambiar en
  // vivo; se cierra al llegar a un estado terminal (el último refetch, que
  // sí puede traer FINALIZADO, ya usa /viajes/{id}, no /activo).
  const ESTADOS_CON_SOCKET: EstadoViaje[] = ["SOLICITADO", "OFERTADO", "ASIGNADO", "EN_CAMINO", "EN_CURSO"];
  useEffect(() => {
    if (!viaje || !ESTADOS_CON_SOCKET.includes(viaje.estado)) return;

    const wsUrl = `${getApiBaseUrl().replace(/^http/, "ws")}/ws/pasajero/${viaje.id}?token=${tokenStorage.getAccess()}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = () => {
      apiFetch<Viaje>(`/viajes/${viaje.id}`)
        .then(setViaje)
        .catch(() => {});
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viaje?.id, viaje?.estado]);

  return (
    <AppShell
      navItems={NAV_ITEMS_PASAJERO}
      activeId={vista}
      onNavigate={(id) => setVista(id as "viaje" | "historial" | "perfil" | "ajustes" | "ayuda")}
      headerActions={<NotificacionesBell />}
    >
      <div style={{ width: "100%" }}>
        {vista === "perfil" ? (
          <PerfilPropio extra={<GestionDireccionesFavoritas />} />
        ) : vista === "ajustes" ? (
          <AjustesPropios version="0.1.0" />
        ) : vista === "ayuda" ? (
          <CentroAyuda
            preguntas={PREGUNTAS_FRECUENTES_PASAJERO}
            correoContacto="soporte@urbanfleet.example"
            telefonoContacto="+593900000000"
          />
        ) : viaje === undefined ? (
          <Card>
            <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
          </Card>
        ) : vista === "historial" ? (
          <HistorialView onVolver={() => setVista("viaje")} />
        ) : (
          <VistaViaje viaje={viaje} setViaje={setViaje} />
        )}
      </div>
    </AppShell>
  );
}

// Sección 1.2 de ux_complementaria.md: página pública de "Compartir viaje" —
// sin sesión. Cadencia de refresco más corta que el resto del polling del
// proyecto (15s) porque acá el propósito completo de la página es ver la
// posición en vivo, no un dato secundario mientras se hace otra cosa.
const INTERVALO_COMPARTIDO_MS = 8000;

interface ViajeCompartido {
  conductor_nombre: string | null;
  conductor_calificacion: number | null;
  conductor_foto_url: string | null;
  vehiculo_placa: string | null;
  estado: EstadoViaje;
  posicion: { lat: number; lon: number } | null;
}

function VistaCompartida({ token }: { token: string }) {
  const [datos, setDatos] = useState<ViajeCompartido | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let cancelado = false;
    const cargar = () => {
      apiFetch<ViajeCompartido>(`/publico/viajes-compartidos/${token}`, { auth: false })
        .then((r) => {
          if (cancelado) return;
          setDatos(r);
          setError(null);
          setCargando(false);
        })
        .catch((e) => {
          if (cancelado) return;
          setError(e instanceof ApiError ? e.message : "Enlace no válido o expirado");
          setCargando(false);
        });
    };
    cargar();
    const id = setInterval(cargar, INTERVALO_COMPARTIDO_MS);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
  }, [token]);

  return (
    <div
      style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-4)",
      }}
    >
      <div style={{ width: "min(480px, 100%)" }}>
        <Card>
          <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-3)" }}>
            Viaje en curso
          </h1>
          {cargando && <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>}
          {error && !cargando && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
          {datos && !error && (
            <>
              <div style={{ marginBottom: "var(--space-2)" }}>
                <Badge texto={ESTADO_TEXTO[datos.estado]} tono={ESTADO_TONO[datos.estado]} />
              </div>
              {datos.conductor_foto_url && (
                <img
                  src={datos.conductor_foto_url}
                  alt="Foto del conductor"
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: "50%",
                    objectFit: "cover",
                    marginBottom: "var(--space-2)",
                  }}
                />
              )}
              {datos.conductor_nombre && <p style={{ margin: 0 }}>Conductor: {datos.conductor_nombre}</p>}
              {datos.conductor_calificacion !== null && (
                <p style={{ margin: 0 }}>Calificación: {datos.conductor_calificacion.toFixed(1)}★</p>
              )}
              {datos.vehiculo_placa && (
                <p style={{ margin: 0, marginBottom: "var(--space-3)" }}>Placa: {datos.vehiculo_placa}</p>
              )}
              {datos.posicion ? (
                <RideMap
                  origen={datos.posicion}
                  destino={null}
                  ruta={null}
                  cercanos={[]}
                  onMapaClick={() => {}}
                  onUbicacionEncontrada={() => {}}
                  onUbicacionError={() => {}}
                  soloLectura
                />
              ) : (
                <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                  Posición no disponible por el momento.
                </p>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function App() {
  const { actor } = useAuth();
  const compartidoMatch = window.location.pathname.match(/^\/compartido\/(.+)$/);
  if (compartidoMatch) return <VistaCompartida token={compartidoMatch[1]} />;
  if (actor) return <InicioAutenticado />;
  return (
    <div
      style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-4)",
      }}
    >
      <div style={{ width: "min(400px, 100%)" }}>
        <LoginCard />
      </div>
    </div>
  );
}
