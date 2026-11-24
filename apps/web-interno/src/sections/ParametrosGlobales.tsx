import {
  ApiError,
  Card,
  ReadOnlyActions,
  Select,
  TextField,
  apiFetch,
  fieldError,
  useReadOnlyGate,
} from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface ParametroSistemaOut {
  id: string | null;
  idioma: string;
  zona_horaria: string;
  radios_despacho_m: number[];
  oferta_expira_segundos: number;
  vigente_desde: string | null;
  vigente_hasta: string | null;
}

// Punto #2 de la ronda de usabilidad de admin_sistema (2026-08-07): antes
// texto libre -- el backend no valida contra un enum (sigue siendo `str`
// en `configuracion/schemas.py`, cambiarlo a un `Literal` real requeriría
// migrar el único valor ya publicado), así que el control real de estos 2
// campos queda del lado del frontend con un catálogo curado. "idioma" no
// se consume todavía en ningún renderizado (grep confirmado: solo se
// guarda), así que la lista es deliberadamente corta.
const IDIOMAS = [
  { value: "es", label: "Español" },
  { value: "en", label: "English" },
];

const ZONAS_HORARIAS = [
  { value: "America/Guayaquil", label: "America/Guayaquil (Ecuador continental)" },
  { value: "Pacific/Galapagos", label: "Pacific/Galapagos (Ecuador insular)" },
  { value: "America/Bogota", label: "America/Bogota" },
  { value: "America/Lima", label: "America/Lima" },
  { value: "America/Mexico_City", label: "America/Mexico_City" },
  { value: "UTC", label: "UTC" },
];

export function SeccionParametrosGlobales() {
  const [vigente, setVigente] = useState<ParametroSistemaOut | null>(null);
  const [idioma, setIdioma] = useState("es");
  const [zonaHoraria, setZonaHoraria] = useState("America/Guayaquil");
  const [radiosTexto, setRadiosTexto] = useState("300, 600, 1000");
  const [ofertaExpira, setOfertaExpira] = useState(20);
  const [error, setError] = useState<unknown>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const { editando, editar, bloquear } = useReadOnlyGate();

  const aplicarValores = (datos: ParametroSistemaOut) => {
    setVigente(datos);
    setIdioma(datos.idioma);
    setZonaHoraria(datos.zona_horaria);
    setRadiosTexto(datos.radios_despacho_m.join(", "));
    setOfertaExpira(datos.oferta_expira_segundos);
  };

  const cargar = async () => aplicarValores(await apiFetch<ParametroSistemaOut>("/configuracion/parametros-sistema"));

  useEffect(() => {
    cargar().catch(setError);
  }, []);

  const radios = radiosTexto
    .split(",")
    .map((r) => Number(r.trim()))
    .filter((r) => Number.isFinite(r) && r > 0);

  const cancelar = () => {
    setError(null);
    if (vigente) aplicarValores(vigente);
    bloquear();
  };

  const publicar = async () => {
    setError(null);
    setOk(null);
    setCargando(true);
    try {
      await apiFetch("/configuracion/parametros-sistema", {
        method: "POST",
        body: {
          idioma,
          zona_horaria: zonaHoraria,
          radios_despacho_m: radios,
          oferta_expira_segundos: ofertaExpira,
          vigente_desde: new Date().toISOString(),
        },
      });
      setOk("Configuración publicada. El motor de despacho la usa desde la próxima búsqueda de conductor.");
      await cargar();
      bloquear();
    } catch (e) {
      setError(e);
    } finally {
      setCargando(false);
    }
  };

  const mensajeGeneral =
    error instanceof ApiError ? error.message : error ? "No se pudo completar la operación" : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Parámetros globales del sistema</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          {vigente?.id
            ? `Publicada — vigente desde ${vigente.vigente_desde ? new Date(vigente.vigente_desde).toLocaleString() : "—"}.`
            : "Nunca se publicó una configuración — rigen los valores por defecto del sistema."}
        </p>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Los radios de despacho gobiernan el auto-despacho de viajes: el primer valor es el radio inicial
          de búsqueda de conductor, los siguientes son las ampliaciones sucesivas si no aparece candidato. Cambiar
          esto afecta viajes nuevos de inmediato — no hay ventana de gracia. Los campos quedan bloqueados hasta
          pulsar "Editar", para evitar un cambio accidental en configuración crítica.
        </p>
      </Card>

      <Card>
        {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
        {ok && <p style={{ color: "var(--color-success)", fontSize: "var(--font-size-sm)" }}>{ok}</p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <Select label="Idioma" options={IDIOMAS} disabled={!editando} value={idioma} onChange={(e) => setIdioma(e.target.value)} />
          <Select
            label="Zona horaria"
            options={ZONAS_HORARIAS}
            disabled={!editando}
            value={zonaHoraria}
            onChange={(e) => setZonaHoraria(e.target.value)}
          />
          <TextField
            label="Radios de despacho en metros (separados por coma, de menor a mayor)"
            disabled={!editando}
            value={radiosTexto}
            onChange={(e) => setRadiosTexto(e.target.value)}
            error={fieldError(error, "radios_despacho_m")}
          />
          <TextField
            label="Expiración de oferta a conductor (segundos)"
            type="number"
            min={5}
            max={300}
            disabled={!editando}
            value={ofertaExpira}
            onChange={(e) => setOfertaExpira(Number(e.target.value))}
            error={fieldError(error, "oferta_expira_segundos")}
          />
        </div>
        <div style={{ marginTop: "var(--space-4)" }}>
          <ReadOnlyActions
            editando={editando}
            onEditar={editar}
            onCancelar={cancelar}
            onGuardar={publicar}
            guardarLabel="Publicar configuración"
            guardarDisabled={radios.length === 0}
            guardarLoading={cargando}
          />
        </div>
      </Card>
    </div>
  );
}
