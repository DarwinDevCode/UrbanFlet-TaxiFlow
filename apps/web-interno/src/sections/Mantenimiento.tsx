import {
  ActionBar,
  ApiError,
  apiFetch,
  Badge,
  Button,
  Card,
  DataTable,
  DetailField,
  DetailPanel,
  invalidateSwrPrefix,
  EvidenciaImagen,
  Pagination,
  Riel,
  Select,
  subirArchivo,
  TextArea,
  TabButton,
  TextField,
  trayectoOrden,
  useSwr,
  type ModoPanel,
  FileField,
} from "@urbanflet/shared-ui";
import { useMemo, useState, type ChangeEvent } from "react";

const RECURSO_ORDENES = "/mantenimiento/ordenes";
const RECURSO_TALLERES = "/catalogos/talleres";
const RECURSO_REPUESTOS_CATALOGO = "/catalogos/repuestos";
const RECURSO_REPORTES_FALLA = "/reportes-falla";
const RECURSO_MOTIVOS_INCIDENCIA = "/catalogos/motivos?categoria=incidencia";
// Flota completa para el combobox de "Nueva orden": el mismo endpoint que ya
// resolvía la búsqueda por placa, ahora sin el parámetro (devuelve todo).
// Excluye por sí solo los vehículos DADO_DE_BAJA (Decisión 3), que es
// justamente lo que no tendría sentido elegir para una orden nueva.
const RECURSO_VEHICULOS = "/mantenimiento/vehiculos/buscar";

// Catálogos Ronda 1 (Ola 1.1): sentinel para la opción "Otro" del selector
// de taller — nunca se guarda tal cual, se resuelve al texto libre antes de
// enviar (ver `tallerFinal`).
const TALLER_OTRO = "__otro__";
// Catálogos Ola 3 (PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md §3.2): mismo
// sentinel, mismo patrón, para el selector de repuestos.
const REPUESTO_OTRO = "__otro__";

interface Repuesto {
  descripcion: string;
  cantidad: number;
  costo_unitario: number;
}

interface Orden {
  id: string;
  vehiculo_id: string;
  vehiculo_placa: string | null;
  tipo: string;
  estado: string;
  descripcion: string;
  km_entrada: number;
  km_salida: number | null;
  taller: string;
  fecha_programada: string;
  costo_total: number | null;
  repuestos_estimados: Repuesto[];
  repuestos_consumidos: Repuesto[];
  horas_taller: number | null;
  // Ronda 2, Fase D: heredada al convertir un reporte de falla en orden
  // (ver SeccionReportesFalla) -- vacío en toda orden creada manualmente.
  evidencias: string[];
  // Ronda 2, Fase E (CU-O12 A3): motivo de la espera de repuesto -- se
  // conserva como rastro histórico incluso tras reanudar.
  motivo_espera: string | null;
  // Ronda 2, Fase F: cronológica (orden de inserción == orden de tiempo).
  actividades: ActividadOrden[];
  // Ronda 2, Fase G (punto 1): costo estimado vs. real.
  mano_obra_estimada: number;
  costo_estimado: number;
  desviacion_costo_pct: number | null;
  // Ronda 2, Fase G (punto 2): solo poblado en la respuesta de cierre.
  orden_encadenada_id: string | null;
  // H9 (CU-O13 P2): solo poblado en la respuesta de POST /cierre.
  proxima_km_preventivo: number | null;
}

interface ActividadOrden {
  ts: string;
  actor_id: string;
  actor_nombre: string | null;
  rol: string;
  tipo: "COMENTARIO" | "CAMBIO_ESTADO";
  detalle: string;
  evidencias: string[];
}

interface OrdenListOut {
  items: Orden[];
  total: number;
}

interface VehiculoBusqueda {
  id: string;
  placa: string;
  marca: string;
  modelo: string;
  estado_habilitacion: string;
}

const SIN_VEHICULOS: VehiculoBusqueda[] = [];

/**
 * Selector de vehículo con filtro por texto.
 *
 * Reemplaza el par "campo de placa + botón Buscar" que obligaba a saber la
 * placa de memoria y a teclearla antes de ver una sola opción. Con ~93
 * vehículos, un `<select>` plano sería una lista larga sin forma de buscar,
 * así que se filtra del lado del cliente sobre la lista ya cargada (una sola
 * petición, cacheada por `useSwr`) -- el filtro por placa/marca/modelo es
 * instantáneo y no dispara red por cada tecla.
 */
