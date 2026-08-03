# Especificación operativa — Coordinación de Flota

Paquete: `pkg-flota` · Objetivo: OP2.3 (registrar posición y estado de cada vehículo en servicio) · OE2

Estados del conductor en servicio: `FUERA_DE_LINEA` → `DISPONIBLE` ⇄ `OCUPADO`; cualquier estado → `SIN_SEÑAL` (transición automática del sistema).

---

## CU-O19 — Reportar la posición y el estado del vehículo

**Actores:** Conductor, Sistema

**Precondiciones:**
- Conductor autenticado en el portal web de conductor (PWA instalada y en primer plano), con documentación vigente y vehículo habilitado.
- Permiso de geolocalización del navegador concedido.

**Flujo principal:**
1. El conductor pulsa "Iniciar turno". El sistema valida las dos banderas (Cumplimiento y Mantenimiento) y lo pasa a `DISPONIBLE`.
2. El portal envía la posición (Geolocation API, `watchPosition`) cada **10 segundos** en `DISPONIBLE` y cada **5 segundos** en `OCUPADO` (durante viaje la traza la consume también Operaciones). Cada reporte incluye: coordenadas, precisión del fix, rumbo, velocidad y timestamp del dispositivo. Al iniciar turno, el portal solicita wake lock para mantener la pantalla activa: el navegador no reporta posición confiable en segundo plano.
3. El sistema actualiza la "última posición conocida" del vehículo, que alimenta: el mapa del pasajero (solo taxis `DISPONIBLE` cercanos), la lista de candidatos del auto-despacho y el tablero en vivo del Coordinador de Flota.
4. Al pulsar "Terminar turno", el conductor pasa a `FUERA_DE_LINEA` y deja de reportar. No se permite terminar turno con un viaje activo.

**Flujos alternos:**
- **A1 — Sin señal:** si no llega reporte en 60 segundos, el sistema marca el vehículo `SIN_SEÑAL`: sale del mapa del pasajero y de la lista de candidatos, y aparece en la lista de alertas del Coordinador. Al primer reporte válido vuelve al estado previo.
- **A2 — Sin señal con viaje activo:** aplica el flujo A5 de CU-O05 / A5 de CU-O07 (`operativo_operaciones_despacho.md`): notificación a los 120 s, reasignación o marca `EN_REVISION` según la fase del viaje.
- **A3 — Fix GPS de baja precisión (> 50 m):** el reporte se acepta y se marca `precision_baja=true`; tres fixes consecutivos de baja precisión sacan al vehículo de la lista de candidatos (evita asignaciones con posición dudosa) sin cambiar su estado visible.
- **A4 — Posición físicamente imposible (salto > 3 km entre reportes consecutivos):** el reporte se descarta, se conserva la posición anterior y el evento queda registrado para auditoría (posible GPS spoofing).
- **A5 — Bandera de Cumplimiento o Mantenimiento en rojo durante el turno:** el sistema no interrumpe el viaje en curso, pero al finalizarlo fuerza el pase a `FUERA_DE_LINEA` con notificación del motivo ("documento vencido" / "vehículo retirado de servicio") y bloquea el nuevo inicio de turno.
- **A6 — Batería del dispositivo < 15% (Battery Status API, si el navegador la expone):** el portal reduce la frecuencia de reporte a 20 s en `DISPONIBLE` y lo notifica al conductor; en `OCUPADO` la frecuencia no se degrada.
- **A7 — Pestaña en segundo plano o pantalla bloqueada durante el turno:** los reportes se degradan o detienen por limitación del navegador; opera el flujo A1 (sin señal a los 60 s). El portal advierte al conductor al perder el foco ("mantén la pantalla activa para seguir recibiendo viajes") y Web Push le notifica si quedó `SIN_SEÑAL`.

**Postcondiciones:** última posición conocida del vehículo actualizada; historial de posiciones persistido para la traza de viajes y para el cálculo horario de disponibilidad por zona (pipeline `dag_flota_gold`); alertas de sin señal registradas con duración.
