import { ApiError, apiFetch, Badge, Card, DataTable } from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface Informe {
  id: string;
  nombre: string;
  datos_al: string | null;
  retrasado: boolean;
  filas: Record<string, unknown>[];
}

interface Catalogo {
  informes: Informe[];
}

function formatearValor(valor: unknown): string {
  if (valor === null || valor === undefined) return "—";
  if (typeof valor === "number") {
    // Las columnas pct_* vienen como fracción [0,1]; el resto son magnitudes.
    return Number.isInteger(valor) ? String(valor) : valor.toFixed(4);
  }
  return String(valor);
}

function etiquetaColumna(col: string): string {
  return col
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

function InformeCard({ informe }: { informe: Informe }) {
  const columnas = informe.filas.length > 0 ? Object.keys(informe.filas[0]) : [];

  return (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-3)" }}>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>{informe.nombre}</h2>
        <Badge
          texto={informe.datos_al ? `Datos al: ${informe.datos_al}` : "Sin datos publicados"}
          tono={informe.retrasado ? "advertencia" : "exito"}
        />
      </div>

      {informe.retrasado && informe.datos_al && (
        <p
          style={{
            background: "var(--color-danger-bg)",
            color: "var(--color-danger)",
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--font-size-sm)",
            fontWeight: 600,
          }}
        >
          Datos retrasados — última corrida exitosa del dominio: {informe.datos_al}. El informe sigue
          sirviendo esa última versión buena (no se publica un informe parcial).
        </p>
      )}

      {informe.retrasado && !informe.datos_al && (
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Este informe todavía no tiene ningún corte publicado (el dominio nunca completó una carga válida, o el
          proceso de publicación aún no se ha ejecutado).
        </p>
      )}

      <DataTable
        rows={informe.filas}
        keyField={(fila) => JSON.stringify(fila)}
        vacio="Sin filas en este informe."
        columns={columnas.map((c) => ({
          header: etiquetaColumna(c),
          render: (fila: Record<string, unknown>) => formatearValor(fila[c]),
          // Bitácora de revisión (hallazgo #8): alinea a la derecha cuando la
          // columna real trae un número -- ninguna tabla de informes lo
          // hacía todavía, pese a que `DataTable` ya lo soporta.
          numerica: typeof informe.filas[0]?.[c] === "number",
        }))}
      />
    </Card>
  );
}

export function SeccionIndicadores() {
  const [catalogo, setCatalogo] = useState<Catalogo>({ informes: [] });
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cargar = async () => {
    setCargando(true);
    try {
      const datos = await apiFetch<Catalogo>("/plataforma/indicadores");
      setCatalogo(datos);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el catálogo de indicadores");
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const algunoRetrasado = catalogo.informes.some((i) => i.retrasado);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}

      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Catálogo de informes</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          Publicados automáticamente por el proceso de carga de datos (Airflow) tras cada actualización confirmada. Cada informe muestra
          su fecha de datos y, si la corrida del dominio de hoy falló, sigue sirviendo la última versión buena
          con aviso de retraso — nunca un informe parcial.
        </p>
        {!cargando && (
          <Badge
            texto={algunoRetrasado ? "Uno o más informes retrasados" : "Todos los informes al día"}
            tono={algunoRetrasado ? "advertencia" : "exito"}
          />
        )}
      </Card>

      {catalogo.informes.map((informe) => (
        <InformeCard key={informe.id} informe={informe} />
      ))}
    </div>
  );
}
