import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api/client";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { TextField } from "./TextField";

interface UsuarioResumen {
  id: string;
  nombre: string;
  telefono: string | null;
  email: string | null;
  roles: string[];
}

interface UserPickerProps {
  label: string;
  /** IDs de usuario ya seleccionados (lo único que el backend recibe/guarda). */
  seleccionados: string[];
  onChange: (ids: string[]) => void;
}

/** Punto #5 de la ronda de usabilidad de admin_sistema (2026-08-07):
 * reemplaza el antipatrón de pedirle al administrador un `usuario_id` crudo
 * (tenía que ir a otra pantalla, copiar un UUID y pegarlo aquí). Busca por
 * nombre/teléfono/correo, muestra información legible, y guarda el ID por
 * detrás sin que el usuario lo vea nunca. Reutilizable en cualquier
 * pantalla que necesite seleccionar uno o más usuarios. */
export function UserPicker({ label, seleccionados, onChange }: UserPickerProps) {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<UsuarioResumen[]>([]);
  const [resueltos, setResueltos] = useState<Record<string, UsuarioResumen>>({});
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ultimoBuscado = useRef<string | null>(null);

  useEffect(() => {
    const faltantes = seleccionados.filter((id) => !resueltos[id]);
    if (faltantes.length === 0) return;
    Promise.all(
      faltantes.map((id) =>
        apiFetch<UsuarioResumen>(`/usuarios/${id}`)
          .then((u) => [id, u] as const)
          .catch(() => [id, { id, nombre: id, telefono: null, email: null, roles: [] }] as const),
      ),
    ).then((pares) => {
      setResueltos((prev) => ({ ...prev, ...Object.fromEntries(pares) }));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seleccionados]);

  const buscar = async (valor: string) => {
    if (!valor.trim()) {
      setResultados([]);
      ultimoBuscado.current = null;
      return;
    }
    // Evita repetir la misma consulta si el debounce en vivo ya la disparó
    // y el administrador igual presiona "Buscar" (o al revés).
    if (ultimoBuscado.current === valor) return;
    ultimoBuscado.current = valor;
    setError(null);
    setBuscando(true);
    try {
      // `estado=ACTIVO` (PROPUESTA_CRUD_Y_BAJA_LOGICA.md, Fase C item 5):
      // una cuenta suspendida o dada de baja no debe poder elegirse como
      // destinataria de un proceso nuevo -- no recibiría la notificación
      // (no puede iniciar sesión) y quedaría como un destinatario fantasma.
      // El filtro ya existía en el backend (`listar_usuarios`), solo no se
      // estaba usando desde acá.
      const resp = await apiFetch<{ items: UsuarioResumen[]; total: number }>(
        `/usuarios?texto=${encodeURIComponent(valor)}&estado=ACTIVO&limit=20`,
      );
      setResultados(resp.items);
    } catch {
      setError("No se pudo buscar usuarios");
    } finally {
      setBuscando(false);
    }
  };

  // Búsqueda en vivo mientras el administrador escribe (debounce de 300ms
  // para no disparar una consulta por cada tecla) -- el botón "Buscar" se
  // mantiene como acción explícita/inmediata, no se elimina.
  useEffect(() => {
    const id = setTimeout(() => buscar(texto), 300);
    return () => clearTimeout(id);
  }, [texto]);

  const agregar = (u: UsuarioResumen) => {
    setResueltos((prev) => ({ ...prev, [u.id]: u }));
    if (!seleccionados.includes(u.id)) onChange([...seleccionados, u.id]);
  };

  const quitar = (id: string) => onChange(seleccionados.filter((s) => s !== id));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", width: "100%" }}>
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>{label}</span>

      {seleccionados.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
          {seleccionados.map((id) => {
            const u = resueltos[id];
            return (
              <span
                key={id}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  padding: "4px 10px",
                  borderRadius: "999px",
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  fontSize: "var(--font-size-sm)",
                }}
              >
                {u ? `${u.nombre}${u.roles[0] ? ` — ${u.roles[0]}` : ""}` : "Cargando…"}
                <button
                  type="button"
                  onClick={() => quitar(id)}
                  aria-label={`Quitar ${u?.nombre ?? id}`}
                  style={{ border: "none", background: "none", cursor: "pointer", color: "var(--color-text-muted)", fontWeight: 700 }}
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      )}

      <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 220px" }}>
          <TextField
            label="Buscar por nombre, teléfono o correo"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), buscar(texto))}
          />
        </div>
        <div style={{ minWidth: 100 }}>
          <Button variant="secondary" onClick={() => buscar(texto)} loading={buscando} disabled={!texto.trim()}>
            Buscar
          </Button>
        </div>
      </div>
      {error && <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-danger)" }}>{error}</span>}

      {resultados.length > 0 && (
        <div style={{ border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", maxHeight: 220, overflowY: "auto" }}>
          {resultados.map((u) => (
            <div
              key={u.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "var(--space-2)",
                padding: "var(--space-2) var(--space-3)",
                borderBottom: "1px solid var(--color-border)",
              }}
            >
              <div>
                <div style={{ fontSize: "var(--font-size-sm)", fontWeight: 600 }}>{u.nombre}</div>
                <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                  {[u.telefono, u.email].filter(Boolean).join(" · ") || "Sin contacto registrado"}
                  {u.roles.length > 0 && (
                    <>
                      {" "}
                      <Badge texto={u.roles[0]} tono="neutral" />
                    </>
                  )}
                </div>
              </div>
              <div style={{ minWidth: 90 }}>
                <Button
                  variant="secondary"
                  onClick={() => agregar(u)}
                  disabled={seleccionados.includes(u.id)}
                >
                  {seleccionados.includes(u.id) ? "Agregado" : "Agregar"}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