function VehiculoPicker({
  valor,
  onSeleccionar,
}: {
  valor: string;
  onSeleccionar: (id: string) => void;
}) {
  const [texto, setTexto] = useState("");
  const [abierto, setAbierto] = useState(false);
  const { data, error } = useSwr<VehiculoBusqueda[]>(RECURSO_VEHICULOS, () =>
    apiFetch<VehiculoBusqueda[]>(RECURSO_VEHICULOS),
  );
  const vehiculos = data ?? SIN_VEHICULOS;

  const elegido = useMemo(() => vehiculos.find((v) => v.id === valor) ?? null, [vehiculos, valor]);

  const filtrados = useMemo(() => {
    const q = texto.trim().toLowerCase();
    if (!q) return vehiculos.slice(0, 50);
    return vehiculos
      .filter((v) => `${v.placa} ${v.marca} ${v.modelo}`.toLowerCase().includes(q))
      .slice(0, 50);
  }, [vehiculos, texto]);

  if (elegido && !abierto) {
    return (
      <div>
        <span style={{ fontSize: "var(--font-size-sm)", display: "block", marginBottom: "var(--space-1)" }}>
          Vehículo
        </span>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          <strong style={{ fontSize: "var(--font-size-sm)" }}>
            {elegido.placa} — {elegido.marca} {elegido.modelo}
          </strong>
          <Button
            variant="secondary"
            onClick={() => {
              setTexto("");
              setAbierto(true);
            }}
          >
            Cambiar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <TextField
        label="Vehículo"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        placeholder="Filtra por placa, marca o modelo"
        hint={data ? `${vehiculos.length} vehículos en servicio` : "Cargando flota…"}
      />
      {Boolean(error) && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>
          No se pudo cargar la lista de vehículos.
        </p>
      )}
      <ul
        style={{
          listStyle: "none",
          margin: "var(--space-1) 0 0",
          padding: 0,
          maxHeight: 190,
          overflowY: "auto",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
        }}
      >
        {filtrados.length === 0 && (
          <li style={{ padding: "var(--space-2)", fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
            Ningún vehículo coincide con ese texto.
          </li>
        )}
        {filtrados.map((v) => (
          <li key={v.id}>
            <button
              type="button"
              onClick={() => {
                setAbierto(false);
                setTexto("");
                onSeleccionar(v.id);
              }}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "var(--space-2)",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                font: "inherit",
                fontSize: "var(--font-size-sm)",
              }}
            >
              <strong>{v.placa}</strong> — {v.marca} {v.modelo}
              {v.estado_habilitacion !== "HABILITADO" && (
                <span style={{ color: "var(--color-text-muted)" }}> ({v.estado_habilitacion})</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface Taller {
  id: string;
  nombre: string;
  // Punto 7.2 de la ronda de correcciones (agosto 2026): ya cargado en el
  // catálogo desde la Ronda 1 (`Catalogos.tsx`), pero nunca expuesto acá.
  url_maps: string | null;
  activo: boolean;
}

/** Acceso directo al mapa del taller seleccionado -- punto 7.2. Se muestra
 * solo si el taller elegido (no "Otro", con texto libre sin catálogo
 * detrás) tiene `url_maps` real cargado. El `<Select>` de taller guarda el
 * NOMBRE, no el id (texto libre sin FK, mismo patrón ya establecido para
 * este catálogo -- ver `tallerFinal`), así que se busca por nombre. */
function EnlaceUbicacionTaller({ talleres, tallerNombre }: { talleres: Taller[]; tallerNombre: string }) {
  const taller = talleres.find((t) => t.nombre === tallerNombre);
  if (!taller?.url_maps) return null;
  return (
    <a
      href={taller.url_maps}
      target="_blank"
      rel="noopener noreferrer"
      style={{ fontSize: "var(--font-size-sm)", color: "var(--color-accent)" }}
    >
      Ver ubicación en el mapa ↗
    </a>
  );
}

// Catálogos Ola 3 (PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md §3.2).
interface RepuestoCatalogo {
  id: string;
  nombre: string;
  categoria: string;
  precio_referencial: number;
  unidad: string;
  activo: boolean;
}

const SIN_REPUESTOS_CATALOGO: RepuestoCatalogo[] = [];

// Ronda 2 (Fase B, H6/CU-O12 P1): ficha del vehículo con kilometraje real.
interface FichaVehiculo {
  id: string;
  placa: string;
  km_acumulado: number;
  fecha_ultima_intervencion: string | null;
  km_ultima_intervencion: number | null;
  proxima_km_preventivo: number;
  le_toca_preventivo: boolean;
  umbral_km_preventivo: number;
}

// Ronda 2, Fase D: bandeja de reportes de falla del conductor (Fase C).
interface ReporteFalla {
  id: string;
  vehiculo_id: string;
  vehiculo_placa: string | null;
  conductor_id: string;
  viaje_id: string | null;
  tipo_falla: string;
  descripcion: string;
  lat: number;
  lon: number;
  ts: string;
  impide_continuar: boolean;
  estado: string;
  orden_id: string | null;
  evidencias: string[];
  motivo_descarte: string | null;
}

// Mismo patrón de pestañas ya usado en Catalogos.tsx/Integraciones.tsx/
// Respaldos.tsx -- sin componente compartido en shared-ui, cada sección lo
// define localmente (convención ya establecida, no una duplicación nueva).
// `GET /archivos/{id}` exige Bearer token -- un <img src> plano no puede
// llevarlo, así que se descarga como blob autenticado (obtenerArchivoBlobUrl,
// shared-ui) y se renderiza desde un Object URL, revocado al desmontar.
// El visor de evidencia autenticado vive en shared-ui (`EvidenciaImagen`) —
// lo comparten esta bandeja y el listado propio del conductor.
function MiniaturaEvidencia({ archivoId }: { archivoId: string }) {
  return <EvidenciaImagen archivoId={archivoId} alt="Evidencia de la falla" />;
}

// Ronda 2, Fase F: cronología de actividades de la orden (comentarios del
// Jefe de Mantenimiento + transiciones automáticas como "pasó a espera de
// repuesto"). Orden de renderizado == orden de llegada del array (el
// backend ya lo entrega cronológico, insert-only).
function TimelineActividades({ actividades }: { actividades: ActividadOrden[] }) {
  if (actividades.length === 0) {
    return (
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
        Todavía no hay actividad registrada en esta orden.
      </p>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {actividades.map((a, i) => (
        <div
          key={i}
          style={{
            borderLeft: `3px solid ${a.tipo === "CAMBIO_ESTADO" ? "var(--color-accent)" : "var(--color-border)"}`,
            paddingLeft: "var(--space-3)",
          }}
        >
          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}>
            <Badge texto={a.tipo === "CAMBIO_ESTADO" ? "Cambio de estado" : "Comentario"} tono={a.tipo === "CAMBIO_ESTADO" ? "advertencia" : "neutral"} />
            <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
              {a.actor_nombre ?? a.actor_id} ({a.rol}) — {new Date(a.ts).toLocaleString()}
            </span>
          </div>
          <p style={{ margin: "var(--space-1) 0 0" }}>{a.detalle}</p>
          {a.evidencias.length > 0 && (
            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", marginTop: "var(--space-2)" }}>
              {a.evidencias.map((id) => (
                <MiniaturaEvidencia key={id} archivoId={id} />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// El estado de la orden pasó al riel (`trayectoOrden` en shared-ui). La
// distinción que este mapa de tonos hacía sigue existiendo, mejor
// expresada: "Esperando repuesto" ya no es solo un color más urgente, es la
// parada de taller marcada como detenida -- se ve que el trayecto está
// frenado ahí y cuánto le falta, no solo que es grave.

type AccionOrden = "ninguna" | "cierre" | "anulacion" | "espera" | "correccion";

// Ronda "corrección acotada por estado": qué campos de la orden son
// corregibles depende de en qué estado sigue -- ver el análisis completo en
// el resumen de esa ronda. ABIERTA es superset de EN_TALLER/
// ESPERANDO_REPUESTO a propósito (los 2 campos de EN_TALLER también valen en
// ABIERTA, nunca al revés). CERRADA/ANULADA no tienen entrada -- ningún
// campo es corregible ahí.
const CAMPOS_CORRECCION_POR_ESTADO: Record<string, readonly string[]> = {
  ABIERTA: ["descripcion", "taller", "fecha_programada", "repuestos_estimados", "mano_obra_estimada"],
  EN_TALLER: ["repuestos_estimados", "mano_obra_estimada"],
  ESPERANDO_REPUESTO: ["repuestos_estimados", "mano_obra_estimada"],
};

const REPUESTO_VACIO: Repuesto = { descripcion: "", cantidad: 1, costo_unitario: 0 };

// Metadato de selección por línea, local a RepuestosEditor -- separado del
// `Repuesto` que se envía al backend porque acá hace falta distinguir
// "todavía no elige nada" de "eligió Otro y está escribiendo libre" (mismo
// problema que resuelve tallerSeleccion/tallerLibre para taller), mientras
// que `Repuesto.descripcion` en el backend siempre es el texto final
// resuelto, sin ese matiz. Se mantiene en lockstep con `repuestos` porque
// las únicas dos mutaciones del arreglo (agregar/quitar línea) ocurren
// siempre dentro de este mismo componente.
interface SeleccionRepuesto {
  seleccion: string; // "" (nada elegido) | REPUESTO_OTRO | nombre exacto del catálogo
  libre: string;
}
const SELECCION_VACIA: SeleccionRepuesto = { seleccion: "", libre: "" };

// Editor de línea de repuestos reutilizado en el formulario de creación
// (repuestos_estimados) y en el de cierre (repuestos_consumidos) — mismo
// shape (descripcion/cantidad/costo_unitario) en ambos, ver RepuestoInput
// en backend/src/mantenimiento/schemas.py. Ola 3: "Descripción" (texto
// libre) reemplazada por un selector contra el catálogo de repuestos, con
// opción "Otro" (mismo patrón que taller) para lo que no está en la lista.
function RepuestosEditor({
  repuestos,
  onChange,
}: {
  repuestos: Repuesto[];
  onChange: (repuestos: Repuesto[]) => void;
}) {
  const { data: catalogoData } = useSwr<RepuestoCatalogo[]>(RECURSO_REPUESTOS_CATALOGO, () =>
    apiFetch<RepuestoCatalogo[]>(RECURSO_REPUESTOS_CATALOGO),
  );
  const catalogo = (catalogoData ?? SIN_REPUESTOS_CATALOGO).filter((r) => r.activo);

  const [selecciones, setSelecciones] = useState<SeleccionRepuesto[]>([]);

  const actualizarCampo = (i: number, campo: "cantidad" | "costo_unitario", valor: string) => {
    const copia = repuestos.slice();
    copia[i] = { ...copia[i], [campo]: Number(valor) };
    onChange(copia);
  };

  const elegirRepuesto = (i: number, valor: string) => {
    const nuevasSelecciones = selecciones.slice();
    if (valor === REPUESTO_OTRO) {
      nuevasSelecciones[i] = { seleccion: REPUESTO_OTRO, libre: "" };
      setSelecciones(nuevasSelecciones);
      const copia = repuestos.slice();
      copia[i] = { ...copia[i], descripcion: "" };
      onChange(copia);
      return;
    }
    const encontrado = catalogo.find((r) => r.nombre === valor);
    if (!encontrado) return;
    nuevasSelecciones[i] = { seleccion: valor, libre: "" };
    setSelecciones(nuevasSelecciones);
    const copia = repuestos.slice();
    // Precarga el costo unitario con el precio de referencia -- el campo
    // sigue editable de inmediato después, el catálogo solo sugiere un
    // punto de partida, nunca lo fuerza.
    copia[i] = { ...copia[i], descripcion: encontrado.nombre, costo_unitario: encontrado.precio_referencial };
    onChange(copia);
  };

  const escribirLibre = (i: number, texto: string) => {
    const nuevasSelecciones = selecciones.slice();
    nuevasSelecciones[i] = { seleccion: REPUESTO_OTRO, libre: texto };
    setSelecciones(nuevasSelecciones);
    const copia = repuestos.slice();
    copia[i] = { ...copia[i], descripcion: texto };
    onChange(copia);
  };

  const agregar = () => {
    onChange([...repuestos, { ...REPUESTO_VACIO }]);
    setSelecciones([...selecciones, { ...SELECCION_VACIA }]);
  };

  const quitar = (i: number) => {
    onChange(repuestos.filter((_, j) => j !== i));
    setSelecciones(selecciones.filter((_, j) => j !== i));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>Repuestos</span>
      {repuestos.map((r, i) => {
        const seleccionLinea = selecciones[i] ?? SELECCION_VACIA;
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end" }}>
              <div style={{ flex: 2 }}>
                <Select
                  label="Repuesto"
                  value={seleccionLinea.seleccion}
                  onChange={(e) => elegirRepuesto(i, e.target.value)}
                  options={[
                    { value: "", label: "Selecciona un repuesto" },
                    ...catalogo.map((c) => ({
                      value: c.nombre,
                      label: `${c.nombre} — $${c.precio_referencial.toFixed(2)}/${c.unidad}`,
                    })),
                    { value: REPUESTO_OTRO, label: "Otro (no está en la lista)…" },
                  ]}
                />
              </div>
              <div style={{ flex: 1 }}>
                <TextField
                  label="Cantidad"
                  type="number"
                  min={1}
                  step={1}
                  bloquearNegativo
                  value={String(r.cantidad)}
                  onChange={(e) => actualizarCampo(i, "cantidad", e.target.value)}
                />
              </div>
              <div style={{ flex: 1 }}>
                <TextField
                  label="Costo unitario"
                  type="number"
                  min={0}
                  step={0.01}
                  bloquearNegativo
                  value={String(r.costo_unitario)}
                  onChange={(e) => actualizarCampo(i, "costo_unitario", e.target.value)}
                />
              </div>
              <div style={{ minWidth: 90 }}>
                <Button variant="secondary" onClick={() => quitar(i)}>
                  Quitar
                </Button>
              </div>
            </div>
            {seleccionLinea.seleccion === REPUESTO_OTRO && (
              <TextField
                label="Descripción del repuesto"
                value={seleccionLinea.libre}
                onChange={(e) => escribirLibre(i, e.target.value)}
              />
            )}
          </div>
        );
      })}
      <div style={{ minWidth: 160 }}>
        <Button variant="secondary" onClick={agregar}>
          Agregar repuesto
        </Button>
      </div>
    </div>
  );
}

// Misma convención de "Salir" que Solicitudes y Finanzas: en la barra fija
// de acciones limpia los criterios de búsqueda y vuelve a la lista por
// defecto; dentro del panel de detalle cierra sin aplicar cambios.
function SeccionOrdenes() {
  const [filtroPlaca, setFiltroPlaca] = useState("");
  const [placaInput, setPlacaInput] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [errorAccion, setError] = useState<string | null>(null);

  const [seleccionada, setSeleccionada] = useState<Orden | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [accion, setAccion] = useState<AccionOrden>("ninguna");

  // --- Campos del formulario "Nuevo registro" (crear orden) ---
  const [vehiculoId, setVehiculoId] = useState("");
  const [tipo, setTipo] = useState<"PREVENTIVA" | "CORRECTIVA">("PREVENTIVA");
  const [descripcion, setDescripcion] = useState("");
  const [kmEntrada, setKmEntrada] = useState("");
  // Catálogos Ronda 1 (Ola 1.1): selector contra GET /catalogos/talleres +
  // opción "Otro" con texto libre — `tallerFinal` (más abajo) resuelve cuál
  // de los dos se guarda, tal como ya funcionaba antes (texto libre en
  // `ordenes.taller`, sin FK). Sin registro en bandeja de solicitudes ni
  // notificación al administrador todavía — eso es Ola 2, fuera de esta
  // ronda.
  const [tallerSeleccion, setTallerSeleccion] = useState("");
  const [tallerLibre, setTallerLibre] = useState("");
  const [fechaProgramada, setFechaProgramada] = useState("");
  const [retirar, setRetirar] = useState(false);
  const [repuestosEstimados, setRepuestosEstimados] = useState<Repuesto[]>([]);
  // Ronda 2, Fase G (punto 1): costo estimado vs. real -- único monto de
  // mano de obra (a diferencia de repuestos, no es una lista de líneas).
  const [manoObraEstimada, setManoObraEstimada] = useState("0");
  // Ronda 2 (Fase B): ficha real del vehículo elegido -- km acumulado,
  // última intervención y próxima proyectada (H6/CU-O12 P1).
  const [fichaVehiculo, setFichaVehiculo] = useState<FichaVehiculo | null>(null);
  const [cargandoFicha, setCargandoFicha] = useState(false);
  // Mensaje informativo persistente tras cerrar una orden (H9): la próxima
  // intervención proyectada no cabe en el detalle, que se cierra al
  // terminar la acción -- se muestra como banner en la lista.
  const [mensajeInfo, setMensajeInfo] = useState<string | null>(null);

  // --- Campos del formulario de cierre ---
  const [costoCierre, setCostoCierre] = useState("");
  const [kmSalidaCierre, setKmSalidaCierre] = useState("");
  const [trabajosCierre, setTrabajosCierre] = useState("");
  const [repuestosConsumidos, setRepuestosConsumidos] = useState<Repuesto[]>([]);
  const [horasTallerCierre, setHorasTallerCierre] = useState("");
  const [ajusteJustificado, setAjusteJustificado] = useState(false);
  const [motivoAjuste, setMotivoAjuste] = useState("");

  // --- Ronda 2, Fase G (punto 2, CU-O13 A1): orden correctiva encadenada,
  //     abierta opcionalmente al cerrar ---
  const [abrirEncadenada, setAbrirEncadenada] = useState(false);
  const [descripcionEncadenada, setDescripcionEncadenada] = useState("");
  const [tallerSeleccionEncadenada, setTallerSeleccionEncadenada] = useState("");
  const [tallerLibreEncadenada, setTallerLibreEncadenada] = useState("");
  const [fechaProgramadaEncadenada, setFechaProgramadaEncadenada] = useState("");

  // --- Campos del formulario de anulación ---
  const [motivoAnulacion, setMotivoAnulacion] = useState("");

  // --- Campo del formulario de espera de repuesto (Ronda 2, Fase E) ---
  const [motivoEspera, setMotivoEspera] = useState("");

  // --- Ronda "corrección acotada por estado": qué campos se muestran
  //     depende del estado real de la orden al abrir el formulario (ver
  //     `camposCorreccionDisponibles` más abajo) -- ABIERTA ofrece los 5,
  //     EN_TALLER/ESPERANDO_REPUESTO solo repuestos/mano de obra. Mismo
  //     patrón taller+"Otro" que el resto del archivo, sufijo "Correccion"
  //     para no colisionar con el formulario de "Nuevo registro".
  const [descripcionCorreccion, setDescripcionCorreccion] = useState("");
  const [tallerSeleccionCorreccion, setTallerSeleccionCorreccion] = useState("");
  const [tallerLibreCorreccion, setTallerLibreCorreccion] = useState("");
  const [fechaProgramadaCorreccion, setFechaProgramadaCorreccion] = useState("");
  const [repuestosEstimadosCorreccion, setRepuestosEstimadosCorreccion] = useState<Repuesto[]>([]);
  const [manoObraEstimadaCorreccion, setManoObraEstimadaCorreccion] = useState("0");
  const [motivoCorreccion, setMotivoCorreccion] = useState("");

  // --- Ronda 2, Fase F: agregar actividad (comentario/avance) ---
  const [nuevoComentario, setNuevoComentario] = useState("");
  const [evidenciaComentario, setEvidenciaComentario] = useState<{ id: string; previewUrl: string } | null>(null);
  const [subiendoEvidenciaComentario, setSubiendoEvidenciaComentario] = useState(false);
  const [agregandoActividad, setAgregandoActividad] = useState(false);
  const [errorActividad, setErrorActividad] = useState<string | null>(null);

  const [cargando, setCargando] = useState(false);

  const claveConsulta = (() => {
    const params = new URLSearchParams();
    if (filtroPlaca) params.set("placa", filtroPlaca);
    if (filtroEstado) params.set("estado", filtroEstado);
    params.set("limit", String(pageSize));
    params.set("offset", String(page * pageSize));
    return `${RECURSO_ORDENES}?${params.toString()}`;
  })();
  const { data, error: errorCarga, refetch } = useSwr<OrdenListOut>(claveConsulta, () =>
    apiFetch<OrdenListOut>(claveConsulta),
  );
  const ordenes = data?.items ?? [];
  const total = data?.total ?? 0;
  const error =
    errorAccion ??
    (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar las órdenes") : null);

  // Catálogos Ronda 1 (Ola 1.1): talleres activos para el selector -- no
  // usa paginación (lista corta, mismo criterio que los otros catálogos).
  const { data: talleresData } = useSwr<Taller[]>(RECURSO_TALLERES, () => apiFetch<Taller[]>(RECURSO_TALLERES));
  const talleresActivos = (talleresData ?? []).filter((t) => t.activo);
  const tallerFinal = tallerSeleccion === TALLER_OTRO ? tallerLibre.trim() : tallerSeleccion;
  // Ronda 2, Fase G (punto 2): mismo patrón de selector taller+"Otro" que
  // el resto del archivo, para la orden encadenada opcional del cierre.
  const tallerFinalEncadenada =
    tallerSeleccionEncadenada === TALLER_OTRO ? tallerLibreEncadenada.trim() : tallerSeleccionEncadenada;
  const tallerFinalCorreccion =
    tallerSeleccionCorreccion === TALLER_OTRO ? tallerLibreCorreccion.trim() : tallerSeleccionCorreccion;
  // Suma en vivo de repuestos_estimados + mano de obra, mientras se llena
  // el formulario -- mismo cálculo que hace el backend
  // (service._costo_estimado), solo para que el Jefe vea el total antes de
  // enviar, no se envía este número al backend (se recalcula ahí).
  const costoEstimadoPreview =
    (Number(manoObraEstimada) || 0) +
    repuestosEstimados.reduce((acc, r) => acc + r.cantidad * r.costo_unitario, 0);

  const buscar = () => {
    setFiltroPlaca(placaInput.trim());
    setPage(0);
  };

  const limpiarBusqueda = () => {
    setFiltroPlaca("");
    setPlacaInput("");
    setFiltroEstado("");
    setPage(0);
    setSeleccionada(null);
  };

  const resetFormularioNuevo = () => {
    setVehiculoId("");
    setTipo("PREVENTIVA");
    setDescripcion("");
    setKmEntrada("");
    setTallerSeleccion("");
    setTallerLibre("");
    setFechaProgramada("");
    setRetirar(false);
    setRepuestosEstimados([]);
    setManoObraEstimada("0");
    setFichaVehiculo(null);
  };

  const abrirNuevo = () => {
    resetFormularioNuevo();
    setSeleccionada(null);
    setAccion("ninguna");
    setModo("nuevo");
    setError(null);
    setMensajeInfo(null);
  };

  const abrirDetalle = (o: Orden) => {
    setSeleccionada(o);
    setAccion("ninguna");
    setModo("consulta");
    setCostoCierre("");
    setKmSalidaCierre(String(o.km_entrada));
    setTrabajosCierre("");
    setRepuestosConsumidos([]);
    setHorasTallerCierre("");
    setAjusteJustificado(false);
    setMotivoAjuste("");
    setMotivoAnulacion("");
    setMotivoEspera("");
    setNuevoComentario("");
    setEvidenciaComentario(null);
    setErrorActividad(null);
    setAbrirEncadenada(false);
    setDescripcionEncadenada("");
    setTallerSeleccionEncadenada("");
    setTallerLibreEncadenada("");
    setFechaProgramadaEncadenada("");
    setError(null);
  };

  // Ronda 2 (Fase B, H6/CU-O12 P1): al elegir el vehículo se abre su ficha
  // real -- reemplaza el km tecleado a ciegas por un valor de referencia
  // real (prefill editable, no de solo lectura: el Jefe sigue verificando
  // contra el tablero físico del vehículo, ahora con un punto de partida
  // real en vez de arbitrario).
  const seleccionarVehiculo = async (id: string) => {
    setVehiculoId(id);
    setFichaVehiculo(null);
    if (!id) return;
    setCargandoFicha(true);
    try {
      const ficha = await apiFetch<FichaVehiculo>(`/mantenimiento/vehiculos/${id}/ficha`);
      setFichaVehiculo(ficha);
      setKmEntrada(String(Math.round(ficha.km_acumulado)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar la ficha del vehículo");
    } finally {
      setCargandoFicha(false);
    }
  };

  const crearOrden = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/mantenimiento/ordenes", {
        method: "POST",
        body: {
          vehiculo_id: vehiculoId,
          tipo,
          descripcion,
          km_entrada: Number(kmEntrada),
          taller: tallerFinal,
          fecha_programada: fechaProgramada,
          retirar_vehiculo: retirar,
          repuestos_estimados: repuestosEstimados,
          mano_obra_estimada: Number(manoObraEstimada) || 0,
        },
      });
      setModo("consulta");
      resetFormularioNuevo();
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear la orden");
    } finally {
      setCargando(false);
    }
  };

  const marcarEnTaller = async (id: string) => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/ordenes/${id}/taller`, { method: "POST" });
      setSeleccionada(null);
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo marcar en taller");
    } finally {
      setCargando(false);
    }
  };

  const cerrarOrden = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      const actualizada = await apiFetch<Orden>(`/mantenimiento/ordenes/${seleccionada.id}/cierre`, {
        method: "POST",
        body: {
          trabajos_realizados: trabajosCierre,
          repuestos_consumidos: repuestosConsumidos,
          costo_total: Number(costoCierre),
          horas_taller: horasTallerCierre ? Number(horasTallerCierre) : null,
          km_salida: Number(kmSalidaCierre),
          habilitar_vehiculo: true,
          ajuste_justificado: ajusteJustificado,
          motivo_ajuste: ajusteJustificado ? motivoAjuste : null,
          // Ronda 2, Fase G (punto 2): solo se manda el objeto si el Jefe
          // marcó la casilla -- el backend interpreta "sin encadenada" como
          // ausencia del campo (default None), no como un objeto vacío.
          orden_encadenada: abrirEncadenada
            ? {
                descripcion: descripcionEncadenada,
                taller: tallerFinalEncadenada,
                fecha_programada: fechaProgramadaEncadenada,
              }
            : null,
        },
      });
      // H9 (CU-O13 P2) + Fase G (punto 1/2): la próxima intervención
      // preventiva, la desviación de costo y el id de la orden encadenada
      // vienen todas en la propia respuesta del cierre -- un solo banner
      // informativo con lo que aplique, sin llamadas extra.
      const partes: string[] = ["Orden cerrada."];
      if (actualizada.proxima_km_preventivo != null) {
        partes.push(`Próxima intervención preventiva proyectada: ${actualizada.proxima_km_preventivo.toLocaleString()} km.`);
      }
      if (actualizada.desviacion_costo_pct != null) {
        const signo = actualizada.desviacion_costo_pct >= 0 ? "+" : "";
        partes.push(
          `Costo real vs. estimado ($${actualizada.costo_estimado.toFixed(2)}): ${signo}${actualizada.desviacion_costo_pct.toFixed(1)}%.`,
        );
      }
      if (actualizada.orden_encadenada_id) {
        partes.push("Se abrió una orden correctiva encadenada.");
      }
      setMensajeInfo(partes.join(" "));
      setSeleccionada(null);
      setAccion("ninguna");
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cerrar la orden");
    } finally {
      setCargando(false);
    }
  };

  const anularOrden = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/ordenes/${seleccionada.id}/anulacion`, {
        method: "POST",
        body: { motivo: motivoAnulacion },
      });
      setSeleccionada(null);
      setAccion("ninguna");
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo anular la orden");
    } finally {
      setCargando(false);
    }
  };

  // Ronda 2, Fase E: EN_TALLER -> ESPERANDO_REPUESTO, con motivo obligatorio
  // (CU-O12 A3, espera visible).
  const esperarRepuesto = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/ordenes/${seleccionada.id}/espera-repuesto`, {
        method: "POST",
        body: { motivo: motivoEspera },
      });
      setSeleccionada(null);
      setAccion("ninguna");
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo marcar como esperando repuesto");
    } finally {
      setCargando(false);
    }
  };

  // ESPERANDO_REPUESTO -> EN_TALLER (el repuesto llegó, sin motivo -- el
  // motivo solo se pide al ENTRAR en espera, no al salir de ella).
  const reanudarTaller = async (id: string) => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/ordenes/${id}/reanudar`, { method: "POST" });
      setSeleccionada(null);
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo reanudar el taller");
    } finally {
      setCargando(false);
    }
  };

  const iniciarCierre = () => {
    setAccion("cierre");
    setModo("edicion");
  };
  const iniciarAnulacion = () => {
    setAccion("anulacion");
    setModo("edicion");
  };
  const iniciarEspera = () => {
    setAccion("espera");
    setModo("edicion");
  };

  const iniciarCorreccion = () => {
    if (!seleccionada) return;
    setDescripcionCorreccion(seleccionada.descripcion);
    setTallerSeleccionCorreccion(seleccionada.taller);
    setTallerLibreCorreccion("");
    setFechaProgramadaCorreccion(seleccionada.fecha_programada.slice(0, 10));
    setRepuestosEstimadosCorreccion(seleccionada.repuestos_estimados);
    setManoObraEstimadaCorreccion(String(seleccionada.mano_obra_estimada));
    setMotivoCorreccion("");
    setAccion("correccion");
    setModo("edicion");
  };

  const corregirOrdenAccion = async () => {
    if (!seleccionada) return;
    const campos = CAMPOS_CORRECCION_POR_ESTADO[seleccionada.estado] ?? [];
    setError(null);
    setCargando(true);
    try {
      const actualizada = await apiFetch<Orden>(`/mantenimiento/ordenes/${seleccionada.id}/correccion`, {
        method: "PATCH",
        body: {
          descripcion: campos.includes("descripcion") ? descripcionCorreccion.trim() : undefined,
          taller: campos.includes("taller") ? tallerFinalCorreccion : undefined,
          fecha_programada: campos.includes("fecha_programada") ? fechaProgramadaCorreccion : undefined,
          repuestos_estimados: campos.includes("repuestos_estimados") ? repuestosEstimadosCorreccion : undefined,
          mano_obra_estimada: campos.includes("mano_obra_estimada") ? Number(manoObraEstimadaCorreccion) : undefined,
          motivo: motivoCorreccion.trim(),
        },
      });
      setSeleccionada(actualizada);
      setAccion("ninguna");
      setModo("consulta");
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo corregir la orden");
    } finally {
      setCargando(false);
    }
  };

  // Ronda 2, Fase F: subida inmediata al elegir el archivo (mismo patrón
  // que ReportarFallaForm en web-conductor) -- el id ya subido se adjunta
  // recién al enviar el comentario.
  const seleccionarEvidenciaComentario = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setErrorActividad(null);
    setSubiendoEvidenciaComentario(true);
    try {
      const subido = await subirArchivo(file, "actividad_orden");
      setEvidenciaComentario({ id: subido.id, previewUrl: URL.createObjectURL(file) });
    } catch (err) {
      setErrorActividad(err instanceof ApiError ? err.message : "No se pudo subir la foto");
    } finally {
      setSubiendoEvidenciaComentario(false);
    }
  };

  // No cierra el panel de detalle al terminar -- a diferencia de las demás
  // acciones (cerrar/anular/esperar), agregar varios comentarios seguidos
  // mientras se revisa la orden es el flujo normal, no la excepción.
  const agregarActividad = async () => {
    if (!seleccionada || !nuevoComentario.trim()) return;
    setErrorActividad(null);
    setAgregandoActividad(true);
    try {
      const actualizada = await apiFetch<Orden>(`/mantenimiento/ordenes/${seleccionada.id}/actividades`, {
        method: "POST",
        body: {
          detalle: nuevoComentario.trim(),
          evidencias: evidenciaComentario ? [evidenciaComentario.id] : [],
        },
      });
      setSeleccionada(actualizada);
      setNuevoComentario("");
      setEvidenciaComentario(null);
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setErrorActividad(e instanceof ApiError ? e.message : "No se pudo agregar la actividad");
    } finally {
      setAgregandoActividad(false);
    }
  };

  const placaSeleccionada = seleccionada
    ? (seleccionada.vehiculo_placa ?? `vehículo ${seleccionada.vehiculo_id.slice(0, 8)}…`)
    : "";

  const tituloDetalle = seleccionada
    ? accion === "cierre"
      ? `Cerrar orden — ${placaSeleccionada}`
      : accion === "anulacion"
        ? `Anular orden — ${placaSeleccionada}`
        : accion === "espera"
          ? `Esperar repuesto — ${placaSeleccionada}`
          : accion === "correccion"
            ? `Corregir orden — ${placaSeleccionada}`
            : `Orden de mantenimiento — ${placaSeleccionada}`
    : "Nueva orden de mantenimiento";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Buscar órdenes de mantenimiento</h2>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Placa del vehículo"
              value={placaInput}
              onChange={(e) => setPlacaInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscar()}
            />
          </div>
          <div style={{ minWidth: 220 }}>
            <Select
              label="Estado"
              value={filtroEstado}
              onChange={(e) => {
                setFiltroEstado(e.target.value);
                setPage(0);
              }}
              options={[
                { value: "", label: "Todas" },
                { value: "ABIERTA", label: "Abierta" },
                { value: "EN_TALLER", label: "En taller" },
                { value: "ESPERANDO_REPUESTO", label: "Esperando repuesto" },
                { value: "CERRADA", label: "Cerrada" },
                { value: "ANULADA", label: "Anulada" },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* "Eliminar" quitado (segunda pasada, punto 1): las órdenes no se
          eliminan, solo se cierran o se anulan -- ningún rol tiene un uso
          real para eliminar acá. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
        buscar={{ onClick: buscar }}
        salir={{ onClick: limpiarBusqueda }}
      />

      <Card>
        {error && !seleccionada && modo !== "nuevo" && (
          <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>
        )}
        {mensajeInfo && !seleccionada && modo !== "nuevo" && (
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{mensajeInfo}</p>
        )}
        <DataTable
          rows={ordenes}
          keyField={(o) => o.id}
          vacio="No hay órdenes registradas."
          columns={[
            {
              header: "Vehículo",
              render: (o) =>
                o.vehiculo_placa ?? (
                  <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }} title={o.vehiculo_id}>
                    Sin placa ({o.vehiculo_id.slice(0, 8)}…)
                  </span>
                ),
            },
            { header: "Tipo", render: (o) => o.tipo },
            { header: "Estado", render: (o) => <Riel {...trayectoOrden(o.estado)} variante="etiquetado" /> },
            { header: "Taller", render: (o) => o.taller },
            { header: "Costo", render: (o) => (o.costo_total != null ? `$${o.costo_total.toFixed(2)}` : "—") },
            {
              header: "Detalle",
              render: (o) => (
                <Button variant="secondary" onClick={() => abrirDetalle(o)}>
                  Ver
                </Button>
              ),
            },
          ]}
          ocultarContador
        />
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={(n) => {
            setPageSize(n);
            setPage(0);
          }}
        />
      </Card>

      {modo === "nuevo" && (
        <DetailPanel
          titulo={tituloDetalle}
          modo="nuevo"
          onSalir={() => setModo("consulta")}
          onAceptar={crearOrden}
          aceptarLabel="Crear orden"
          aceptarLoading={cargando}
          aceptarDisabled={!vehiculoId || !descripcion || !kmEntrada || !tallerFinal || !fechaProgramada}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <VehiculoPicker valor={vehiculoId} onSeleccionar={seleccionarVehiculo} />
            {cargandoFicha && (
              <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
                Cargando ficha del vehículo…
              </p>
            )}
            {fichaVehiculo && (
              <Card>
                <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>
                  Ficha de {fichaVehiculo.placa}
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-2)" }}>
                  <DetailField label="Km acumulado real" value={`${fichaVehiculo.km_acumulado.toLocaleString()} km`} />
                  <DetailField
                    label="Última intervención"
                    value={
                      fichaVehiculo.fecha_ultima_intervencion
                        ? `${new Date(fichaVehiculo.fecha_ultima_intervencion).toLocaleDateString()} (${fichaVehiculo.km_ultima_intervencion?.toLocaleString()} km)`
                        : "Sin intervenciones registradas"
                    }
                  />
                  <DetailField
                    label={`Próxima preventiva (umbral ${fichaVehiculo.umbral_km_preventivo.toLocaleString()} km)`}
                    value={`${fichaVehiculo.proxima_km_preventivo.toLocaleString()} km`}
                  />
                </div>
                {fichaVehiculo.le_toca_preventivo && (
                  <div style={{ marginTop: "var(--space-2)" }}>
                    <Badge texto="Le toca preventivo" tono="advertencia" />
                  </div>
                )}
              </Card>
            )}
            <Select
              label="Tipo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as typeof tipo)}
              options={[
                { value: "PREVENTIVA", label: "Preventiva" },
                { value: "CORRECTIVA", label: "Correctiva" },
              ]}
            />
            <TextField label="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
            <TextField
              label="Kilometraje de entrada"
              type="number"
              min={0}
              step={1}
              bloquearNegativo
              value={kmEntrada}
              onChange={(e) => setKmEntrada(e.target.value)}
              hint={fichaVehiculo ? `Referencia real: ${fichaVehiculo.km_acumulado.toLocaleString()} km — confirma contra el tablero físico` : undefined}
            />
            <Select
              label="Taller"
              value={tallerSeleccion}
              onChange={(e) => setTallerSeleccion(e.target.value)}
              options={[
                { value: "", label: "Selecciona un taller" },
                ...talleresActivos.map((t) => ({ value: t.nombre, label: t.nombre })),
                { value: TALLER_OTRO, label: "Otro (no está en la lista)…" },
              ]}
            />
            <EnlaceUbicacionTaller talleres={talleresActivos} tallerNombre={tallerSeleccion} />
            {tallerSeleccion === TALLER_OTRO && (
              <TextField
                label="Nombre del taller"
                value={tallerLibre}
                onChange={(e) => setTallerLibre(e.target.value)}
              />
            )}
            <TextField label="Fecha programada" type="date" value={fechaProgramada} onChange={(e) => setFechaProgramada(e.target.value)} />
            <label style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
              <input type="checkbox" checked={retirar} onChange={(e) => setRetirar(e.target.checked)} />
              Retirar el vehículo de servicio mientras dure la orden
            </label>
            <RepuestosEditor repuestos={repuestosEstimados} onChange={setRepuestosEstimados} />
            <TextField
              label="Mano de obra estimada"
              type="number"
              min={0}
              step={0.01}
              bloquearNegativo
              value={manoObraEstimada}
              onChange={(e) => setManoObraEstimada(e.target.value)}
            />
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
              Costo estimado total (referencia): ${costoEstimadoPreview.toFixed(2)}
            </p>
          </div>
        </DetailPanel>
      )}

      {seleccionada && (
        <DetailPanel
          titulo={tituloDetalle}
          modo={modo}
          onSalir={() => {
            setSeleccionada(null);
            setAccion("ninguna");
          }}
          onAceptar={
            accion === "cierre"
              ? cerrarOrden
              : accion === "anulacion"
                ? anularOrden
                : accion === "espera"
                  ? esperarRepuesto
                  : accion === "correccion"
                    ? corregirOrdenAccion
                    : undefined
          }
          aceptarLabel={
            accion === "cierre"
              ? "Cerrar y habilitar vehículo"
              : accion === "anulacion"
                ? "Confirmar anulación"
                : accion === "espera"
                  ? "Confirmar espera de repuesto"
                  : accion === "correccion"
                    ? "Guardar corrección"
                    : "Aceptar"
          }
          aceptarLoading={cargando}
          aceptarDisabled={
            accion === "cierre"
              ? !costoCierre ||
                !kmSalidaCierre ||
                !trabajosCierre ||
                (seleccionada !== null &&
                  Number(kmSalidaCierre) < seleccionada.km_entrada &&
                  (!ajusteJustificado || !motivoAjuste)) ||
                (abrirEncadenada && (!descripcionEncadenada.trim() || !tallerFinalEncadenada || !fechaProgramadaEncadenada))
              : accion === "anulacion"
                ? !motivoAnulacion
                : accion === "espera"
                  ? !motivoEspera.trim()
                  : accion === "correccion"
                    ? motivoCorreccion.trim().length < 3 ||
                      Boolean(
                        seleccionada !== null &&
                          CAMPOS_CORRECCION_POR_ESTADO[seleccionada.estado]?.includes("taller") &&
                          !tallerFinalCorreccion,
                      )
                    : false
          }
          accionesExtra={
            accion === "ninguna" ? (
              <>
                {/* Ronda "corrección acotada por estado": siempre visible,
                    deshabilitada (no oculta) fuera de ABIERTA/EN_TALLER/
                    ESPERANDO_REPUESTO -- con el motivo exacto, no un
                    "no disponible" genérico. */}
                <div style={{ minWidth: 140 }}>
                  <Button
                    variant="secondary"
                    onClick={iniciarCorreccion}
                    disabled={!(seleccionada.estado in CAMPOS_CORRECCION_POR_ESTADO)}
                    title={
                      seleccionada.estado in CAMPOS_CORRECCION_POR_ESTADO
                        ? undefined
                        : `No se puede corregir una orden ${seleccionada.estado === "CERRADA" ? "cerrada" : "anulada"} -- ya es historial.`
                    }
                  >
                    Corregir
                  </Button>
                </div>
                {seleccionada.estado === "ABIERTA" && (
                  <>
                    <div style={{ minWidth: 140 }}>
                      <Button variant="secondary" onClick={() => marcarEnTaller(seleccionada.id)} loading={cargando}>
                        En taller
                      </Button>
                    </div>
                    <div style={{ minWidth: 140 }}>
                      <Button variant="danger" onClick={iniciarAnulacion}>
                        Anular
                      </Button>
                    </div>
                  </>
                )}
                {seleccionada.estado === "EN_TALLER" && (
                  <>
                    <div style={{ minWidth: 140 }}>
                      <Button onClick={iniciarCierre}>Cerrar</Button>
                    </div>
                    <div style={{ minWidth: 160 }}>
                      <Button variant="secondary" onClick={iniciarEspera}>
                        Esperar repuesto
                      </Button>
                    </div>
                  </>
                )}
                {seleccionada.estado === "ESPERANDO_REPUESTO" && (
                  <>
                    <div style={{ minWidth: 140 }}>
                      <Button onClick={iniciarCierre}>Cerrar</Button>
                    </div>
                    <div style={{ minWidth: 140 }}>
                      <Button
                        variant="secondary"
                        onClick={() => reanudarTaller(seleccionada.id)}
                        loading={cargando}
                      >
                        Reanudar taller
                      </Button>
                    </div>
                  </>
                )}
              </>
            ) : undefined
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Vehículo" value={seleccionada.vehiculo_placa ?? `Sin placa (${seleccionada.vehiculo_id})`} />
              <DetailField label="Tipo" value={seleccionada.tipo} />
              <DetailField label="Estado" value={<Riel {...trayectoOrden(seleccionada.estado)} />} />
              <DetailField label="Taller" value={seleccionada.taller} />
              <DetailField label="Descripción" value={seleccionada.descripcion} />
              <DetailField label="Km entrada" value={seleccionada.km_entrada} />
              <DetailField label="Km salida" value={seleccionada.km_salida ?? "—"} />
              <DetailField label="Fecha programada" value={new Date(seleccionada.fecha_programada).toLocaleDateString()} />
              <DetailField label="Costo total" value={seleccionada.costo_total != null ? `$${seleccionada.costo_total.toFixed(2)}` : "—"} />
              <DetailField label="Horas de taller" value={seleccionada.horas_taller ?? "—"} />
              <DetailField label="Mano de obra estimada" value={`$${seleccionada.mano_obra_estimada.toFixed(2)}`} />
              <DetailField label="Costo estimado" value={`$${seleccionada.costo_estimado.toFixed(2)}`} />
              {seleccionada.desviacion_costo_pct != null && (
                <DetailField
                  label="Desviación de costo (real vs. estimado)"
                  value={`${seleccionada.desviacion_costo_pct >= 0 ? "+" : ""}${seleccionada.desviacion_costo_pct.toFixed(1)}%`}
                />
              )}
              {seleccionada.motivo_espera && (
                <DetailField label="Motivo de la espera de repuesto" value={seleccionada.motivo_espera} />
              )}
              <DetailField
                label="Repuestos estimados"
                value={
                  seleccionada.repuestos_estimados.length
                    ? seleccionada.repuestos_estimados.map((r) => `${r.cantidad}× ${r.descripcion}`).join(", ")
                    : "—"
                }
              />
              <DetailField
                label="Repuestos consumidos"
                value={
                  seleccionada.repuestos_consumidos.length
                    ? seleccionada.repuestos_consumidos.map((r) => `${r.cantidad}× ${r.descripcion}`).join(", ")
                    : "—"
                }
              />
            </div>

            {seleccionada.evidencias.length > 0 && (
              <div>
                <span
                  style={{
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-muted)",
                    display: "block",
                    marginBottom: "var(--space-1)",
                  }}
                >
                  Evidencia fotográfica (heredada del reporte de falla que originó esta orden)
                </span>
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                  {seleccionada.evidencias.map((id) => (
                    <MiniaturaEvidencia key={id} archivoId={id} />
                  ))}
                </div>
              </div>
            )}

            {/* Ronda 2, Fase F: cronología de la orden + agregar comentario/
                avance -- solo mientras está activa en taller, mismo criterio
                que el backend (agregar_actividad). Se oculta mientras se
                está llenando otro formulario (cierre/anulación/espera) para
                no competir visualmente con esos campos. */}
            {(seleccionada.estado === "EN_TALLER" || seleccionada.estado === "ESPERANDO_REPUESTO") &&
              accion === "ninguna" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                  <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Actividad de la orden</h3>
                  <TimelineActividades actividades={seleccionada.actividades} />
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
                    <TextArea
                      label="Agregar comentario o avance"
                      value={nuevoComentario}
                      onChange={(e) => setNuevoComentario(e.target.value)}
                    />
                    <div>
                      <FileField
                        label="Foto de evidencia (opcional)"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={seleccionarEvidenciaComentario}
                        disabled={subiendoEvidenciaComentario}
                      />
                      {evidenciaComentario && (
                        <img
                          src={evidenciaComentario.previewUrl}
                          alt="Evidencia del comentario"
                          style={{ maxWidth: "120px", marginTop: "var(--space-2)", borderRadius: "var(--radius-sm)" }}
                        />
                      )}
                    </div>
                    {errorActividad && (
                      <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", margin: 0 }}>
                        {errorActividad}
                      </p>
                    )}
                    <div style={{ minWidth: 160 }}>
                      <Button
                        variant="secondary"
                        onClick={agregarActividad}
                        loading={agregandoActividad}
                        disabled={!nuevoComentario.trim() || subiendoEvidenciaComentario}
                      >
                        Agregar actividad
                      </Button>
                    </div>
                  </div>
                </div>
              )}

            {accion === "cierre" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <TextField label="Trabajos realizados" value={trabajosCierre} onChange={(e) => setTrabajosCierre(e.target.value)} />
                <TextField
                  label="Costo total"
                  type="number"
                  min={0.01}
                  step={0.01}
                  bloquearNegativo
                  value={costoCierre}
                  onChange={(e) => setCostoCierre(e.target.value)}
                />
                <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
                  Costo estimado de referencia: ${seleccionada.costo_estimado.toFixed(2)}
                </p>
                <TextField
                  label="Horas de taller"
                  type="number"
                  min={0}
                  step={0.1}
                  bloquearNegativo
                  value={horasTallerCierre}
                  onChange={(e) => setHorasTallerCierre(e.target.value)}
                />
                <TextField
                  label="Kilometraje de salida"
                  type="number"
                  min={0}
                  step={1}
                  bloquearNegativo
                  value={kmSalidaCierre}
                  onChange={(e) => setKmSalidaCierre(e.target.value)}
                />
                <RepuestosEditor repuestos={repuestosConsumidos} onChange={setRepuestosConsumidos} />
                {/* CU-O13: km_salida &lt; km_entrada bloquea el cierre a menos que
                    se marque un ajuste justificado con motivo — antes el Jefe
                    de Mantenimiento no tenía forma de pasar por aquí en la UI
                    aunque el backend ya lo soportaba. */}
                {kmSalidaCierre !== "" && Number(kmSalidaCierre) < seleccionada.km_entrada && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                    <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", margin: 0 }}>
                      El kilometraje de salida es menor al de entrada — requiere un ajuste justificado.
                    </p>
                    <label style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                      <input type="checkbox" checked={ajusteJustificado} onChange={(e) => setAjusteJustificado(e.target.checked)} />
                      Ajuste de kilometraje justificado
                    </label>
                    {ajusteJustificado && (
                      <TextField label="Motivo del ajuste" value={motivoAjuste} onChange={(e) => setMotivoAjuste(e.target.value)} />
                    )}
                  </div>
                )}

                {/* Ronda 2, Fase G (punto 2, CU-O13 A1): abrir una correctiva
                    encadenada al cerrar -- el selector de taller reusa el
                    mismo componente/patrón "Otro" que "Nueva orden", no se
                    reconstruye. */}
                <label style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                  <input
                    type="checkbox"
                    checked={abrirEncadenada}
                    onChange={(e) => setAbrirEncadenada(e.target.checked)}
                  />
                  Abrir una orden correctiva encadenada al cerrar
                </label>
                {abrirEncadenada && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", paddingLeft: "var(--space-3)", borderLeft: "3px solid var(--color-border)" }}>
                    <TextField
                      label="Descripción de la orden encadenada"
                      value={descripcionEncadenada}
                      onChange={(e) => setDescripcionEncadenada(e.target.value)}
                    />
                    <Select
                      label="Taller"
                      value={tallerSeleccionEncadenada}
                      onChange={(e) => setTallerSeleccionEncadenada(e.target.value)}
                      options={[
                        { value: "", label: "Selecciona un taller" },
                        ...talleresActivos.map((t) => ({ value: t.nombre, label: t.nombre })),
                        { value: TALLER_OTRO, label: "Otro (no está en la lista)…" },
                      ]}
                    />
                    <EnlaceUbicacionTaller talleres={talleresActivos} tallerNombre={tallerSeleccionEncadenada} />
                    {tallerSeleccionEncadenada === TALLER_OTRO && (
                      <TextField
                        label="Nombre del taller"
                        value={tallerLibreEncadenada}
                        onChange={(e) => setTallerLibreEncadenada(e.target.value)}
                      />
                    )}
                    <TextField
                      label="Fecha programada"
                      type="date"
                      value={fechaProgramadaEncadenada}
                      onChange={(e) => setFechaProgramadaEncadenada(e.target.value)}
                    />
                    <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
                      Kilometraje de entrada de la orden nueva: el mismo kilometraje de salida de esta orden.
                    </p>
                  </div>
                )}
              </div>
            )}

            {accion === "anulacion" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <TextField label="Motivo" value={motivoAnulacion} onChange={(e) => setMotivoAnulacion(e.target.value)} />
              </div>
            )}

            {accion === "espera" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                {/* CU-O12 A3: espera visible de repuesto, motivo obligatorio
                    -- no un limbo silencioso entre EN_TALLER y CERRADA. */}
                <TextField
                  label="Motivo de la espera"
                  value={motivoEspera}
                  onChange={(e) => setMotivoEspera(e.target.value)}
                />
              </div>
            )}

            {accion === "correccion" && seleccionada && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                {/* Ronda "corrección acotada por estado": solo los campos
                    que el análisis de esa ronda clasificó como seguros en
                    el estado ACTUAL de la orden -- nunca un formulario de
                    edición general. */}
                <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                  {seleccionada.estado === "ABIERTA"
                    ? "El vehículo todavía no entró a taller: cualquiera de estos 5 campos se puede corregir."
                    : "El vehículo ya está en taller sobre la descripción y el lugar actuales -- solo la estimación de repuestos y mano de obra sigue siendo corregible."}
                </p>
                {CAMPOS_CORRECCION_POR_ESTADO[seleccionada.estado]?.includes("descripcion") && (
                  <TextArea
                    label="Descripción"
                    value={descripcionCorreccion}
                    onChange={(e) => setDescripcionCorreccion(e.target.value)}
                  />
                )}
                {CAMPOS_CORRECCION_POR_ESTADO[seleccionada.estado]?.includes("taller") && (
                  <>
                    <Select
                      label="Taller"
                      value={tallerSeleccionCorreccion}
                      onChange={(e) => setTallerSeleccionCorreccion(e.target.value)}
                      options={[
                        { value: "", label: "Selecciona un taller" },
                        ...talleresActivos.map((t) => ({ value: t.nombre, label: t.nombre })),
                        { value: TALLER_OTRO, label: "Otro (no está en la lista)…" },
                      ]}
                    />
                    <EnlaceUbicacionTaller talleres={talleresActivos} tallerNombre={tallerSeleccionCorreccion} />
                    {tallerSeleccionCorreccion === TALLER_OTRO && (
                      <TextField
                        label="Nombre del taller"
                        value={tallerLibreCorreccion}
                        onChange={(e) => setTallerLibreCorreccion(e.target.value)}
                      />
                    )}
                  </>
                )}
                {CAMPOS_CORRECCION_POR_ESTADO[seleccionada.estado]?.includes("fecha_programada") && (
                  <TextField
                    label="Fecha programada"
                    type="date"
                    value={fechaProgramadaCorreccion}
                    onChange={(e) => setFechaProgramadaCorreccion(e.target.value)}
                  />
                )}
                {CAMPOS_CORRECCION_POR_ESTADO[seleccionada.estado]?.includes("repuestos_estimados") && (
                  <RepuestosEditor repuestos={repuestosEstimadosCorreccion} onChange={setRepuestosEstimadosCorreccion} />
                )}
                {CAMPOS_CORRECCION_POR_ESTADO[seleccionada.estado]?.includes("mano_obra_estimada") && (
                  <TextField
                    label="Mano de obra estimada"
                    type="number"
                    min={0}
                    step={0.01}
                    bloquearNegativo
                    value={manoObraEstimadaCorreccion}
                    onChange={(e) => setManoObraEstimadaCorreccion(e.target.value)}
                  />
                )}
                <TextArea
                  label="Motivo de la corrección (obligatorio)"
                  value={motivoCorreccion}
                  onChange={(e) => setMotivoCorreccion(e.target.value)}
                />
              </div>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}

type AccionReporte = "ninguna" | "convertir" | "descartar" | "corregir" | "nuevo";

// Ronda 2, Fase D: bandeja del Jefe de Mantenimiento sobre los reportes de
// falla que llegan de web-conductor (Fase C) -- listar PENDIENTE, convertir
// en orden (reusa el selector de taller de Ronda 1 y RepuestosEditor de
// arriba, sin reconstruir ninguno de los dos) o descartar con motivo.
function SeccionReportesFalla() {
  const [seleccionado, setSeleccionado] = useState<ReporteFalla | null>(null);
  const [accion, setAccion] = useState<AccionReporte>("ninguna");
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  // Bitácora de revisión (hallazgo #7): antes "Convertir en orden" no daba
  // ninguna confirmación de qué orden se creó -- la fila simplemente
  // desaparecía de la bandeja y había que ir a buscarla a mano en Órdenes.
  const [mensajeInfo, setMensajeInfo] = useState<string | null>(null);

  const claveConsulta = `${RECURSO_REPORTES_FALLA}?estado=PENDIENTE`;
  const { data: reportes = [], error: errorCarga, refetch } = useSwr<ReporteFalla[]>(claveConsulta, () =>
    apiFetch<ReporteFalla[]>(claveConsulta),
  );
  const error =
    errorAccion ??
    (errorCarga
      ? errorCarga instanceof ApiError
        ? errorCarga.message
        : "No se pudieron cargar los reportes de falla"
      : null);

  // --- Campos del formulario de conversión (mismo shape que "Nueva orden"
  //     de SeccionOrdenes, taller/repuestos reusados tal cual) ---
  const [tallerSeleccion, setTallerSeleccion] = useState("");
  const [tallerLibre, setTallerLibre] = useState("");
  const [fechaProgramada, setFechaProgramada] = useState("");
  const [kmEntrada, setKmEntrada] = useState("");
  const [retirar, setRetirar] = useState(false);
  const [repuestosEstimados, setRepuestosEstimados] = useState<Repuesto[]>([]);
  const [fichaVehiculo, setFichaVehiculo] = useState<FichaVehiculo | null>(null);
  const [cargandoFicha, setCargandoFicha] = useState(false);

  // --- Campo del formulario de descarte ---
  const [motivoDescarte, setMotivoDescarte] = useState("");

  // --- Campos del formulario de corrección (ronda "corrección acotada por
  //     estado") -- reusa el mismo catálogo de tipos de falla que ya carga
  //     "Nuevo reporte de falla", ver abajo. Como esta bandeja SOLO muestra
  //     reportes PENDIENTE (?estado=PENDIENTE), la acción está disponible
  //     en cada fila sin necesidad de deshabilitarla por estado -- el
  //     backend sigue siendo el guard real (`_reporte_pendiente`).
  const [tipoFallaCorreccion, setTipoFallaCorreccion] = useState("");
  const [descripcionCorreccion, setDescripcionCorreccion] = useState("");
  const [motivoCorreccion, setMotivoCorreccion] = useState("");

  // --- Campos del formulario "Nuevo reporte de falla" (personal interno) ---
  // Mismo patrón de búsqueda de vehículo ya usado en "Nueva orden"
  // (SeccionOrdenes.buscarVehiculo/seleccionarVehiculo), sin la ficha de
  // kilometraje -- acá no hace falta, no se está abriendo una orden todavía.
  const [placaBuscadaNuevo, setPlacaBuscadaNuevo] = useState("");
  const [resultadosVehiculoNuevo, setResultadosVehiculoNuevo] = useState<VehiculoBusqueda[]>([]);
  const [vehiculoIdNuevo, setVehiculoIdNuevo] = useState("");
  const [tipoFallaNuevo, setTipoFallaNuevo] = useState("");
  const [descripcionNuevo, setDescripcionNuevo] = useState("");
  const [evidenciaNuevo, setEvidenciaNuevo] = useState<{ id: string; previewUrl: string } | null>(null);
  const [subiendoEvidenciaNuevo, setSubiendoEvidenciaNuevo] = useState(false);

  // Mismo catálogo (categoría "incidencia") que ya usa `ReportarFallaForm`
  // en web-conductor -- ver `/catalogos/motivos?categoria=incidencia`.
  const { data: tiposFallaData } = useSwr<{ id: string; nombre: string }[]>(RECURSO_MOTIVOS_INCIDENCIA, () =>
    apiFetch<{ id: string; nombre: string }[]>(RECURSO_MOTIVOS_INCIDENCIA),
  );
  const tiposFalla = tiposFallaData ?? [];

  const { data: talleresData } = useSwr<Taller[]>(RECURSO_TALLERES, () => apiFetch<Taller[]>(RECURSO_TALLERES));
  const talleresActivos = (talleresData ?? []).filter((t) => t.activo);
  const tallerFinal = tallerSeleccion === TALLER_OTRO ? tallerLibre.trim() : tallerSeleccion;

  const cerrar = () => {
    setSeleccionado(null);
    setAccion("ninguna");
  };

  const abrirNuevoReporte = () => {
    setSeleccionado(null);
    setAccion("nuevo");
    setError(null);
    setMensajeInfo(null);
    setPlacaBuscadaNuevo("");
    setResultadosVehiculoNuevo([]);
    setVehiculoIdNuevo("");
    setTipoFallaNuevo("");
    setDescripcionNuevo("");
    setEvidenciaNuevo(null);
  };

  const buscarVehiculoNuevo = async () => {
    if (!placaBuscadaNuevo) return;
    try {
      const datos = await apiFetch<VehiculoBusqueda[]>(
        `/mantenimiento/vehiculos/buscar?placa=${encodeURIComponent(placaBuscadaNuevo)}`,
      );
      setResultadosVehiculoNuevo(datos);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo buscar el vehículo");
    }
  };

  const seleccionarEvidenciaNuevo = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setSubiendoEvidenciaNuevo(true);
    try {
      const subido = await subirArchivo(file, "reporte_falla");
      setEvidenciaNuevo({ id: subido.id, previewUrl: URL.createObjectURL(file) });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo subir la foto");
    } finally {
      setSubiendoEvidenciaNuevo(false);
    }
  };

  const crearReporte = async () => {
    if (!vehiculoIdNuevo || !tipoFallaNuevo || !descripcionNuevo.trim()) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`${RECURSO_REPORTES_FALLA}/personal-interno`, {
        method: "POST",
        body: {
          vehiculo_id: vehiculoIdNuevo,
          tipo_falla: tipoFallaNuevo,
          descripcion: descripcionNuevo.trim(),
          evidencias: evidenciaNuevo ? [evidenciaNuevo.id] : [],
        },
      });
      cerrar();
      invalidateSwrPrefix(RECURSO_REPORTES_FALLA);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear el reporte de falla");
    } finally {
      setCargando(false);
    }
  };

  const abrirConversion = async (r: ReporteFalla) => {
    setSeleccionado(r);
    setAccion("convertir");
    setError(null);
    setMensajeInfo(null);
    setTallerSeleccion("");
    setTallerLibre("");
    setFechaProgramada("");
    setRetirar(false);
    setRepuestosEstimados([]);
    setFichaVehiculo(null);
    setKmEntrada("");
    setCargandoFicha(true);
    try {
      const ficha = await apiFetch<FichaVehiculo>(`/mantenimiento/vehiculos/${r.vehiculo_id}/ficha`);
      setFichaVehiculo(ficha);
      setKmEntrada(String(Math.round(ficha.km_acumulado)));
    } catch {
      // Sin ficha real no bloquea la conversión — el Jefe puede teclear el
      // km de entrada a mano, igual que si la búsqueda de vehículo fallara
      // en "Nueva orden".
    } finally {
      setCargandoFicha(false);
    }
  };

  const abrirDescarte = (r: ReporteFalla) => {
    setSeleccionado(r);
    setAccion("descartar");
    setError(null);
    setMensajeInfo(null);
    setMotivoDescarte("");
  };

  const abrirCorreccion = (r: ReporteFalla) => {
    setSeleccionado(r);
    setAccion("corregir");
    setError(null);
    setMensajeInfo(null);
    setTipoFallaCorreccion(r.tipo_falla);
    setDescripcionCorreccion(r.descripcion);
    setMotivoCorreccion("");
  };

  const convertir = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      const actualizado = await apiFetch<ReporteFalla>(`${RECURSO_REPORTES_FALLA}/${seleccionado.id}/convertir`, {
        method: "POST",
        body: {
          taller: tallerFinal,
          fecha_programada: fechaProgramada,
          km_entrada: Number(kmEntrada),
          retirar_vehiculo: retirar,
          repuestos_estimados: repuestosEstimados,
        },
      });
      setMensajeInfo(
        actualizado.orden_id
          ? `Reporte convertido en la orden ${actualizado.orden_id.slice(0, 8)}… — buscala en la pestaña "Órdenes".`
          : "Reporte convertido en orden.",
      );
      cerrar();
      invalidateSwrPrefix(RECURSO_REPORTES_FALLA);
      invalidateSwrPrefix(RECURSO_ORDENES);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo convertir el reporte en orden");
    } finally {
      setCargando(false);
    }
  };

  const descartar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`${RECURSO_REPORTES_FALLA}/${seleccionado.id}/descartar`, {
        method: "POST",
        body: { motivo: motivoDescarte },
      });
      cerrar();
      invalidateSwrPrefix(RECURSO_REPORTES_FALLA);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo descartar el reporte");
    } finally {
      setCargando(false);
    }
  };

  const corregirReporte = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`${RECURSO_REPORTES_FALLA}/${seleccionado.id}/correccion`, {
        method: "PATCH",
        body: {
          tipo_falla: tipoFallaCorreccion !== seleccionado.tipo_falla ? tipoFallaCorreccion : undefined,
          descripcion: descripcionCorreccion.trim() !== seleccionado.descripcion ? descripcionCorreccion.trim() : undefined,
          motivo: motivoCorreccion.trim(),
        },
      });
      cerrar();
      invalidateSwrPrefix(RECURSO_REPORTES_FALLA);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo corregir el reporte");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      {/* "Eliminar"/"Buscar" quitados (segunda pasada, punto 1): un reporte
          se descarta con motivo desde su propio detalle (no se elimina), y
          la bandeja siempre muestra los pendientes completos -- ningún rol
          tiene un uso real para ninguno de los dos acá. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevoReporte }}
        actualizar={{ onClick: () => refetch() }}
        salir={{ onClick: cerrar }}
      />
      {error && !seleccionado && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>
          {error}
        </p>
      )}
      {mensajeInfo && !seleccionado && (
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>
          {mensajeInfo}
        </p>
      )}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={reportes}
          keyField={(r) => r.id}
          vacio="No hay reportes de falla pendientes."
          columns={[
            {
              header: "Vehículo",
              render: (r) => r.vehiculo_placa ?? `Sin placa (${r.vehiculo_id.slice(0, 8)}…)`,
            },
            { header: "Tipo de falla", render: (r) => r.tipo_falla },
            { header: "Descripción", render: (r) => r.descripcion },
            {
              header: "Impide continuar",
              render: (r) => (r.impide_continuar ? <Badge texto="Sí" tono="peligro" /> : "No"),
            },
            { header: "Reportado", render: (r) => new Date(r.ts).toLocaleString() },
            {
              header: "Evidencia",
              render: (r) => (r.evidencias.length > 0 ? <MiniaturaEvidencia archivoId={r.evidencias[0]} /> : "—"),
            },
            {
              header: "Acciones",
              render: (r) => (
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <div style={{ minWidth: 140 }}>
                    <Button variant="secondary" onClick={() => abrirConversion(r)}>
                      Convertir en orden
                    </Button>
                  </div>
                  <div style={{ minWidth: 100 }}>
                    <Button variant="secondary" onClick={() => abrirCorreccion(r)}>
                      Corregir
                    </Button>
                  </div>
                  <div style={{ minWidth: 110 }}>
                    <Button variant="danger" onClick={() => abrirDescarte(r)}>
                      Descartar
                    </Button>
                  </div>
                </div>
              ),
            },
          ]}
        />
      </div>

      {seleccionado && accion === "convertir" && (
        <DetailPanel
          titulo={`Convertir en orden — ${seleccionado.vehiculo_placa ?? seleccionado.vehiculo_id}`}
          modo="nuevo"
          onSalir={cerrar}
          onAceptar={convertir}
          aceptarLabel="Crear orden"
          aceptarLoading={cargando}
          aceptarDisabled={!kmEntrada || !tallerFinal || !fechaProgramada}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Tipo de falla" value={seleccionado.tipo_falla} />
              <DetailField label="Descripción" value={seleccionado.descripcion} />
              <DetailField label="Reportado" value={new Date(seleccionado.ts).toLocaleString()} />
              <DetailField
                label="¿Impidió continuar el viaje?"
                value={seleccionado.impide_continuar ? "Sí" : "No"}
              />
            </div>
            {seleccionado.evidencias.length > 0 && (
              <div>
                <span
                  style={{
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-muted)",
                    display: "block",
                    marginBottom: "var(--space-1)",
                  }}
                >
                  Evidencia fotográfica
                </span>
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                  {seleccionado.evidencias.map((id) => (
                    <MiniaturaEvidencia key={id} archivoId={id} />
                  ))}
                </div>
              </div>
            )}
            {cargandoFicha && (
              <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
                Cargando ficha del vehículo…
              </p>
            )}
            {fichaVehiculo && (
              <Card>
                <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Ficha de {fichaVehiculo.placa}</h3>
                <DetailField label="Km acumulado real" value={`${fichaVehiculo.km_acumulado.toLocaleString()} km`} />
              </Card>
            )}
            <TextField
              label="Kilometraje de entrada"
              type="number"
              min={0}
              step={1}
              bloquearNegativo
              value={kmEntrada}
              onChange={(e) => setKmEntrada(e.target.value)}
              hint={fichaVehiculo ? `Referencia real: ${fichaVehiculo.km_acumulado.toLocaleString()} km — confirma contra el tablero físico` : undefined}
            />
            <Select
              label="Taller"
              value={tallerSeleccion}
              onChange={(e) => setTallerSeleccion(e.target.value)}
              options={[
                { value: "", label: "Selecciona un taller" },
                ...talleresActivos.map((t) => ({ value: t.nombre, label: t.nombre })),
                { value: TALLER_OTRO, label: "Otro (no está en la lista)…" },
              ]}
            />
            <EnlaceUbicacionTaller talleres={talleresActivos} tallerNombre={tallerSeleccion} />
            {tallerSeleccion === TALLER_OTRO && (
              <TextField label="Nombre del taller" value={tallerLibre} onChange={(e) => setTallerLibre(e.target.value)} />
            )}
            <TextField
              label="Fecha programada"
              type="date"
              value={fechaProgramada}
              onChange={(e) => setFechaProgramada(e.target.value)}
            />
            <label style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
              <input type="checkbox" checked={retirar} onChange={(e) => setRetirar(e.target.checked)} />
              Retirar el vehículo de servicio mientras dure la orden
            </label>
            <RepuestosEditor repuestos={repuestosEstimados} onChange={setRepuestosEstimados} />
          </div>
        </DetailPanel>
      )}

      {seleccionado && accion === "descartar" && (
        <DetailPanel
          titulo={`Descartar reporte — ${seleccionado.vehiculo_placa ?? seleccionado.vehiculo_id}`}
          modo="edicion"
          onSalir={cerrar}
          onAceptar={descartar}
          aceptarLabel="Confirmar descarte"
          aceptarLoading={cargando}
          aceptarDisabled={!motivoDescarte.trim()}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <DetailField label="Tipo de falla" value={seleccionado.tipo_falla} />
            <DetailField label="Descripción del conductor" value={seleccionado.descripcion} />
            <TextField
              label="Motivo del descarte"
              value={motivoDescarte}
              onChange={(e) => setMotivoDescarte(e.target.value)}
            />
          </div>
        </DetailPanel>
      )}

      {seleccionado && accion === "corregir" && (
        <DetailPanel
          titulo={`Corregir reporte — ${seleccionado.vehiculo_placa ?? seleccionado.vehiculo_id}`}
          modo="edicion"
          onSalir={cerrar}
          onAceptar={corregirReporte}
          aceptarLabel="Guardar corrección"
          aceptarLoading={cargando}
          aceptarDisabled={!tipoFallaCorreccion || !descripcionCorreccion.trim() || motivoCorreccion.trim().length < 3}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            {/* Solo mientras el reporte sigue PENDIENTE -- esta bandeja no
                muestra reportes ya CONVERTIDO_A_ORDEN/DESCARTADO (ver el
                filtro fijo `?estado=PENDIENTE` de arriba), así que la
                acción siempre aplica desde acá. El backend igual la
                bloquea con un 409 si el estado cambió entre que se cargó
                la bandeja y se guardó la corrección. */}
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
              Corrige el tipo de falla o la descripción si el conductor se equivocó al reportar. Solo disponible
              mientras el reporte sigue pendiente de conversión o descarte.
            </p>
            <Select
              label="Tipo de falla"
              value={tipoFallaCorreccion}
              onChange={(e) => setTipoFallaCorreccion(e.target.value)}
              options={[
                { value: "", label: "Selecciona un tipo" },
                ...tiposFalla.map((t) => ({ value: t.nombre, label: t.nombre })),
              ]}
            />
            <TextArea
              label="Descripción"
              value={descripcionCorreccion}
              onChange={(e) => setDescripcionCorreccion(e.target.value)}
            />
            <TextArea
              label="Motivo de la corrección (obligatorio)"
              value={motivoCorreccion}
              onChange={(e) => setMotivoCorreccion(e.target.value)}
            />
          </div>
        </DetailPanel>
      )}

      {accion === "nuevo" && (
        <DetailPanel
          titulo="Nuevo reporte de falla"
          modo="nuevo"
          onSalir={cerrar}
          onAceptar={crearReporte}
          aceptarLabel="Crear reporte"
          aceptarLoading={cargando}
          aceptarDisabled={!vehiculoIdNuevo || !tipoFallaNuevo || !descripcionNuevo.trim() || subiendoEvidenciaNuevo}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end" }}>
              <TextField
                label="Buscar vehículo por placa"
                value={placaBuscadaNuevo}
                onChange={(e) => setPlacaBuscadaNuevo(e.target.value)}
              />
              <div style={{ minWidth: 120 }}>
                <Button variant="secondary" onClick={buscarVehiculoNuevo} disabled={!placaBuscadaNuevo}>
                  Buscar
                </Button>
              </div>
            </div>
            {resultadosVehiculoNuevo.length > 0 && (
              <Select
                label="Vehículo"
                value={vehiculoIdNuevo}
                onChange={(e) => setVehiculoIdNuevo(e.target.value)}
                options={[
                  { value: "", label: "Selecciona un vehículo" },
                  ...resultadosVehiculoNuevo.map((v) => ({
                    value: v.id,
                    label: `${v.placa} — ${v.marca} ${v.modelo} (${v.estado_habilitacion})`,
                  })),
                ]}
              />
            )}
            <Select
              label="Tipo de falla"
              value={tipoFallaNuevo}
              onChange={(e) => setTipoFallaNuevo(e.target.value)}
              options={[
                { value: "", label: "Selecciona un tipo" },
                ...tiposFalla.map((t) => ({ value: t.nombre, label: t.nombre })),
              ]}
            />
            <TextArea
              label="Descripción"
              value={descripcionNuevo}
              onChange={(e) => setDescripcionNuevo(e.target.value)}
            />
            <div>
              <FileField
                label="Foto de evidencia (opcional)"
                accept="image/jpeg,image/png,image/webp"
                onChange={seleccionarEvidenciaNuevo}
                disabled={subiendoEvidenciaNuevo}
              />
              {evidenciaNuevo && (
                <img
                  src={evidenciaNuevo.previewUrl}
                  alt="Evidencia de la falla"
                  style={{ maxWidth: "160px", marginTop: "var(--space-2)", borderRadius: "var(--radius-sm)" }}
                />
              )}
            </div>
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

// Decisión 3: baja lógica de un vehículo. Vive en Mantenimiento y no en el
// tablero de Flota por dos razones concretas: (1) Flota es un tablero EN VIVO
// que solo lista vehículos con turno activo -- el vehículo que se quiere dar
// de baja normalmente no está ahí; (2) el endpoint está gateado a
// `jefe_mantenimiento`, mientras que Flota la ve `coordinador_flota`, así que
// el botón le aparecería a un rol que recibiría 403. Acá, además, ya existía
// la búsqueda de vehículos por placa que este flujo necesita.
function SeccionVehiculos() {
  // Punto 7.3 de la ronda de correcciones (agosto 2026): esta pestaña
  // exigía escribir una placa y pulsar "Buscar" antes de mostrar cualquier
  // vehículo -- no era el picker de "Nueva orden" (ese sí es intencional,
  // ver `VehiculoPicker` arriba: ahí se busca UN vehículo puntual para
  // asociarlo a una orden). Corregido con el mismo patrón ya usado ahí:
  // carga la flota completa una vez (`useSwr`, mismo `RECURSO_VEHICULOS`) y
  // filtra del lado del cliente, sin viaje de red por cada tecla.
  const { data, error: errorCarga, refetch } = useSwr<VehiculoBusqueda[]>(RECURSO_VEHICULOS, () =>
    apiFetch<VehiculoBusqueda[]>(RECURSO_VEHICULOS),
  );
  const vehiculos = data ?? SIN_VEHICULOS;
  const [filtroTexto, setFiltroTexto] = useState("");
  const [seleccionado, setSeleccionado] = useState<VehiculoBusqueda | null>(null);
  // Punto 3 del cierre integral: la pestaña pasó de solo-baja a la D + la U
  // del CRUD, así que el panel de detalle necesita saber cuál de las dos se
  // pidió (mismo `DetailPanel`, dos modos de uso).
  const [accion, setAccion] = useState<"baja" | "editar">("baja");
  const [edicion, setEdicion] = useState({ placa: "", marca: "", modelo: "" });
  const [motivo, setMotivo] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const filtrados = useMemo(() => {
    const q = filtroTexto.trim().toLowerCase();
    if (!q) return vehiculos;
    return vehiculos.filter((v) => `${v.placa} ${v.marca} ${v.modelo}`.toLowerCase().includes(q));
  }, [vehiculos, filtroTexto]);

  const abrir = (v: VehiculoBusqueda, cual: "baja" | "editar") => {
    setSeleccionado(v);
    setAccion(cual);
    setMotivo("");
    setEdicion({ placa: v.placa, marca: v.marca, modelo: v.modelo });
    setError(null);
    setMensaje(null);
  };

  const guardarEdicion = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/vehiculos/${seleccionado.id}`, {
        method: "PATCH",
        body: { placa: edicion.placa.trim(), marca: edicion.marca.trim(), modelo: edicion.modelo.trim() },
      });
      setMensaje(`Datos de ${edicion.placa.trim()} actualizados.`);
      setSeleccionado(null);
      invalidateSwrPrefix(RECURSO_VEHICULOS);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el vehículo");
    } finally {
      setCargando(false);
    }
  };

  const darDeBaja = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/vehiculos/${seleccionado.id}/dar-de-baja`, {
        method: "POST",
        body: { motivo: motivo.trim() },
      });
      setMensaje(`${seleccionado.placa} quedó fuera de la flota operativa.`);
      setSeleccionado(null);
      setMotivo("");
      invalidateSwrPrefix(RECURSO_VEHICULOS);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo dar de baja el vehículo");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Vehículos de la flota</h2>
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
        Toda la flota activa. Si un vehículo ya no forma parte de la flota (vendido, siniestrado,
        fuera de servicio de forma definitiva), se puede dar de baja. Los vehículos ya dados de
        baja no aparecen en esta lista.
      </p>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      {mensaje && <p style={{ color: "var(--color-success)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}
      {Boolean(errorCarga) && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>
          No se pudo cargar la lista de vehículos.
        </p>
      )}

      <div style={{ marginBottom: "var(--space-3)", maxWidth: 320 }}>
        <TextField
          label="Buscar por placa, marca o modelo"
          value={filtroTexto}
          onChange={(e) => setFiltroTexto(e.target.value)}
          hint={data ? `${vehiculos.length} vehículos en la flota` : "Cargando flota…"}
        />
      </div>

      <DataTable
        rows={filtrados}
        keyField={(v) => v.id}
        vacio="Ningún vehículo coincide con este filtro."
        columns={[
            { header: "Placa", render: (v) => v.placa },
            { header: "Marca", render: (v) => v.marca },
            { header: "Modelo", render: (v) => v.modelo },
            { header: "Estado", render: (v) => <Badge texto={v.estado_habilitacion} tono={v.estado_habilitacion === "HABILITADO" ? "exito" : "advertencia"} /> },
            {
              header: "Acciones",
              sinTruncar: true,
              render: (v) => (
                <div style={{ display: "flex", gap: "var(--space-1)", minWidth: 210 }}>
                  <Button variant="secondary" onClick={() => abrir(v, "editar")}>
                    Editar
                  </Button>
                  <Button variant="danger" onClick={() => abrir(v, "baja")}>
                    Dar de baja
                  </Button>
                </div>
              ),
            },
          ]}
      />

      {seleccionado && accion === "editar" && (
        <DetailPanel
          titulo={`Editar vehículo — ${seleccionado.placa}`}
          modo="edicion"
          onSalir={() => setSeleccionado(null)}
          onAceptar={guardarEdicion}
          aceptarLabel="Guardar cambios"
          aceptarLoading={cargando}
          aceptarDisabled={
            !edicion.placa.trim() || !edicion.marca.trim() || !edicion.modelo.trim()
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
              Corrección de los datos con los que se registró el vehículo al aprobar la postulación.
              El estado de habilitación no se edita acá: lo mueven las órdenes de mantenimiento y la
              baja definitiva.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-3)" }}>
              <TextField label="Placa" value={edicion.placa} onChange={(e) => setEdicion({ ...edicion, placa: e.target.value })} />
              <TextField label="Marca" value={edicion.marca} onChange={(e) => setEdicion({ ...edicion, marca: e.target.value })} />
              <TextField label="Modelo" value={edicion.modelo} onChange={(e) => setEdicion({ ...edicion, modelo: e.target.value })} />
            </div>
          </div>
        </DetailPanel>
      )}

      {seleccionado && accion === "baja" && (
        <DetailPanel
          titulo={`Dar de baja — ${seleccionado.placa}`}
          modo="edicion"
          onSalir={() => setSeleccionado(null)}
          onAceptar={darDeBaja}
          aceptarLabel="Confirmar baja"
          aceptarLoading={cargando}
          aceptarDisabled={motivo.trim().length < 3}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            {/* Mismo patrón de advertencia previa que la baja de una cuenta. */}
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-accent-deep)" }}>
              El vehículo sale <strong>de forma permanente</strong> de la flota operativa: deja de poder
              recibir viajes y no aparecerá al crear órdenes nuevas. Su historial (órdenes y viajes
              anteriores) <strong>se conserva intacto</strong>. No se puede dar de baja un vehículo con una
              orden de mantenimiento abierta.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Placa" value={seleccionado.placa} />
              <DetailField label="Vehículo" value={`${seleccionado.marca} ${seleccionado.modelo}`} />
              <DetailField label="Estado actual" value={seleccionado.estado_habilitacion} />
            </div>
            <TextArea label="Motivo (obligatorio)" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

type PestanaMantenimiento = "ordenes" | "reportes" | "vehiculos";

export function SeccionMantenimiento() {
  const [pestana, setPestana] = useState<PestanaMantenimiento>("ordenes");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <TabButton activa={pestana === "ordenes"} onClick={() => setPestana("ordenes")}>
          Órdenes
        </TabButton>
        <TabButton activa={pestana === "reportes"} onClick={() => setPestana("reportes")}>
          Reportes de falla
        </TabButton>
        <TabButton activa={pestana === "vehiculos"} onClick={() => setPestana("vehiculos")}>
          Vehículos
        </TabButton>
      </div>

      {pestana === "ordenes" && <SeccionOrdenes />}
      {pestana === "reportes" && <SeccionReportesFalla />}
      {pestana === "vehiculos" && <SeccionVehiculos />}
    </div>
  );
}
