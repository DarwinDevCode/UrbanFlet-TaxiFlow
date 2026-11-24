import {
  AjustesPropios,
  ApiError,
  Alert,
  Avatar,
  Badge,
  apiFetch,
  BuscadorLugar,
  Button,
  CalleShell,
  Card,
  CentroAyuda,
  DataTable,
  DesgloseTarifa,
  DetailField,
  DetailPanel,
  distanciaKm,
  EvidenciaImagen,
  estimarRuta,
  KpiCard,
  LandingPage,
  LoginLogo,
  MapaRutaViaje,
  MapOverlayCard,
  nombreTipoDocumento,
  NotificacionesBell,
  PasswordField,
  PerfilPropio,
  SeccionNotificaciones,
  Select,
  subirArchivo,
  TextArea,
  TextField,
  tokenStorage,
  UMBRAL_DESVIO_RUTA_KM,
  useAuth,
  type DesgloseTarifaValores,
  type PreguntaFrecuente,
  FileField,
} from "@urbanflet/shared-ui";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
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

// Catálogos Ronda 1 (Ola 1.6): "Modelo" quedaba lleno de años en 76 de 81
// vehículos reales (auditoría §2.3) -- la gente confunde este campo con
// "Año", contiguo en el formulario. Detecta 4 dígitos en rango de año
// plausible (1900-2099) para avisar antes de enviar, sin bloquear un modelo
// legítimo que por coincidencia sea numérico (no hay ninguno en los datos
// reales, pero no vale la pena arriesgar un falso bloqueo).
const MODELO_PARECE_ANIO = /^(19|20)\d{2}$/;

// Revisión general de "Otro" (auditoría posterior a la Ronda 2 de flujo de
// fallas): mismo sentinel/patrón ya usado por el selector de taller en
// web-interno (Mantenimiento.tsx::TALLER_OTRO) -- ninguno de estos 4
// selectores (marca, color, motivo de cancelación, tipo de falla) lo tenía
// todavía, pese a estar cableados contra un catálogo desde Ronda 1/Fase C.
const MARCA_OTRO = "__otro__";
const COLOR_OTRO = "__otro__";
const MOTIVO_OTRO = "__otro__";

/** Un documento de la postulación: archivo + fecha de caducidad, con
 * previsualización local del archivo elegido (aún no subido -- la subida real
 * ocurre al enviar, ver `enviar()` en PostulacionForm). Mismo par
 * FileField + previsualización que ya usa "Mis documentos" para una
 * renovación, sin inventar un control nuevo. */
function DocumentoPostulacion({
  titulo,
  archivo,
  onArchivo,
  vencimiento,
  onVencimiento,
}: {
  titulo: string;
  archivo: File | null;
  onArchivo: (f: File | null) => void;
  vencimiento: string;
  onVencimiento: (v: string) => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!archivo) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(archivo);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <FileField
        label={titulo}
        accept="image/jpeg,image/png,image/webp"
        onChange={(e) => onArchivo(e.target.files?.[0] ?? null)}
      />
      {previewUrl && (
        <img
          src={previewUrl}
          alt={`Vista previa de ${titulo.toLowerCase()}`}
          style={{ maxWidth: 200, borderRadius: "var(--radius-sm)" }}
        />
      )}
      <TextField
        label={`Fecha de caducidad — ${titulo.toLowerCase()}`}
        type="date"
        value={vencimiento}
        onChange={(e) => onVencimiento(e.target.value)}
      />
    </div>
  );
}

function PostulacionForm({ onEnviada }: { onEnviada: () => void }) {
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmar, setPasswordConfirmar] = useState("");
  const [cedula, setCedula] = useState("");
  const [licencia, setLicencia] = useState("");
  const [placa, setPlaca] = useState("");
  const [marcaSeleccion, setMarcaSeleccion] = useState("");
  const [marcaLibre, setMarcaLibre] = useState("");
  const [modelo, setModelo] = useState("");
  const [anio, setAnio] = useState("");
  const [colorSeleccion, setColorSeleccion] = useState("");
  const [colorLibre, setColorLibre] = useState("");
  const [capacidad, setCapacidad] = useState("4");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  // Gestión documental en la postulación (Fase 1, CU-O01 paso 2: "adjunta
  // los documentos requeridos"). Hasta esta ronda el formulario mandaba
  // `documentos: []` y el texto de arriba prometía un "paso posterior" que
  // no existía en ninguna pantalla. Los 2 tipos exigidos salen del catálogo
  // real `tipos_documento` (LICENCIA_CONDUCIR es del conductor,
  // MATRICULA_VEHICULAR es del vehículo) -- no son literales inventados acá.
  const [archivoLicencia, setArchivoLicencia] = useState<File | null>(null);
  const [vencimientoLicencia, setVencimientoLicencia] = useState("");
  const [archivoMatricula, setArchivoMatricula] = useState<File | null>(null);
  const [vencimientoMatricula, setVencimientoMatricula] = useState("");
  const [paso, setPaso] = useState<string | null>(null);
  // Catálogos Ronda 1 (Ola 1.5): marcas_vehiculo/colores_vehiculo son
  // catálogos nuevos, consumidos aquí sin sesión (formulario público de
  // postulación, CU-O01) -- ver catalogos/router.py (lectura pública, sin
  // Depends de actor).
  const [marcas, setMarcas] = useState<{ id: string; nombre: string }[]>([]);
  const [colores, setColores] = useState<{ id: string; nombre: string }[]>([]);

  useEffect(() => {
    apiFetch<{ id: string; nombre: string }[]>("/catalogos/marcas-vehiculo", { auth: false })
      .then(setMarcas)
      .catch(() => {});
    apiFetch<{ id: string; nombre: string }[]>("/catalogos/colores-vehiculo", { auth: false })
      .then(setColores)
      .catch(() => {});
  }, []);

  const modeloPareceAnio = MODELO_PARECE_ANIO.test(modelo.trim());
  // Revisión general de "Otro": mismo criterio que tallerFinal en
  // Mantenimiento.tsx -- el valor libre se guarda tal cual, sin FK.
  const marcaFinal = marcaSeleccion === MARCA_OTRO ? marcaLibre.trim() : marcaSeleccion;
  const colorFinal = colorSeleccion === COLOR_OTRO ? colorLibre.trim() : colorSeleccion;

  const camposCompletos =
    nombre &&
    telefono &&
    password.length >= 8 &&
    password === passwordConfirmar &&
    cedula &&
    licencia &&
    placa &&
    marcaFinal &&
    modelo &&
    !modeloPareceAnio &&
    anio &&
    colorFinal &&
    capacidad &&
    archivoLicencia &&
    vencimientoLicencia &&
    archivoMatricula &&
    vencimientoMatricula;

  // Fase 1 de gestión documental: el envío pasó de 1 a 3 llamadas, y el orden
  // NO es negociable. `POST /archivos` exige un actor autenticado, y la cuenta
  // del postulante recién existe después de crear la solicitud -- así que
  // primero se crea en BORRADOR (`enviar: false`, sin efectos de bandeja:
  // nadie la ve ni se notifica a Captación todavía), luego se inicia sesión
  // con las credenciales que el propio postulante acaba de definir, se suben
  // los archivos, y recién ahí `POST /captacion/solicitudes/mia/documentos`
  // los adjunta y pasa la solicitud a ENVIADA de una sola vez. Si algo falla
  // a mitad, la solicitud queda en BORRADOR (invisible para Captación) y el
  // postulante puede reintentar -- nunca queda una solicitud enviada sin sus
  // documentos.
  //
  // La sesión que se abre acá es puramente instrumental (subir los archivos
  // como su dueño) y se cierra en el `finally`: el postulante termina en la
  // pantalla de "Solicitud enviada" sin sesión, igual que antes de esta ronda.
  const enviar = async () => {
    setError(null);
    setCargando(true);
    try {
      setPaso("Creando tu solicitud…");
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
            marca: marcaFinal,
            modelo,
            anio: Number(anio),
            color: colorFinal,
            capacidad: Number(capacidad),
          },
          documentos: [],
          enviar: false,
        },
      });

      setPaso("Subiendo tus documentos…");
      const sesion = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        auth: false,
        body: { identificador: telefono, password },
      });
      tokenStorage.set(sesion.access_token, sesion.refresh_token);

      const subidaLicencia = await subirArchivo(archivoLicencia!, "documento_postulacion");
      const subidaMatricula = await subirArchivo(archivoMatricula!, "documento_postulacion");

      setPaso("Enviando la solicitud…");
      await apiFetch("/captacion/solicitudes/mia/documentos", {
        method: "POST",
        body: {
          documentos: [
            {
              tipo: "LICENCIA_CONDUCIR",
              propietario_tipo: "CONDUCTOR",
              archivo_id: subidaLicencia.id,
              fecha_vencimiento: vencimientoLicencia,
            },
            {
              tipo: "MATRICULA_VEHICULAR",
              propietario_tipo: "VEHICULO",
              archivo_id: subidaMatricula.id,
              fecha_vencimiento: vencimientoMatricula,
            },
          ],
        },
      });
      onEnviada();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo enviar la solicitud");
    } finally {
      tokenStorage.clear();
      setPaso(null);
      setCargando(false);
    }
  };

  return (
    <Card>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-2)",
        }}
      >
        Postula a socio conductor
      </h1>
      <p style={{ color: "var(--color-text-muted)", marginTop: 0, marginBottom: "var(--space-4)" }}>
        Revisaremos tu solicitud en un plazo de hasta 5 días hábiles. Necesitamos tu licencia de conducir y
        la matrícula del vehículo, con su fecha de caducidad — sin esas dos no podemos procesar la
        postulación. La contraseña que definas aquí es la que usarás para iniciar sesión una vez aprobada
        tu solicitud.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <TextField label="Nombre completo" value={nombre} onChange={(e) => setNombre(e.target.value)} />
        <TextField label="Teléfono" type="tel" placeholder="+593..." value={telefono} onChange={(e) => setTelefono(e.target.value)} />
        <PasswordField
          label="Contraseña (mínimo 8 caracteres)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <PasswordField
          label="Confirmar contraseña"
          value={passwordConfirmar}
          onChange={(e) => setPasswordConfirmar(e.target.value)}
          confirmarContra={password}
        />
        <TextField label="Cédula" value={cedula} onChange={(e) => setCedula(e.target.value)} />
        <TextField label="Número de licencia" value={licencia} onChange={(e) => setLicencia(e.target.value)} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <TextField label="Placa" value={placa} onChange={(e) => setPlaca(e.target.value.toUpperCase())} />
          <TextField
            label="Año"
            type="number"
            min={1950}
            max={2100}
            step={1}
            bloquearNegativo
            value={anio}
            onChange={(e) => setAnio(e.target.value)}
          />
          <Select
            label="Marca"
            value={marcaSeleccion}
            onChange={(e) => setMarcaSeleccion(e.target.value)}
            options={[
              { value: "", label: "Selecciona una marca" },
              ...marcas.map((m) => ({ value: m.nombre, label: m.nombre })),
              { value: MARCA_OTRO, label: "Otro (no está en la lista)…" },
            ]}
          />
          {marcaSeleccion === MARCA_OTRO && (
            <TextField label="Nombre de la marca" value={marcaLibre} onChange={(e) => setMarcaLibre(e.target.value)} />
          )}
          <TextField
            label="Modelo (ej. Yaris, Sail)"
            placeholder="Ej. Yaris, Sail, Aveo"
            value={modelo}
            onChange={(e) => setModelo(e.target.value)}
            error={modeloPareceAnio ? "Ingresa el modelo del vehículo, no el año (el año va en el campo de arriba)" : undefined}
          />
          <Select
            label="Color"
            value={colorSeleccion}
            onChange={(e) => setColorSeleccion(e.target.value)}
            options={[
              { value: "", label: "Selecciona un color" },
              ...colores.map((c) => ({ value: c.nombre, label: c.nombre })),
              { value: COLOR_OTRO, label: "Otro (no está en la lista)…" },
            ]}
          />
          {colorSeleccion === COLOR_OTRO && (
            <TextField label="Nombre del color" value={colorLibre} onChange={(e) => setColorLibre(e.target.value)} />
          )}
          <TextField
            label="Capacidad"
            type="number"
            min={1}
            max={20}
            step={1}
            bloquearNegativo
            value={capacidad}
            onChange={(e) => setCapacidad(e.target.value)}
          />
        </div>

        <div
          style={{
            borderTop: "1px solid var(--color-border)",
            paddingTop: "var(--space-3)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-3)",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Documentos</h2>
          <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Sube una foto o escaneo legible de cada documento (JPG, PNG o WEBP, máximo 5 MB). La fecha de
            caducidad es la que usaremos para avisarte antes de que venza.
          </p>
          <DocumentoPostulacion
            titulo="Licencia de conducir"
            archivo={archivoLicencia}
            onArchivo={setArchivoLicencia}
            vencimiento={vencimientoLicencia}
            onVencimiento={setVencimientoLicencia}
          />
          <DocumentoPostulacion
            titulo="Matrícula del vehículo"
            archivo={archivoMatricula}
            onArchivo={setArchivoMatricula}
            vencimiento={vencimientoMatricula}
            onVencimiento={setVencimientoMatricula}
          />
        </div>

        {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
        {paso && (
          <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{paso}</span>
        )}
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
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-2)",
        }}
      >
        Portal del socio conductor
      </h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <TextField
          label="Teléfono o correo"
          value={identificador}
          onChange={(e) => setIdentificador(e.target.value)}
        />
        <PasswordField label="Contraseña" value={password} onChange={(e) => setPassword(e.target.value)} />
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

