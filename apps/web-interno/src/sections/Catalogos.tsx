import {
  ActionBar,
  ApiError,
  apiFetch,
  Badge,
  Button,
  Card,
  DataTable,
  DetailPanel,
  Select,
  TabButton,
  TextField,
  useSwr,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useState } from "react";

// Ronda de personalización/QA: los endpoints de catálogo ahora devuelven
// SOLO los activos por defecto (para que un selector que se olvide del
// filtro no siga ofreciendo una entrada desactivada). Esta pantalla es la
// única que necesita verlos todos -- para poder reactivar uno -- así que es
// la única que pasa `incluir_inactivos=true`, de forma explícita.
const TODOS = "?incluir_inactivos=true";
const RECURSO_TIPOS_DOCUMENTO = `/catalogos/tipos-documento${TODOS}`;
const RECURSO_MOTIVOS = `/catalogos/motivos${TODOS}`;
const RECURSO_TALLERES = `/catalogos/talleres${TODOS}`;
const RECURSO_MARCAS_VEHICULO = `/catalogos/marcas-vehiculo${TODOS}`;
const RECURSO_COLORES_VEHICULO = `/catalogos/colores-vehiculo${TODOS}`;
const RECURSO_REPUESTOS = `/catalogos/repuestos${TODOS}`;

interface TipoDocumento {
  id: string;
  nombre: string;
  descripcion: string;
  aplica_a: "conductor" | "vehiculo" | "ambos";
  activo: boolean;
}

interface Motivo {
  id: string;
  nombre: string;
  descripcion: string;
  categoria: "cancelacion" | "incidencia";
  activo: boolean;
}

interface Taller {
  id: string;
  nombre: string;
  direccion: string;
  telefono: string;
  url_maps: string | null;
  activo: boolean;
}

interface RepuestoCatalogo {
  id: string;
  nombre: string;
  categoria: string;
  precio_referencial: number;
  unidad: string;
  activo: boolean;
}

const CATEGORIAS_REPUESTO = ["Motor", "Frenos", "Eléctrico", "Suspensión", "Neumáticos", "Otro"];
const UNIDADES_REPUESTO = ["unidad", "litro", "juego"];

type Pestana = "tipos" | "motivos" | "talleres" | "marcas" | "colores" | "repuestos";

// Catálogos Ronda 1 (Ola 1.5): marca/color de vehículo son el catálogo más
// simple del módulo (solo nombre + activo, sin campos propios como taller o
// tipos_documento) -- de ahí un componente genérico en vez de duplicar el
// mismo CRUD dos veces.
interface ItemCatalogoSimple {
  id: string;
  nombre: string;
  activo: boolean;
}

