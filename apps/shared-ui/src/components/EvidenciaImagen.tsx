import { useEffect, useState } from "react";
import { obtenerArchivoBlobUrl } from "../api/client";
import { Lightbox } from "./Lightbox";

export interface EvidenciaImagenProps {
  archivoId: string;
  /** Lado máximo en px de la MINIATURA. 120 es el tamaño ya usado en las
   * bandejas de `web-interno`; el detalle de un registro puede pedir más.
   * No afecta a la ampliación, que siempre usa el espacio de la pantalla. */
  tamano?: number;
  alt?: string;
  /** Desactiva la ampliación a pantalla completa. Por defecto está activa —
   * una miniatura de 120px no alcanza para leer una placa o una pieza rota. */
  ampliable?: boolean;
}

/**
 * Miniatura de un archivo servido por `GET /archivos/{id}` (Ronda 2, Fase A),
 * ampliable a tamaño completo con un clic.
 *
 * Ese endpoint exige Bearer token, así que un `<img src>` plano no sirve — hay
 * que descargarlo como blob y renderizar el Object URL, revocándolo al
 * desmontar. La ampliación reusa EL MISMO blob que ya se descargó para la
 * miniatura: abrirla no dispara una segunda petición.
 *
 * Vive en `shared-ui` porque lo consumen los dos portales que muestran
 * evidencia fotográfica: `web-interno` (detalle de orden de mantenimiento,
 * cronología de actividades de la orden, bandeja y detalle de reportes de
 * falla) y `web-conductor` (detalle de un reporte propio). Cualquier arreglo
 * acá los cubre a todos a la vez.
 */
export function EvidenciaImagen({
  archivoId,
  tamano = 120,
  alt = "Evidencia adjunta",
  ampliable = true,
}: EvidenciaImagenProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [ampliada, setAmpliada] = useState(false);

  useEffect(() => {
    let cancelado = false;
    let objectUrl: string | null = null;
    setError(false);
    obtenerArchivoBlobUrl(archivoId)
      .then((u) => {
        if (cancelado) {
          URL.revokeObjectURL(u);
          return;
        }
        objectUrl = u;
        setUrl(u);
      })
      .catch(() => {
        if (!cancelado) setError(true);
      });
    return () => {
      cancelado = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [archivoId]);

  if (error) {
    return (
      <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>No se pudo cargar la foto</span>
    );
  }
  if (!url) {
    return <span style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>Cargando…</span>;
  }

  const miniatura = (
    <img
      src={url}
      alt={alt}
      style={{ maxWidth: tamano, maxHeight: tamano, borderRadius: "var(--radius-sm)", display: "block" }}
    />
  );

  if (!ampliable) return miniatura;

  return (
    <>
      {/* Botón y no un <img onClick>: así la miniatura es alcanzable por
          teclado y anuncia que se puede abrir, sin depender del cursor. */}
      <button
        type="button"
        onClick={() => setAmpliada(true)}
        aria-label={`Ampliar: ${alt}`}
        title="Ampliar"
        style={{
          padding: 0,
          border: "none",
          background: "none",
          cursor: "zoom-in",
          display: "block",
          lineHeight: 0,
        }}
      >
        {miniatura}
      </button>

      {ampliada && <Lightbox src={url} alt={alt} onClose={() => setAmpliada(false)} />}
    </>
  );
}
