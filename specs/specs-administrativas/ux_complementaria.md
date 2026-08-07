# Especificación — Funcionalidades complementarias de experiencia de usuario

Paquete propuesto: `pkg-ux-complementario` · Nivel: transversal (no pertenece a los niveles
operativo/táctico/estratégico de negocio — son capacidades de producto que hacen la app completa
y usable, comparables a lo que cualquier app comercial de transporte ya ofrece)

## 0. Marco de análisis

Antes de proponer nada nuevo, se verificó qué de lo pedido **ya existe** en el sistema, para no
duplicar trabajo — el mismo criterio que se ha aplicado en todo el proyecto.

| Ejemplo de la referencia | Estado real en UrbanFleet |
|---|---|
| Mapa con taxis visibles de forma permanente | **Ya construido.** El mapa del pasajero y del conductor es persistente desde la corrección de diseño aplicada anteriormente — ya no depende de un evento para mostrarse. |
| Historial de viajes | **Ya construido** para pasajero y conductor (CU-O14: filtro por fecha, detalle con mapa/tarifa). **Parcialmente construido** para personal interno: existe un panel de despacho en vivo (viajes activos del día), pero no un historial navegable de todos los viajes históricos de la cooperativa — se propone como Sección 3.3. |
| Sección de configuraciones/ajustes | **No existe** en ninguna de las 3 apps. Se propone como Sección 4. |
| Edición de perfil propio | **No existe** para ningún rol — ni pasajero/conductor ni personal interno. El Administrador del Sistema puede editar el contacto de una cuenta ajena (Módulo 1.1), pero ningún usuario puede editar el suyo propio. Se propone como Sección 1.3 / 2.3 / 3.1. |

El resto de este documento organiza las propuestas por audiencia: **Pasajero**, **Conductor**,
**Personal interno** (las 10 cuentas administrativas de `web-interno`), y una sección **transversal**
que aplica a los tres.

---

## 1. Pasajero (`web-pasajero`)

### 1.1. Direcciones favoritas

- **Objetivo:** eliminar la fricción de escribir la misma dirección (casa, trabajo) en cada
  solicitud.
- **Funciones:** guardar hasta un número razonable de direcciones con etiqueta (Casa, Trabajo,
  Otro); seleccionarlas con un toque como destino en vez de marcar en el mapa cada vez.
- **Beneficio:** reduce el tiempo de solicitud del viaje más común (el trayecto diario), que es
  probablemente el caso de uso más frecuente de cualquier pasajero recurrente.
- **Módulo/sección:** `web-pasajero` → dentro del flujo de solicitud, como accesos rápidos sobre
  el buscador de destino.
- **Consideraciones:** son datos personales de ubicación — deben poder eliminarse individualmente
  y quedar cubiertos por la misma política de gobernanza de datos ya construida en Administración.

### 1.2. Compartir viaje en tiempo real

- **Objetivo:** seguridad percibida y real del pasajero durante el viaje.
- **Funciones:** generar un enlace de solo lectura (sin necesitar cuenta) que un contacto de
  confianza puede abrir para ver la posición del vehículo y el conductor asignado mientras el
  viaje está `EN_CAMINO`/`EN_CURSO`. El enlace expira al finalizar el viaje.
- **Beneficio:** es una de las funciones de seguridad más valoradas en apps de transporte reales;
  da tranquilidad sin exigir que el contacto tenga la app instalada.
- **Módulo/sección:** overlay del mapa de viaje activo, junto al perfil del conductor asignado.
- **Consideraciones:** el enlace no debe exponer datos personales del conductor (solo nombre de
  pila y posición, igual que ya se restringe en CU-O05 P5); debe expirar automáticamente, nunca
  quedar accesible después del viaje.

### 1.3. Perfil y ajustes de cuenta

- **Objetivo:** que el pasajero administre su propia información sin depender de soporte.
- **Funciones:** editar nombre, foto, correo/teléfono (con la misma verificación OTP ya usada en
  el registro); cambiar contraseña; ver/gestionar sus propias sesiones activas (mismo mecanismo ya
  construido para el administrador en Módulo 1.4, aquí en versión de autoservicio); solicitar la
  eliminación de su cuenta (deriva al flujo de gobernanza de datos ya construido).
- **Beneficio:** es la funcionalidad de "cuenta" mínima esperable en cualquier app — su ausencia
  hoy es la brecha más notoria frente a una app comercial real.
