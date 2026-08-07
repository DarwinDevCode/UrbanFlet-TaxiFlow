"""Matriz de permisos vigente por rol — Módulo 1.2 de admin_sistema
(specs/specs-administrativas/admin_sistema.md).

Alcance recortado y APROBADO por el usuario (ver PLAN_ADMIN_SISTEMA.md,
nota de 1.2): esto es un diccionario mantenido A MANO, reflejo de las
llamadas reales a `require_roles(...)` en cada router — no hay
introspección dinámica de las rutas de FastAPI. La fuente de verdad real
sigue siendo `require_roles(...)` en cada router; este archivo es solo una
vista de consulta para el administrador, igual que `core/rbac.py::ROLES` se
mantiene a mano.

**Si agregas o cambias un `require_roles(...)` en cualquier router, actualiza
esta tabla en el mismo cambio** — no hay ningún test que lo haga por vos.
"""

# {grupo lógico de endpoints: [roles que pueden usarlos]} -- agrupado por
# router, no por endpoint individual, para que la matriz quede legible; dos
# roles distintos dentro del mismo router (ej. viajes tiene pasajero Y
# conductor en endpoints distintos) se listan juntos con una nota.
MATRIZ_PERMISOS: dict[str, list[str]] = {
    "auditoria.eventos (GET /auditoria/*)": [
        "supervisor_cumplimiento",
        "admin_plataforma",
        "gerencia",
        "admin_sistema",
    ],
    "captacion.solicitudes (POST/GET /captacion/*)": ["admin_captacion"],
    "cumplimiento (POST/GET /documentos, /cumplimiento/*)": ["supervisor_cumplimiento"],
    "flota.tablero (GET /flota/tablero, panel-tactico)": ["coordinador_flota", "admin_plataforma"],
    "flota.posicion (POST /flota/posicion)": ["conductor"],
    "mantenimiento.ordenes (POST/GET /mantenimiento/*)": ["jefe_mantenimiento"],
    "parametros.escritura (POST /parametros/tarifas, /comisiones, /zonas)": ["admin_plataforma", "gerencia"],
    "plataforma.indicadores (GET /plataforma/*)": ["gerencia", "responsable_plataforma", "admin_plataforma"],
    "recaudacion.pago (POST /pagos)": ["conductor"],
    "recaudacion.liquidaciones (GET/POST /liquidaciones/*)": ["admin_financiero"],
    "viajes.solicitar (POST /viajes)": ["pasajero"],
    "viajes.ejecucion/finalizacion (conductor en curso)": ["conductor"],
    "viajes.panel-tactico-despacho (GET /viajes/panel-tactico/*)": ["coordinador_operaciones"],
    "usuarios.* (Módulo 1 — este documento)": ["admin_sistema"],
    "seguridad.politica-auth (Módulo 1.3)": ["admin_sistema"],
}


def obtener_matriz() -> dict[str, list[str]]:
    return MATRIZ_PERMISOS
