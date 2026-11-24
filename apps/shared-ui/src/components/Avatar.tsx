import { useState } from "react";
import { urlArchivo } from "../api/client";
import avatarPorDefecto from "../assets/avatar-por-defecto.png";
import { Lightbox } from "./Lightbox";

export interface AvatarProps {
  /** Id de un archivo subido con contexto `foto_perfil` (ver
   * `archivos/service.py`), o `null`/`undefined` para el avatar por
   * defecto. Ese contexto es de LECTURA PÚBLICA a propósito -- por eso este
   * componente puede armar el `<img src>` directo, sin el vaivén de
   * descargar como blob autenticado que sí necesita `EvidenciaImagen`
   * (evidencia operativa, contextos gateados por rol). */
  fotoUrl?: string | null;
  nombre?: string | null;
  tamano?: number;
}

/** Avatar circular de un usuario -- ronda de foto de perfil + siembra de 26
 * usuarios ficticios, con ampliación (ronda de fotos en historial/usuarios).
 * Reutilizado en las 3 apps: header de `AppShell`, tarjeta de "Mi
 * cuenta"/"Mi perfil" (`PerfilPropio`), el detalle del conductor asignado
 * en `web-pasajero`, y la vista pública de "Compartir viaje" (sin sesión --
 * por eso `foto_perfil` es un contexto público).
 *
 * Ampliable con un clic, reusando el mismo `Lightbox` que ya usa
 * `EvidenciaImagen` para evidencia fotográfica -- un solo lugar para el
 * comportamiento de ampliación, no dos. Solo se activa cuando hay una foto
 * PROPIA real: el avatar por defecto es un ícono genérico (no una foto de
 * la persona), ampliarlo no aporta nada más que verlo más grande, así que
 * ni siquiera se envuelve en un botón -- decisión aplicada de forma
 * automática (no un prop por sitio de uso) para que el comportamiento sea
 * idéntico en cualquier lugar donde se use `Avatar`. */
export function Avatar({ fotoUrl, nombre, tamano = 40 }: AvatarProps) {
  const [roto, setRoto] = useState(false);
  const [ampliada, setAmpliada] = useState(false);

  const tieneFotoPropia = Boolean(fotoUrl) && !roto;
  const src = tieneFotoPropia ? urlArchivo(fotoUrl as string) : avatarPorDefecto;
  const alt = nombre ? `Foto de perfil de ${nombre}` : "Foto de perfil";

  const imagen = (
    <img
      src={src}
      alt={alt}
      width={tamano}
      height={tamano}
      // Si el id quedó apuntando a un archivo borrado/inválido, se degrada
      // al avatar por defecto (vía estado, no manipulación directa del DOM)
      // en vez de romper el layout con un ícono roto -- el estado también
      // apaga la ampliación, ya no hay una foto real que mostrar en grande.
      onError={() => {
        if (!roto) setRoto(true);
      }}
      style={{
        width: tamano,
        height: tamano,
        borderRadius: "50%",
        objectFit: "cover",
        flexShrink: 0,
        background: "var(--color-surface)",
      }}
    />
  );

  if (!tieneFotoPropia) return imagen;

  return (
    <>
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
          borderRadius: "50%",
        }}
      >
        {imagen}
      </button>
      {ampliada && <Lightbox src={src} alt={alt} onClose={() => setAmpliada(false)} />}
    </>
  );
}
