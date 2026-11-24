import { useEffect } from "react";

export interface LightboxProps {
  src: string;
  alt: string;
  onClose: () => void;
}

/**
 * Ampliación a pantalla completa de una imagen — extraído de
 * `EvidenciaImagen` (Ronda 2 del flujo de fallas, Fase A/D) para que
 * `Avatar` (ronda de fotos de perfil) lo reuse tal cual en vez de duplicar
 * el modal. Backdrop oscuro con clic para cerrar, botón ✕ fijo, y Escape —
 * mismo comportamiento en los dos consumidores, un solo lugar para
 * corregirlo si hace falta.
 */
export function Lightbox({ src, alt, onClose }: LightboxProps) {
  useEffect(() => {
    const alPresionar = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", alPresionar);
    return () => document.removeEventListener("keydown", alPresionar);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: "var(--z-lightbox)",
        background: "rgba(0, 0, 0, 0.82)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-4)",
        cursor: "zoom-out",
      }}
    >
      <img
        src={src}
        alt={alt}
        // El clic sobre la propia imagen NO cierra -- solo el fondo. Si no,
        // arrastrar o mirar de cerca cierra sin querer.
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "100%",
          maxHeight: "100%",
          objectFit: "contain",
          borderRadius: "var(--radius-md)",
          cursor: "default",
        }}
      />
      <button
        type="button"
        onClick={onClose}
        aria-label="Cerrar la imagen ampliada"
        title="Cerrar"
        style={{
          position: "fixed",
          top: "var(--space-4)",
          right: "var(--space-4)",
          width: 40,
          height: 40,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          color: "var(--color-text)",
          lineHeight: 1,
          cursor: "pointer",
        }}
      >
        {/* v2: ícono real en vez del emoji "✕". */}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}
