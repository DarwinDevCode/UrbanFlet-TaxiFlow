import {
  AjustesPropios,
  ApiError,
  AppShell,
  Badge,
  apiFetch,
  Button,
  Card,
  CentroAyuda,
  DataTable,
  DetailField,
  DetailPanel,
  logoUrbanFleetFull,
  NotificacionesBell,
  PerfilPropio,
  Select,
  TextArea,
  TextField,
  useAuth,
  type PreguntaFrecuente,
} from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";
import { DriverMap } from "./DriverMap";

const PREGUNTAS_FRECUENTES_CONDUCTOR: PreguntaFrecuente[] = [
  {
    pregunta: "¿Por qué no me llegan ofertas?",
    respuesta: "Verifica que tu turno esté iniciado (\"Mi turno\") y que tengas buena señal de ubicación. El reparto de ofertas lo decide el sistema.",
  },
  {
    pregunta: "¿Cómo veo mis ingresos del periodo actual?",
    respuesta: "En \"Mis liquidaciones\" puedes consultar el detalle de cada periodo ya calculado.",
  },
  {
    pregunta: "¿Cómo actualizo mi foto de perfil?",
    respuesta: "Entra a \"Mi perfil\" y pega la URL de tu foto en el campo correspondiente, junto con tu contraseña actual.",
  },
];

function PostulacionForm({ onEnviada }: { onEnviada: () => void }) {
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [password, setPassword] = useState("");
  const [cedula, setCedula] = useState("");
  const [licencia, setLicencia] = useState("");
  const [placa, setPlaca] = useState("");
  const [marca, setMarca] = useState("");
  const [modelo, setModelo] = useState("");
  const [anio, setAnio] = useState("");
  const [color, setColor] = useState("");
  const [capacidad, setCapacidad] = useState("4");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const camposCompletos =
    nombre &&
    telefono &&
    password.length >= 8 &&
    cedula &&
    licencia &&
    placa &&
    marca &&
    modelo &&
    anio &&
    color &&
    capacidad;

  const enviar = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/captacion/solicitudes", {
        method: "POST",
        auth: false,
        body: {
          nombre,
          telefono,
          password,
          cedula,
          licencia_numero: licencia,
          vehiculo: {
            placa,
            marca,
            modelo,
            anio: Number(anio),
            color,
            capacidad: Number(capacidad),
          },
          documentos: [],
          enviar: true,
        },
      });
      onEnviada();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo enviar la solicitud");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
        Postula a socio conductor
      </h1>
      <p style={{ color: "var(--color-text-muted)", marginTop: 0, marginBottom: "var(--space-4)" }}>
        Revisaremos tu solicitud en un plazo de hasta 5 días hábiles. La carga de documentos (licencia,
        matrícula, SOAT) se habilita en un paso posterior. La contraseña que definas aquí es la que usarás
        para iniciar sesión una vez aprobada tu solicitud.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <TextField label="Nombre completo" value={nombre} onChange={(e) => setNombre(e.target.value)} />
        <TextField label="Teléfono" type="tel" placeholder="+593..." value={telefono} onChange={(e) => setTelefono(e.target.value)} />
        <TextField
          label="Contraseña (mínimo 8 caracteres)"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <TextField label="Cédula" value={cedula} onChange={(e) => setCedula(e.target.value)} />
        <TextField label="Número de licencia" value={licencia} onChange={(e) => setLicencia(e.target.value)} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <TextField label="Placa" value={placa} onChange={(e) => setPlaca(e.target.value.toUpperCase())} />
          <TextField label="Año" type="number" value={anio} onChange={(e) => setAnio(e.target.value)} />
          <TextField label="Marca" value={marca} onChange={(e) => setMarca(e.target.value)} />
          <TextField label="Modelo" value={modelo} onChange={(e) => setModelo(e.target.value)} />
          <TextField label="Color" value={color} onChange={(e) => setColor(e.target.value)} />
          <TextField label="Capacidad" type="number" value={capacidad} onChange={(e) => setCapacidad(e.target.value)} />
        </div>
        {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
        <Button onClick={enviar} loading={cargando} disabled={!camposCompletos}>
          Enviar solicitud
        </Button>
      </div>
    </Card>
  );
}