// Bitácora de revisión (2026-08-26, hallazgo #7): antes se mostraba el enum
// crudo del backend ("Estado: FUERA_DE_LINEA") en 2 lugares -- el badge del
// resumen minimizado ya lo traducía con un ternario propio, ahora los 3
// comparten esta misma etiqueta.
const ETIQUETA_ESTADO_TURNO: Record<EstadoServicio, string> = {
  FUERA_DE_LINEA: "Fuera de línea",
  DISPONIBLE: "Disponible",
  OCUPADO: "Ocupado",
};

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
  min_espera: number | null;
  tarifa_final: number | null;
  desglose_tarifa: DesgloseTarifaValores | null;
  calificacion_conductor_a_pasajero: { puntaje: number } | null;
}

function OfertaModal({
  oferta,
  onRespondida,
}: {
  oferta: OfertaActual;
  onRespondida: (aceptada: boolean, motivoFallo?: string) => void;
}) {
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
    } catch (e) {
      // La oferta pudo expirar o ya no estar disponible (A1/A2) — el próximo
      // poll de oferta-actual refleja el estado real. Bitácora de revisión
      // (hallazgo #7): antes esto fallaba en silencio -- el modal
      // desaparecía sin decir por qué, indistinguible de un rechazo. Ahora
      // se propaga el motivo para que se muestre un aviso.
      onRespondida(false, e instanceof ApiError ? e.message : "No se pudo responder a la oferta");
    } finally {
      setRespondiendo(false);
    }
  };

  // CU-O06: overlay flotante sobre el mapa persistente (ver PantallaTurno),
  // ya no una pantalla completa desconectada de él — el pasajero ya se ve
  // como marcador de recogida detrás de este panel.
  return (
    <Card>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-2)",
        }}
      >
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
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-2)",
        }}
      >
        Pago recibido
      </h1>
      <p style={{ color: "var(--color-text-muted)", margin: "0 0 var(--space-3)" }}>
        Tarifa a cobrar: ${tarifaFinal.toFixed(2)}
      </p>
      <TextField
        label="Monto cobrado en efectivo"
        type="number"
        min={0}
        step={0.01}
        bloquearNegativo
        value={monto}
        onChange={(e) => setMonto(e.target.value)}
      />
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
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-2)",
        }}
      >
        Califica al pasajero
      </h1>
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

