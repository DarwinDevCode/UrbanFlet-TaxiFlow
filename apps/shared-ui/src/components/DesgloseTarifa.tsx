export interface DesgloseTarifaValores {
  arrancada: number;
  distancia: number;
  espera: number;
  subtotal: number;
}

export interface DesgloseTarifaProps {
  desglose: DesgloseTarifaValores;
  tarifaFinal: number;
  kmRecorridos: number | null;
  minEspera: number | null;
}

// Comparación de flotantes ya redondeados a 2 decimales (backend,
// service_finalizacion.py) -- un epsilon chico evita falsos positivos por
// representación binaria sin exigir igualdad exacta.
const EPSILON = 0.005;

function Fila({ etiqueta, monto, enfasis }: { etiqueta: string; monto: number; enfasis?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "var(--space-3)",
        fontWeight: enfasis ? 600 : 400,
      }}
    >
      <span>{etiqueta}</span>
      <span>${monto.toFixed(2)}</span>
    </div>
  );
}

/** CU-O08 paso 3: "el sistema muestra la tarifa final a ambos actores con el
 * desglose de los tres rubros" -- compartido por `web-pasajero` y
 * `web-conductor` (misma pantalla de viaje finalizado en ambas apps). La
 * línea de "Carrera mínima aplicada" solo se muestra cuando el piso
 * efectivamente subió el total por encima del subtotal calculado; un viaje
 * cuyo subtotal ya supera la carrera mínima no la muestra. */
export function DesgloseTarifa({ desglose, tarifaFinal, kmRecorridos, minEspera }: DesgloseTarifaProps) {
  const pisoAplicado = tarifaFinal - desglose.subtotal > EPSILON;
  const km = kmRecorridos ?? 0;
  const minutos = Math.round(minEspera ?? 0);

  return (
    <div
      style={{
        fontSize: "var(--font-size-sm)",
        color: "var(--color-text-muted)",
        marginTop: "var(--space-1)",
        display: "flex",
        flexDirection: "column",
        gap: "2px",
      }}
    >
      <Fila etiqueta="Arrancada" monto={desglose.arrancada} />
      <Fila etiqueta={`Distancia (${km.toFixed(1)} km)`} monto={desglose.distancia} />
      <Fila etiqueta={`Espera (${minutos} min)`} monto={desglose.espera} />
      <div style={{ borderTop: "1px solid var(--color-border)", margin: "2px 0" }} />
      <Fila etiqueta="Subtotal" monto={desglose.subtotal} enfasis />
      {pisoAplicado && (
        <div style={{ color: "var(--color-accent-deep)" }}>
          <Fila etiqueta="Carrera mínima aplicada" monto={tarifaFinal} enfasis />
        </div>
      )}
    </div>
  );
}
