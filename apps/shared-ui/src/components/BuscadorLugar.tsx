import { useState } from "react";
import { geocodificarLugar, type LugarGeocodificado } from "../api/rutas";
import { Button } from "./Button";
import { TextField } from "./TextField";

function IconoLupa() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="11" cy="11" r="7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m21 21-4.3-4.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface BuscadorLugarProps {
  label: string;
  placeholder?: string;
  /** Controlado -- el texto vive en el padre (mismo valor que ya muestra el
   * campo "Destino"/de referencia existente), así que las 3 formas de fijar
   * un lugar (mapa, favorita, búsqueda) quedan siempre en sincronía visual. */
  value: string;
  onChangeTexto: (v: string) => void;
  onSeleccionar: (lugar: LugarGeocodificado) => void;
  disabled?: boolean;
}

/**
 * Segunda pasada de ajustes de usabilidad (2026): buscador de lugares por
 * nombre/dirección, mismo patrón visual ya establecido por `UserPicker`
 * (campo + botón "Buscar" + lista de resultados debajo) -- acá el resultado
 * es geocoding real (`geocodificarLugar`) en vez de una consulta al backend.
 * Reutilizado tal cual por web-pasajero (fija el destino del viaje) y
 * web-conductor (marca un lugar de referencia en el mapa) -- cada app decide
 * qué hacer con el resultado en `onSeleccionar`, este componente solo busca
 * y muestra candidatos.
 */
export function BuscadorLugar({ label, placeholder, value, onChangeTexto, onSeleccionar, disabled }: BuscadorLugarProps) {
  const [resultados, setResultados] = useState<LugarGeocodificado[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const buscar = async () => {
    const texto = value.trim();
    if (!texto) return;
    setBuscando(true);
    setError(null);
    setResultados([]);
    try {
      const encontrados = await geocodificarLugar(texto);
      if (encontrados.length === 0) setError("No se encontró ningún lugar con ese nombre.");
      setResultados(encontrados);
    } catch {
      setError("No se pudo buscar en este momento.");
    } finally {
      setBuscando(false);
    }
  };

  const seleccionar = (lugar: LugarGeocodificado) => {
    setResultados([]);
    setError(null);
    onSeleccionar(lugar);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <TextField
            label={label}
            value={value}
            placeholder={placeholder}
            disabled={disabled}
            onChange={(e) => {
              onChangeTexto(e.target.value);
              if (resultados.length > 0) setResultados([]);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                buscar();
              }
            }}
          />
        </div>
        <Button
          type="button"
          variant="secondary"
          onClick={buscar}
          loading={buscando}
          disabled={disabled || !value.trim()}
          style={{ width: "auto", flexShrink: 0 }}
          aria-label="Buscar lugar"
        >
          <IconoLupa />
        </Button>
      </div>
      {error && <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-danger)" }}>{error}</span>}
      {resultados.length > 0 && (
        <div style={{ border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
          {resultados.map((r, i) => (
            <button
              key={`${r.lat}-${r.lon}-${i}`}
              type="button"
              onClick={() => seleccionar(r)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "var(--space-2) var(--space-3)",
                background: "var(--color-surface)",
                color: "var(--color-text)",
                border: "none",
                borderTop: i > 0 ? "1px solid var(--color-border)" : "none",
                cursor: "pointer",
                fontSize: "var(--font-size-sm)",
              }}
            >
              {r.direccion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