- **Módulo/sección:** nueva sección "Mi perfil" en `web-pasajero`, accesible desde el menú.
- **Consideraciones:** cambiar el teléfono debe re-disparar la verificación OTP (no se debe poder
  cambiar sin confirmar propiedad del nuevo número); toda edición queda auditada.

### 1.4. Ajustes de la aplicación

- **Objetivo:** personalización básica de la experiencia.
- **Funciones:** activar/desactivar notificaciones push por categoría (oferta aceptada, conductor
  en camino, promociones si existieran); elegir tema claro/oscuro; ver la versión de la app.
- **Beneficio:** reduce fatiga de notificaciones y da control mínimo de personalización esperado.
- **Módulo/sección:** sección "Ajustes", separada de "Mi perfil".
- **Consideraciones:** las notificaciones de seguridad (spoofing, alertas del sistema) nunca deben
  poder desactivarse desde aquí — ese control es exclusivo del Módulo 6.3 de Administración, no del
  usuario final.

### 1.5. Programar un viaje

- **Objetivo:** cubrir el caso de uso de "necesito un taxi a una hora específica" (ej. vuelo,
  turno de trabajo), que hoy no existe — el sistema solo atiende demanda inmediata.
- **Funciones:** solicitar un viaje con una hora futura; el sistema dispara el proceso de
  auto-despacho normal (CU-O05) automáticamente cerca de la hora programada, no antes.
- **Beneficio:** captura demanda que hoy la cooperativa pierde porque el pasajero no puede
  garantizar disponibilidad futura.
- **Módulo/sección:** nueva opción en el flujo de solicitud ("Ahora" vs. "Programar").
- **Consideraciones:** requiere un mecanismo de disparo diferido (job programado) — es la pieza de
  mayor complejidad técnica de esta lista; evaluar con Claude Code si conviene resolverlo con
  Airflow (ya presente en la arquitectura) en vez de infraestructura nueva.

---

## 2. Conductor (`web-conductor`)

### 2.1. Estadísticas personales

- **Objetivo:** que el conductor entienda su propio desempeño sin pedirle el dato al Coordinador.
- **Funciones:** calificación promedio propia, tasa de aceptación/rechazo de ofertas, ingresos del
  periodo actual (adelanto de lo que su próxima liquidación mostrará).
- **Beneficio:** transparencia que motiva al socio y reduce consultas manuales al personal interno.
- **Módulo/sección:** nueva sección "Mi desempeño" en `web-conductor`, alimentada por datos que ya
  existen (calificaciones, ofertas, liquidaciones) — no requiere pipeline nuevo.
- **Consideraciones:** mostrar solo datos propios, nunca comparativos con otros conductores por
  nombre (evita fricción social innecesaria entre socios).

### 2.2. Perfil y ajustes de cuenta

- Mismo alcance que 1.3, adaptado al conductor: además de datos de contacto, permitir actualizar
  la foto de perfil que el pasajero ve al ser asignado (CU-O05 P5). Los datos del vehículo
  (placa, marca, modelo) **no** son editables aquí — siguen bajo control de Mantenimiento/Flota,
  para no crear una vía paralela que rompa la trazabilidad ya establecida.

### 2.3. Preferencias de turno

- **Objetivo:** dar al conductor algo de control sobre cómo recibe ofertas, sin tocar la lógica de
  despacho automático que ya es responsabilidad del sistema.
- **Funciones:** sonido/vibración distintivo para nueva oferta; recordatorio para iniciar turno a
  una hora habitual.
- **Beneficio:** mejora la experiencia de uso diaria sin ningún riesgo de negocio.
- **Módulo/sección:** sección "Ajustes" en `web-conductor`.
- **Consideraciones:** explícitamente **no** incluir un "radio de aceptación automática" ni
  cualquier control que le permita al conductor filtrar qué ofertas recibe — eso alteraría la
  imparcialidad del algoritmo de despacho (CU-O05), que ya reparte trabajo entre socios por diseño.

---

## 3. Personal interno (`web-interno`)

### 3.1. Perfil propio (autoservicio, distinto de la gestión de Administración)

- **Objetivo:** que cualquier empleado (no solo el Administrador del Sistema) pueda actualizar su
  propio contacto y contraseña, sin depender de que alguien más lo haga por él.
- **Funciones:** editar nombre/correo/teléfono propios, cambiar la propia contraseña, ver las
  propias sesiones activas.