// Ronda 2 del flujo de fallas, Fase C (CU-O07 A4): reporte de falla del
// conductor, con o sin viaje activo -- misma forma de formulario en ambos
// casos, distinguidos solo por si `viajeId` viene o no (el checkbox "no
// puedo continuar" solo tiene sentido con un viaje EN_CURSO de por medio).
function ReportarFallaForm({
  viajeId,
  posicionConocida,
  onCerrar,
  onEnviado,
}: {
  viajeId: string | null;
  posicionConocida: { lat: number; lon: number } | null;
  onCerrar: () => void;
  onEnviado: (viajeCancelado: boolean) => void;
}) {
  const [tipos, setTipos] = useState<{ id: string; nombre: string }[]>([]);
  const [cargandoTipos, setCargandoTipos] = useState(true);
  const [tipoFalla, setTipoFalla] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [impideContinuar, setImpideContinuar] = useState(false);
  const [evidencia, setEvidencia] = useState<{ id: string; previewUrl: string } | null>(null);
  const [subiendoEvidencia, setSubiendoEvidencia] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ id: string; nombre: string }[]>("/catalogos/motivos?categoria=incidencia")
      .then(setTipos)
      .catch(() => setError("No se pudieron cargar los tipos de falla"))
      .finally(() => setCargandoTipos(false));
  }, []);

  const seleccionarEvidencia = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setSubiendoEvidencia(true);
    try {
      const subido = await subirArchivo(file, "reporte_falla");
      setEvidencia({ id: subido.id, previewUrl: URL.createObjectURL(file) });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo subir la foto");
    } finally {
      setSubiendoEvidencia(false);
    }
  };

  // Fuera de un viaje (patio / fin de turno) `posicionConocida` puede no
  // existir todavía -- se pide la ubicación en el momento en vez de
  // bloquear el formulario hasta que el polling de turno la resuelva sola.
  const obtenerPosicion = (): Promise<{ lat: number; lon: number }> => {
    if (posicionConocida) return Promise.resolve(posicionConocida);
    return new Promise((resolve, reject) => {
      if (!("geolocation" in navigator)) {
        reject(new Error("Este navegador no soporta geolocalización"));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => reject(new Error("No se pudo obtener tu ubicación — revisa el permiso de geolocalización")),
        { enableHighAccuracy: true },
      );
    });
  };

  const enviar = async () => {
    if (!tipoFalla || !descripcion.trim()) return;
    setError(null);
    setEnviando(true);
    try {
      const { lat, lon } = await obtenerPosicion();
      const reporte = await apiFetch<{ impide_continuar: boolean; viaje_id: string | null }>("/reportes-falla", {
        method: "POST",
        body: {
          tipo_falla: tipoFalla,
          descripcion: descripcion.trim(),
          lat,
          lon,
          impide_continuar: viajeId ? impideContinuar : false,
          evidencias: evidencia ? [evidencia.id] : [],
        },
      });
      onEnviado(reporte.impide_continuar && reporte.viaje_id !== null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "No se pudo enviar el reporte");
    } finally {
      setEnviando(false);
    }
  };

  // Grupo B de la ronda de correcciones UX/UI: antes era un <Card> suelto
  // embutido dentro del panel flotante del mapa (340px de ancho, sin el
  // chrome de modal del resto del sistema). Ahora usa el MISMO DetailPanel
  // que las pantallas de web-interno -- encabezado, chip de modo, y
  // Aceptar/Salir en posición fija -- en vez de un patrón propio.
  return (
    <DetailPanel
      titulo={viajeId ? "Registrar incidencia" : "Reportar falla del vehículo"}
      modo="nuevo"
      onAceptar={enviar}
      aceptarLabel="Enviar reporte"
      aceptarLoading={enviando}
      aceptarDisabled={!tipoFalla || !descripcion.trim() || subiendoEvidencia}
      onSalir={onCerrar}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <Select
          label="Tipo de falla"
          value={tipoFalla}
          onChange={(e) => setTipoFalla(e.target.value)}
          options={[
            { value: "", label: cargandoTipos ? "Cargando…" : "Selecciona un tipo" },
            ...tipos.map((t) => ({ value: t.nombre, label: t.nombre })),
          ]}
        />
        <TextArea label="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
        {viajeId && (
          <label style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
            <input
              type="checkbox"
              checked={impideContinuar}
              onChange={(e) => setImpideContinuar(e.target.checked)}
            />
            No puedo continuar el viaje por esta falla
          </label>
        )}
        <div>
          <FileField
            label="Foto de evidencia (opcional)"
            accept="image/jpeg,image/png,image/webp"
            onChange={seleccionarEvidencia}
            disabled={subiendoEvidencia}
          />
          {evidencia && (
            <img
              src={evidencia.previewUrl}
              alt="Evidencia de la falla"
              style={{ maxWidth: "160px", marginTop: "var(--space-2)", borderRadius: "var(--radius-sm)" }}
            />
          )}
        </div>
        {viajeId && impideContinuar && (
          <p style={{ color: "var(--color-warning)", fontSize: "var(--font-size-sm)", margin: 0 }}>
            Se cancelará tu viaje actual y se buscará otro conductor para el pasajero desde tu posición.
          </p>
        )}
        {error && (
          <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", whiteSpace: "pre-wrap" }}>
            {error}
          </p>
        )}
      </div>
    </DetailPanel>
  );
}

// ---------------------------------------------------------------------------
// Grupo B de la ronda de correcciones UX/UI: el conductor podía CREAR un
// reporte de falla pero no volver a verlo -- el flujo terminaba en el envío.
// Esta sección cierra el ciclo con el mismo patrón de lista/detalle del resto
// del sistema (DataTable + DetailPanel), sin inventar uno nuevo.
// ---------------------------------------------------------------------------

interface ReporteFalla {
  id: string;
  vehiculo_placa: string | null;
  viaje_id: string | null;
  tipo_falla: string;
  descripcion: string;
  ts: string;
  impide_continuar: boolean;
  estado: "PENDIENTE" | "CONVERTIDO_A_ORDEN" | "DESCARTADO";
  orden_id: string | null;
  evidencias: string[];
  motivo_descarte: string | null;
}

const ETIQUETA_ESTADO_REPORTE: Record<ReporteFalla["estado"], string> = {
  PENDIENTE: "En revisión",
  CONVERTIDO_A_ORDEN: "Convertido en orden",
  DESCARTADO: "Descartado",
};

const TONO_ESTADO_REPORTE: Record<ReporteFalla["estado"], "neutral" | "exito" | "advertencia" | "peligro"> = {
  PENDIENTE: "advertencia",
  CONVERTIDO_A_ORDEN: "exito",
  DESCARTADO: "neutral",
};

function FallasView({ posicionConocida }: { posicionConocida: { lat: number; lon: number } | null }) {
  const [items, setItems] = useState<ReporteFalla[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seleccionado, setSeleccionado] = useState<ReporteFalla | null>(null);
  const [reportando, setReportando] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const cargar = () => {
    setCargando(true);
    apiFetch<ReporteFalla[]>("/reportes-falla/mias")
      .then((datos) => {
        setItems(datos);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar tus reportes"))
      .finally(() => setCargando(false));
  };

  useEffect(cargar, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Card>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "var(--font-size-xl)",
            margin: 0,
            marginBottom: "var(--space-2)",
          }}
        >
          Fallas del vehículo
        </h1>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: 0 }}>
          Reporta una falla de tu vehículo y sigue en qué quedó cada reporte. El Jefe de Mantenimiento lo revisa y
          puede convertirlo en una orden de taller.
        </p>
        {mensaje && <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
          <div style={{ minWidth: 180 }}>
            <Button onClick={() => setReportando(true)}>Reportar una falla</Button>
          </div>
          <div style={{ minWidth: 140 }}>
            <Button variant="secondary" onClick={cargar} loading={cargando}>
              Actualizar
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={[
            { header: "Fecha", render: (r: ReporteFalla) => new Date(r.ts).toLocaleString() },
            { header: "Vehículo", render: (r: ReporteFalla) => r.vehiculo_placa ?? "—" },
            { header: "Tipo de falla", render: (r: ReporteFalla) => r.tipo_falla },
            {
              header: "Estado",
              render: (r: ReporteFalla) => (
                <Badge texto={ETIQUETA_ESTADO_REPORTE[r.estado]} tono={TONO_ESTADO_REPORTE[r.estado]} />
              ),
            },
            {
              header: "Evidencia",
              // v2: ícono real en vez del emoji "📷".
              render: (r: ReporteFalla) =>
                r.evidencias.length > 0 ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-label="Con evidencia fotográfica">
                    <path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" strokeLinejoin="round" />
                    <circle cx="12" cy="13" r="3.5" />
                  </svg>
                ) : (
                  "—"
                ),
            },
            {
              header: "",
              // Mismo patrón de apertura de detalle que las pantallas de
              // web-interno (botón en su propia columna, no clic en la fila).
              render: (r: ReporteFalla) => (
                <Button variant="secondary" onClick={() => setSeleccionado(r)}>
                  Ver
                </Button>
              ),
            },
          ]}
          rows={items}
          keyField={(r) => r.id}
          vacio={cargando ? "Cargando…" : "Todavía no reportaste ninguna falla."}
        />
      </Card>

      {seleccionado && (
        <DetailPanel titulo="Reporte de falla" modo="consulta" onSalir={() => setSeleccionado(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <DetailField
              label="Estado"
              value={
                <Badge
                  texto={ETIQUETA_ESTADO_REPORTE[seleccionado.estado]}
                  tono={TONO_ESTADO_REPORTE[seleccionado.estado]}
                />
              }
            />
            <DetailField label="Fecha del reporte" value={new Date(seleccionado.ts).toLocaleString()} />
            <DetailField label="Vehículo" value={seleccionado.vehiculo_placa ?? "—"} />
            <DetailField label="Tipo de falla" value={seleccionado.tipo_falla} />
            <DetailField label="Descripción" value={seleccionado.descripcion} />
            <DetailField
              label="Impidió continuar el viaje"
              value={seleccionado.impide_continuar ? "Sí — el viaje se canceló y se reasignó" : "No"}
            />
            {seleccionado.viaje_id && <DetailField label="Viaje asociado" value={seleccionado.viaje_id} />}
            {seleccionado.estado === "CONVERTIDO_A_ORDEN" && (
              <DetailField label="Orden de mantenimiento" value={seleccionado.orden_id ?? "—"} />
            )}
            {seleccionado.estado === "DESCARTADO" && (
              <DetailField label="Motivo del descarte" value={seleccionado.motivo_descarte ?? "—"} />
            )}
            <DetailField
              label="Evidencia fotográfica"
              value={
                seleccionado.evidencias.length === 0 ? (
                  "Sin fotos adjuntas"
                ) : (
                  <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                    {seleccionado.evidencias.map((id) => (
                      <EvidenciaImagen key={id} archivoId={id} tamano={200} alt="Evidencia de la falla" />
                    ))}
                  </div>
                )
              }
            />
          </div>
        </DetailPanel>
      )}

      {reportando && (
        <ReportarFallaForm
          viajeId={null}
          posicionConocida={posicionConocida}
          onCerrar={() => setReportando(false)}
          onEnviado={() => {
            setReportando(false);
            setMensaje("Reporte de falla enviado.");
            cargar();
          }}
        />
      )}
    </div>
  );
}