function SeccionTiposDocumento() {
  const [seleccionado, setSeleccionado] = useState<TipoDocumento | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [aplicaA, setAplicaA] = useState<"conductor" | "vehiculo" | "ambos">("ambos");
  const [activo, setActivo] = useState(true);
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const { data: tipos = [], error: errorCarga, refetch } = useSwr<TipoDocumento[]>(RECURSO_TIPOS_DOCUMENTO, () =>
    apiFetch<TipoDocumento[]>(RECURSO_TIPOS_DOCUMENTO),
  );
  const error =
    errorAccion ??
    (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar los tipos de documento") : null);

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setDescripcion("");
    setAplicaA("ambos");
    setActivo(true);
    setError(null);
  };

  const abrirDetalle = (t: TipoDocumento) => {
    setSeleccionado(t);
    setModo("edicion");
    setNombre(t.nombre);
    setDescripcion(t.descripcion);
    setAplicaA(t.aplica_a);
    setActivo(t.activo);
    setError(null);
  };

  const guardar = async () => {
    setError(null);
    setCargando(true);
    try {
      if (modo === "nuevo") {
        await apiFetch("/catalogos/tipos-documento", { method: "POST", body: { nombre, descripcion, aplica_a: aplicaA, activo } });
      } else if (seleccionado) {
        await apiFetch(`/catalogos/tipos-documento/${seleccionado.id}`, { method: "PATCH", body: { nombre, descripcion, aplica_a: aplicaA, activo } });
      }
      setSeleccionado(null);
      setModo("consulta");
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el tipo de documento");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      {/* "Eliminar"/"Buscar" quitados (segunda pasada, punto 1): un tipo de
          documento se desactiva (no se elimina) y la lista no pagina. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
        salir={{ onClick: () => setSeleccionado(null) }}
      />
      {error && !seleccionado && modo !== "nuevo" && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>{error}</p>}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={tipos}
          keyField={(t) => t.id}
          vacio="No hay tipos de documento creados todavía."
          columns={[
            { header: "Nombre", render: (t) => t.nombre },
            { header: "Aplica a", render: (t) => t.aplica_a },
            { header: "Estado", render: (t) => <Badge texto={t.activo ? "ACTIVO" : "INACTIVO"} tono={t.activo ? "exito" : "neutral"} /> },
            { header: "Detalle", render: (t) => <Button variant="secondary" onClick={() => abrirDetalle(t)}>Ver</Button> },
          ]}
        />
      </div>

      {(modo === "nuevo" || (seleccionado && modo === "edicion")) && (
        <DetailPanel
          titulo={modo === "nuevo" ? "Nuevo tipo de documento" : `Tipo de documento — ${seleccionado?.nombre}`}
          modo={modo}
          onSalir={() => { setSeleccionado(null); setModo("consulta"); }}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={!nombre}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            <TextField label="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
            <Select
              label="Aplica a"
              value={aplicaA}
              onChange={(e) => setAplicaA(e.target.value as typeof aplicaA)}
              options={[
                { value: "ambos", label: "Ambos" },
                { value: "conductor", label: "Conductor" },
                { value: "vehiculo", label: "Vehículo" },
              ]}
            />
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activo
            </label>
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

function SeccionMotivos() {
  const [seleccionado, setSeleccionado] = useState<Motivo | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [categoria, setCategoria] = useState<"cancelacion" | "incidencia">("cancelacion");
  const [activo, setActivo] = useState(true);
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const { data: motivos = [], error: errorCarga, refetch } = useSwr<Motivo[]>(RECURSO_MOTIVOS, () =>
    apiFetch<Motivo[]>(RECURSO_MOTIVOS),
  );
  const error =
    errorAccion ?? (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar los motivos") : null);

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setDescripcion("");
    setCategoria("cancelacion");
    setActivo(true);
    setError(null);
  };

  const abrirDetalle = (m: Motivo) => {
    setSeleccionado(m);
    setModo("edicion");
    setNombre(m.nombre);
    setDescripcion(m.descripcion);
    setCategoria(m.categoria);
    setActivo(m.activo);
    setError(null);
  };

  const guardar = async () => {
    setError(null);
    setCargando(true);
    try {
      if (modo === "nuevo") {
        await apiFetch("/catalogos/motivos", { method: "POST", body: { nombre, descripcion, categoria, activo } });
      } else if (seleccionado) {
        await apiFetch(`/catalogos/motivos/${seleccionado.id}`, { method: "PATCH", body: { nombre, descripcion, categoria, activo } });
      }
      setSeleccionado(null);
      setModo("consulta");
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el motivo");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      {/* "Eliminar"/"Buscar" quitados (segunda pasada, punto 1): un motivo se desactiva, no se elimina. y la lista no pagina. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
        salir={{ onClick: () => setSeleccionado(null) }}
      />
      {error && !seleccionado && modo !== "nuevo" && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>{error}</p>}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={motivos}
          keyField={(m) => m.id}
          vacio="No hay motivos creados todavía."
          columns={[
            { header: "Nombre", render: (m) => m.nombre },
            { header: "Categoría", render: (m) => m.categoria },
            { header: "Estado", render: (m) => <Badge texto={m.activo ? "ACTIVO" : "INACTIVO"} tono={m.activo ? "exito" : "neutral"} /> },
            { header: "Detalle", render: (m) => <Button variant="secondary" onClick={() => abrirDetalle(m)}>Ver</Button> },
          ]}
        />
      </div>

      {(modo === "nuevo" || (seleccionado && modo === "edicion")) && (
        <DetailPanel
          titulo={modo === "nuevo" ? "Nuevo motivo" : `Motivo — ${seleccionado?.nombre}`}
          modo={modo}
          onSalir={() => { setSeleccionado(null); setModo("consulta"); }}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={!nombre}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            <TextField label="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
            <Select
              label="Categoría"
              value={categoria}
              onChange={(e) => setCategoria(e.target.value as typeof categoria)}
              options={[
                { value: "cancelacion", label: "Cancelación" },
                { value: "incidencia", label: "Incidencia" },
              ]}
            />
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activo
            </label>
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

function SeccionTalleres() {
  const [seleccionado, setSeleccionado] = useState<Taller | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [direccion, setDireccion] = useState("");
  const [telefono, setTelefono] = useState("");
  // Catálogos Ronda 1 (Ola 1.2): enlace a Google Maps, texto validado como
  // URL en el backend -- sin lat/lon ni mapa en esta ronda (web-interno no
  // monta ningún mapa hoy, ver PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md §3.1).
  const [urlMaps, setUrlMaps] = useState("");
  const [activo, setActivo] = useState(true);
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const { data: talleres = [], error: errorCarga, refetch } = useSwr<Taller[]>(RECURSO_TALLERES, () =>
    apiFetch<Taller[]>(RECURSO_TALLERES),
  );
  const error =
    errorAccion ?? (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar los talleres") : null);

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setDireccion("");
    setTelefono("");
    setUrlMaps("");
    setActivo(true);
    setError(null);
  };

  const abrirDetalle = (t: Taller) => {
    setSeleccionado(t);
    setModo("edicion");
    setNombre(t.nombre);
    setDireccion(t.direccion);
    setTelefono(t.telefono);
    setUrlMaps(t.url_maps ?? "");
    setActivo(t.activo);
    setError(null);
  };

  const guardar = async () => {
    setError(null);
    setCargando(true);
    try {
      const body = { nombre, direccion, telefono, url_maps: urlMaps.trim() || null, activo };
      if (modo === "nuevo") {
        await apiFetch("/catalogos/talleres", { method: "POST", body });
      } else if (seleccionado) {
        await apiFetch(`/catalogos/talleres/${seleccionado.id}`, { method: "PATCH", body });
      }
      setSeleccionado(null);
      setModo("consulta");
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el taller");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      {/* "Eliminar"/"Buscar" quitados (segunda pasada, punto 1): un taller se desactiva, no se elimina. y la lista no pagina. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
        salir={{ onClick: () => setSeleccionado(null) }}
      />
      {error && !seleccionado && modo !== "nuevo" && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>{error}</p>}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={talleres}
          keyField={(t) => t.id}
          vacio="No hay talleres creados todavía."
          columns={[
            { header: "Nombre", render: (t) => t.nombre },
            { header: "Dirección", render: (t) => t.direccion || "—" },
            { header: "Teléfono", render: (t) => t.telefono || "—" },
            {
              header: "Maps",
              render: (t) =>
                t.url_maps ? (
                  <a href={t.url_maps} target="_blank" rel="noreferrer">
                    Ver en el mapa
                  </a>
                ) : (
                  "—"
                ),
            },
            { header: "Estado", render: (t) => <Badge texto={t.activo ? "ACTIVO" : "INACTIVO"} tono={t.activo ? "exito" : "neutral"} /> },
            { header: "Detalle", render: (t) => <Button variant="secondary" onClick={() => abrirDetalle(t)}>Ver</Button> },
          ]}
        />
      </div>

      {(modo === "nuevo" || (seleccionado && modo === "edicion")) && (
        <DetailPanel
          titulo={modo === "nuevo" ? "Nuevo taller" : `Taller — ${seleccionado?.nombre}`}
          modo={modo}
          onSalir={() => { setSeleccionado(null); setModo("consulta"); }}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={!nombre}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            <TextField label="Dirección" value={direccion} onChange={(e) => setDireccion(e.target.value)} />
            <TextField label="Teléfono" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
            <TextField
              label="Enlace de Google Maps (opcional)"
              type="url"
              placeholder="https://maps.google.com/…"
              value={urlMaps}
              onChange={(e) => setUrlMaps(e.target.value)}
            />
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activo
            </label>
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

// Ola 3 de PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md (§3.2): catálogo de
// repuestos, antes aplazado por falta de evidencia, decisión ya tomada de
// avanzar igual. Mismo patrón CRUD que SeccionTalleres, con categoría/
// precio de referencia/unidad en vez de dirección/teléfono/maps.
function SeccionRepuestos() {
  const [seleccionado, setSeleccionado] = useState<RepuestoCatalogo | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [categoria, setCategoria] = useState(CATEGORIAS_REPUESTO[0]);
  const [precioReferencial, setPrecioReferencial] = useState("");
  const [unidad, setUnidad] = useState(UNIDADES_REPUESTO[0]);
  const [activo, setActivo] = useState(true);
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const { data: repuestos = [], error: errorCarga, refetch } = useSwr<RepuestoCatalogo[]>(RECURSO_REPUESTOS, () =>
    apiFetch<RepuestoCatalogo[]>(RECURSO_REPUESTOS),
  );
  const error =
    errorAccion ??
    (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar los repuestos") : null);

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setCategoria(CATEGORIAS_REPUESTO[0]);
    setPrecioReferencial("");
    setUnidad(UNIDADES_REPUESTO[0]);
    setActivo(true);
    setError(null);
  };

  const abrirDetalle = (r: RepuestoCatalogo) => {
    setSeleccionado(r);
    setModo("edicion");
    setNombre(r.nombre);
    setCategoria(r.categoria);
    setPrecioReferencial(String(r.precio_referencial));
    setUnidad(r.unidad);
    setActivo(r.activo);
    setError(null);
  };

  const guardar = async () => {
    setError(null);
    setCargando(true);
    try {
      const body = {
        nombre,
        categoria,
        precio_referencial: Number(precioReferencial),
        unidad,
        activo,
      };
      if (modo === "nuevo") {
        await apiFetch("/catalogos/repuestos", { method: "POST", body });
      } else if (seleccionado) {
        await apiFetch(`/catalogos/repuestos/${seleccionado.id}`, { method: "PATCH", body });
      }
      setSeleccionado(null);
      setModo("consulta");
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el repuesto");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      {/* "Eliminar"/"Buscar" quitados (segunda pasada, punto 1): un repuesto se desactiva, no se elimina. y la lista no pagina. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
        salir={{ onClick: () => setSeleccionado(null) }}
      />
      {error && !seleccionado && modo !== "nuevo" && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>{error}</p>
      )}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={repuestos}
          keyField={(r) => r.id}
          vacio="No hay repuestos creados todavía."
          columns={[
            { header: "Nombre", render: (r) => r.nombre },
            { header: "Categoría", render: (r) => r.categoria },
            { header: "Precio referencial", render: (r) => `$${r.precio_referencial.toFixed(2)}` },
            { header: "Unidad", render: (r) => r.unidad },
            { header: "Estado", render: (r) => <Badge texto={r.activo ? "ACTIVO" : "INACTIVO"} tono={r.activo ? "exito" : "neutral"} /> },
            { header: "Detalle", render: (r) => <Button variant="secondary" onClick={() => abrirDetalle(r)}>Ver</Button> },
          ]}
        />
      </div>

      {(modo === "nuevo" || (seleccionado && modo === "edicion")) && (
        <DetailPanel
          titulo={modo === "nuevo" ? "Nuevo repuesto" : `Repuesto — ${seleccionado?.nombre}`}
          modo={modo}
          onSalir={() => { setSeleccionado(null); setModo("consulta"); }}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={!nombre || !precioReferencial}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            <Select
              label="Categoría"
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
              options={CATEGORIAS_REPUESTO.map((c) => ({ value: c, label: c }))}
            />
            <TextField
              label="Precio referencial"
              type="number"
              min={0}
              step={0.01}
              bloquearNegativo
              value={precioReferencial}
              onChange={(e) => setPrecioReferencial(e.target.value)}
            />
            <Select
              label="Unidad"
              value={unidad}
              onChange={(e) => setUnidad(e.target.value)}
              options={UNIDADES_REPUESTO.map((u) => ({ value: u, label: u }))}
            />
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activo
            </label>
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

function SeccionCatalogoSimple({
  recurso,
  articuloNombre,
  vacioTexto,
}: {
  recurso: string;
  articuloNombre: string;
  vacioTexto: string;
}) {
  const [seleccionado, setSeleccionado] = useState<ItemCatalogoSimple | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [activo, setActivo] = useState(true);
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const { data: items = [], error: errorCarga, refetch } = useSwr<ItemCatalogoSimple[]>(recurso, () =>
    apiFetch<ItemCatalogoSimple[]>(recurso),
  );
  const error =
    errorAccion ??
    (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : `No se pudo cargar ${articuloNombre}`) : null);

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setActivo(true);
    setError(null);
  };

  const abrirDetalle = (item: ItemCatalogoSimple) => {
    setSeleccionado(item);
    setModo("edicion");
    setNombre(item.nombre);
    setActivo(item.activo);
    setError(null);
  };

  const guardar = async () => {
    setError(null);
    setCargando(true);
    try {
      if (modo === "nuevo") {
        await apiFetch(recurso, { method: "POST", body: { nombre, activo } });
      } else if (seleccionado) {
        await apiFetch(`${recurso}/${seleccionado.id}`, { method: "PATCH", body: { nombre, activo } });
      }
      setSeleccionado(null);
      setModo("consulta");
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : `No se pudo guardar ${articuloNombre}`);
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      {/* "Eliminar"/"Buscar" quitados (segunda pasada, punto 1): ${articuloNombre} se desactiva, no se elimina. y la lista no pagina. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
        salir={{ onClick: () => setSeleccionado(null) }}
      />
      {error && !seleccionado && modo !== "nuevo" && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>{error}</p>
      )}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={items}
          keyField={(i) => i.id}
          vacio={vacioTexto}
          columns={[
            { header: "Nombre", render: (i) => i.nombre },
            { header: "Estado", render: (i) => <Badge texto={i.activo ? "ACTIVO" : "INACTIVO"} tono={i.activo ? "exito" : "neutral"} /> },
            { header: "Detalle", render: (i) => <Button variant="secondary" onClick={() => abrirDetalle(i)}>Ver</Button> },
          ]}
        />
      </div>

      {(modo === "nuevo" || (seleccionado && modo === "edicion")) && (
        <DetailPanel
          titulo={modo === "nuevo" ? `Nuevo — ${articuloNombre}` : `${articuloNombre} — ${seleccionado?.nombre}`}
          modo={modo}
          onSalir={() => { setSeleccionado(null); setModo("consulta"); }}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={!nombre}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activo
            </label>
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

export function SeccionCatalogos() {
  const [pestana, setPestana] = useState<Pestana>("tipos");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Catálogos y tablas maestras</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Tipos de documento exigidos a conductores/vehículos, motivos de cancelación/incidencia y talleres
          asociados — datos de referencia que hoy vivían fijos en código o como texto libre sin catálogo.
        </p>
      </Card>

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <TabButton activa={pestana === "tipos"} onClick={() => setPestana("tipos")}>Tipos de documento</TabButton>
        <TabButton activa={pestana === "motivos"} onClick={() => setPestana("motivos")}>Motivos</TabButton>
        <TabButton activa={pestana === "talleres"} onClick={() => setPestana("talleres")}>Talleres</TabButton>
        <TabButton activa={pestana === "marcas"} onClick={() => setPestana("marcas")}>Marcas de vehículo</TabButton>
        <TabButton activa={pestana === "colores"} onClick={() => setPestana("colores")}>Colores de vehículo</TabButton>
        <TabButton activa={pestana === "repuestos"} onClick={() => setPestana("repuestos")}>Repuestos</TabButton>
      </div>

      {pestana === "tipos" && <SeccionTiposDocumento />}
      {pestana === "motivos" && <SeccionMotivos />}
      {pestana === "talleres" && <SeccionTalleres />}
      {pestana === "marcas" && (
        <SeccionCatalogoSimple
          recurso={RECURSO_MARCAS_VEHICULO}
          articuloNombre="la marca"
          vacioTexto="No hay marcas creadas todavía."
        />
      )}
      {pestana === "colores" && (
        <SeccionCatalogoSimple
          recurso={RECURSO_COLORES_VEHICULO}
          articuloNombre="el color"
          vacioTexto="No hay colores creados todavía."
        />
      )}
      {pestana === "repuestos" && <SeccionRepuestos />}
    </div>
  );
}