- **Beneficio:** hoy solo `admin_sistema` puede tocar estos datos (de cualquier cuenta) — un
  Coordinador de Flota no puede corregir su propio número de teléfono sin pedírselo al
  administrador. Es una fricción operativa innecesaria para el día a día.
- **Módulo/sección:** nueva sección "Mi cuenta", visible para todos los roles internos.
- **Consideraciones:** un usuario nunca debe poder cambiar su propio rol desde aquí (eso sigue
  siendo exclusivo del Módulo 1.2 de Administración) — solo sus datos de contacto y credenciales.

### 3.2. Preferencias de interfaz

- **Objetivo:** comodidad de uso para quien pasa horas frente a estas pantallas.
- **Funciones:** tema claro/oscuro, densidad de las tablas (compacta/cómoda).
- **Beneficio:** mejora ergonómica de bajo costo de construcción.
- **Módulo/sección:** sección "Mi cuenta" o un ícono de ajustes junto al nombre de usuario.

### 3.3. Historial global de viajes (para roles con visibilidad autorizada)

- **Objetivo:** cerrar la brecha identificada en la Sección 0 — hoy no existe una vista histórica
  navegable de todos los viajes de la cooperativa, solo el estado en vivo del día.
- **Funciones:** búsqueda y filtro de cualquier viaje histórico por fecha, pasajero, conductor o
  zona, con el mismo detalle (mapa, tarifa, calificaciones) que ya ve el pasajero/conductor sobre
  sus propios viajes.
- **Beneficio:** da a gerencia y a Cumplimiento Regulatorio una herramienta de consulta puntual
  que hoy no existe — el dashboard táctico muestra agregados, no permite buscar un viaje
  específico por nombre o fecha.
- **Módulo/sección:** nuevo work panel "Historial de viajes" en `web-interno`, patrón WorkPanel
  estándar.
- **Consideraciones:** acceso restringido por rol — `coordinador_operaciones`, `supervisor_
  cumplimiento`, `gerencia` y `admin_sistema`; nunca datos completos de contacto del pasajero/
  conductor a roles que no los necesiten, mismo principio de mínimo privilegio ya aplicado en
  Administración.

---

## 4. Transversal (las 3 apps)

### 4.1. Centro de ayuda y soporte

- **Objetivo:** dar un canal de contacto visible, en vez de que el usuario no sepa a quién
  recurrir ante un problema.
- **Funciones:** preguntas frecuentes básicas, y un canal de contacto (correo o número) hacia la
  cooperativa. No implica un sistema de tickets — sería sobredimensionado para el alcance actual.
- **Beneficio:** presente en toda app de transporte real; su ausencia se nota de inmediato.
- **Módulo/sección:** ícono de ayuda accesible desde cualquier pantalla.

### 4.2. Centro de notificaciones in-app

- **Objetivo:** que las notificaciones no dependan solo de Web Push (que puede fallar o estar
  desactivado) — dar un lugar donde revisarlas después.
- **Funciones:** bandeja con las notificaciones recientes del usuario (oferta, arribo, cambios de
  estado, alertas si aplica al rol).
- **Beneficio:** red de seguridad ante notificaciones push perdidas, mejora la confianza en que
  "nada se pasó por alto".
- **Módulo/sección:** ícono de campana en el header de las 3 apps.

---

## 5. Priorización sugerida

No todo tiene el mismo costo ni el mismo impacto. Orden recomendado si el tiempo es limitado:

1. **Perfil propio editable (1.3 / 2.2 / 3.1)** — la brecha más notoria frente a una app real, y
   la de menor riesgo técnico (reutiliza patrones ya construidos: OTP, auditoría, work panels).
2. **Ajustes básicos (1.4 / 2.3 / 3.2)** — bajo costo, alto valor percibido.
3. **Centro de notificaciones (4.2)** — reutiliza la infraestructura de notificaciones ya existente
   del Módulo 6.3.
4. **Historial global de viajes (3.3)** — valor real para gerencia/cumplimiento, complejidad media
   (un work panel más, sin lógica de negocio nueva).
5. **Direcciones favoritas (1.1)** y **compartir viaje (1.2)** — valorados por el usuario final,
   pero no urgentes para la evaluación funcional del sistema.
6. **Programar viaje (1.5)** — el de mayor complejidad técnica (requiere disparo diferido); dejarlo
   para el final o evaluarlo aparte si el tiempo no alcanza.
