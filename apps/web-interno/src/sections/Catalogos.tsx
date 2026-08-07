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
  TextField,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface Zona {
  id: string;
  nombre: string;
  geometria: Record<string, unknown>;
}

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
  activo: boolean;
}

type Pestana = "zonas" | "tipos" | "motivos" | "talleres";

function TabButton({ activa, onClick, children }: { activa: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "var(--space-2) var(--space-4)",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--color-border)",
        background: activa ? "var(--color-accent)" : "var(--color-surface)",
        color: activa ? "#fff" : "var(--color-text)",
        fontWeight: 600,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

function SeccionZonas() {
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [seleccionada, setSeleccionada] = useState<Zona | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => setZonas(await apiFetch<Zona[]>("/parametros/zonas", { auth: false }));

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar las zonas"));
  }, []);

  const abrirNuevo = () => {
    setSeleccionada(null);
    setModo("nuevo");
    setNombre("");
    setError(null);
  };

  const abrirDetalle = (z: Zona) => {
    setSeleccionada(z);
    setModo("edicion");
    setNombre(z.nombre);
    setError(null);
  };

  const guardar = async () => {
    setError(null);
    setCargando(true);
    try {
      if (modo === "nuevo") {
        await apiFetch("/parametros/zonas", { method: "POST", body: { nombre, geometria: {} } });
      } else if (seleccionada) {
        await apiFetch(`/parametros/zonas/${seleccionada.id}`, { method: "PATCH", body: { nombre, geometria: seleccionada.geometria } });
      }
      setSeleccionada(null);
      setModo("consulta");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar la zona");
    } finally {
      setCargando(false);
    }
  };

  const eliminar = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/parametros/zonas/${seleccionada.id}`, { method: "DELETE" });
      setSeleccionada(null);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo eliminar la zona");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "Elige una zona en la tabla y usa 'Eliminar' dentro de su detalle." }}
        buscar={{ onClick: () => {}, disabled: true, title: "No aplica: la lista de zonas no pagina." }}
        salir={{ onClick: () => setSeleccionada(null) }}
      />
      {error && !seleccionada && modo !== "nuevo" && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>{error}</p>}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={zonas}
          keyField={(z) => z.id}
          vacio="No hay zonas creadas todavía."
          columns={[
            { header: "Nombre", render: (z) => z.nombre },
            { header: "Detalle", render: (z) => <Button variant="secondary" onClick={() => abrirDetalle(z)}>Ver</Button> },
          ]}
        />
      </div>

      {(modo === "nuevo" || (seleccionada && modo === "edicion")) && (
        <DetailPanel
          titulo={modo === "nuevo" ? "Nueva zona" : `Zona — ${seleccionada?.nombre}`}
          modo={modo}
          onSalir={() => { setSeleccionada(null); setModo("consulta"); }}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={!nombre}
          aceptarLoading={cargando}
          accionesExtra={
            modo === "edicion" ? (
              <div style={{ minWidth: 140 }}>
                <Button variant="danger" onClick={eliminar} loading={cargando}>Eliminar</Button>
              </div>
            ) : undefined
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

function SeccionTiposDocumento() {
  const [tipos, setTipos] = useState<TipoDocumento[]>([]);
  const [seleccionado, setSeleccionado] = useState<TipoDocumento | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [aplicaA, setAplicaA] = useState<"conductor" | "vehiculo" | "ambos">("ambos");
  const [activo, setActivo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => setTipos(await apiFetch<TipoDocumento[]>("/catalogos/tipos-documento"));

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los tipos de documento"));
  }, []);

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
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el tipo de documento");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica: un tipo de documento se desactiva, no se elimina." }}
        buscar={{ onClick: () => {}, disabled: true, title: "No aplica: la lista no pagina." }}
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
  const [motivos, setMotivos] = useState<Motivo[]>([]);
  const [seleccionado, setSeleccionado] = useState<Motivo | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [categoria, setCategoria] = useState<"cancelacion" | "incidencia">("cancelacion");
  const [activo, setActivo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => setMotivos(await apiFetch<Motivo[]>("/catalogos/motivos"));

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los motivos"));
  }, []);

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
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el motivo");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica: un motivo se desactiva, no se elimina." }}
        buscar={{ onClick: () => {}, disabled: true, title: "No aplica: la lista no pagina." }}
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
  const [talleres, setTalleres] = useState<Taller[]>([]);
  const [seleccionado, setSeleccionado] = useState<Taller | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [direccion, setDireccion] = useState("");
  const [telefono, setTelefono] = useState("");
  const [activo, setActivo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => setTalleres(await apiFetch<Taller[]>("/catalogos/talleres"));

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los talleres"));
  }, []);

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setDireccion("");
    setTelefono("");
    setActivo(true);
    setError(null);
  };

  const abrirDetalle = (t: Taller) => {
    setSeleccionado(t);
    setModo("edicion");
    setNombre(t.nombre);
    setDireccion(t.direccion);
    setTelefono(t.telefono);
    setActivo(t.activo);
    setError(null);
  };

  const guardar = async () => {
    setError(null);
    setCargando(true);
    try {
      if (modo === "nuevo") {
        await apiFetch("/catalogos/talleres", { method: "POST", body: { nombre, direccion, telefono, activo } });
      } else if (seleccionado) {
        await apiFetch(`/catalogos/talleres/${seleccionado.id}`, { method: "PATCH", body: { nombre, direccion, telefono, activo } });
      }
      setSeleccionado(null);
      setModo("consulta");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el taller");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica: un taller se desactiva, no se elimina." }}
        buscar={{ onClick: () => {}, disabled: true, title: "No aplica: la lista no pagina." }}
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
  const [pestana, setPestana] = useState<Pestana>("zonas");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Catálogos y tablas maestras</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Zonas de despacho, tipos de documento exigidos a conductores/vehículos, motivos de cancelación/incidencia y
          talleres asociados — datos de referencia que hoy vivían fijos en código o como texto libre sin catálogo.
        </p>
      </Card>

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <TabButton activa={pestana === "zonas"} onClick={() => setPestana("zonas")}>Zonas</TabButton>
        <TabButton activa={pestana === "tipos"} onClick={() => setPestana("tipos")}>Tipos de documento</TabButton>
        <TabButton activa={pestana === "motivos"} onClick={() => setPestana("motivos")}>Motivos</TabButton>
        <TabButton activa={pestana === "talleres"} onClick={() => setPestana("talleres")}>Talleres</TabButton>
      </div>

      {pestana === "zonas" && <SeccionZonas />}
      {pestana === "tipos" && <SeccionTiposDocumento />}
      {pestana === "motivos" && <SeccionMotivos />}
      {pestana === "talleres" && <SeccionTalleres />}
    </div>
  );
}
