import { Card } from "./Card";

export interface PreguntaFrecuente {
  pregunta: string;
  respuesta: string;
}

/** Centro de ayuda — Sección 4.1 de `specs/specs-administrativas/
 * ux_complementaria.md`. FAQ estática (en código, no en base de datos —
 * alcance mínimo pedido explícitamente por la spec: "no implica un sistema
 * de tickets") + un canal de contacto real. `preguntas`/`contacto` son
 * props porque cada app tiene una audiencia distinta (pasajero, conductor,
 * personal interno) con dudas distintas. */
export function CentroAyuda({
  preguntas,
  correoContacto,
  telefonoContacto,
}: {
  preguntas: PreguntaFrecuente[];
  correoContacto: string;
  telefonoContacto: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Centro de ayuda</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Preguntas frecuentes y cómo contactar a la cooperativa si necesitas ayuda con algo que no está aquí.
        </p>
      </Card>

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Contacto</h3>
        <p style={{ margin: 0 }}>
          Correo: <a href={`mailto:${correoContacto}`}>{correoContacto}</a>
        </p>
        <p style={{ margin: 0, marginTop: "var(--space-2)" }}>
          Teléfono: <a href={`tel:${telefonoContacto}`}>{telefonoContacto}</a>
        </p>
      </Card>

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Preguntas frecuentes</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {preguntas.map((p) => (
            <div key={p.pregunta}>
              <p style={{ fontWeight: 600, margin: 0 }}>{p.pregunta}</p>
              <p style={{ color: "var(--color-text-muted)", margin: 0, marginTop: "var(--space-1)" }}>{p.respuesta}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