interface MiDocumento {
  id: string;
  tipo: string;
  fecha_vencimiento: string | null;
  estado_verificacion: string;
  dias_restantes: number | null;
  tiene_renovacion_pendiente: boolean;
  archivo_id: string | null;
}

function estadoVigencia(dias: number | null): { texto: string; tono: "exito" | "advertencia" | "peligro" } {
  if (dias === null) return { texto: "Sin fecha registrada", tono: "advertencia" };
  if (dias < 0) return { texto: "Vencido", tono: "peligro" };
  if (dias <= 30) return { texto: `Vence en ${dias} día${dias === 1 ? "" : "s"}`, tono: "advertencia" };
  return { texto: "Vigente", tono: "exito" };
}

/**
 * Autoservicio de renovación documental (cierre del gap real, ver
 * CLAUDE.md): antes de esto no existía NINGUNA pantalla desde donde un
 * conductor pudiera ver sus propios documentos ni subir una renovación --
 * la bandeja del Supervisor de Cumplimiento ("Buscar renovaciones
 * pendientes") estaba condenada a quedar vacía para siempre, sin importar
 * cuántos documentos vencieran, porque no había forma humana de generar una
 * renovación pendiente. Reusa `GET /cumplimiento/documentos/mios` (nuevo,
 * acotado por `actor.usuario_id`) y el mismo mecanismo de carga de
 * archivos ya usado para evidencia de fallas -- `subirArchivo(file,
 * "documento_renovacion")` -- no un sistema de subida paralelo.
 */
function MisDocumentosView() {
  const [items, setItems] = useState<MiDocumento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [renovando, setRenovando] = useState<MiDocumento | null>(null);
  const [archivo, setArchivo] = useState<{ id: string; previewUrl: string } | null>(null);
  const [subiendoArchivo, setSubiendoArchivo] = useState(false);
  const [fechaVencimientoNueva, setFechaVencimientoNueva] = useState("");
  const [enviando, setEnviando] = useState(false);
  const vencidos = items.filter((d) => d.dias_restantes !== null && d.dias_restantes < 0);

  const cargar = () => {
    setCargando(true);
    apiFetch<MiDocumento[]>("/cumplimiento/documentos/mios")
      .then((datos) => {
        setItems(datos);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar tus documentos"))
      .finally(() => setCargando(false));
  };

  useEffect(cargar, []);

  const abrirRenovacion = (doc: MiDocumento) => {
    setRenovando(doc);
    setArchivo(null);
    setFechaVencimientoNueva("");
    setError(null);
  };

  const seleccionarArchivo = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setSubiendoArchivo(true);
    try {
      const subido = await subirArchivo(file, "documento_renovacion");
      setArchivo({ id: subido.id, previewUrl: URL.createObjectURL(file) });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo subir el archivo");
    } finally {
      setSubiendoArchivo(false);
    }
  };

  const enviarRenovacion = async () => {
    if (!renovando || !archivo || !fechaVencimientoNueva) return;
    setError(null);
    setEnviando(true);
    try {
      await apiFetch(`/cumplimiento/documentos/${renovando.id}/renovacion`, {
        method: "POST",
        body: { archivo_id: archivo.id, fecha_vencimiento: fechaVencimientoNueva },
      });
      setRenovando(null);
      setMensaje("Renovación enviada — el Supervisor de Cumplimiento la va a revisar.");
      cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo enviar la renovación");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Card>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "var(--font-size-xl)",
            margin: 0,
            marginBottom: "var(--space-2)",
          }}
        >
          Mis documentos
        </h1>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: 0 }}>
          Tu licencia y la matrícula de tu vehículo, con su vigencia real. Si alguno está vencido o por vencer,
          subí la renovación acá mismo.
        </p>
        {/* Advertencia visible por documentación vencida. Es SOLO un aviso:
            no bloquea iniciar turno, aceptar ofertas ni ninguna otra acción.
            Activar un bloqueo automático por documentación vencida afecta la
            capacidad de un socio de trabajar y es una decisión operativa de
            la cooperativa — queda pendiente, deliberadamente sin activar. */}
        {vencidos.length > 0 && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <Alert tono="peligro">
              <strong>
                {vencidos.length === 1
                  ? "Tenés 1 documento vencido."
                  : `Tenés ${vencidos.length} documentos vencidos.`}
              </strong>{" "}
              {vencidos.map((d) => nombreTipoDocumento(d.tipo)).join(", ")}. Subí la renovación
              cuanto antes para regularizar tu situación con la cooperativa.
            </Alert>
          </div>
        )}
        {mensaje && <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}
        {error && !renovando && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <div style={{ minWidth: 140 }}>
          <Button variant="secondary" onClick={cargar} loading={cargando}>
            Actualizar
          </Button>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={[
            {
              header: "Evidencia",
              render: (d: MiDocumento) =>
                d.archivo_id ? (
                  <EvidenciaImagen archivoId={d.archivo_id} tamano={48} alt={`Documento ${nombreTipoDocumento(d.tipo)}`} />
                ) : (
                  "—"
                ),
            },
            { header: "Documento", render: (d: MiDocumento) => nombreTipoDocumento(d.tipo) },
            {
              header: "Vence",
              render: (d: MiDocumento) => (d.fecha_vencimiento ? new Date(d.fecha_vencimiento).toLocaleDateString() : "—"),
            },
            {
              header: "Vigencia",
              render: (d: MiDocumento) => {
                const v = estadoVigencia(d.dias_restantes);
                return <Badge texto={v.texto} tono={v.tono} />;
              },
            },
            {
              header: "",
              render: (d: MiDocumento) =>
                d.tiene_renovacion_pendiente ? (
                  <Badge texto="Renovación en revisión" tono="advertencia" />
                ) : (
                  <Button variant="secondary" onClick={() => abrirRenovacion(d)}>
                    Subir renovación
                  </Button>
                ),
            },
          ]}
          rows={items}
          keyField={(d) => d.id}
          vacio={cargando ? "Cargando…" : "Todavía no tenés documentos registrados."}
        />
      </Card>

      {renovando && (
        <DetailPanel
          titulo={`Renovar ${nombreTipoDocumento(renovando.tipo)}`}
          modo="nuevo"
          onAceptar={enviarRenovacion}
          aceptarLabel="Enviar renovación"
          aceptarLoading={enviando}
          aceptarDisabled={!archivo || !fechaVencimientoNueva || subiendoArchivo}
          onSalir={() => setRenovando(null)}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <FileField
              label="Foto o escaneo del documento renovado"
              accept="image/jpeg,image/png,image/webp"
              onChange={seleccionarArchivo}
              disabled={subiendoArchivo}
            />
            {archivo && (
              <img
                src={archivo.previewUrl}
                alt="Documento renovado"
                style={{ maxWidth: "200px", borderRadius: "var(--radius-sm)" }}
              />
            )}
            <TextField
              label="Nueva fecha de vencimiento"
              type="date"
              value={fechaVencimientoNueva}
              onChange={(e) => setFechaVencimientoNueva(e.target.value)}
            />
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
              El Supervisor de Cumplimiento revisa la foto y confirma la fecha antes de que quede vigente.
            </p>
            {error && (
              <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}

// Ficha de mantenimiento del propio vehículo (autoservicio, ver
// GET /mantenimiento/vehiculos/mio/ficha) — mismo shape que
// mantenimiento/schemas.py::FichaVehiculoOut, sin campos nuevos.
interface MiFichaVehiculo {
  id: string;
  placa: string;
  marca: string;
  modelo: string;
  estado_habilitacion: string;
  km_acumulado: number;
  fecha_ultima_intervencion: string | null;
  km_ultima_intervencion: number | null;
  proxima_km_preventivo: number;
  le_toca_preventivo: boolean;
  umbral_km_preventivo: number;
}

function FichaVehiculoView() {
  const [ficha, setFicha] = useState<MiFichaVehiculo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [sinVehiculo, setSinVehiculo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = () => {
    setCargando(true);
    setSinVehiculo(false);
    setError(null);
    apiFetch<MiFichaVehiculo>("/mantenimiento/vehiculos/mio/ficha")
      .then((datos) => setFicha(datos))
      .catch((e) => {
        if (e instanceof ApiError && e.code === "VEHICULO_CONDUCTOR_NO_ASIGNADO") {
          setFicha(null);
          setSinVehiculo(true);
        } else {
          setError(e instanceof ApiError ? e.message : "No se pudo cargar la ficha de tu vehículo");
        }
      })
      .finally(() => setCargando(false));
  };

  useEffect(cargar, []);

  // Tope defensivo para que la marca de referencia nunca quede fuera de la
  // escala (0-1) — ver design.md D5. `|| 1` evita dividir por cero cuando
  // ambos valores son 0 (vehículo recién habilitado, sin ninguna orden).
  const tope = ficha ? Math.max(ficha.proxima_km_preventivo, ficha.km_acumulado, 1) : 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Card>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "var(--font-size-xl)",
            margin: 0,
            marginBottom: "var(--space-2)",
          }}
        >
          Mi vehículo
        </h1>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: 0 }}>
          Kilometraje acumulado, última intervención y próxima preventiva de tu vehículo.
        </p>
        {sinVehiculo && (
          <Alert tono="advertencia">
            Todavía no tenés un vehículo asignado — esta información va a aparecer en cuanto tu
            vehículo quede registrado.
          </Alert>
        )}
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <div style={{ minWidth: 140, marginTop: "var(--space-2)" }}>
          <Button variant="secondary" onClick={cargar} loading={cargando}>
            Actualizar
          </Button>
        </div>
      </Card>

      {ficha && (
        <>
          <Card>
            <KpiCard
              etiqueta={`${ficha.placa} — kilometraje acumulado`}
              valor={`${ficha.km_acumulado.toLocaleString("es-EC")} km`}
              tono={ficha.le_toca_preventivo ? "advertencia" : undefined}
              descripcion="Contra el umbral de la próxima preventiva"
              escala={ficha.km_acumulado / tope}
              referencia={ficha.proxima_km_preventivo / tope}
            />
          </Card>

          {ficha.le_toca_preventivo && (
            <Alert tono="advertencia">
              Le toca preventivo — el kilometraje acumulado ya superó lo proyectado para la
              próxima intervención. Coordiná con el Jefe de Mantenimiento.
            </Alert>
          )}

          <Card>
            <p style={{ margin: 0 }}>
              <strong>Última intervención: </strong>
              {ficha.fecha_ultima_intervencion && ficha.km_ultima_intervencion !== null
                ? `${new Date(ficha.fecha_ultima_intervencion).toLocaleDateString()} — ${ficha.km_ultima_intervencion.toLocaleString("es-EC")} km`
                : "Todavía no hay ninguna orden cerrada para este vehículo."}
            </p>
            <p style={{ margin: "var(--space-2) 0 0" }}>
              <strong>Próxima preventiva proyectada: </strong>
              {ficha.proxima_km_preventivo.toLocaleString("es-EC")} km (umbral de{" "}
              {ficha.umbral_km_preventivo.toLocaleString("es-EC")} km sobre la última intervención)
            </p>
          </Card>
        </>
      )}
    </div>
  );
}