function LoginCard({ onPostular }: { onPostular: () => void }) {
  const { login } = useAuth();
  const [identificador, setIdentificador] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const entrar = async () => {
    setError(null);
    setCargando(true);
    try {
      await login(identificador, password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo iniciar sesión");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
        Portal del socio conductor
      </h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <TextField
          label="Teléfono o correo"
          value={identificador}
          onChange={(e) => setIdentificador(e.target.value)}
        />
        <TextField label="Contraseña" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
        <Button onClick={entrar} loading={cargando} disabled={!identificador || !password}>
          Entrar
        </Button>
        <button
          type="button"
          onClick={onPostular}
          style={{ background: "none", border: "none", color: "var(--color-accent)", cursor: "pointer" }}
        >
          ¿Eres postulante nuevo? Postula aquí
        </button>
      </div>
    </Card>
  );
}

type EstadoServicio = "FUERA_DE_LINEA" | "DISPONIBLE" | "OCUPADO";

interface OfertaActual {
  viaje_id: string;
  pasajero_nombre: string;
  pasajero_calificacion: number | null;
  // CU-O06: el backend (schemas.OfertaActualOut) ya incluye la posición de
  // recogida del pasajero en toda oferta — se usa para pintar su marcador
  // en el mapa persistente en vez de dejar la oferta como texto suelto.
  origen_lat: number;
  origen_lon: number;
  distancia_km: number | null;
  tiene_destino: boolean;
  segundos_restantes: number;
}

interface ViajeAsignado {
  id: string;
  estado: string;
  origen_lat: number;
  origen_lon: number;
  origen_direccion: string;
  destino_lat: number | null;
  destino_lon: number | null;
  destino_direccion: string | null;
  ts_llegada_origen: string | null;
  km_recorridos: number | null;
  tarifa_final: number | null;
  calificacion_conductor_a_pasajero: { puntaje: number } | null;
}

function OfertaModal({ oferta, onRespondida }: { oferta: OfertaActual; onRespondida: (aceptada: boolean) => void }) {
  const [segundos, setSegundos] = useState(oferta.segundos_restantes);
  const [respondiendo, setRespondiendo] = useState(false);

  useEffect(() => {
    setSegundos(oferta.segundos_restantes);
  }, [oferta]);

  useEffect(() => {
    const id = setInterval(() => setSegundos((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, []);

  const responder = async (aceptar: boolean) => {
    setRespondiendo(true);
    try {
      await apiFetch<{ estado: string }>("/viajes/oferta/responder", { method: "POST", body: { aceptar } });
      onRespondida(aceptar);
    } catch {
      // La oferta pudo expirar o ya no estar disponible (A1/A2) — el próximo
      // poll de oferta-actual refleja el estado real, no hace falta más aquí.
      onRespondida(false);
    } finally {
      setRespondiendo(false);
    }
  };

  // CU-O06: overlay flotante sobre el mapa persistente (ver PantallaTurno),
  // ya no una pantalla completa desconectada de él — el pasajero ya se ve
  // como marcador de recogida detrás de este panel.
  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
        Nuevo viaje — {segundos}s
      </h1>
      <p style={{ margin: "var(--space-1) 0" }}>
        Pasajero: {oferta.pasajero_nombre}
        {oferta.pasajero_calificacion !== null && ` (${oferta.pasajero_calificacion.toFixed(1)}★)`}
      </p>
      {oferta.distancia_km !== null && (
        <p style={{ margin: "var(--space-1) 0" }}>Distancia hasta el origen: {oferta.distancia_km.toFixed(1)} km</p>
      )}
      <p style={{ margin: "var(--space-1) 0", color: "var(--color-text-muted)" }}>
        {oferta.tiene_destino ? "Con destino marcado" : "Sin destino marcado"}
      </p>
      <div style={{ display: "flex", gap: "var(--space-3)", marginTop: "var(--space-4)" }}>
        <Button variant="danger" onClick={() => responder(false)} loading={respondiendo}>
          Rechazar
        </Button>
        <Button onClick={() => responder(true)} loading={respondiendo}>
          Aceptar
        </Button>
      </div>
    </Card>
  );
}

function PagoForm({
  viajeId,
  tarifaFinal,
  onRegistrado,
}: {
  viajeId: string;
  tarifaFinal: number;
  onRegistrado: (pago: { estado: string; diferencia: number | null }) => void;
}) {
  const [monto, setMonto] = useState(tarifaFinal.toFixed(2));
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const registrar = async () => {
    setEnviando(true);
    setError(null);
    try {
      const pago = await apiFetch<{ estado: string; diferencia: number | null }>("/pagos/efectivo", {
        method: "POST",
        body: { viaje_id: viajeId, monto_cobrado: Number(monto) },
      });
      onRegistrado(pago);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo registrar el pago");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
        Pago recibido
      </h1>
      <p style={{ color: "var(--color-text-muted)", margin: "0 0 var(--space-3)" }}>
        Tarifa a cobrar: ${tarifaFinal.toFixed(2)}
      </p>
      <TextField label="Monto cobrado en efectivo" type="number" value={monto} onChange={(e) => setMonto(e.target.value)} />
      {error && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-2)" }}>{error}</p>
      )}
      <Button onClick={registrar} loading={enviando} style={{ marginTop: "var(--space-3)" }}>
        Confirmar pago recibido
      </Button>
    </Card>
  );
}

function CalificarPasajeroForm({ viajeId, onListo }: { viajeId: string; onListo: () => void }) {
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
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>Califica al pasajero</h1>
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

function ViajeAsignadoCard({
  viaje,
  onActualizado,
  onLiberado,
}: {
  viaje: ViajeAsignado;
  onActualizado: (viaje: ViajeAsignado) => void;
  onLiberado: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const accion = async (path: string, body?: unknown) => {
    setError(null);
    setCargando(true);
    try {
      const actualizado = await apiFetch<ViajeAsignado>(path, { method: "POST", body });
      onActualizado(actualizado);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo completar la acción");
    } finally {
      setCargando(false);
    }
  };

  const cancelar = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/viajes/conductor/cancelar", { method: "POST", body: { motivo: "cancelado por el conductor" } });
      onLiberado();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cancelar");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
        Viaje asignado
      </h1>
      <div style={{ marginBottom: "var(--space-2)" }}>
        <Badge texto={viaje.estado} tono="exito" />
      </div>
      <p style={{ margin: "var(--space-1) 0" }}>Recoger en: {viaje.origen_direccion}</p>
      {viaje.destino_direccion && <p style={{ margin: "var(--space-1) 0" }}>Destino: {viaje.destino_direccion}</p>}
      {viaje.ts_llegada_origen && (
        <p style={{ margin: "var(--space-1) 0", color: "var(--color-text-muted)" }}>Llegada registrada</p>
      )}
      {(viaje.estado === "EN_CURSO" || viaje.estado === "FINALIZADO") && (
        <p style={{ margin: "var(--space-1) 0" }}>Distancia recorrida: {(viaje.km_recorridos ?? 0).toFixed(2)} km</p>
      )}
      {viaje.estado === "FINALIZADO" && viaje.tarifa_final !== null && (
        <p style={{ margin: "var(--space-1) 0" }}>Tarifa final: ${viaje.tarifa_final.toFixed(2)}</p>
      )}

      {error && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", whiteSpace: "pre-wrap" }}>{error}</p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
        {viaje.estado === "ASIGNADO" && (
          <Button onClick={() => accion("/viajes/conductor/en-camino")} loading={cargando}>
            Voy en camino
          </Button>
        )}
        {viaje.estado === "EN_CAMINO" && !viaje.ts_llegada_origen && (
          <Button variant="secondary" onClick={() => accion("/viajes/conductor/llegue")} loading={cargando}>
            He llegado
          </Button>
        )}
        {viaje.estado === "EN_CAMINO" && (
          <Button onClick={() => accion("/viajes/conductor/iniciar")} loading={cargando}>
            Iniciar viaje
          </Button>
        )}
        {viaje.estado === "EN_CURSO" && (
          <Button onClick={() => accion("/viajes/conductor/finalizar")} loading={cargando}>
            Finalizar viaje
          </Button>
        )}
        {(viaje.estado === "ASIGNADO" || viaje.estado === "EN_CAMINO") && (
          <Button variant="danger" onClick={cancelar} loading={cargando}>
            Cancelar viaje
          </Button>
        )}
      </div>
    </Card>
  );
}

interface HistorialItem {
  id: string;
  ts_solicitud: string;
  origen_direccion: string;
  destino_direccion: string | null;
  estado: string;
  tarifa_final: number | null;
  pasajero_nombre: string | null;
  calificacion_conductor_a_pasajero: { puntaje: number } | null;
}

const OPCIONES_ESTADO_HISTORIAL = [
  { value: "", label: "Todos" },
  { value: "FINALIZADO", label: "Finalizados" },
  { value: "CANCELADO", label: "Cancelados" },
];

// CU-O14 paso 3: detalle de un viaje puntual del historial, obtenido de GET
// /viajes/{id} — el mismo endpoint que ya usa PantallaTurno para seguir el
// viaje asignado en vivo, reutilizado aquí para uno ya cerrado. El
// enriquecimiento con datos del pasajero (nombre, nunca teléfono ni
// ubicaciones) ya lo hace el backend (service_historial.enriquecer_con_pasajero).
interface ViajeDetalle {
  id: string;
  origen_direccion: string;
  destino_direccion: string | null;
  estado: string;
  tarifa_final: number | null;
  pasajero_nombre: string | null;
}

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
    const params = new URLSearchParams({ rol: "conductor", pagina: String(pagina), limite: String(limite) });
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
            options={OPCIONES_ESTADO_HISTORIAL}
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
            // CU-O14 A2: solo nombre de pila y calificación del pasajero — nunca teléfono ni ubicaciones.
            { header: "Pasajero", render: (v) => v.pasajero_nombre ?? "—" },
            { header: "Tarifa", render: (v) => (v.tarifa_final !== null ? `$${v.tarifa_final.toFixed(2)}` : "—") },
            {
              header: "Estado",
              render: (v) => <Badge texto={v.estado} tono={v.estado === "CANCELADO" ? "peligro" : "exito"} />,
            },
            {
              header: "Calificación",
              render: (v) =>
                v.calificacion_conductor_a_pasajero ? `${v.calificacion_conductor_a_pasajero.puntaje}★` : "—",
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
        <DetailPanel titulo="Detalle del viaje" modo="consulta" onSalir={() => setDetalleAbierto(false)}>
          {errorDetalle ? (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{errorDetalle}</p>
          ) : cargandoDetalle || !seleccionado ? (
            <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Origen" value={seleccionado.origen_direccion} />
              <DetailField label="Destino" value={seleccionado.destino_direccion ?? "—"} />
              <DetailField label="Pasajero" value={seleccionado.pasajero_nombre ?? "—"} />
              <DetailField
                label="Tarifa final"
                value={seleccionado.tarifa_final !== null ? `$${seleccionado.tarifa_final.toFixed(2)}` : "—"}
              />
              <DetailField label="Estado" value={<Badge texto={seleccionado.estado} tono={seleccionado.estado === "CANCELADO" ? "peligro" : "exito"} />} />
            </div>
          )}
        </DetailPanel>
      )}
    </Card>
  );
}

interface MiLiquidacion {
  id: string;
  periodo_inicio: string;
  periodo_fin: string;
  estado: string;
  bruto: number;
  comisiones: number;
  neto: number;
  saldo: number;
  observacion_motivo: string | null;
}

function LiquidacionesView({ onVolver }: { onVolver: () => void }) {
  const [items, setItems] = useState<MiLiquidacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enObservacion, setEnObservacion] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");

  const cargar = () => {
    setCargando(true);
    setError(null);
    apiFetch<MiLiquidacion[]>("/liquidaciones/mias")
      .then(setItems)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar tus liquidaciones"))
      .finally(() => setCargando(false));
  };

  useEffect(cargar, []);

  const observar = async (liquidacionId: string) => {
    setError(null);
    try {
      await apiFetch(`/liquidaciones/${liquidacionId}/observar`, { method: "POST", body: { motivo } });
      setEnObservacion(null);
      setMotivo("");
      cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo registrar la observación");
    }
  };

  return (
    <Card>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-4)" }}>Mis liquidaciones</h1>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      {cargando ? (
        <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
      ) : (
        <DataTable
          rows={items}
          keyField={(l) => l.id}
          vacio="Todavía no tienes liquidaciones."
          columns={[
            {
              header: "Periodo",
              render: (l) =>
                `${new Date(l.periodo_inicio).toLocaleDateString()} – ${new Date(l.periodo_fin).toLocaleDateString()}`,
            },
            {
              header: "Estado",
              render: (l) => (
                <Badge
                  texto={l.estado}
                  tono={
                    l.estado === "PAGADA"
                      ? "exito"
                      : l.estado === "OBSERVADA"
                        ? "peligro"
                        : l.estado === "APROBADA"
                          ? "neutral"
                          : "advertencia"
                  }
                />
              ),
            },
            { header: "Bruto", render: (l) => `$${l.bruto.toFixed(2)}` },
            { header: "Comisiones", render: (l) => `$${l.comisiones.toFixed(2)}` },
            { header: "Neto (en mano)", render: (l) => `$${l.neto.toFixed(2)}` },
            {
              header: "Saldo",
              render: (l) => <Badge texto={`$${l.saldo.toFixed(2)}`} tono={l.saldo < 0 ? "peligro" : "exito"} />,
            },
            {
              header: "Acciones",
              render: (l) => {
                if (l.estado !== "EMITIDA") {
                  return <span style={{ color: "var(--color-text-muted)" }}>—</span>;
                }
                if (enObservacion !== l.id) {
                  return (
                    <Button variant="danger" onClick={() => setEnObservacion(l.id)}>
                      Observar
                    </Button>
                  );
                }
                return (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", minWidth: 220 }}>
                    <TextArea label="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
                    <div style={{ display: "flex", gap: "var(--space-2)" }}>
                      <Button onClick={() => observar(l.id)} disabled={!motivo.trim()}>
                        Enviar
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setEnObservacion(null);
                          setMotivo("");
                        }}
                      >
                        Cancelar
                      </Button>
                    </div>
                  </div>
                );
              },
            },
          ]}
        />
      )}
      <Button variant="secondary" onClick={onVolver} style={{ marginTop: "var(--space-3)" }}>
        Volver
      </Button>
    </Card>
  );
}

