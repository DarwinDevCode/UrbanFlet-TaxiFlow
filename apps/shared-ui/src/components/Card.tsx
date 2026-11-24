import type { ReactNode } from "react";
import "./Card.css";

export interface CardProps {
  children: ReactNode;
  /** Título del plano. Se compone con `--font-display`, el mismo
   * tratamiento que los títulos de área. */
  titulo?: string;
  /** Rótulo corto a la derecha del título (origen del dato, periodo,
   * conteo). Sustituye al patrón de meter un `<span>` suelto al lado del
   * `<h3>` en cada pantalla. */
  rotulo?: ReactNode;
  /** Acciones del plano, alineadas al extremo del encabezado. */
  acciones?: ReactNode;
  /** Marca el plano como principal de la pantalla: la barra superior pasa
   * de línea neutra a ámbar de marca. Uno por pantalla, no todos. */
  acento?: boolean;
  /** Quita el relleno interno -- para un plano que contiene únicamente un
   * registro (la tabla ya trae su propio ritmo). */
  sinRelleno?: boolean;
}

/**
 * EL PLANO — reemplaza a la tarjeta (Fase 1 del Sistema Riel).
 *
 * La tarjeta genérica se define por superficie + borde + radio + sombra:
 * un objeto que flota. El plano se define por una **barra superior más
 * gruesa que el resto de las líneas del sistema**, sin radio y sin sombra:
 * un objeto que se apoya, como una hoja de plano sobre una mesa.
 *
 * El cambio es deliberadamente estructural y no cosmético: al quitar radio
 * y elevación, la separación entre bloques pasa a hacerla el espacio y la
 * línea, que es lo que sostiene la lectura de todo el sistema.
 *
 * Compatible con el uso anterior: `<Card>{contenido}</Card>` sigue
 * funcionando igual en las pantallas que aún no declaran encabezado.
 */
export function Card({ children, titulo, rotulo, acciones, acento, sinRelleno }: CardProps) {
  const tieneEncabezado = Boolean(titulo || rotulo || acciones);
  return (
    <section className={`uf-plano${acento ? " uf-plano--acento" : ""}`}>
      {tieneEncabezado && (
        <header className="uf-plano-encabezado">
          {titulo && <h3 className="uf-plano-titulo">{titulo}</h3>}
          {rotulo && <span className="uf-rotulo uf-plano-rotulo">{rotulo}</span>}
          {acciones && <div className="uf-plano-acciones">{acciones}</div>}
        </header>
      )}
      <div className={sinRelleno ? "uf-plano-cuerpo uf-plano-cuerpo--pleno" : "uf-plano-cuerpo"}>
        {children}
      </div>
    </section>
  );
}