function ViajeAsignadoCard({
  viaje,
  posicionPropia,
  onActualizado,
  onLiberado,
}: {
  viaje: ViajeAsignado;
  posicionPropia: { lat: number; lon: number } | null;
  onActualizado: (viaje: ViajeAsignado) => void;
  onLiberado: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [mostrarIncidencia, setMostrarIncidencia] = useState(false);
  // Catálogos Ronda 1 (Ola 1.3): antes se hardcodeaba `motivo: "cancelado
  // por el conductor"` -- CU-O07 A3 exige "selección obligatoria de
  // motivo", así que esto era un incumplimiento de spec, no solo una
  // mejora de UX. El backend ya aceptaba cualquier motivo (sin cambios
  // ahí); lo que faltaba era este selector.
  const [mostrarCancelacion, setMostrarCancelacion] = useState(false);
  const [motivosCancelacion, setMotivosCancelacion] = useState<{ id: string; nombre: string }[]>([]);
  const [motivoSeleccionado, setMotivoSeleccionado] = useState("");
  const [motivoLibre, setMotivoLibre] = useState("");
  const [cargandoMotivos, setCargandoMotivos] = useState(false);
  // Revisión general de "Otro": el motivo libre se guarda tal cual, mismo
  // criterio que tallerFinal.
  const motivoFinal = motivoSeleccionado === MOTIVO_OTRO ? motivoLibre.trim() : motivoSeleccionado;

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

  const abrirCancelacion = async () => {
    setError(null);
    setMostrarCancelacion(true);
    if (motivosCancelacion.length > 0) return;
    setCargandoMotivos(true);
    try {
      const datos = await apiFetch<{ id: string; nombre: string }[]>("/catalogos/motivos?categoria=cancelacion");
      setMotivosCancelacion(datos);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudieron cargar los motivos");
    } finally {
      setCargandoMotivos(false);
    }
  };

  const cancelar = async () => {
    if (!motivoFinal) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/viajes/conductor/cancelar", { method: "POST", body: { motivo: motivoFinal } });
      onLiberado();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cancelar");
    } finally {
      setCargando(false);
    }
  };

  if (mostrarIncidencia) {
    return (
      <ReportarFallaForm
        viajeId={viaje.id}
        posicionConocida={posicionPropia}
        onCerrar={() => setMostrarIncidencia(false)}
        onEnviado={(viajeCancelado) => {
          setMostrarIncidencia(false);
          if (viajeCancelado) onLiberado();
        }}
      />
    );
  }

  return (
    <Card>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-2)",
        }}
      >
        Viaje asignado
      </h1>
      {/* El estado del viaje se muestra (ya legible, no el enum crudo) en la
          franja de resumen de la tarjeta flotante, visible expandida y
          minimizada -- acá era además el valor crudo del backend. */}
      <p style={{ margin: "var(--space-1) 0" }}>Recoger en: {viaje.origen_direccion}</p>
      {viaje.destino_direccion && <p style={{ margin: "var(--space-1) 0" }}>Destino: {viaje.destino_direccion}</p>}
      {viaje.ts_llegada_origen && (
        <p style={{ margin: "var(--space-1) 0", color: "var(--color-text-muted)" }}>Llegada registrada</p>
      )}
      {(viaje.estado === "EN_CURSO" || viaje.estado === "FINALIZADO") && (
        <p style={{ margin: "var(--space-1) 0" }}>Distancia recorrida: {(viaje.km_recorridos ?? 0).toFixed(2)} km</p>
      )}
      {viaje.estado === "FINALIZADO" && viaje.tarifa_final !== null && (
        <>
          <p style={{ margin: "var(--space-1) 0" }}>Tarifa final: ${viaje.tarifa_final.toFixed(2)}</p>
          {viaje.desglose_tarifa && (
            <DesgloseTarifa
              desglose={viaje.desglose_tarifa}
              tarifaFinal={viaje.tarifa_final}
              kmRecorridos={viaje.km_recorridos}
              minEspera={viaje.min_espera}
            />
          )}
        </>
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
        {viaje.estado === "EN_CURSO" && (
          <Button variant="secondary" onClick={() => setMostrarIncidencia(true)}>
            Registrar incidencia
          </Button>
        )}
        {(viaje.estado === "ASIGNADO" || viaje.estado === "EN_CAMINO") && !mostrarCancelacion && (
          <Button variant="danger" onClick={abrirCancelacion}>
            Cancelar viaje
          </Button>
        )}
        {mostrarCancelacion && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <Select
              label="Motivo de la cancelación"
              value={motivoSeleccionado}
              onChange={(e) => setMotivoSeleccionado(e.target.value)}
              options={[
                { value: "", label: cargandoMotivos ? "Cargando…" : "Selecciona un motivo" },
                ...motivosCancelacion.map((m) => ({ value: m.nombre, label: m.nombre })),
                { value: MOTIVO_OTRO, label: "Otro (no está en la lista)…" },
              ]}
            />
            {motivoSeleccionado === MOTIVO_OTRO && (
              <TextField
                label="Describe el motivo"
                value={motivoLibre}
                onChange={(e) => setMotivoLibre(e.target.value)}
              />
            )}
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <Button variant="danger" onClick={cancelar} loading={cargando} disabled={!motivoFinal}>
                Confirmar cancelación
              </Button>
              <Button variant="secondary" onClick={() => setMostrarCancelacion(false)}>
                Volver
              </Button>
            </div>
          </div>
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
  pasajero_foto_url: string | null;
  calificacion_conductor_a_pasajero: { puntaje: number } | null;
}

// Etiquetas legibles del estado del viaje en curso — para el resumen de una
// línea de la tarjeta minimizada sobre el mapa (Grupo A de la ronda de
// correcciones UX/UI). Cualquier estado no listado cae al valor crudo.
const ETIQUETA_ESTADO_VIAJE: Record<string, string> = {
  ASIGNADO: "Asignado",
  EN_CAMINO: "En camino",
  EN_CURSO: "Viaje en curso",
  FINALIZADO: "Finalizado",
  PAGADO: "Pagado",
};

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
  // Coordenadas: hasta esta ronda el detalle del conductor no las tipaba (no
  // había mapa acá). El backend ya las devolvía siempre en `ViajeOut`.
  origen_lat: number;
  origen_lon: number;
  origen_direccion: string;
  destino_lat: number | null;
  destino_lon: number | null;
  destino_direccion: string | null;
  estado: string;
  tarifa_final: number | null;
  pasajero_nombre: string | null;
  pasajero_foto_url: string | null;
  // Traza GPS real del recorrido -- la acumuló este mismo conductor con sus
  // reportes de posición durante el viaje. Solo viene en el detalle.
  traza: [number, number][] | null;
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
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-4)",
        }}
      >
        Mis viajes
      </h1>
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
            // CU-O14 A2: solo nombre de pila, calificación y foto del pasajero
            // (mismo tipo de dato de identidad visual) — nunca teléfono ni ubicaciones.
            {
              header: "Pasajero",
              render: (v) =>
                v.pasajero_nombre ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <Avatar fotoUrl={v.pasajero_foto_url} nombre={v.pasajero_nombre} tamano={28} />
                    {v.pasajero_nombre}
                  </div>
                ) : (
                  "—"
                ),
            },
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
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {/* CU-O14 paso 3: mismo mapa de recorrido que ya usan
                  web-pasajero y web-interno -- dibuja la traza GPS real y, si
                  el viaje no la tiene, solo origen/destino con la nota
                  explícita, nunca una ruta fabricada. */}
              <MapaRutaViaje
                viajeId={seleccionado.id}
                origen={{ lat: seleccionado.origen_lat, lon: seleccionado.origen_lon }}
                destino={
                  seleccionado.destino_lat !== null && seleccionado.destino_lon !== null
                    ? { lat: seleccionado.destino_lat, lon: seleccionado.destino_lon }
                    : null
                }
                traza={seleccionado.traza}
                origenDireccion={seleccionado.origen_direccion}
                destinoDireccion={seleccionado.destino_direccion}
              />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Origen" value={seleccionado.origen_direccion} />
              <DetailField label="Destino" value={seleccionado.destino_direccion ?? "—"} />
              <DetailField
                label="Pasajero"
                value={
                  seleccionado.pasajero_nombre ? (
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Avatar fotoUrl={seleccionado.pasajero_foto_url} nombre={seleccionado.pasajero_nombre} tamano={32} />
                      {seleccionado.pasajero_nombre}
                    </div>
                  ) : (
                    "—"
                  )
                }
              />
              <DetailField
                label="Tarifa final"
                value={seleccionado.tarifa_final !== null ? `$${seleccionado.tarifa_final.toFixed(2)}` : "—"}
              />
              <DetailField label="Estado" value={<Badge texto={seleccionado.estado} tono={seleccionado.estado === "CANCELADO" ? "peligro" : "exito"} />} />
            </div>
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
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: "var(--font-size-xl)",
          margin: 0,
          marginBottom: "var(--space-4)",
        }}
      >
        Mis liquidaciones
      </h1>
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