const NAV_ITEMS_CONDUCTOR: {
  id: "turno" | "historial" | "liquidaciones" | "perfil" | "ajustes" | "ayuda";
  label: string;
}[] = [
  { id: "turno", label: "Mi turno" },
  { id: "historial", label: "Mis viajes" },
  { id: "liquidaciones", label: "Mis liquidaciones" },
  { id: "perfil", label: "Mi perfil" },
  { id: "ajustes", label: "Ajustes" },
  { id: "ayuda", label: "Ayuda" },
];

function PantallaTurno() {
  const { actor } = useAuth();
  const [estado, setEstado] = useState<EstadoServicio>("FUERA_DE_LINEA");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [oferta, setOferta] = useState<OfertaActual | null>(null);
  const [viajeAsignado, setViajeAsignado] = useState<ViajeAsignado | null>(null);
  const [pago, setPago] = useState<{ estado: string; diferencia: number | null } | null>(null);
  const [vista, setVista] = useState<"turno" | "historial" | "liquidaciones" | "perfil" | "ajustes" | "ayuda">(
    "turno",
  );
  // Última posición propia geolocalizada — misma fuente que reportarPosicion
  // usa para POST /flota/posiciones, reutilizada acá solo para centrar/marcar
  // el mapa persistente (no dispara una segunda llamada de geolocalización).
  const [posicionPropia, setPosicionPropia] = useState<{ lat: number; lon: number } | null>(null);

  const iniciarTurno = async () => {
    setError(null);
    setCargando(true);
    try {
      const resp = await apiFetch<{ estado_servicio: EstadoServicio }>("/flota/turno/iniciar", { method: "POST" });
      setEstado(resp.estado_servicio);
      setMensaje("Turno iniciado. Reportando posición cada 15s.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo iniciar turno");
    } finally {
      setCargando(false);
    }
  };

  const terminarTurno = async () => {
    setError(null);
    setCargando(true);
    try {
      const resp = await apiFetch<{ estado_servicio: EstadoServicio }>("/flota/turno/terminar", { method: "POST" });
      setEstado(resp.estado_servicio);
      setMensaje(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo terminar turno");
    } finally {
      setCargando(false);
    }
  };

  const reportarPosicion = async () => {
    if (!("geolocation" in navigator)) {
      setError("Este navegador no soporta geolocalización");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        // Reutilizada para el mapa persistente (ver DriverMap en
        // PantallaTurno) — misma lectura de geolocalización que ya se hacía
        // para el POST, sin pedir un segundo permiso ni una segunda lectura.
        setPosicionPropia({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        try {
          const resp = await apiFetch<{ aceptada: boolean; precision_baja: boolean }>("/flota/posiciones", {
            method: "POST",
            body: {
              lat: pos.coords.latitude,
              lon: pos.coords.longitude,
              precision_m: pos.coords.accuracy,
              // Geolocation API entrega speed en m/s; el backend (y la spec,
              // CU-O07: "minutos de espera... velocidad < 10 km/h") trabaja
              // en km/h — se convierte aquí, en el origen del dato.
              velocidad: pos.coords.speed !== null ? pos.coords.speed * 3.6 : undefined,
              rumbo: pos.coords.heading ?? undefined,
              ts_dispositivo: new Date().toISOString(),
            },
          });
          setMensaje(
            resp.aceptada
              ? `Posición reportada${resp.precision_baja ? " (precisión baja)" : ""} — ${new Date().toLocaleTimeString()}`
              : "Posición descartada por el servidor (salto de ubicación implausible)",
          );
        } catch (e) {
          setError(e instanceof ApiError ? e.message : "No se pudo reportar la posición");
        }
      },
      () => setError("No se pudo obtener tu ubicación — revisa el permiso de geolocalización"),
      { enableHighAccuracy: true },
    );
  };

  // Mientras el turno está activo, reporta posición automáticamente cada
  // 15s (y una vez de inmediato al iniciar, para que el mapa tenga un centro
  // apenas se activa el turno en vez de esperar el primer tick). La cadencia
  // real (10s DISPONIBLE / 5s OCUPADO) y el buffer offline en IndexedDB son
  // de Fase 3, cuando el conductor pasa turnos completos con viajes reales,
  // no solo el shell de turno.
  useEffect(() => {
    if (estado === "FUERA_DE_LINEA") return;
    reportarPosicion();
    const id = setInterval(reportarPosicion, 15000);
    return () => clearInterval(id);
  }, [estado]);

  // A5 (spec CU-O07): "ambos portales restauran el estado con GET
  // /viajes/activo al reconectar" — al montar, si el conductor ya tenía un
  // viaje asignado (p. ej. recargó la página), lo recupera del backend en
  // vez de perderlo.
  useEffect(() => {
    // 200 con cuerpo vacío cuando no hay viaje activo — no es un error (ya
    // no 404), pero tampoco significa que haya uno: solo pasar a OCUPADO si
    // realmente vino un viaje.
    apiFetch<ViajeAsignado | null>("/viajes/conductor/activo")
      .then((v) => {
        if (v) {
          setViajeAsignado(v);
          setEstado("OCUPADO");
        }
      })
      .catch(() => {});
  }, []);

  // Mientras está DISPONIBLE y sin viaje asignado, sondea si le llegó una
  // oferta (CU-O06). La notificación en vivo por WebSocket es un slice
  // posterior de esta misma fase — por ahora el polling es la fuente visible.
  useEffect(() => {
    if (estado !== "DISPONIBLE" || viajeAsignado) return;
    const consultar = () => {
      apiFetch<OfertaActual>("/viajes/oferta-actual")
        .then(setOferta)
        .catch(() => setOferta(null));
    };
    consultar();
    const id = setInterval(consultar, 3000);
    return () => clearInterval(id);
  }, [estado, viajeAsignado]);

  // Respaldo por polling mientras hay un viaje asignado (sin WebSocket del
  // lado del conductor todavía — Slice 3 solo cableó el canal del pasajero).
  // Una vez que ya se conoce el id, se usa GET /viajes/{id} en vez de
  // /viajes/conductor/activo: ese último solo devuelve viajes en un estado
  // activo por diseño, así que un viaje FINALIZADO desaparecería de ahí y
  // una recarga de página perdería la pantalla de calificación (mismo
  // problema ya corregido del lado del pasajero).
  useEffect(() => {
    if (!viajeAsignado || viajeAsignado.estado === "FINALIZADO") return;
    const id = setInterval(() => {
      apiFetch<ViajeAsignado>(`/viajes/${viajeAsignado.id}`)
        .then(setViajeAsignado)
        .catch(() => {
          setViajeAsignado(null);
          setEstado("DISPONIBLE");
        });
    }, 5000);
    return () => clearInterval(id);
    // Deps acotadas a los campos usados — mismo criterio que el polling
    // equivalente del lado del pasajero (evita reiniciar el timer en cada
    // cambio de identidad de `viajeAsignado` que no afecte estos campos).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viajeAsignado?.id, viajeAsignado?.estado]);

  const onOfertaRespondida = (aceptada: boolean) => {
    setOferta(null);
    if (!aceptada) return;
    apiFetch<ViajeAsignado | null>("/viajes/conductor/activo")
      .then((v) => {
        if (v) {
          setViajeAsignado(v);
          setEstado("OCUPADO");
        }
      })
      .catch(() => {});
  };

  let contenido: JSX.Element;

  if (vista === "historial") {
    contenido = <HistorialView onVolver={() => setVista("turno")} />;
  } else if (vista === "liquidaciones") {
    contenido = <LiquidacionesView onVolver={() => setVista("turno")} />;
  } else if (vista === "perfil") {
    contenido = <PerfilPropio mostrarFoto />;
  } else if (vista === "ajustes") {
    contenido = <AjustesPropios version="0.1.0" mostrarTurno />;
  } else if (vista === "ayuda") {
    contenido = (
      <CentroAyuda
        preguntas={PREGUNTAS_FRECUENTES_CONDUCTOR}
        correoContacto="soporte@urbanfleet.example"
        telefonoContacto="+593900000000"
      />
    );
  } else if (estado === "FUERA_DE_LINEA") {
    // Sin turno activo todavía no hay nada que centrar en un mapa (spec
    // deja a criterio de esta implementación el comportamiento en estado
    // inactivo) — se mantiene la tarjeta simple de antes, sin mapa.
    contenido = (
      <Card>
        <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>Mi turno</h1>
        <p style={{ color: "var(--color-text-muted)" }}>Socio conductor: {actor?.sub}</p>
        <p style={{ margin: "var(--space-2) 0" }}>
          Estado: <strong>{estado}</strong>
        </p>
        {error && (
          <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", whiteSpace: "pre-wrap" }}>
            {error}
          </p>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
          <Button onClick={iniciarTurno} loading={cargando}>
            Iniciar turno
          </Button>
        </div>
      </Card>
    );
  } else {
    // CU-O06/CU-O07/CU-O08: turno activo (DISPONIBLE u OCUPADO) — el mapa se
    // monta una sola vez acá y se mantiene montado mientras cambian
    // oferta/viajeAsignado; solo el panel que flota encima cambia de
    // contenido. Nunca se recrea <DriverMap> al llegar/aceptar/finalizar
    // una oferta.
    let panel: JSX.Element;
    let recogida: { lat: number; lon: number } | null = null;
    let destino: { lat: number; lon: number } | null = null;
    let vaHaciaRecogida = true;

    if (viajeAsignado) {
      recogida = { lat: viajeAsignado.origen_lat, lon: viajeAsignado.origen_lon };
      destino =
        viajeAsignado.destino_lat !== null && viajeAsignado.destino_lon !== null
          ? { lat: viajeAsignado.destino_lat, lon: viajeAsignado.destino_lon }
          : null;
      vaHaciaRecogida = viajeAsignado.estado === "ASIGNADO" || viajeAsignado.estado === "EN_CAMINO";

      const liberar = () => {
        setViajeAsignado(null);
        setPago(null);
        setEstado("DISPONIBLE");
      };
      const refrescarTrasPago = (resultado: { estado: string; diferencia: number | null }) => {
        setPago(resultado);
        apiFetch<ViajeAsignado>(`/viajes/${viajeAsignado.id}`)
          .then(setViajeAsignado)
          .catch(() => {});
      };
      // CU-O09: mientras el viaje esté FINALIZADO y no se haya intentado un
      // pago todavía, se pide "Pago recibido" antes que nada — la
      // calificación (CU-O08 paso 5) queda disponible después, sin importar
      // si el pago validó o quedó en discrepancia (son preocupaciones
      // separadas).
      const pagoPendiente = viajeAsignado.estado === "FINALIZADO" && !pago;
      const puedeCalificar =
        (viajeAsignado.estado === "PAGADO" || (viajeAsignado.estado === "FINALIZADO" && pago)) &&
        !viajeAsignado.calificacion_conductor_a_pasajero;
      panel = (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <ViajeAsignadoCard viaje={viajeAsignado} onActualizado={setViajeAsignado} onLiberado={liberar} />
          {pagoPendiente && viajeAsignado.tarifa_final !== null && (
            <PagoForm
              viajeId={viajeAsignado.id}
              tarifaFinal={viajeAsignado.tarifa_final}
              onRegistrado={refrescarTrasPago}
            />
          )}
          {pago?.estado === "DISCREPANCIA" && (
            <Card>
              <p style={{ color: "var(--color-danger)", margin: 0 }}>
                El monto no coincide con la tarifa (diferencia: ${pago.diferencia?.toFixed(2)}). Queda registrado
                para revisión del Administrador Financiero — el viaje no pasa a liquidación todavía.
              </p>
            </Card>
          )}
          {puedeCalificar && <CalificarPasajeroForm viajeId={viajeAsignado.id} onListo={liberar} />}
        </div>
      );
    } else if (oferta) {
      recogida = { lat: oferta.origen_lat, lon: oferta.origen_lon };
      panel = <OfertaModal oferta={oferta} onRespondida={onOfertaRespondida} />;
    } else {
      panel = (
        <Card>
          <p style={{ margin: 0 }}>
            Estado: <strong>{estado}</strong>
          </p>
          {error && (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", whiteSpace: "pre-wrap" }}>
              {error}
            </p>
          )}
          {mensaje && <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}
          <div style={{ display: "flex", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
            <Button onClick={reportarPosicion} variant="secondary">
              Actualizar posición
            </Button>
            <Button onClick={terminarTurno} loading={cargando} variant="danger">
              Terminar turno
            </Button>
          </div>
        </Card>
      );
    }

    // Ruta simple (línea recta, sin motor de ruteo — fuera de alcance de
    // este proyecto): hacia la recogida del pasajero mientras el conductor
    // no ha iniciado el viaje, y de la recogida al destino una vez en curso.
    let ruta: [number, number][] | null = null;
    if (posicionPropia && recogida && vaHaciaRecogida) {
      ruta = [
        [posicionPropia.lat, posicionPropia.lon],
        [recogida.lat, recogida.lon],
      ];
    } else if (recogida && destino) {
      ruta = [
        [recogida.lat, recogida.lon],
        [destino.lat, destino.lon],
      ];
    }

    contenido = (
      // Rediseño (ronda de correcciones tras UX complementaria): el mapa
      // llena todo el alto disponible de la pantalla (ver `llenarAltura` en
      // DriverMap) en vez de un recuadro fijo de 480px, y el panel ya no
      // tiene un tope duro de 260px que forzaba scroll interno — el tope
      // ahora es relativo al alto real del mapa. Mismo patrón que RideMap
      // en web-pasajero.
      <div style={{ position: "relative", flex: 1, minHeight: "320px" }}>
        {posicionPropia ? (
          <DriverMap
            propia={posicionPropia}
            recogida={recogida}
            destino={destino}
            ruta={ruta}
            llenarAltura
            onUbicacionEncontrada={(lat, lon) => {
              setPosicionPropia({ lat, lon });
              setError(null);
            }}
            onUbicacionError={setError}
          />
        ) : (
          <div
            style={{
              height: "100%",
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
            {error ?? "Obteniendo tu ubicación para centrar el mapa…"}
          </div>
        )}
        {/* Compacto (ancho al contenido, no todo el mapa) y zIndex muy por
            encima de los controles internos de Leaflet (.leaflet-top/
            .leaflet-bottom usan z-index:1000 en su propio CSS) — corregido
            tras hallazgo en pruebas reales: con zIndex:10 el panel quedaba
            visualmente tapado por el mapa. */}
        <div
          style={{
            position: "absolute",
            left: "var(--space-3)",
            bottom: "var(--space-3)",
            width: "min(340px, calc(100% - 2 * var(--space-3)))",
            maxHeight: "calc(100% - 2 * var(--space-3))",
            overflowY: "auto",
            zIndex: 1001,
          }}
        >
          {panel}
        </div>
      </div>
    );
  }

  return (
    <AppShell
      navItems={NAV_ITEMS_CONDUCTOR}
      activeId={vista}
      onNavigate={(id) => setVista(id as "turno" | "historial" | "liquidaciones" | "perfil" | "ajustes" | "ayuda")}
      headerActions={<NotificacionesBell />}
    >
      <div
        style={
          // Mapa del turno activo: llena todo el alto disponible (ver
          // `contenido` arriba). El resto de secciones siguen con su alto
          // natural de contenido.
          vista === "turno" && estado !== "FUERA_DE_LINEA"
            ? { width: "100%", display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }
            : { width: "100%" }
        }
      >
        {contenido}
      </div>
    </AppShell>
  );
}

export default function App() {
  const { actor } = useAuth();
  const [vista, setVista] = useState<"login" | "postulacion" | "postulacion-enviada">("login");

  if (actor) {
    return <PantallaTurno />;
  }

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
      <div style={{ width: "min(440px, 100%)" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--space-4)" }}>
          <img src={logoUrbanFleetFull} alt="UrbanFleet" style={{ width: 160, maxWidth: "100%", height: "auto" }} />
        </div>
        {vista === "login" && <LoginCard onPostular={() => setVista("postulacion")} />}
        {vista === "postulacion" && <PostulacionForm onEnviada={() => setVista("postulacion-enviada")} />}
        {vista === "postulacion-enviada" && (
          <Card>
            <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
              Solicitud enviada
            </h1>
            <p style={{ color: "var(--color-text-muted)" }}>
              Te contactaremos por teléfono cuando la revisemos. Puedes iniciar sesión con tu teléfono y la
              contraseña que definiste una vez aprobada.
            </p>
            <Button onClick={() => setVista("login")}>Volver al inicio de sesión</Button>
          </Card>
        )}
      </div>
    </div>
  );
}
