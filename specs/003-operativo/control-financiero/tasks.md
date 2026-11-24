# Tareas (retroactivo): Control Financiero

Trazabilidad completa en `CLAUDE.md` §33 ("Comisión de la cooperativa — consolidación de
duplicados, salvaguarda de índice y pantalla nueva").

1. Confirmar el hallazgo real: 2 documentos de comisión "vigentes para siempre" simultáneos en
   Mongo, creados por un bug de aplicación ya corregido en su momento pero nunca limpiado en los
   datos.
2. Consolidar los 2 documentos en uno, con evento de bitácora explícito documentando la
   consolidación (no solo el evento de rutina de la creación).
3. Agregar el índice único parcial que hace la colisión estructuralmente imposible, verificado con
   un intento real de inserción manual rechazado por Mongo.
4. Construir la pantalla `Comision.tsx` (vigente actual + historial + crear nueva versión), separada
   de "Parámetros Globales" (dominio de configuración de sistema distinto) y de "Administración"
   (que a propósito no puede tocar reglas de dinero).
5. Verificar el efecto real de un cambio de comisión de punta a punta: viajes cobrados antes y
   después de la fecha de vigencia, confirmando en `movimientos` que cada uno aplicó la comisión
   correcta según su propia fecha.