// CU-O07 A6, registro en bitácora del recálculo por desvío: 1 intento +
// hasta 2 reintentos con backoff corto (1s, 3s) antes de darlo por perdido.
// El dominio (conductor en movimiento, cobertura variable) es justo donde
// una pérdida de señal momentánea es el caso típico, no el raro -- y la
// spec exige que el dato "quede para auditoría" -- así que un solo intento
// fire-and-forget se perdía en el escenario más común. Deliberadamente NO
// es una cola persistente ni un mecanismo genérico de reintento para toda
// la app: acotado a esta llamada, en memoria, sin sobrevivir un reload de
// página. Nunca bloquea ni retrasa el redibujado de la ruta -- se dispara
// después de `setRuta`, ver el useEffect de PantallaTurno.
const REINTENTOS_RECALCULO_RUTA_BACKOFF_MS = [1000, 3000];

async function registrarRecalculoRutaConReintento(body: {
  lat: number;
  lon: number;
  distancia_desvio_km: number;
  ruta_anterior: [number, number][];
  ruta_nueva: [number, number][];
}): Promise<void> {
  for (let intento = 0; ; intento++) {
    try {
      await apiFetch("/viajes/conductor/recalculo-ruta", { method: "POST", body });
      return;
    } catch {
      if (intento >= REINTENTOS_RECALCULO_RUTA_BACKOFF_MS.length) return;
      await new Promise((resolve) => setTimeout(resolve, REINTENTOS_RECALCULO_RUTA_BACKOFF_MS[intento]));
    }
  }
}

type VistaConductor =
  | "turno"
  | "historial"
  | "liquidaciones"
  | "fallas"
  | "documentos"
  | "vehiculo"
  | "notificaciones"
  | "perfil"
  | "ajustes"
  | "ayuda";

// Grupo D de la ronda de correcciones UX/UI: la navegación estaba plana, con
// lo operativo y lo de la cuenta personal mezclados en una sola lista. Ahora
// se separan en dos zonas -- mismo criterio "personal vs. funcional" que se
// aplica en los 3 portales, con los nombres de grupo que tienen sentido para
// cada uno. "Fallas del vehículo" (Grupo B) entra en la zona operativa: es
// del vehículo/turno, no de un viaje puntual.
function navItemsConductor(
  noLeidas: number,
  // Punto 6 de la ronda de auditoría de pantallas: una oferta puede llegar
  // (polling de PantallaTurno, corre sin importar la vista activa —
  // gateado solo a estado/viajeAsignado, nunca a `vista`) mientras el
  // conductor está mirando otra pantalla. Antes no había ninguna señal
  // visible hasta volver a "Mi turno" — mismo patrón ya usado para
  // notificaciones (badge numérico en el nav item), no uno nuevo. Se apaga
  // solo al volver a "Mi turno" (ahí ya se ve el modal de la oferta).
  ofertaPendienteFueraDeVista: boolean,
): { id: VistaConductor; label: string; group?: string; badge?: number }[] {
  return [
    { id: "turno", label: "Mi turno", group: "Operación", badge: ofertaPendienteFueraDeVista ? 1 : 0 },
    { id: "historial", label: "Mis viajes", group: "Operación" },
    { id: "liquidaciones", label: "Mis liquidaciones", group: "Operación" },
    { id: "fallas", label: "Fallas del vehículo", group: "Operación" },
    { id: "documentos", label: "Mis documentos", group: "Operación" },
    { id: "vehiculo", label: "Mi vehículo", group: "Operación" },
    { id: "perfil", label: "Mi perfil", group: "Mi cuenta" },
    { id: "notificaciones", label: "Notificaciones", group: "Mi cuenta", badge: noLeidas },
    { id: "ajustes", label: "Ajustes", group: "Mi cuenta" },
    { id: "ayuda", label: "Ayuda", group: "Mi cuenta" },
  ];
}

// Tipos reales que un socio conductor puede llegar a recibir (Fase 0 de
// esta ronda, confirmado por grep de cada `notify_user(...)` real): ningún
// VIAJE_* llega acá -- esos siempre van al pasajero.
const TIPOS_CONDUCTOR = [
  "SOLICITUD_DECISION",
  "DOCUMENTO_VENCIDO",
  "DOCUMENTO_POR_VENCER",
  "RENOVACION_DOCUMENTO_DECISION",
  "ORDEN_MANTENIMIENTO_REGISTRADA",
  "ORDEN_MANTENIMIENTO_CERRADA",
];

