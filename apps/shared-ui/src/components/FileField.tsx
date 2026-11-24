import { useId, useState, type ChangeEvent } from "react";
import "./FileField.css";

interface FileFieldProps {
  /** Etiqueta encima del campo. Se omite cuando el contexto ya la da (ej. la
   *  sección "Foto de perfil", que tiene su propio encabezado). */
  label?: string;
  /** Igual que el `accept` nativo. */
  accept?: string;
  disabled?: boolean;
  /** Texto del botón. Por defecto "Seleccionar archivo". */
  textoBoton?: string;
  /** Muestra el nombre del archivo elegido. Se apaga cuando la propia pantalla
   *  ya confirma la selección de otra forma (ej. el avatar que se actualiza al
   *  instante), donde el nombre del archivo sería ruido. */
  mostrarNombre?: boolean;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
}

/**
 * Campo de archivo con la piel del sistema de diseño.
 *
 * Antes de esto había 4 inputs `type="file"` sueltos en el proyecto, ninguno
 * compartido: 3 con el control nativo del navegador sin estilo (Arial, radio y
 * paleta del sistema operativo, fuera de la identidad visual) y 1 con este
 * mismo patrón resuelto a mano inline (la foto de perfil de `AjustesPropios`).
 * Este componente unifica los 4.
 *
 * El input nativo se conserva y solo se oculta visualmente (nunca
 * `display:none` ni `visibility:hidden`, que lo sacarían del orden de
 * tabulación): sigue siendo enfocable con teclado, el lector de pantalla lo
 * anuncia con su etiqueta real, y el diálogo de archivos es el del sistema
 * operativo. Lo único que cambia es qué se dibuja.
 */
export function FileField({
  label,
  accept,
  disabled = false,
  textoBoton = "Seleccionar archivo",
  mostrarNombre = true,
  onChange,
}: FileFieldProps) {
  const id = useId();
  const [nombre, setNombre] = useState<string | null>(null);

  const manejar = (e: ChangeEvent<HTMLInputElement>) => {
    setNombre(e.target.files?.[0]?.name ?? null);
    onChange(e);
  };

  return (
    <div>
      {label && (
        <label
          htmlFor={id}
          style={{ fontSize: "var(--font-size-sm)", display: "block", marginBottom: "var(--space-1)" }}
        >
          {label}
        </label>
      )}
      <label className={`uf-file-field${disabled ? " uf-file-field--deshabilitado" : ""}`}>
        <input
          id={id}
          className="uf-file-field__input"
          type="file"
          accept={accept}
          disabled={disabled}
          onChange={manejar}
          aria-label={label ?? textoBoton}
        />
        <span className="uf-file-field__boton">{textoBoton}</span>
        {/* Reemplaza el "Ningún archivo seleccionado" del control nativo, que
            se pierde al ocultarlo. */}
        {mostrarNombre && (
          <span className="uf-file-field__nombre">{nombre ?? "Ningún archivo seleccionado"}</span>
        )}
      </label>
    </div>
  );
}
