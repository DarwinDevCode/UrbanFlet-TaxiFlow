import { useEffect, useState, type ReactNode } from "react";
import { apiFetch, ApiError } from "../api/client";
import { aplicarDensidad } from "../densidad";
import { aplicarTema } from "../theme";
import { Card } from "./Card";
import { Select } from "./Select";
import { TextField } from "./TextField";

interface PreferenciasOut {
  tema: "claro" | "oscuro";
  densidad_tablas: "comoda" | "compacta";
  notificaciones_push: Record<string, boolean>;
  sonido_oferta: boolean;
  vibracion_oferta: boolean;
  recordatorio_turno_hora: string | null;
}

interface CategoriaNotificacion {
  valor: string;
  etiqueta: string;
}

/** Sección "Ajustes" — Sección 1.4/2.3/3.2 de
 * `specs/specs-administrativas/ux_complementaria.md`. Componente único
 * reutilizado por las 3 apps: tema claro/oscuro y notificaciones push por
 * categoría siempre presentes; el resto (densidad de tablas, preferencias
 * de turno) son slots opcionales activados por prop, para no forzar campos
 * que no aplican a un rol. Las categorías de push (`/notificaciones/
 * categorias`) nunca incluyen "seguridad" -- esas alertas son exclusivas
 * del Módulo 6.3 de Administración, un usuario final no puede apagarlas. */
export function AjustesPropios({
  mostrarDensidad,
  mostrarTurno,
  version,
  extra,
}: {
  mostrarDensidad?: boolean;
  mostrarTurno?: boolean;
  version: string;
  extra?: ReactNode;
}) {
  const [prefs, setPrefs] = useState<PreferenciasOut | null>(null);
  const [categorias, setCategorias] = useState<CategoriaNotificacion[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [guardandoCampo, setGuardandoCampo] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<PreferenciasOut>("/preferencias")
      .then((datos) => {
        setPrefs(datos);
        aplicarTema(datos.tema);
        if (mostrarDensidad) aplicarDensidad(datos.densidad_tablas);
      })
      .catch(setError);
    apiFetch<CategoriaNotificacion[]>("/notificaciones/categorias")
      .then(setCategorias)
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const guardar = async (campo: string, valor: unknown) => {
    setError(null);
    setGuardandoCampo(campo);
    try {
      const datos = await apiFetch<PreferenciasOut>("/preferencias", { method: "PATCH", body: { [campo]: valor } });
      setPrefs(datos);
      if (campo === "tema") aplicarTema(datos.tema);
      if (campo === "densidad_tablas") aplicarDensidad(datos.densidad_tablas);
    } catch (e) {
      setError(e);
    } finally {
      setGuardandoCampo(null);
    }
  };

  const guardarCategoriaPush = (categoria: string, activo: boolean) =>
    guardar("notificaciones_push", { ...(prefs?.notificaciones_push ?? {}), [categoria]: activo });

  const mensajeGeneral =
    error instanceof ApiError ? error.message : error ? "No se pudo completar la operación" : null;

  if (!prefs) {
    return (
      <Card>
        <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Ajustes</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Preferencias de esta cuenta. Los cambios se aplican de inmediato.
        </p>
        {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <Select
            label="Tema"
            value={prefs.tema}
            onChange={(e) => guardar("tema", e.target.value)}
            disabled={guardandoCampo === "tema"}
            options={[
              { value: "claro", label: "Claro" },
              { value: "oscuro", label: "Oscuro" },
            ]}
          />
          {mostrarDensidad && (
            <Select
              label="Densidad de tablas"
              value={prefs.densidad_tablas}
              onChange={(e) => guardar("densidad_tablas", e.target.value)}
              disabled={guardandoCampo === "densidad_tablas"}
              options={[
                { value: "comoda", label: "Cómoda" },
                { value: "compacta", label: "Compacta" },
              ]}
            />
          )}
        </div>
      </Card>

      {categorias.length > 0 && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Notificaciones push</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Elige qué categorías te llegan como notificación push (fuera de la app). Desactivar una categoría no
            borra su historial — sigue disponible en la bandeja de notificaciones. Las alertas de seguridad del
            sistema no se pueden desactivar desde aquí.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {categorias.map((c) => (
              <label
                key={c.valor}
                style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}
              >
                <input
                  type="checkbox"
                  checked={prefs.notificaciones_push[c.valor] ?? true}
                  disabled={guardandoCampo === "notificaciones_push"}
                  onChange={(e) => guardarCategoriaPush(c.valor, e.target.checked)}
                />
                {c.etiqueta}
              </label>
            ))}
          </div>
        </Card>
      )}

      {mostrarTurno && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Preferencias de turno</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Cómo recibes el aviso de una nueva oferta, y un recordatorio para iniciar turno a tu hora habitual. Esto
            no cambia qué ofertas te llegan — el reparto entre socios lo sigue decidiendo el sistema.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
              <input
                type="checkbox"
                checked={prefs.sonido_oferta}
                disabled={guardandoCampo === "sonido_oferta"}
                onChange={(e) => guardar("sonido_oferta", e.target.checked)}
              />
              Sonido al llegar una nueva oferta
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
              <input
                type="checkbox"
                checked={prefs.vibracion_oferta}
                disabled={guardandoCampo === "vibracion_oferta"}
                onChange={(e) => guardar("vibracion_oferta", e.target.checked)}
              />
              Vibración al llegar una nueva oferta
            </label>
            <div style={{ maxWidth: 260 }}>
              <TextField
                label="Recordatorio para iniciar turno (hora habitual)"
                type="time"
                value={prefs.recordatorio_turno_hora ?? ""}
                disabled={guardandoCampo === "recordatorio_turno_hora"}
                onChange={(e) => guardar("recordatorio_turno_hora", e.target.value || null)}
              />
            </div>
          </div>
        </Card>
      )}

      {extra}

      <Card>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
          Versión de la app: {version}
        </p>
      </Card>
    </div>
  );
}
