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
  nombreRol,
  TextField,
  useSwr,
} from "@urbanflet/shared-ui";
import { useState } from "react";

const RECURSO_POLITICA_RETENCION = "/sistema/politica-retencion";

interface Usuario {
  id: string;
  nombre: string;
  telefono: string | null;
  email: string | null;
  roles: string[];
  estado: string;
  anonimizado: boolean;
}

interface PoliticaRetencionItem {
  coleccion: string;
  descripcion: string;
  retencion: string;
  fuente: "indice_ttl_real" | "documentado";
}

const TEXTO_CONFIRMACION = "ANONIMIZAR";

function SeccionAnonimizacion() {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<Usuario[]>([]);
  const [seleccionado, setSeleccionado] = useState<Usuario | null>(null);
  const [confirmacion, setConfirmacion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [buscando, setBuscando] = useState(false);

  const buscar = async () => {
    if (!texto.trim()) return;
    setError(null);
    setBuscando(true);
    try {
      const resp = await apiFetch<{ items: Usuario[]; total: number }>(
        `/usuarios?texto=${encodeURIComponent(texto)}&limit=20`,
      );
      setResultados(resp.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo buscar usuarios");
    } finally {
      setBuscando(false);
    }
  };

  const abrirConfirmacion = (u: Usuario) => {
    setSeleccionado(u);
    setConfirmacion("");
    setError(null);
  };

  const anonimizar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/usuarios/${seleccionado.id}/anonimizar`, {
        method: "POST",
        body: { confirmacion },
      });
      setSeleccionado(null);
      setResultados((prev) => prev.filter((u) => u.id !== seleccionado.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo anonimizar la cuenta");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Anonimizar una cuenta</h3>
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
        Acción irreversible (derechos ARCO / LOPDP): borra nombre, teléfono y correo real de la cuenta y los
        reemplaza por un seudónimo. No existe forma de deshacerla. Los eventos de bitácora ya escritos con esta
        cuenta se conservan sin modificarse — el identificador que usan (un id interno, nunca el nombre) sigue
        siendo válido; el propio evento de anonimización queda registrado, sin exponer el dato purgado.
      </p>
      {/* "Nuevo"/"Eliminar" quitados (segunda pasada, punto 1): esta pantalla
          solo anonimiza cuentas existentes, vía "Anonimizar" en el
          resultado -- ningún rol tiene un uso real para crear o eliminar
          acá. */}
      <ActionBar
        actualizar={{ onClick: () => buscar(), disabled: !texto.trim() }}
        buscar={{ onClick: () => buscar(), disabled: !texto.trim() }}
        salir={{ onClick: () => { setTexto(""); setResultados([]); } }}
      />
      <div style={{ marginTop: "var(--space-3)", maxWidth: 400 }}>
        <TextField
          label="Nombre, teléfono o correo"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && buscar()}
        />
      </div>
      {error && !seleccionado && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>
          {error}
        </p>
      )}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={resultados}
          keyField={(u) => u.id}
          vacio={buscando ? "Buscando…" : "Sin resultados — busca por nombre, teléfono o correo."}
          columns={[
            { header: "Nombre", render: (u) => u.nombre },
            { header: "Teléfono", render: (u) => u.telefono ?? "—" },
            { header: "Correo", render: (u) => u.email ?? "—" },
            { header: "Roles", render: (u) => u.roles.map(nombreRol).join(", ") },
            {
              header: "Acción",
              render: (u) =>
                u.anonimizado ? (
                  <Badge texto="YA ANONIMIZADA" tono="neutral" />
                ) : (
                  <Button variant="danger" onClick={() => abrirConfirmacion(u)}>Anonimizar</Button>
                ),
            },
          ]}
        />
      </div>

      {seleccionado && (
        <DetailPanel
          titulo={`Anonimizar cuenta — ${seleccionado.nombre}`}
          modo="edicion"
          onSalir={() => setSeleccionado(null)}
          onAceptar={anonimizar}
          aceptarLabel="Anonimizar de forma permanente"
          aceptarDisabled={confirmacion !== TEXTO_CONFIRMACION}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <DetailField label="Nombre actual" value={seleccionado.nombre} />
            <DetailField label="Teléfono" value={seleccionado.telefono ?? "—"} />
            <DetailField label="Correo" value={seleccionado.email ?? "—"} />
            <p style={{ color: "var(--color-danger)", fontWeight: 600, fontSize: "var(--font-size-sm)" }}>
              Esto es irreversible. El nombre, teléfono y correo de esta cuenta se van a borrar de forma
              permanente y se reemplazan por un seudónimo. Escribe {TEXTO_CONFIRMACION} para confirmar.
            </p>
            <TextField
              label={`Escribe "${TEXTO_CONFIRMACION}" para confirmar`}
              value={confirmacion}
              onChange={(e) => setConfirmacion(e.target.value)}
            />
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

function SeccionPoliticaRetencion() {
  const { data: items = [], error: errorCarga } = useSwr<PoliticaRetencionItem[]>(RECURSO_POLITICA_RETENCION, () =>
    apiFetch<PoliticaRetencionItem[]>(RECURSO_POLITICA_RETENCION),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar la política de retención"
    : null;

  return (
    <Card>
      <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Política de retención vigente</h3>
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
        Solo lectura. "TTL real" significa que el valor se lee del índice configurado en la base de datos, no de
        un texto escrito a mano.
      </p>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={items}
          keyField={(i) => i.coleccion}
          vacio="Sin datos."
          columns={[
            { header: "Colección", render: (i) => i.coleccion },
            { header: "Descripción", render: (i) => i.descripcion },
            { header: "Retención", render: (i) => i.retencion },
            {
              header: "Fuente",
              render: (i) => (
                <Badge
                  texto={i.fuente === "indice_ttl_real" ? "TTL REAL" : "DOCUMENTADO"}
                  tono={i.fuente === "indice_ttl_real" ? "exito" : "neutral"}
                />
              ),
            },
          ]}
        />
      </div>
    </Card>
  );
}

export function SeccionGobernanzaDatos() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Gobernanza de datos</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Anonimización de cuentas (derechos ARCO / LOPDP) y política de retención vigente por tipo de dato.
        </p>
      </Card>
      <SeccionAnonimizacion />
      <SeccionPoliticaRetencion />
    </div>
  );
}
