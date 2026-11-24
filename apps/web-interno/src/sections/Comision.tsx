import {
  ApiError,
  Button,
  Card,
  DataTable,
  TextField,
  apiFetch,
  fieldError,
  invalidateSwrPrefix,
  useSwr,
  type Column,
} from "@urbanflet/shared-ui";
import { useState } from "react";

interface ParametroComisionOut {
  id: string;
  tipo: "comision";
  valores: { porcentaje: number };
  vigente_desde: string;
  vigente_hasta: string | null;
}

const RECURSO_VIGENTE = "/parametros/vigente?tipo=comision";
const RECURSO_HISTORIAL = "/parametros/historial?tipo=comision";

const fechaLegible = (iso: string) => new Date(iso).toLocaleString("es-EC", { dateStyle: "medium", timeStyle: "short" });
const pct = (frac: number) => `${(frac * 100).toFixed(2)}%`;

const SIN_HISTORIAL: ParametroComisionOut[] = [];

const columnas: Column<ParametroComisionOut>[] = [
  { header: "Porcentaje", render: (v) => pct(v.valores.porcentaje), numerica: true },
  { header: "Vigente desde", render: (v) => fechaLegible(v.vigente_desde) },
  {
    header: "Vigente hasta",
    render: (v) => (v.vigente_hasta ? fechaLegible(v.vigente_hasta) : "Actual"),
  },
];

/**
 * Comisión de la cooperativa (CU-O10) — el porcentaje que se descuenta de
 * cada viaje pagado, ya existía como parámetro versionado y auditado desde
 * antes (`parametros/service.py::crear_parametro_comision`), pero sin
 * ninguna pantalla: la única forma de cambiarlo era una llamada directa a
 * la API. No entra en "Parámetros Globales" (Módulo 2 de admin_sistema,
 * `/configuracion/parametros-sistema`) — ese es un dominio de sistema
 * completamente distinto (radios de despacho, idioma, zona horaria), y su
 * rol (`admin_sistema`) no coincide con quien puede tocar "reglas de
 * dinero" (`admin_plataforma`/`gerencia`, ver el comentario de
 * `parametros/router.py`). Sección propia, gateada exactamente a esos 2
 * roles -- ni más ni menos que lo que el endpoint ya exige.
 *
 * No es un WorkPanel de búsqueda/edición: los parámetros de este tipo son
 * registros versionados e inmutables (nunca se edita ni se borra una
 * versión, solo se crea una nueva con una fecha de vigencia). El patrón acá
 * es "vigente actual" + "nueva versión" + "historial", no
 * Search/ActionBar/DetailPanel.
 */
export function SeccionComision() {
  const { data: vigente, refetch: refetchVigente } = useSwr<ParametroComisionOut>(RECURSO_VIGENTE, () =>
    apiFetch<ParametroComisionOut>(RECURSO_VIGENTE),
  );
  const {
    data: historial,
    loading: cargandoHistorial,
    refetch: refetchHistorial,
  } = useSwr<ParametroComisionOut[]>(RECURSO_HISTORIAL, () => apiFetch<ParametroComisionOut[]>(RECURSO_HISTORIAL));

  const [porcentajeTexto, setPorcentajeTexto] = useState("");
  const [vigenteDesde, setVigenteDesde] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const crearVersion = async () => {
    setError(null);
    setOk(null);
    const porcentajeNum = Number(porcentajeTexto);
    if (!Number.isFinite(porcentajeNum) || porcentajeNum <= 0 || porcentajeNum > 100) {
      setError(new ApiError("VALIDACION_CLIENTE", "El porcentaje debe ser un número entre 0 y 100.", 422));
      return;
    }
    if (!vigenteDesde) {
      setError(new ApiError("VALIDACION_CLIENTE", "Elige la fecha y hora de vigencia.", 422));
      return;
    }
    setEnviando(true);
    try {
      await apiFetch("/parametros/comisiones", {
        method: "POST",
        body: {
          porcentaje: porcentajeNum / 100,
          vigente_desde: new Date(vigenteDesde).toISOString(),
        },
      });
      // Una versión nueva cierra la anterior en el servidor -- ambos
      // recursos (vigente + historial) quedan obsoletos, no solo uno.
      invalidateSwrPrefix("/parametros/vigente");
      invalidateSwrPrefix("/parametros/historial");
      await Promise.all([refetchVigente(), refetchHistorial()]);
      setOk(`Nueva versión creada: ${pct(porcentajeNum / 100)} vigente desde ${fechaLegible(new Date(vigenteDesde).toISOString())}.`);
      setPorcentajeTexto("");
      setVigenteDesde("");
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  };

  const mensajeGeneral =
    error instanceof ApiError && Object.keys(error.fieldErrors).length === 0
      ? error.message
      : error
        ? "No se pudo completar la operación"
        : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card titulo="Comisión vigente" rotulo="CU-O10">
        {vigente ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            <span style={{ fontFamily: "var(--font-display)", fontSize: "var(--font-size-3xl)", fontWeight: 700 }}>
              {pct(vigente.valores.porcentaje)}
            </span>
            <span style={{ color: "var(--color-text-muted)" }}>Vigente desde {fechaLegible(vigente.vigente_desde)}</span>
          </div>
        ) : (
          <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
        )}
      </Card>

      <Card titulo="Crear nueva versión" rotulo="admin_plataforma / gerencia">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", maxWidth: "360px" }}>
          <TextField
            label="Porcentaje (%)"
            type="number"
            step="0.1"
            min="0"
            max="100"
            value={porcentajeTexto}
            onChange={(e) => setPorcentajeTexto(e.target.value)}
            error={fieldError(error, "porcentaje")}
            hint="Se guarda como fracción (20 → 0.20)."
          />
          <TextField
            label="Vigente desde"
            type="datetime-local"
            value={vigenteDesde}
            onChange={(e) => setVigenteDesde(e.target.value)}
            error={fieldError(error, "vigente_desde")}
          />
          {mensajeGeneral && <p style={{ color: "var(--color-danger)" }}>{mensajeGeneral}</p>}
          {ok && <p style={{ color: "var(--color-success)" }}>{ok}</p>}
          <Button onClick={crearVersion} disabled={enviando}>
            {enviando ? "Guardando…" : "Crear nueva versión"}
          </Button>
        </div>
      </Card>

      <Card titulo="Historial de versiones">
        <DataTable
          columns={columnas}
          rows={historial ?? SIN_HISTORIAL}
          keyField={(v) => v.id}
          vacio={cargandoHistorial ? "Cargando…" : "Sin versiones registradas."}
        />
      </Card>
    </div>
  );
}
