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
  TextField,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

// Todos los roles del sistema -- un flag puede gatear una función tanto
// para personal interno como para pasajero/conductor (a diferencia del
// catálogo de Módulo 1, que excluye estos dos porque ahí se trata de
// creación de cuentas, no de visibilidad de función).
const TODOS_LOS_ROLES = [
  "pasajero",
  "conductor",
  "admin_captacion",
  "coordinador_operaciones",
  "coordinador_flota",
  "jefe_mantenimiento",
  "admin_financiero",
  "supervisor_cumplimiento",
  "responsable_plataforma",
  "gerencia",
  "integracion_externa",
  "admin_plataforma",
  "admin_sistema",
];

interface Flag {
  id: string;
  nombre: string;
  activo: boolean;
  porcentaje: number | null;
  roles: string[];
  creado_en: string;
  actualizado_en: string;
}

function RolesCheckboxes({ seleccionados, onChange }: { seleccionados: string[]; onChange: (roles: string[]) => void }) {
  const alternar = (rol: string) => {
    onChange(seleccionados.includes(rol) ? seleccionados.filter((r) => r !== rol) : [...seleccionados, rol]);
  };
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-2)" }}>
      {TODOS_LOS_ROLES.map((rol) => (
        <label key={rol} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
          <input type="checkbox" checked={seleccionados.includes(rol)} onChange={() => alternar(rol)} />
          {rol}
        </label>
      ))}
    </div>
  );
}

export function SeccionFeatureFlags() {
  const [flags, setFlags] = useState<Flag[]>([]);
  const [seleccionado, setSeleccionado] = useState<Flag | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  // Formulario de creación.
  const [nombre, setNombre] = useState("");
  const [activo, setActivo] = useState(false);
  const [porcentaje, setPorcentaje] = useState("");
  const [rolesForm, setRolesForm] = useState<string[]>([]);

  // Edición.
  const [activoEdit, setActivoEdit] = useState(false);
  const [porcentajeEdit, setPorcentajeEdit] = useState("");
  const [rolesEdit, setRolesEdit] = useState<string[]>([]);

  const cargar = async () => {
    const datos = await apiFetch<Flag[]>("/configuracion/flags");
    setFlags(datos);
  };

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los flags"));
  }, []);

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setActivo(false);
    setPorcentaje("");
    setRolesForm([]);
    setError(null);
  };

  const abrirDetalle = (f: Flag) => {
    setSeleccionado(f);
    setModo("edicion");
    setActivoEdit(f.activo);
    setPorcentajeEdit(f.porcentaje === null ? "" : String(f.porcentaje));
    setRolesEdit(f.roles);
    setError(null);
  };

  const crear = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/configuracion/flags", {
        method: "POST",
        body: {
          nombre,
          activo,
          porcentaje: porcentaje === "" ? undefined : Number(porcentaje),
          roles: rolesForm.length > 0 ? rolesForm : undefined,
        },
      });
      setModo("consulta");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear el flag");
    } finally {
      setCargando(false);
    }
  };

  const guardar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      const actualizado = await apiFetch<Flag>(`/configuracion/flags/${seleccionado.nombre}`, {
        method: "PATCH",
        body: {
          activo: activoEdit,
          porcentaje: porcentajeEdit === "" ? null : Number(porcentajeEdit),
          roles: rolesEdit,
        },
      });
      setSeleccionado(actualizado);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo actualizar el flag");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Funcionalidades (feature flags)</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Activa o desactiva una función por porcentaje de usuarios o por rol, sin desplegar código nuevo. Los flags
          gobiernan visibilidad de funcionalidad — nunca reemplazan un control de acceso real.
        </p>
      </Card>

      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica: un flag se desactiva, no se elimina." }}
        buscar={{ onClick: () => {}, disabled: true, title: "No aplica: la lista de flags no pagina, se ve completa." }}
        salir={{ onClick: () => setSeleccionado(null) }}
      />

      <Card>
        {error && !seleccionado && modo !== "nuevo" && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <DataTable
          rows={flags}
          keyField={(f) => f.id}
          vacio="No hay feature flags creados todavía."
          columns={[
            { header: "Nombre", render: (f) => f.nombre },
            { header: "Estado", render: (f) => <Badge texto={f.activo ? "ACTIVO" : "INACTIVO"} tono={f.activo ? "exito" : "neutral"} /> },
            { header: "Porcentaje", render: (f) => (f.porcentaje === null ? "100%" : `${f.porcentaje}%`) },
            { header: "Roles", render: (f) => (f.roles.length > 0 ? f.roles.join(", ") : "Todos") },
            {
              header: "Detalle",
              render: (f) => (
                <Button variant="secondary" onClick={() => abrirDetalle(f)}>
                  Ver
                </Button>
              ),
            },
          ]}
        />
      </Card>

      {modo === "nuevo" && (
        <DetailPanel
          titulo="Nuevo feature flag"
          modo="nuevo"
          onSalir={() => setModo("consulta")}
          onAceptar={crear}
          aceptarLabel="Crear flag"
          aceptarDisabled={!nombre}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
              <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
              <TextField label="Porcentaje (vacío = 100%)" type="number" value={porcentaje} onChange={(e) => setPorcentaje(e.target.value)} />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activo desde su creación
            </label>
            <div>
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                Roles habilitados (vacío = todos los roles)
              </p>
              <RolesCheckboxes seleccionados={rolesForm} onChange={setRolesForm} />
            </div>
          </div>
        </DetailPanel>
      )}

      {seleccionado && modo === "edicion" && (
        <DetailPanel titulo={`Flag — ${seleccionado.nombre}`} modo={modo} onSalir={() => setSeleccionado(null)} onAceptar={guardar} aceptarLabel="Guardar cambios" aceptarLoading={cargando}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Nombre" value={seleccionado.nombre} />
              <DetailField label="Creado" value={new Date(seleccionado.creado_en).toLocaleString()} />
              <DetailField label="Actualizado" value={new Date(seleccionado.actualizado_en).toLocaleString()} />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activoEdit} onChange={(e) => setActivoEdit(e.target.checked)} />
              Activo
            </label>
            <TextField label="Porcentaje (vacío = 100%)" type="number" value={porcentajeEdit} onChange={(e) => setPorcentajeEdit(e.target.value)} />
            <div>
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                Roles habilitados (vacío = todos los roles)
              </p>
              <RolesCheckboxes seleccionados={rolesEdit} onChange={setRolesEdit} />
            </div>
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