function PantallaTurno() {
  const { actor, noLeidas } = useAuth();
  const [estado, setEstado] = useState<EstadoServicio>("FUERA_DE_LINEA");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [oferta, setOferta] = useState<OfertaActual | null>(null);
  const [viajeAsignado, setViajeAsignado] = useState<ViajeAsignado | null>(null);
  const [pago, setPago] = useState<{ estado: string; diferencia: number | null } | null>(null);
  const [vista, setVista] = useState<VistaConductor>("turno");
  // Grupo A de la ronda de correcciones UX/UI: la tarjeta flotante sobre el
  // mapa se puede minimizar para despejar la vista de la ruta. Se re-expande
  // sola cuando cambia el estado del viaje asignado (o cuando aparece/
  // desaparece), para que un cambio importante no quede escondido detrás de
  // un plegado que el conductor hizo hace rato.
  const [overlayColapsado, setOverlayColapsado] = useState(false);
  // Última posición propia geolocalizada — misma fuente que reportarPosicion
  // usa para POST /flota/posiciones, reutilizada acá solo para centrar/marcar
  // el mapa persistente (no dispara una segunda llamada de geolocalización).
  const [posicionPropia, setPosicionPropia] = useState<{ lat: number; lon: number } | null>(null);
  // Punto 1 de la segunda ronda de ajustes de usabilidad: lugar encontrado
  // con el buscador dentro del viaje asignado (ver el panel más abajo) --
  // solo una referencia visual sobre el mapa, no se envía a ningún endpoint
  // ni forma parte del viaje.
  const [lugarBuscado, setLugarBuscado] = useState<{ lat: number; lon: number; direccion: string } | null>(null);
  const [textoBusquedaLugar, setTextoBusquedaLugar] = useState("");
  // Ruta óptima del tramo activo (conductor->origen mientras ASIGNADO/
  // EN_CAMINO, origen->destino desde EN_CURSO) — ver el useEffect de más
  // abajo, mismo mecanismo (estimarRuta de shared-ui, Directions vía
  // backend con respaldo de línea recta) que ya usa RideMap en web-pasajero.
  const [ruta, setRuta] = useState<[number, number][] | null>(null);
  // Posición + destino con los que se calculó la ruta vigente — permite
  // decidir cuándo recalcular (CU-O07 A6) sin volver a llamar a Directions
  // en cada reporte de posición (cada 15s).
  const ultimaRutaRef = useRef<{
    origenLat: number;
    origenLon: number;
    destinoLat: number;
    destinoLon: number;
  } | null>(null);

  // Punto de recogida y destino del tramo activo, derivados de
  // viajeAsignado/oferta — calculados acá (no solo dentro del branch de
  // render de más abajo) porque el useEffect de ruta óptima los necesita
  // como dependencia.
  const recogida: { lat: number; lon: number } | null = viajeAsignado
    ? { lat: viajeAsignado.origen_lat, lon: viajeAsignado.origen_lon }
    : oferta
      ? { lat: oferta.origen_lat, lon: oferta.origen_lon }
      : null;
  const destino: { lat: number; lon: number } | null =
    viajeAsignado && viajeAsignado.destino_lat !== null && viajeAsignado.destino_lon !== null
      ? { lat: viajeAsignado.destino_lat, lon: viajeAsignado.destino_lon }
      : null;
  // CU-O06 P4/CU-O07 P4: hacia el origen (recogida) mientras ASIGNADO/
  // EN_CAMINO (incluida la oferta sin aceptar todavía, con recogida=origen
  // de la oferta); hacia el destino desde EN_CURSO (tras "Iniciar viaje",
  // paso 4 de CU-O07 — validado a <150m del origen antes de habilitar ese
  // botón, ver ViajeAsignadoCard/backend).
  const vaHaciaRecogida =
    !viajeAsignado || viajeAsignado.estado === "ASIGNADO" || viajeAsignado.estado === "EN_CAMINO";
  // Objetivo del tramo activo, calculado ACÁ (no dentro del efecto) para que
  // sus coordenadas -- no `recogida`/`destino` por separado -- sean la
  // dependencia real del useEffect de abajo. Bug real encontrado en
  // verificación real en navegador: al aceptar una oferta, `destino` pasa de
  // `null` a un valor (el viaje ya trae destino) aunque el tramo activo
  // seguía siendo "hacia origen" (`vaHaciaRecogida` true) -- con
  // `destino?.lat`/`destino?.lon` en las deps, ese cambio por sí solo
  // reactivaba el efecto y su cleanup cancelaba la petición de ruta ya en
  // vuelo (`cancelado = true`) sin que ninguna de las dos ejecuciones
  // llegara a pintar la ruta. Con el objetivo ya resuelto acá, ese caso ni
  // siquiera cambia la dependencia (sigue siendo `recogida`).
  const objetivoTramo = vaHaciaRecogida ? recogida : destino;

  // Ver `overlayColapsado`: el estado del viaje asignado (o su ausencia) es
  // la señal de "algo cambió, vuelve a mostrarlo completo".
  const estadoViajeAsignado = viajeAsignado?.estado ?? null;
  useEffect(() => {
    setOverlayColapsado(false);
  }, [estadoViajeAsignado]);

  // CU-O05/O06 paso 4 y CU-O07 paso 4: ruta óptima del tramo activo, con el
  // mismo cliente que usa RideMap en web-pasajero (estimarRuta -> GET
  // /viajes/estimacion-ruta, Directions server-side con respaldo de línea
  // recta). Se recalcula al cambiar de tramo/objetivo o cuando la posición
  // en vivo se desvía más de UMBRAL_DESVIO_RUTA_KM de la usada en el último
  // cálculo (CU-O07 A6) — nunca en cada reporte de posición sin más, para no
  // saturar Directions. Si no hay destino todavía para el tramo activo (p.
  // ej. viaje sin destino marcado, A1 de CU-O04, mientras sigue EN_CAMINO
  // hacia el origen) o no se conoce la posición propia, no hay ruta que
  // trazar — el mapa ya maneja `ruta=null` sin romperse.
  useEffect(() => {
    const destinoTramo = objetivoTramo;
    if (!posicionPropia || !destinoTramo) {
      setRuta(null);
      ultimaRutaRef.current = null;
      return;
    }

    const anterior = ultimaRutaRef.current;
    const cambioDeTramo =
      !anterior || anterior.destinoLat !== destinoTramo.lat || anterior.destinoLon !== destinoTramo.lon;
    const desvioKm = anterior
      ? distanciaKm(posicionPropia.lat, posicionPropia.lon, anterior.origenLat, anterior.origenLon)
      : Infinity;
    if (!cambioDeTramo && desvioKm < UMBRAL_DESVIO_RUTA_KM) return;

    // CU-O07 A6: "...el sistema recalcula la ruta y lo registra... el dato
    // queda para auditoría". Un cambio de tramo (o el primer cálculo, sin
    // `anterior` todavía) NO es un desvío real -- solo se registra en
    // bitácora cuando el recálculo lo disparó la posición alejándose del
    // trazado vigente, con un tramo ya fijado antes. `rutaPrevia` se captura
    // ACÁ (no dentro del `.then`) para no perder el valor si otro render
    // llega a correr antes de que la promesa resuelva.
    const esRecalculoPorDesvio = !cambioDeTramo && !!anterior;
    const rutaPrevia = ruta;

    let cancelado = false;
    ultimaRutaRef.current = {
      origenLat: posicionPropia.lat,
      origenLon: posicionPropia.lon,
      destinoLat: destinoTramo.lat,
      destinoLon: destinoTramo.lon,
    };
    estimarRuta(posicionPropia, destinoTramo).then((r) => {
      if (cancelado) return;
      setRuta(r.ruta);
      if (esRecalculoPorDesvio && viajeAsignado) {
        // Registro en bitácora (CU-O17, mismo mecanismo write-ahead que
        // VIAJE_TRANSICION_ESTADO) -- no bloquea ni condiciona el redibujado
        // de la ruta, que ya ocurrió arriba; si el registro falla (red,
        // backend caído) no tiene sentido deshacer una ruta que el
        // conductor ya está viendo. Con reintento acotado (ver
        // registrarRecalculoRutaConReintento) porque este dominio es
        // justo donde una pérdida de señal momentánea es lo típico, no lo
        // raro -- un solo intento se perdería el evento en el escenario más
        // común.
        registrarRecalculoRutaConReintento({
          lat: posicionPropia.lat,
          lon: posicionPropia.lon,
          distancia_desvio_km: desvioKm,
          ruta_anterior: rutaPrevia ?? [],
          ruta_nueva: r.ruta,
        });
      }
    });
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [posicionPropia, objetivoTramo?.lat, objetivoTramo?.lon]);

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

  const onOfertaRespondida = (aceptada: boolean, motivoFallo?: string) => {
    setOferta(null);
    if (motivoFallo) setError(motivoFallo);
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
    contenido = <PerfilPropio />;
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
  } else if (vista === "fallas") {
    contenido = <FallasView posicionConocida={posicionPropia} />;
  } else if (vista === "documentos") {
    contenido = <MisDocumentosView />;
  } else if (vista === "vehiculo") {
    contenido = <FichaVehiculoView />;
  } else if (vista === "notificaciones") {
    contenido = (
      <SeccionNotificaciones
        tiposRelevantes={TIPOS_CONDUCTOR}
        resolverAccionRapida={(n) => {
          // Cierre del gap de renovación documental: "Mis documentos" ya
          // existe -- DOCUMENTO_VENCIDO/DOCUMENTO_POR_VENCER dejan de ser
          // informativos. "Mi vehículo" (ficha de mantenimiento) cierra el
          // mismo gap para ORDEN_MANTENIMIENTO_REGISTRADA/_CERRADA -- antes
          // de esto, esos 2 tipos seguían sin pantalla propia. El resto de
          // los tipos de este portal (decisión de la postulación) sigue sin
          // acción rápida fabricada.
          if (n.tipo === "DOCUMENTO_VENCIDO" || n.tipo === "DOCUMENTO_POR_VENCER") {
            return { etiqueta: "Ver mis documentos", onClick: () => setVista("documentos") };
          }
          if (n.tipo === "ORDEN_MANTENIMIENTO_REGISTRADA" || n.tipo === "ORDEN_MANTENIMIENTO_CERRADA") {
            return { etiqueta: "Ver mi vehículo", onClick: () => setVista("vehiculo") };
          }
          return null;
        }}
      />
    );
  } else if (estado === "FUERA_DE_LINEA") {
    // Sin turno activo todavía no hay nada que centrar en un mapa (spec
    // deja a criterio de esta implementación el comportamiento en estado
    // inactivo) — se mantiene la tarjeta simple de antes, sin mapa.
    contenido = (
      <Card>
          <h1
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "var(--font-size-xl)",
              margin: 0,
              marginBottom: "var(--space-2)",
            }}
          >
            Mi turno
          </h1>
          <p style={{ color: "var(--color-text-muted)" }}>Socio conductor: {actor?.sub}</p>
          <p style={{ margin: "var(--space-2) 0" }}>
            Estado: <strong>{ETIQUETA_ESTADO_TURNO[estado]}</strong>
          </p>
          {mensaje && <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}
          {error && (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", whiteSpace: "pre-wrap" }}>
              {error}
            </p>
          )}
        {/* "Reportar falla del vehículo" ya no vive acá: pasó a su propia
            sección del menú (Grupo B/D de la ronda de correcciones UX/UI),
            junto al resto de lo que es del vehículo y no de un viaje
            puntual, y ahí además se puede consultar el historial de
            reportes. Reportar una incidencia DURANTE un viaje sigue donde
            estaba (ViajeAsignadoCard), porque ese flujo sí es del viaje
            (CU-O07 A4: puede cancelarlo y reasignar al pasajero). */}
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
    // recogida/destino/vaHaciaRecogida ya se derivan a nivel de componente
    // (ver arriba, los necesita el useEffect de ruta óptima) — acá solo se
    // arma el panel flotante.
    let panel: JSX.Element;

    if (viajeAsignado) {
      const liberar = () => {
        setViajeAsignado(null);
        setPago(null);
        setEstado("DISPONIBLE");
        // El lugar buscado era una referencia de ESTE viaje -- no debe
        // seguir marcado en el mapa del próximo.
        setLugarBuscado(null);
        setTextoBusquedaLugar("");
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
          <ViajeAsignadoCard
            viaje={viajeAsignado}
            posicionPropia={posicionPropia}
            onActualizado={setViajeAsignado}
            onLiberado={liberar}
          />
          {/* Punto 1 de la segunda ronda de ajustes de usabilidad: buscar un
              lugar relacionado con el viaje (una referencia dada por el
              pasajero, un punto de encuentro, un lugar cercano) -- marca un
              pin de referencia en el mapa, sin tocar los datos del viaje. */}
          <Card>
            <BuscadorLugar
              label="Buscar un lugar en el mapa"
              placeholder="Ej. Terminal Terrestre, un centro comercial…"
              value={textoBusquedaLugar}
              onChangeTexto={setTextoBusquedaLugar}
              onSeleccionar={(lugar) => setLugarBuscado(lugar)}
            />
            {lugarBuscado && (
              <div
                style={{
                  marginTop: "var(--space-2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "var(--space-2)",
                }}
              >
                <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                  Marcado en el mapa: {lugarBuscado.direccion}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setLugarBuscado(null);
                    setTextoBusquedaLugar("");
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--color-text-muted)",
                    fontSize: "var(--font-size-sm)",
                    textDecoration: "underline",
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  Quitar
                </button>
              </div>
            )}
          </Card>
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
      panel = <OfertaModal oferta={oferta} onRespondida={onOfertaRespondida} />;
    } else {
      panel = (
        <Card>
          <p style={{ margin: 0 }}>
            Estado: <strong>{ETIQUETA_ESTADO_TURNO[estado]}</strong>
          </p>
          {/* Bitácora de revisión (hallazgo #7): antes, DISPONIBLE sin
              ninguna oferta activa no daba ninguna señal de que la app
              seguía escuchando -- el pasajero sí ve "Xs buscando...", acá
              no había equivalente. */}
          {estado === "DISPONIBLE" && (
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-1)" }}>
              Buscando pasajeros cercanos…
            </p>
          )}
          {error && (
            <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", whiteSpace: "pre-wrap" }}>
              {error}
            </p>
          )}
          {mensaje && <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
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

    // Resumen de una línea que queda visible con la tarjeta minimizada — lo
    // esencial para saber qué está pasando sin desplegarla.
    const resumenOverlay = viajeAsignado ? (
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", minWidth: 0 }}>
        <Badge texto={ETIQUETA_ESTADO_VIAJE[viajeAsignado.estado] ?? viajeAsignado.estado} tono="advertencia" />
        <span
          style={{
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
          }}
        >
          {vaHaciaRecogida ? viajeAsignado.origen_direccion : (viajeAsignado.destino_direccion ?? "Sin destino")}
        </span>
      </div>
    ) : (
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <Badge texto={ETIQUETA_ESTADO_TURNO[estado]} tono={estado === "DISPONIBLE" ? "exito" : "neutral"} />
        <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>Turno activo</span>
      </div>
    );

    // `ruta` (estado) ya viene calculada por el useEffect de más arriba —
    // ruta óptima real (Directions vía backend), no la línea recta que había
    // acá antes.
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
            lugarBuscado={lugarBuscado}
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
        {/* Posicionamiento y capa vienen de MapOverlayCard (shared-ui) — el
            zIndex:1001 "mágico" que había acá ya no hace falta: Leaflet queda
            encerrado en su propio stacking context (ver tokens.css), así que
            la tarjeta compite contra la escala de capas de la app, no contra
            los 1000 internos del mapa. Una oferta entrante no se puede
            plegar: esconderla sería perder el viaje. */}
        <MapOverlayCard
          plegable={oferta === null}
          colapsado={overlayColapsado}
          onToggle={() => setOverlayColapsado((v) => !v)}
          resumen={resumenOverlay}
        >
          {panel}
        </MapOverlayCard>
      </div>
    );
  }

  // Mapa del turno activo: llena todo el alto disponible (ver `contenido`
  // arriba). El resto de secciones siguen con su alto natural de contenido.
  const mapaALaPantalla = vista === "turno" && estado !== "FUERA_DE_LINEA";

  return (
    <CalleShell
      navItems={navItemsConductor(noLeidas, oferta !== null && vista !== "turno")}
      activeId={vista}
      onNavigate={(id) => setVista(id as VistaConductor)}
      // Las 3 paradas que un socio toca durante la jornada. Fallas y
      // Documentos son de "estar habilitado para trabajar", no de la jornada
      // en curso: quedan en la hoja, con su tramo "Operación" intacto, junto
      // a lo personal. Un riel de 6 nodos en 375 px dejaría objetivos de
      // 60 px con etiquetas cortadas — deja de ser un riel de calle.
      principales={["turno", "historial", "liquidaciones"]}
      contenidoLleno={mapaALaPantalla}
      headerActions={<NotificacionesBell onVerTodas={() => setVista("notificaciones")} />}
    >
      <div
        style={
          mapaALaPantalla
            ? { width: "100%", display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }
            : { width: "100%" }
        }
      >
        {contenido}
      </div>
    </CalleShell>
  );
}

export default function App() {
  const { actor } = useAuth();
  // Bitácora de revisión (segunda pasada, punto 4): la landing pública real
  // es la puerta de entrada por defecto -- "Postula aquí" reusa tal cual el
  // flujo de postulación ya existente, sin duplicar nada.
  const [vista, setVista] = useState<"landing" | "login" | "postulacion" | "postulacion-enviada">("landing");

  if (actor) {
    return <PantallaTurno />;
  }

  if (vista === "landing") {
    return (
      <LandingPage
        variante="conductor"
        registrarLabel="Postula aquí"
        onIniciarSesion={() => setVista("login")}
        onRegistrar={() => setVista("postulacion")}
      />
    );
  }

  return (
    <div
      style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-4)",
        // v2: lavado suave de ámbar de marca (PLAN_REDISENO_V2.md §2), mismo
        // criterio que web-pasajero.
        background: "radial-gradient(ellipse at top, color-mix(in srgb, var(--color-accent) 10%, var(--color-bg)) 0%, var(--color-bg) 60%)",
      }}
    >
      <div style={{ width: "min(440px, 100%)" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--space-4)" }}>
          <LoginLogo />
        </div>
        {vista === "login" && <LoginCard onPostular={() => setVista("postulacion")} />}
        {vista === "postulacion" && <PostulacionForm onEnviada={() => setVista("postulacion-enviada")} />}
        {vista === "postulacion-enviada" && (
          <Card>
            <h1
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: "var(--font-size-xl)",
                margin: 0,
                marginBottom: "var(--space-2)",
              }}
            >
              Solicitud enviada
            </h1>
            <p style={{ color: "var(--color-text-muted)" }}>
              Te contactaremos por teléfono cuando la revisemos. Puedes iniciar sesión con tu teléfono y la
              contraseña que definiste una vez aprobada.
            </p>
            <Button onClick={() => setVista("login")}>Volver al inicio de sesión</Button>
          </Card>
        )}
        {(vista === "login" || vista === "postulacion") && (
          <button
            type="button"
            onClick={() => setVista("landing")}
            style={{
              display: "block",
              margin: "var(--space-3) auto 0",
              background: "none",
              border: "none",
              color: "var(--color-text-muted)",
              fontSize: "var(--font-size-sm)",
              textDecoration: "underline",
              cursor: "pointer",
            }}
          >
            ← Volver a la página principal
          </button>
        )}
      </div>
    </div>
  );
}
