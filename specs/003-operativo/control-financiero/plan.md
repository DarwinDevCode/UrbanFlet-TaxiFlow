# Plan técnico (retroactivo): Control Financiero

## Backend

- `backend/src/recaudacion/` (`router.py`/`service.py`): discrepancias, `generar_liquidaciones`
  (sin parámetro de periodo — siempre calcula la semana ya cerrada respecto a `datetime.now(UTC)`),
  ciclo de aprobación.
- `backend/src/parametros/`: comisión y tarifa versionadas, con el mismo patrón de vigencia por
  fecha.
- Colecciones: `pagos`, `movimientos`, `liquidaciones`, `parametros`.

## Frontend

- `apps/web-interno/src/sections/Finanzas.tsx` — WorkPanel, con las 2 bandejas (discrepancias/sin
  pago) más el bloque de liquidaciones y alertas.
- `apps/web-interno/src/sections/Comision.tsx` — pantalla propia (fuera del WorkPanel de Finanzas,
  gateada a `admin_plataforma`/`gerencia`) para el historial y creación de nuevas versiones de
  comisión.

## Decisión de arquitectura: por qué la comisión tiene un índice único a nivel de base de datos

Se encontraron 2 documentos "vigentes para siempre" simultáneos por un bug de aplicación en una
ronda anterior. La corrección no se limitó a arreglar el código que los creó — se agregó un índice
único parcial en Mongo (`{tipo, franja}` con `vigente_hasta:null`) para que el problema sea
estructuralmente imposible de repetir, no solo corregido en el camino feliz.
