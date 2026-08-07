# PLAN — Funcionalidades complementarias de UX

Spec fuente: `specs/specs-administrativas/ux_complementaria.md`. Este archivo se
actualiza conforme avanza el trabajo — cada tarea se marca `[x]` al cerrarse
(con verificación en navegador donde aplique), nunca se da por completa solo
porque el código fue escrito.

Leyenda de estado: ⬜ pendiente · 🔶 en curso · ✅ completo y verificado ·
✂️ alcance recortado (aprobado) · 🚫 fuera de alcance (backlog consciente) ·
❓ **requiere tu decisión antes de construir**

**Plan aprobado por el usuario (2026-08-07)**, con las 3 decisiones ya
resueltas — ver detalle de cada una en la Sección 1, dejado como referencia
histórica del razonamiento, no se reabre sin pedido explícito:
- **D1 → Opción A**: sin OTP, edición de contacto propio exige contraseña
  actual + queda auditada.
- **D2 → Aprobado** el enfoque Airflow + HTTP interno + estado nuevo
  `PROGRAMADO`. Confirmado explícitamente: si a la hora programada no hay
  conductor disponible, cae en `SIN_CONDUCTOR` — mismo comportamiento que ya
  existe hoy, **sin mecanismo de reintento especial** para este caso
  mientras el reintento general (CU-O05 A3) siga en backlog.
- **D3 → Aprobado**: Centro de ayuda (4.1) se construye junto a Ajustes.

**Ajuste pedido antes de construir la Sección 8 (Compartir viaje)**: el
usuario pidió confirmar el diseño anti-enumeración del token público
(longitud/aleatoriedad, rate limiting) antes de escribir el endpoint —
tratado en el momento de construir esa sección, no antes (no bloquea el
resto del plan).

---

## 0. Verificación de la Sección 0 de la spec contra el código real (2026-08-07)

La spec ya adelanta un diagnóstico de qué existe. Se verificó cada punto
contra el código real antes de planificar nada:

| Punto de la spec | Verificado | Detalle |
|---|---|---|
| Mapa persistente (pasajero/conductor) | ✅ Confirmado | `RideMap`/`DriverMap` se montan una sola vez, decisión ya documentada en `CLAUDE.md` §4. Sin cambios necesarios. |
| Historial de viajes (pasajero/conductor) | ✅ Confirmado | `HistorialView` en ambos `App.tsx`, respaldado por `GET /viajes` (`viajes/service_historial.py`, CU-O14) — filtro por fecha/estado, detalle con tarifa y calificaciones. Sin mapa de ruta ni comprobante PDF (cortes de alcance ya documentados en el propio `service_historial.py`, anteriores a este trabajo). |
| Historial global (personal interno) | ✅ Confirmado — falta | Existe `GET /viajes/panel-tactico/activos` (viajes del día, `coordinador_operaciones`) pero ningún endpoint de búsqueda histórica de todos los viajes. Ver Sección 6 de este plan. |
| Sección de ajustes/configuración | ✅ Confirmado — no existe | Cero coincidencias de "Ajustes"/tema oscuro/densidad en las 3 apps. |
| Edición de perfil propio | ✅ Confirmado — no existe | Todos los endpoints de `usuarios/router.py` (incluida edición de contacto) están gateados a `admin_sistema` exclusivo — ninguna cuenta puede editarse a sí misma. `POST /auth/cambiar-password` sí es de autoservicio (cualquier actor autenticado) y ya está construido — reutilizable directo, ver Sección 3. |

**Hallazgo adicional no cubierto por la Sección 0 de la spec, relevante para
Fase 1** — la spec asume en el punto 1.3 "la misma verificación OTP ya usada
en el registro" para reconfirmar un teléfono nuevo. **Eso ya no existe**: el
login/registro migró a usuario+contraseña (`CLAUDE.md` §4, decisión ya
tomada) y no hay ningún mecanismo de OTP activo en el backend — `otp_codes`
es una colección con un único documento residual de antes de la migración,
sin código que la lea o escriba hoy (confirmado por grep, cero referencias
reales). Tampoco existe infraestructura de envío de SMS o correo en el
proyecto (`CLAUDE.md` ya documenta "no hay envío de correo en ningún lado").
Esto afecta 1.3/2.2/3.1 — ver decisión ❓D1 en la Sección 1.

---

## 1. Decisiones que requieren tu aprobación antes de construir

### ❓D1 — Verificación de teléfono/correo nuevo al editar el perfil propio (1.3/2.2/3.1)

La spec pide re-disparar OTP al cambiar el teléfono. No es posible sin
reintroducir un mecanismo que `CLAUDE.md` documenta como retirado a
propósito ("no reintroducir OTP/Firebase sin que el usuario lo pida
explícitamente") y sin infraestructura de envío (SMS/correo) que hoy no
existe en el proyecto.

**Opciones:**
- **A — Sin verificación adicional (recomendada).** Editar el propio
  contacto queda al mismo nivel de confianza que ya tiene el admin_sistema
  editando el contacto de un tercero (Módulo 1.1): requiere sesión
  autenticada + contraseña actual (reutilizando el mismo patrón de
  `POST /auth/cambiar-password`, que ya exige `password_actual`), sin OTP.
  Toda edición queda auditada igual (cumple la consideración de "toda
  edición queda auditada" del punto 1.3).
- **B — Reintroducir OTP.** Requeriría (a) tu autorización explícita para
  reintroducir el mecanismo retirado, y (b) construir infraestructura de
  envío real (SMS o correo) que hoy no existe — alcance considerablemente
  mayor, no incluido en esta ronda salvo que lo pidas.

Sin tu confirmación, este plan avanza con la **Opción A**.

### ❓D2 — Programar un viaje (1.5)

Confirmado como el ítem de mayor complejidad, tal como ya advierte la spec.
No se construye sin tu aprobación explícita — se documenta el enfoque
propuesto para que lo revises:

- **Nuevo estado `PROGRAMADO`** en `EstadoViaje` (hoy 9 valores:
  `SOLICITADO, OFERTADO, ASIGNADO, EN_CAMINO, EN_CURSO, FINALIZADO, PAGADO,
  CANCELADO, SIN_CONDUCTOR`) — toca la máquina de estados del viaje, el
  corazón del sistema. Un viaje programado se crea en `PROGRAMADO` con un
  `ts_programado` futuro, y al disparar transiciona a `SOLICITADO` (punto de
  entrada normal del despacho ya existente, CU-O05, sin duplicar su lógica).
- **Disparo diferido vía Airflow** (recomendado sobre alternativas): un DAG
  nuevo (`dag_disparar_viajes_programados`) con `schedule_interval` corto
  (candidato: cada 1-2 minutos — Airflow no es idóneo para granularidad de
  segundos, hay que aceptar esa ventana de margen) que:
  1. Consulta Mongo directo (`pymongo`, ya disponible en la imagen de
     Airflow, mismo patrón que `analytics/plugins/medallion.py`) por
     viajes `PROGRAMADO` con `ts_programado <= ahora + margen`.
  2. Por cada uno, hace un `POST` HTTP al backend (mismo contenedor Docker,
     red interna) a un endpoint nuevo (`POST /viajes/{id}/disparar-programado`
     o similar) que transiciona el viaje a `SOLICITADO` y reutiliza
     `service_dispatch` tal cual — **el DAG nunca reimplementa lógica de
     despacho**, solo dispara el punto de entrada ya existente.
  - Alternativa descartada: que Airflow importe directamente el código del
    backend (acoplaría el paquete `backend/` a la imagen de Airflow,
    innecesariamente invasivo comparado con una llamada HTTP dentro de la
    misma red docker-compose).
- **Cancelación de un viaje programado no disparado todavía**: reutiliza el
  flujo de cancelación existente (CU-O05 A1), con `PROGRAMADO` agregado a
  los estados cancelables.
- **Riesgo aceptado y a decidir contigo**: ¿qué pasa si a la hora
  programada no hay conductores disponibles? Mismo comportamiento que hoy
  (`SIN_CONDUCTOR`, con la A3 de reintento ya pendiente en el backlog del
  proyecto — ver `CLAUDE.md` §3, CU-O05 A3 no construida) o algo distinto
  (ej. reintentar automáticamente N veces antes de avisar)?

Espero tu aprobación explícita (o ajustes al enfoque) antes de tocar
`EstadoViaje` o construir el DAG.

### ❓D3 (informativa, no bloqueante) — Centro de ayuda (4.1) no tiene prioridad asignada en la Sección 5 de la spec

La priorización sugerida (Sección 5) cubre los puntos 1.1-1.5, 2.1-2.3,
3.1-3.3 y 4.2, pero **no menciona 4.1** en ningún lugar del orden. Es,
además, el ítem más barato de construir de todo el documento (FAQ estática
+ dato de contacto, sin backend nuevo). Propongo insertarlo junto al bloque
de Ajustes (Fase 2 de este plan) por su costo casi nulo — lo señalo aquí
para que puedas objetar el orden si preferís que espere.

### Nota de diseño (no requiere aprobación, solo documentada)

Para no crear un módulo de backend por cada micro-funcionalidad, y siguiendo
el mismo criterio de reutilización ya aplicado en Administración, se agrupan
las piezas nuevas de backend así:

- **`perfil/`** (nuevo dominio) — autoservicio de cuenta propia: editar
  contacto (reutiliza `usuarios/service.py::editar_usuario` con
  `usuario_id=actor.usuario_id`, nunca expone `roles`/`forzar_cambio_password`),
  listar/revocar sesiones propias (reutiliza `core/sessions.py`, ya
  construido para Módulo 1.4). Separado de `usuarios/` (que la spec y el
  código ya tratan como exclusivamente administrativo) y de `auth/` (que se
  mantiene enfocado en tokens/credenciales).
- **`preferencias/`** (nuevo dominio) — una sola colección
  `preferencias_usuario` (un documento por `usuario_id`, JSON libre por
  namespace: tema, densidad, notificaciones push por categoría, sonido/
  vibración, hora habitual de turno) en vez de una colección/tabla por
  cada preferencia suelta. Autoservicio total (`GET`/`PATCH` sobre el propio
  actor).
- **`notificaciones/`** (dominio ya existente) — se extiende con la
  persistencia in-app (Sección 5 de este plan), sin tocar lo ya construido
  del Módulo 6.3.
- **`direcciones/`** (nuevo dominio, exclusivo `pasajero`) — CRUD de
  direcciones favoritas.
- **`viajes/`** (dominio ya existente) — se extiende con compartir viaje
  (token + expiración en el propio documento del viaje, sin colección
  nueva) e historial global (nuevo endpoint de solo lectura).

---

## 2. Orden de construcción propuesto

Se parte de la priorización de la Sección 5 de la spec. Un ajuste real
encontrado en la Fase 0: la spec describe el Centro de Notificaciones (4.2)
como si solo *"reutilizara la infraestructura ya existente del Módulo
6.3"* — no es así del todo. `notify_user()` ya centraliza el envío en
vivo, pero **nunca persiste nada** — hoy es enteramente fire-and-forget
(WebSocket o Web Push, sin registro). Construir un centro de notificaciones
navegable requiere: (a) una colección nueva + envolver `notify_user()` para
que también guarde, y (b) sumar llamadas a `notify_user()` en los puntos
del ciclo de vida del viaje que hoy solo usan `broadcast_channel()` (efímero,
sin persistencia — "conductor en camino", "conductor llegó") si se quiere
que esos eventos aparezcan en el centro de notificaciones del pasajero. Es
trabajo real, no solo una vista nueva sobre algo ya construido — mantengo
igual la posición de este ítem en el orden (el costo real sigue siendo
razonable), pero lo dejo señalado para que la estimación sea honesta.

No encontré ninguna otra razón técnica para alterar el orden sugerido.
Queda así:

1. **Perfil propio editable** (1.3 / 2.2 / 3.1) — fundacional, construye
   `perfil/` que nada más depende.
2. **Ajustes básicos** (1.4 / 2.3 / 3.2) + **Centro de ayuda** (4.1,
   agregado por costo casi nulo, ver D3) — construye `preferencias/`.
   *Nota:* el sub-punto de 1.4 "activar/desactivar notificaciones push por
   categoría" se implementa técnicamente junto con el paso 3 (necesita la
   misma taxonomía de tipos de notificación que ese paso define) — el
   resto de Ajustes (tema, densidad, sonido/vibración, recordatorio de
   turno, centro de ayuda) no tiene esa dependencia y se cierra aquí.
3. **Centro de notificaciones in-app** (4.2) — incluye cerrar el
   sub-punto de push-por-categoría de 1.4 pendiente del paso 2.
4. **Historial global de viajes** (3.3) — sin dependencias de los pasos
   anteriores, podría ir en paralelo si hace falta.
5. **Direcciones favoritas** (1.1) y **Compartir viaje** (1.2).
6. **Programar viaje** (1.5) — **bloqueado por ❓D2**, no se inicia sin tu
   aprobación explícita del enfoque.

---

## 3. Perfil propio editable (1.3 / 2.2 / 3.1) — ✅ completo y verificado (2026-08-07)

**Backend — dominio nuevo `perfil/`** (`schemas.py`/`service.py`/`router.py`):
- [x] `GET /perfil` — datos propios (nombre, teléfono, correo, `foto_url`
      si aplica, roles de solo lectura).
- [x] `PATCH /perfil` — editar nombre/teléfono/correo propios. Reutiliza
      `usuarios/service.py::editar_usuario` internamente (mismo chequeo de
      unicidad de teléfono/correo ya existente — se le agregó un parámetro
      `accion` opcional para esto, con `USUARIO_EDICION` como default, sin
      romper Módulo 1.1). Exige `password_actual` en el body (Opción A de
      D1) antes de aplicar el cambio. Auditado con la acción nueva
      `PERFIL_EDICION` (agregada a `ACCIONES_ADMINISTRATIVAS`, mismo
      criterio ya usado con `PASSWORD_CAMBIO`).
- [x] `GET /perfil/sesiones` / `DELETE /perfil/sesiones/{jti}` — reutiliza
      `core/sessions.py::listar_sesiones`/`revocar_sesion` tal cual, solo
      cambia el origen del `usuario_id` (del propio actor).
- [x] Foto de perfil del conductor (2.2): implementada como campo de texto
      (URL) en `usuarios.conductor.foto_url` — mismo patrón `url_objeto` ya
      usado por documentos de captación, sin upload propio (confirmado que
      no existe infraestructura de upload de archivos en el backend). Se
      agregó `_valor_anidado()` en `usuarios/service.py` para que la
      auditoría capture correctamente el "antes" de un campo anidado
      (`conductor.foto_url`), y se propagó `conductor_foto_url` a
      `ViajeOut`/`service_dispatch.py` para que el pasajero la vea al ser
      asignado (CU-O05 P5).
- [x] `POST /auth/cambiar-password` — sin cambios, ya construido; conectado
      indirectamente (el formulario de `PerfilPropio` pide `password_actual`
      para *editar contacto*, no para cambiar contraseña — cambiar
      contraseña en sí queda fuera de esta pantalla, sigue siendo un flujo
      aparte ya existente al que no se le tocó nada).

**Frontend — componente único reutilizado (`PerfilPropio`, nuevo en
`shared-ui`), sección "Mi perfil"/"Mi cuenta":**
- [x] `web-pasajero`: nuevo nav item "Mi perfil".
- [x] `web-conductor`: nuevo nav item "Mi perfil", con `mostrarFoto` activo
      (campo de URL de foto + previsualización circular).
- [x] `web-interno`: nuevo nav item "Mi cuenta" al final de `SECCIONES`
      (a propósito, no al inicio — para no convertirse en la sección por
      defecto de ningún rol ya existente), visible para los 13 roles vía
      un sentinel `ROL_CUALQUIERA = "*"` reconocido en el filtro de
      `Panel()`.
- [x] Formulario con el estándar de errores ya construido (`fieldError`),
      patrón `ReadOnlyGate` (bloqueado por defecto, "Editar" explícito).
- [x] Sub-sección "Sesiones activas" (lista con IP/dispositivo/inicio,
      botón "Cerrar sesión" por fila).
- [x] Tarjeta informativa "Eliminar mi cuenta": deriva al flujo de
      gobernanza de datos ya construido — no duplica la anonimización, dice
      explícitamente que hoy no es autoservicio total (la ejecución real
      sigue siendo de `admin_sistema`), sin prometer más de lo que el
      sistema hace.

**Bloqueo respetado:** `PerfilEditar` (schema) nunca incluye `roles` — un
usuario no puede cambiar su propio rol desde esta pantalla, en ningún rol
de las 3 apps.

**Verificación real (no solo tests)**:
- Backend: `pytest tests/perfil -q` → 8 passed (obtener perfil, password
  incorrecta → 401, edición real con evento `PERFIL_EDICION` confirmado en
  Mongo, `roles` ignorado si se envía, teléfono duplicado → 409, listar/
  cerrar una segunda sesión real con JWT decodificado para identificar el
  jti propio, 401 sin autenticación, cuenta de personal interno ve su
  perfil). Suite completa: **282 passed + 8 skipped** (subió de 274).
  `ruff check src tests` limpio.
- Frontend: `npm run build/lint/test` limpios en las 3 apps + `shared-ui`
  lint. Tests nuevos: 1 en `web-pasajero` (edición con password), 1 en
  `web-conductor` (campo de foto), 1 en `web-interno` (rol sin sección
  propia asignada usando "Mi cuenta", edición con password) — 21/21 en
  web-interno, 6/6 en web-pasajero, 4/4 en web-conductor.
- **Navegador real, las 3 apps, contra el stack corriendo**:
  - `web-interno` (login real `admin_sistema`): editar con contraseña
    incorrecta mostró "La contraseña actual no coincide" inline; con la
    contraseña correcta, el nombre cambió de verdad — confirmado en Mongo
    (`usuarios.nombre`) y el evento `PERFIL_EDICION` real con
    `datos_previos`/`datos_posteriores` correctos. Sesiones activas mostró
    7 sesiones reales (con user-agent/IP reales). Revertido el nombre al
    cierre.
  - `web-pasajero` (login real `+593987001122`): "Mi perfil" cargó sin
    error pese a tener un viaje activo de sesiones previas en curso —
    confirmado que `GET /perfil`/`GET /perfil/sesiones` devuelven 200
    reales en el log de red del navegador.
  - `web-conductor` (login real `+593911223344`): confirmado que el campo
    "URL de foto de perfil" solo aparece aquí (no en pasajero/interno).
  - Sin errores de consola en ninguna de las 3 sesiones — el único 404 real
    observado (`GET /flota/posicion/...`) es preexistente y no relacionado
    (posición de vehículo vencida en un viaje de prueba viejo).

---

## 4. Ajustes básicos (1.4 / 2.3 / 3.2) + Centro de ayuda (4.1) — ✅ completo y verificado (2026-08-07)

**Backend — dominio nuevo `preferencias/`:**
- [x] `GET /preferencias` / `PATCH /preferencias` — documento único por
      usuario (`preferencias_usuario`), campos: `tema`, `densidad_tablas`,
      `notificaciones_push` (dict libre por categoría, la taxonomía real se
      conecta en la Sección 5), `sonido_oferta`, `vibracion_oferta`,
      `recordatorio_turno_hora`. Defaults sensatos si el documento no
      existe (mismo patrón que `configuracion/service.py::DEFAULTS`). Sin
      auditoría — son preferencias de interfaz, no acciones de seguridad ni
      de negocio (a diferencia de `perfil/`, que sí audita).

**Frontend — 2 componentes únicos reutilizados por las 3 apps
(`AjustesPropios`, `CentroAyuda`, nuevos en `shared-ui`):**
- [x] Tema claro/oscuro — paleta oscura completa construida en
      `shared-ui/src/tokens.css` (bloque `:root[data-theme="dark"]`,
      re-calibrando los ~30 tokens de color/estado/gráficos para contraste
      sobre fondo oscuro, misma identidad de matiz que la paleta clara).
      Mecanismo: `theme.ts` (`aplicarTemaInicial()` síncrono en `main.tsx`
      de las 3 apps, antes del primer render, para no parpadear en claro;
      `aplicarTema()` al cargar `/preferencias` o al cambiarlo). Verificado
      con `getComputedStyle` real: fondo pasó a `rgb(15, 17, 21)` (`#0f1115`)
      al elegir "Oscuro".
- [x] Densidad de tablas (`web-interno` únicamente, 3.2) — implementada vía
      variables CSS (`--table-cell-padding-y/x`, mecanismo `densidad.ts`
      idéntico a `theme.ts`) en vez de una prop nueva en `DataTable` (ajuste
      real sobre el diseño original del plan: una variable CSS global
      aplica a las ~15 pantallas con `DataTable` sin tocar ninguna, una prop
      hubiera exigido pasarla manualmente en cada `sections/*.tsx`).
      Verificado con `getComputedStyle` real sobre una celda de la tabla de
      Usuarios: `padding-top` pasó de 8px a 3px al elegir "Compacta".
- [x] Notificaciones push por categoría (1.4) — el modelo de datos
      (`notificaciones_push: dict[str, bool]`) y el endpoint ya existen;
      la UI de toggles por categoría se conecta en la Sección 5 (necesita
      la taxonomía real de tipos de notificación que se define ahí) — tal
      como se anticipó en el plan original, no es un recorte nuevo.
- [x] Preferencias de turno del conductor (2.3) — sonido/vibración
      (checkboxes, sin Web Audio/Vibration API real todavía: el ajuste solo
      persiste la preferencia; el disparo real del sonido/vibración al
      recibir una oferta queda para cuando se conecte con el flujo de
      oferta en vivo, no bloqueante para este cierre) + recordatorio de
      hora habitual (`<input type="time">`, persistido; el banner real al
      abrir la app cerca de esa hora queda como mejora futura, igual
      documentado aquí en vez de simulado).
- [x] Centro de ayuda (4.1) — **ajuste real sobre el diseño del plan**: en
      vez de un ícono flotante en el header (`AppShell.headerActions`,
      hubiera requerido construir un popover/modal nuevo desde cero), se
      implementó como un nav item más ("Ayuda"), mismo patrón que "Mi
      perfil"/"Ajustes" — sigue siendo accesible en un clic desde cualquier
      pantalla vía el sidebar, sin inventar un componente flotante nuevo.
      FAQ estática por app (`PreguntaFrecuente[]`, distinta audiencia por
      app) + contacto. **Contacto con placeholder documentado**
      (`soporte@urbanfleet.example` / `+593900000000`) — no se tenía un
      correo/teléfono real de la cooperativa a la mano; reemplazar por el
      dato real cuando se confirme.

**Verificación real (no solo tests)**:
- Backend: `pytest tests/preferencias -q` → 6 passed (defaults sin
  documento previo, edición parcial que no pisa otros campos, categorías
  de notificaciones push libres, validación de formato HH:MM con 422 real,
  preferencias no compartidas entre cuentas, 401 sin autenticación). Suite
  completa: **288 passed + 8 skipped** (subió de 282). `ruff check src
  tests` limpio.
- Frontend: `npm run build/lint/test` limpios en las 3 apps + `shared-ui`
  lint. Tests nuevos: tema oscuro en `web-pasajero`, preferencias de turno
  en `web-conductor`, densidad de tablas en `web-interno` — 22/22 en
  web-interno, 7/7 en web-pasajero, 5/5 en web-conductor.
- **Navegador real, las 3 apps, contra el stack corriendo**:
  - `web-interno`: cambiar tema a "Oscuro" confirmado con
    `getComputedStyle` real (`rgb(15, 17, 21)`); cambiar densidad a
    "Compacta" confirmado sobre una celda real de la tabla de Usuarios
    (`padding-top: 3px`, antes 8px). Ambos revertidos a los valores por
    defecto al cerrar.
  - `web-pasajero`: "Ayuda" renderiza FAQ + contacto reales.
  - `web-conductor`: "Ajustes" muestra "Preferencias de turno" (no
    aparece en pasajero/interno); guardar la hora del recordatorio
    (`06:30`) confirmado con un `PATCH /preferencias` real (200) y el
    documento real en Mongo (`recordatorio_turno_hora: "06:30"`) —
    limpiado al cerrar.
  - Sin errores de consola nuevos en ninguna de las 3 apps — los únicos
    errores observados (401 por expiración normal de access token,
    auto-resuelto por refresh; 404 de `GET /flota/posicion/...`) son
    preexistentes y no relacionados con este trabajo.

---

## 5. Centro de notificaciones in-app (4.2) + cierre de push-por-categoría (1.4) — ✅ completo y verificado (2026-08-07)

**Backend:**
- [x] Nueva colección `notificaciones_usuario` (`usuario_id`/`tipo`/
      `categoria`/`payload`/`ts`/`leida`). TTL de **30 días** (más generoso
      que `historial_monitoreo`, 7 días — esto es contenido visible al
      usuario final, no solo telemetría interna).
- [x] `NotificationService.notify_user()` envuelto para persistir SIEMPRE
      (sin importar canal en vivo ni preferencia de push) antes de intentar
      la entrega — un solo punto de cambio, ningún call site existente
      tocado (captación, cumplimiento, mantenimiento, alertas de
      seguridad).
- [x] Taxonomía (`CATEGORIA_POR_EVENTO` en `notificaciones/service.py`):
      `captacion`, `cumplimiento`, `mantenimiento`, `viaje`, `seguridad`
      (esta última nunca configurable — `_push_habilitado()` la ignora a
      propósito). Se agregaron los eventos de ciclo de vida del viaje que
      antes solo usaban `broadcast_channel` (efímero): `VIAJE_ASIGNADO`
      (`router_dispatch.py`), `CONDUCTOR_EN_CAMINO`/`CONDUCTOR_LLEGO`/
      `VIAJE_INICIADO`/`VIAJE_CANCELADO_CONDUCTOR` (`router_ejecucion.py`),
      `VIAJE_FINALIZADO` (`router_finalizacion.py`) — cada uno ahora
      también llama `notify_user`, sin reemplazar el `broadcast_channel`
      que el mapa en vivo sigue necesitando.
- [x] `GET /notificaciones/mias` (paginado, con `no_leidas`) / `PATCH
      /notificaciones/mias/{id}/leida` (404 real si la notificación es de
      otro usuario) / `GET /notificaciones/categorias` (excluye
      "seguridad") — autoservicio, cualquier actor autenticado.
- [x] `_push_habilitado()` conecta `preferencias.notificaciones_push`: si
      el usuario desactivó una categoría, no se envía Web Push — pero la
      persistencia en la bandeja ocurre siempre, incondicionalmente.

**Frontend (3 apps, componentes nuevos en `shared-ui`):**
- [x] `NotificacionesBell` — ícono de campana con contador de no leídas,
      vía el nuevo slot `AppShell.headerActions` (mismo slot reservado para
      Centro de Ayuda originalmente, aquí es el primer consumidor real),
      refresco cada 20s, panel desplegable con clic-fuera-para-cerrar.
- [x] Toggles de notificaciones push por categoría, agregados a
      `AjustesPropios` (fetch de `/notificaciones/categorias`, siempre
      visible salvo que la lista venga vacía).

**Verificación real (no solo tests)**:
- Backend: `pytest tests/notificaciones -q` → 14 passed (persistencia real
  vía `NotificationService.notify_user()`, listar con contador de no
  leídas, marcar leída actualiza el contador, 404 real al intentar marcar
  una notificación ajena, 401 sin autenticación, categorías nunca incluyen
  "seguridad", `_push_habilitado()` probado directo confirmando que
  "seguridad" ignora la preferencia y que otra categoría sí la respeta).
  Suite completa: **296 passed + 8 skipped** (subió de 288). `ruff check
  src tests` limpio.
- Frontend: `npm run build/lint/test` limpios en las 3 apps + `shared-ui`
  lint. **Hallazgo real corregido durante los tests**: el botón de la
  campana (`aria-label="Notificaciones"`) colisionaba con el nombre
  accesible del ítem de nav "Notificaciones" ya existente en `web-interno`
  (Módulo 6.3) — `findByRole` fallaba con "multiple elements". Corregido
  a `aria-label="Bandeja de notificaciones"`. También se agregó un default
  de `GET /notificaciones/mias` a los 3 `mockFetch` de test (la campana,
  montada globalmente, dispara su propio fetch de fondo en cualquier
  test). Tests nuevos: campana con contador y marcar-leída en
  `web-pasajero` — 8/8 en web-pasajero, 22/22 en web-interno, 5/5 en
  web-conductor.
- **Navegador real, contra el stack corriendo**: se creó una orden de
  mantenimiento real (vía `jefe_mantenimiento`/staff-verificación, cuenta
  demo real) sobre el vehículo del conductor demo conocido
  (`+593911223344`) — confirmado el documento real en
  `notificaciones_usuario` (`categoria: "mantenimiento"`). Con el conductor
  logueado en `web-conductor`, la campana mostró **"🔔1"** real (no
  simulado), el panel abrió con "Nueva orden de mantenimiento" y su hora
  real, "Marcar leída" disparó un `PATCH` real (200) y el contador volvió a
  0. Los toggles de "Notificaciones push" cargaron las 4 categorías reales
  (sin "seguridad"); desactivar "Estado del viaje" confirmado en Mongo
  (`preferencias_usuario.notificaciones_push.viaje: false`). Un error de
  consola "NotificacionesBell is not defined" apareció en la pestaña que
  había estado abierta durante la sesión de edición (artefacto de HMR de
  Vite, mismo tipo de gotcha ya documentado para Airflow en este proyecto,
  no específico de este código) — confirmado con una pestaña nueva
  (`http://localhost:5174` recién abierta) que la app carga limpia, sin
  ese error ni ningún otro. Datos de prueba (notificación, orden,
  preferencia) limpiados al cerrar.

---

## 6. Historial global de viajes (3.3) — ✅ completo y verificado (2026-08-07)

**Backend:**
- [x] `listar_historial_global` en `viajes/service_historial.py` — mismo
      shape que `listar_historial` pero sin fijar `pasajero_id`/
      `conductor_id` al actor. `texto` busca por nombre de pasajero
      (resuelto vía `usuarios`, ya que `pasajero_nombre` no vive en el
      documento del viaje) o de conductor (directo sobre `conductor_nombre`,
      que sí está snapshoteado desde la asignación). Filtro por zona:
      **gap ya conocido, no implementado** — `zona_origen_id`/
      `zona_destino_id` existen en el schema pero nunca se resuelven
      (mismo límite ya documentado para el panel táctico de Flota); no se
      ofreció un parámetro que prometería un filtro roto.
- [x] `GET /viajes/historial-global` (`router_trips.py`) — gateado a
      `coordinador_operaciones`, `supervisor_cumplimiento`, `gerencia`,
      `admin_sistema` (`require_roles` con los 4 en OR). Reutiliza
      `to_out()`/`HistorialOut` ya existentes de CU-O14, sin schema nuevo.
      Nunca expone teléfono/correo — mismo enriquecimiento "contraparte
      limitada" (`enriquecer_con_pasajero`) que ya usa CU-O14 A2.

**Frontend (`web-interno`):**
- [x] Nuevo work panel "Historial de viajes"
      (`apps/web-interno/src/sections/HistorialGlobal.tsx`), patrón
      WorkPanel estándar: búsqueda por texto + filtro de estado + rango de
      fechas, paginación, `DetailPanel` de solo lectura (pasajero/
      conductor/vehículo/estado/franja/origen/destino/tarifa/km/
      calificaciones — sin mapa, mismo corte de alcance ya documentado en
      `service_historial.py` para CU-O14, "no hay componente de mapa en el
      stack todavía").
- [x] Agregado a `SECCIONES` en `App.tsx`, grupo propio "Historial",
      **al final de la lista** (después de todos los grupos con roles
      únicos) — mismo motivo que "Mi cuenta": no debe convertirse en la
      sección por defecto de ningún rol ya existente. **Bug real
      encontrado durante los tests**: la primera versión lo insertó antes
      de "Administración", lo que desplazó la sección por defecto de
      `admin_sistema` de "Usuarios" a "Historial de viajes" y rompió 4
      tests preexistentes no relacionados (Usuarios ×3, Notificaciones,
      Gobernanza de datos) — corregido moviéndolo al final, mismo patrón
      que ya se había aplicado (y documentado) para "Mi cuenta".
- [x] Test siguiendo el ejemplo de `App.test.tsx` sobre Solicitudes
      (búsqueda por texto + paginación + apertura de detalle).

**Verificación real (no solo tests)**:
- Backend: `pytest tests/viajes/test_historial_global.py -q` → 6 passed
  (403 para un rol no autorizado, incluye viajes de cualquier pasajero,
  filtra por estado, busca por texto de pasajero o conductor, nunca
  expone teléfono, `supervisor_cumplimiento`/`gerencia` también pueden
  ver). Suite completa: **302 passed + 8 skipped** (subió de 296). `ruff
  check src tests` limpio.
- Frontend: `npm run build/lint/test` limpios en las 3 apps + `shared-ui`
  lint — 23/23 en web-interno (1 test nuevo, más la corrección de los 4
  que rompió el bug de orden de arriba).
- **Navegador real, contra el stack corriendo** (login real
  `admin_sistema`, tras un reinicio completo del stack — Docker Desktop
  se había caído a mitad de esta sesión, relanzado y verificado sano antes
  de continuar): login aterrizó correctamente en "Usuarios" (confirma el
  fix de orden también en vivo, no solo en tests). "Historial de viajes"
  cargó **1,334,885 viajes reales** (el dataset histórico NYC sembrado en
  sesiones previas) con paginación real (Página 1 de 66,745). Buscar
  "Conductor Prueba" filtró a 267,014 resultados reales vía un
  `GET .../historial-global?texto=...` real (200). "Siguiente" avanzó a
  `pagina=2` conservando el filtro. El detalle de un viaje SIN_CONDUCTOR
  real mostró todos los campos correctamente (pasajero con nombre de
  pila + calificación, "—" en los campos que no aplican a ese estado).
  Sin errores de consola.

---

## 7. Direcciones favoritas (1.1) — ✅ completo y verificado (2026-08-07)

**Backend — dominio nuevo `direcciones/`, exclusivo `pasajero`:**
- [x] Colección `direcciones_favoritas` (`usuario_id`, `etiqueta` — Casa/
      Trabajo/Otro —, `direccion`, `lat`, `lon`). Índice por `usuario_id`.
- [x] `GET`/`POST`/`DELETE /direcciones` — límite de 10 (`LIMITE_DIRECCIONES`),
      409 real (`LIMITE_DIRECCIONES_ALCANZADO`) al superarlo. `DELETE`
      exige que la dirección sea del propio actor (404 si no existe o es
      de otro usuario — mismo criterio de no filtrar existencia ajena ya
      usado en otros dominios).
- [x] Cubierta por gobernanza de datos: `usuarios/service.py::
      anonimizar_usuario` ahora también purga `direcciones_favoritas` del
      usuario anonimizado (una línea nueva, sin tocar el resto de la
      función).

**Frontend (`web-pasajero`):**
- [x] Accesos rápidos: chips con la etiqueta (Casa/Trabajo/Otro) sobre el
      campo de destino en `PanelSolicitar` — un toque fija
      `destino_lat`/`destino_lon`/`destino_direccion` directo (sin
      geocodificar, ya vienen guardados), sin tocar el mapa.
  - [x] **Ajuste real sobre el diseño del plan**: en vez de un formulario de
        alta con `lat`/`lon` escritos a mano (mala UX sin mapa a la vista),
        se agregó un botón "☆ Guardar como favorita" junto al destino ya
        elegido en el mapa (aparece solo cuando hay un destino real
        seleccionado) — reutiliza las coordenadas que el propio flujo de
        solicitud ya resolvió, sin pedir al pasajero un dato que no tiene
        forma fácil de dar sin un mapa.
- [x] Gestión (ver/eliminar) dentro de "Mi perfil" (slot `extra` de
      `PerfilPropio`, componente nuevo `GestionDireccionesFavoritas`).
      Alta explicada ahí ("se agregan desde la pantalla de viaje"), sin
      duplicar el formulario.

**Verificación real (no solo tests)**:
- Backend: `pytest tests/direcciones -q` → 7 passed (vacío por defecto,
  crear y listar, eliminar propia, 404 al intentar eliminar la de otro
  pasajero, 409 real al superar el límite de 10, 403 para un rol distinto
  de pasajero, anonimizar una cuenta purga sus direcciones reales en
  Mongo). Suite completa: **309 passed + 8 skipped** (subió de 302). `ruff
  check src tests` limpio.
- Frontend: `npm run build/lint/test` limpios en las 3 apps + `shared-ui`
  lint. Test nuevo: seleccionar una favorita fija el destino y viaja
  correctamente en el `POST /viajes` — 9/9 en web-pasajero.
- **Navegador real, contra el stack corriendo**: con la cuenta demo de
  pasajero (`+593987001122`), se creó una dirección real vía API, se
  confirmó en "Mi perfil" (sección "Direcciones favoritas") y se eliminó
  desde ahí con un `DELETE` real (204) — confirmado también contra Mongo
  directo. Luego, en la pantalla de solicitud, el chip "Trabajo" (creado
  de nuevo vía API) rellenó el campo Destino con el valor real guardado
  sin geocodificar; "☆ Guardar como favorita" abrió el selector de
  etiqueta y guardó una nueva dirección real con un `POST /direcciones`
  real (201), confirmado en Mongo. **Nota operativa**: la cuenta demo de
  pasajero tenía un viaje `EN_CURSO` colgado de una sesión anterior — se
  finalizó por el flujo real (`POST /viajes/conductor/finalizar` como el
  conductor demo asignado), no se tocó Mongo directo, para poder llegar a
  la pantalla de solicitud y probar el flujo completo. Direcciones de
  prueba limpiadas al cerrar.

---

## 8. Compartir viaje en tiempo real (1.2) — ✅ completo y verificado (2026-08-07)

**Diseño anti-enumeración de tokens (aprobado explícitamente antes de
construir)**: `secrets.token_urlsafe(32)` (256 bits de entropía, mismo
generador ya usado en `integraciones/service.py` para el secreto de
credenciales mostrado una sola vez) — nunca derivado de datos adivinables;
un único 404 genérico (`VIAJE_COMPARTIDO_NO_ENCONTRADO`) sin distinguir
token inexistente/expirado/viaje ya no compartible, mismo criterio que
`InvalidCredentialsError` en el login; rate limiting de 20 intentos
fallidos en 15 minutos por IP, reutilizando el patrón exacto de
`_registrar_fallo_login` (`auth/service.py`) adaptado a IP en vez de
identificador — nunca cuenta una consulta válida contra el contador.

**Backend (`viajes/`):**
- [x] Campos nuevos en el documento del viaje: `token_compartir` (solo se
      escribe al pedirlo explícitamente, nunca por defecto) +
      `token_compartir_expira_en` (techo de 4h, `TECHO_EXPIRACION_HORAS` —
      la invalidación real ocurre antes, al finalizar/cancelar el viaje,
      no depende de este techo). Índice único-sparse
      `viajes.token_compartir` en `ensure_indexes()`.
- [x] `POST /viajes/activo/compartir` (autenticado, pasajero) — genera el
      token; idempotente mientras el token previo siga vigente (evita
      invalidar un enlace ya compartido si el pasajero toca el botón dos
      veces). Solo para viaje en `EN_CAMINO`/`EN_CURSO`
      (`ESTADOS_COMPARTIBLES`); `SIN_VIAJE_ACTIVO` (404) en cualquier otro
      caso, reutilizando `SinViajeActivoError` ya existente.
- [x] **Endpoint público nuevo, sin autenticación** —
      `GET /publico/viajes-compartidos/{token}` (primer endpoint sin
      `Depends(get_current_actor)` del proyecto fuera de
      `/auth/registro`/`/auth/login`, documentado como tal en el docstring
      del router). Devuelve solo: nombre + calificación + foto del
      conductor, placa del vehículo, estado del viaje, posición actual
      (leída del mismo caché Redis `pos:{vehiculo_id}` que usa el resto
      del proyecto) — nunca teléfono/correo, nunca ningún dato del
      pasajero.
- [x] Invalidación explícita del token (además del techo de 4h) en 2
      puntos, como defensa en profundidad: `service_finalizacion.py::
      finalizar_viaje` ($unset al cerrar normalmente) y
      `service_ejecucion.py::cancelar_por_conductor` ($unset porque el
      viaje puede terminar reasignado a OTRO conductor, y un token viejo
      no debe seguir mostrando la posición de un vehículo distinto sin que
      el pasajero lo vuelva a compartir).
- [x] Acción de auditoría nueva `VIAJE_COMPARTIR_ACTIVADO` (write-ahead,
      antes de persistir el token) — generar el enlace es una acción
      sensible (expone la posición en vivo a quien lo tenga). Deliberadamente
      NO en `ACCIONES_ADMINISTRATIVAS` (es autoservicio de pasajero, no una
      acción de `admin_sistema`).

**Frontend (`web-pasajero`):**
- [x] Botón "Compartir viaje" en `PanelViajeActivo`, visible solo en
      `EN_CAMINO`/`EN_CURSO` — genera el enlace (`${origin}/compartido/{token}`)
      y muestra un campo de solo lectura + botón "Copiar enlace"
      (`navigator.clipboard`, con fallback silencioso al campo visible si
      el permiso de portapapeles no está disponible).
- [x] `RideMap` ganó el prop `soloLectura` (suprime el control "Ir a mi
      ubicación" y los clics de "elegir destino") — reutilizado sin
      duplicar el componente.
- [x] Página pública nueva `VistaCompartida`, sin router (el proyecto no
      usa uno): un chequeo de `window.location.pathname` contra
      `/^\/compartido\/(.+)$/` al inicio de `App()`, antes de la rama
      autenticada/login — primera ruta pública real de cualquiera de las 3
      apps. Polling cada 8s (más corto que el resto del proyecto, 15s, porque
      acá el propósito completo de la página es la posición en vivo) vía
      `apiFetch(..., { auth: false })`. Sin posición disponible → mensaje
      explícito en vez de un mapa vacío; token inválido/expirado → mensaje
      genérico igual al del backend.

**Verificación real (no solo tests)**:
- Backend: `pytest tests/viajes/test_compartir.py` → 8 passed (generar
  token con viaje EN_CAMINO, idempotencia, 404 sin viaje activo, 404
  genérico con token inválido, limpieza al finalizar, limpieza al cancelar
  por conductor, bloqueo real tras 20 fallos desde una IP, 25 consultas
  válidas seguidas sin disparar el bloqueo). Bug real encontrado y
  corregido durante esta prueba: comparar `expira_en` (datetime naive leído
  de Mongo) contra `datetime.now(UTC)` (aware) reventaba con `TypeError`
  en el chequeo de idempotencia — corregido con `como_utc()` (mismo helper
  ya usado en el resto del proyecto para este problema conocido de
  PyMongo). Suite completa: **317 passed + 8 skipped**. `ruff check src
  tests` limpio.
- Frontend: `npm run build/lint/test` limpios en `web-pasajero` (9/9,
  sin regresión) + `shared-ui` lint.
- **Navegador real, contra el stack corriendo**: viaje real llevado por
  API hasta `EN_CAMINO` (cuenta demo pasajero `+593987001122` + conductor
  `+593911223344`), botón "Compartir viaje" real en la UI generó el enlace,
  abierto en una pestaña nueva SIN sesión — la página pública mostró
  "El conductor va en camino", nombre/calificación/placa reales y el mapa
  de solo lectura (sin botón "Ir a mi ubicación", confirmado por
  `read_page`), con la petición real `GET /publico/viajes-compartidos/...`
  devolviendo 200 sin ningún header de autorización. Un token inventado
  mostró el mensaje genérico "Enlace no válido o expirado". El viaje real
  se llevó hasta `FINALIZADO` por el flujo completo del conductor
  (llegué→iniciar→finalizar) y el mismo enlace ya generado pasó a devolver
  el mismo mensaje genérico (404 real). Confirmado en Mongo directo:
  `token_compartir`/`token_compartir_expira_en` ausentes del documento tras
  finalizar, y el evento `VIAJE_COMPARTIR_ACTIVADO` real en `bitacora` con
  el actor/rol/expiración correctos. Viaje y pago de prueba eliminados de
  Mongo al cerrar (no formaban parte de ningún seed oficial).

---

## 9. Programar un viaje (1.5) — ✅ completo y verificado (2026-08-07)

Construido tal cual el enfoque de D2 aprobado (Sección 1) — un nuevo estado
`PROGRAMADO`, disparo diferido vía Airflow + HTTP interno, sin mecanismo de
reintento especial si no hay conductor a la hora programada (cae en
`SIN_CONDUCTOR`, mismo comportamiento de siempre).

**Backend (`viajes/`):**
- [x] `EstadoViaje` gana `PROGRAMADO` (ahora 10 valores). `SolicitarViajeRequest`
      gana `ts_programado: datetime | None`. Ventana válida:
      `MARGEN_MINIMO_PROGRAMACION_MINUTOS = 15` (para que tenga sentido
      distinto de "Ahora" y le dé margen a la cadencia del DAG) /
      `MARGEN_MAXIMO_PROGRAMACION_DIAS = 7` (evita fechas absurdamente
      lejanas sin caso de uso real detrás) — `TS_PROGRAMADO_INVALIDO` (422)
      fuera de ese rango.
- [x] `solicitar_viaje`: con `ts_programado`, el viaje se crea en
      `PROGRAMADO` (franja/tarifa de vista previa resueltas sobre la hora
      programada, no sobre el momento de la solicitud) y **no** dispara
      `avanzar_despacho` — eso ocurre después, vía `disparar_viaje_programado`.
- [x] `disparar_viaje_programado(db, viaje_id)`: transiciona
      `PROGRAMADO -> SOLICITADO`, actualiza `ts_solicitud` a AHORA (no al
      momento de creación del registro — necesario para que
      `rpt_tiempo_asignacion`/`rpt_tasa_cancelacion`, que particionan
      `fact_ciclo_viaje` por `ts_solicitud`, no mezclen "cuándo se programó"
      con "cuándo entró realmente a buscar conductor"), conserva
      `ts_programado` como registro de la hora pedida, y llama
      `avanzar_despacho` — el mismo punto de entrada de siempre (CU-O05),
      sin duplicar lógica. 404 `VIAJE_NO_PROGRAMADO` si el viaje ya no está
      en ese estado (reintento seguro).
- [x] `POST /viajes/{id}/disparar-programado` — protegido por
      `X-Internal-Token` (`core/config.py::internal_api_token`, comparado
      con `secrets.compare_digest`), primer endpoint del proyecto pensado
      para ser llamado por otro servicio del stack (Airflow), no por un
      usuario final. `TOKEN_INTERNO_INVALIDO` (403) sin token o con uno
      incorrecto.
- [x] `ESTADOS_ACTIVOS`/`ESTADOS_CANCELABLES_PASAJERO` ganan `PROGRAMADO` —
      un viaje programado cuenta como "activo" (bloquea uno nuevo, aparece
      en `GET /viajes/activo`) y es cancelable con el mismo flujo de
      siempre (`POST /viajes/activo/cancelar`).
  - **Bug real encontrado y corregido de paso, necesario para que esto
    funcionara**: `service.py` tenía DOS definiciones de `ESTADOS_ACTIVOS`
    a nivel de módulo (línea 30, para `obtener_viaje_activo`/
    `cancelar_viaje_pasajero`; línea 335, para el panel táctico de
    Despacho) — la segunda reasignaba el mismo nombre, así que TODAS las
    funciones del archivo resolvían contra la segunda definición en tiempo
    de ejecución (sombra de nombre a nivel de módulo), sin PROGRAMADO.
    Agregar PROGRAMADO solo a la primera no habría tenido ningún efecto.
    Corregido renombrando la segunda a `ESTADOS_ACTIVOS_PANEL`
    (deliberadamente SIN PROGRAMADO — un viaje que no disparó su despacho
    no es "un viaje en curso ahora" para ese panel).

**Disparo diferido (`analytics/`):**
- [x] `dag_disparar_viajes_programados.py` (nuevo) — a diferencia de los
      otros 7 DAGs del proyecto, NO es un pipeline Bronze->Silver->Gold (no
      toca `medallion.py`/ClickHouse/"corridas" de Plataforma); es un
      disparador operativo puro. `schedule_interval="*/2 * * * *"`, consulta
      Mongo directo (`pymongo`, mismo patrón que el resto de DAGs) por
      `PROGRAMADO` con `ts_programado <= ahora`, y por cada uno hace
      `POST {BACKEND_URL}/viajes/{id}/disparar-programado` con el token
      interno — nunca reimplementa lógica de despacho. Un 404 en la
      respuesta (otra corrida ya lo disparó) se trata como esperado, no como
      fallo; solo un fallo real (5xx/error de red) hace fallar la tarea
      (reintentable, `retries=2` — el endpoint es seguro de reintentar).
- [x] `BACKEND_URL`/`INTERNAL_API_TOKEN` agregados al `airflow-env` de
      `docker-compose.yml` (mismo secreto que `internal_api_token` del
      backend, vía `.env` nuevo `INTERNAL_API_TOKEN`).

**Frontend (`web-pasajero`):**
- [x] Toggle "Ahora"/"Programar" en `PanelSolicitar`, junto al botón final
      (nunca reemplaza el flujo de "Ahora" — es una opción nueva al lado).
      `Programar` muestra un `<input type="datetime-local">` con `min`
      calculado en cliente (mismo margen de 15 min que el backend, solo
      para UX — la validación real sigue siendo del servidor). Botón final
      cambia de texto ("Solicitar taxi" / "Programar viaje") según el modo.
- [x] `PanelViajeActivo` muestra "Programado para: <fecha/hora local>"
      cuando `estado === "PROGRAMADO"`, con el mismo botón "Cancelar
      solicitud" de siempre (reutilizado, `ESTADOS_CANCELABLES_PASAJERO`
      ya lo incluye).
- [x] Estado del formulario (`modoSolicitud`/`tsProgramadoLocal`) se
      reinicia automáticamente a "Ahora" cada vez que `viaje` vuelve a
      `null` (un solo `useEffect`, cubre los 4 puntos donde eso pasa —
      cancelar, calificar, error de refresco — sin tocar cada uno).

**Verificación real (no solo tests)**:
- Backend: `pytest tests/viajes/test_programar_viaje.py` → 10 passed
  (crea PROGRAMADO sin despachar, rechazo <15min, rechazo >7 días, cuenta
  como activo y bloquea uno nuevo, cancelación, disparar sin/con token
  incorrecto → 403, disparar transiciona a SOLICITADO y avanza despacho,
  disparar sobre no-PROGRAMADO → 404, reintento idempotente → 404 la
  segunda vez). Suite completa: **327 passed + 8 skipped** (subió de 317).
  `ruff check src tests` limpio.
- Frontend: `npm run build/lint/test` limpios en `web-pasajero` (10/10,
  subió de 9) + `shared-ui` lint. Test nuevo: elegir "Programar" + fecha
  futura envía `ts_programado` (calculado con la misma conversión
  local->ISO que usa el propio componente, para no depender de la zona
  horaria de la máquina que corre el test) y muestra "Viaje programado".
- **Navegador real, contra el stack corriendo** (`docker compose up -d`
  para aplicar las variables de entorno nuevas del DAG, backend
  reiniciado): flujo completo en `web-pasajero` con la cuenta demo de
  pasajero — toggle "Programar", fecha a 30 días (rechazada con el mensaje
  real "La hora programada no puede ser más de 7 días en el futuro", 422
  real), fecha válida (+3h) aceptada con un `POST /viajes` real (201),
  panel mostrando "Viaje programado" y "Programado para: 7/8/2026,
  18:39:00" — confirmado en Mongo (`estado: "PROGRAMADO"`,
  `ts_programado` real, `conductor_id: null`, sin despacho disparado).
  **Cadena Airflow -> backend real, no simulada**: DAG confirmado sin
  errores de importación (`airflow dags list-import-errors`), despausado;
  un segundo viaje programado creado por API con un conductor real
  disponible, `ts_programado` adelantado en Mongo para simular que ya
  venció (única parte no ejercitada por la UI: esperar minutos reales), y
  **disparado por una corrida real del DAG** (`airflow dags trigger`, no un
  curl manual) — log real de la tarea: `"1 disparados, 0 fallidos, 1
  candidatos"`, confirmado en Mongo el viaje pasando a `OFERTADO` con
  `ts_solicitud` actualizado al instante del disparo real y `ts_programado`
  preservado. Corridas automáticas del propio schedule (`*/2 * * * *`)
  confirmadas corriendo solas y en verde de fondo durante la prueba. Probado
  también sin token (403 real) y con token incorrecto (403 real). Viajes,
  ofertas y estado de conductor de prueba limpiados de Mongo al cerrar.

---

## 10. Estándar de cierre por funcionalidad (aplica a todas las secciones)

- [ ] Backend + frontend avanzan juntos — no se cierra una funcionalidad
      con un lado a medias.
- [ ] Toda acción sensible nueva (edición de perfil, cambio de contraseña
      ya cubierto, activar compartir viaje) queda en la bitácora de
      auditoría existente (`write_audit_event`, nunca un sistema paralelo).
- [ ] Verificación real en navegador antes de marcar completa, esfuerzo
      ajustado a la complejidad — mismo criterio que el resto del proyecto
      (`CLAUDE.md` §6).
- [ ] `npm run build/lint/test` en las 3 apps + `pytest` backend al cerrar
      **cada funcionalidad**, no solo al final del bloque completo.
- [ ] Reporte de cierre por funcionalidad, no se espera a tener todo el
      bloque.

## 11. Estado final por funcionalidad (se completa al cierre de cada una)

| Funcionalidad | Estado |
|---|---|
| 1.3/2.2/3.1 — Perfil propio editable | ✅ completo y verificado (2026-08-07) |
| 1.4/2.3/3.2 — Ajustes básicos | ✅ completo y verificado (2026-08-07) |
| 4.1 — Centro de ayuda | ✅ completo y verificado (2026-08-07) — contacto con placeholder documentado |
| 4.2 — Centro de notificaciones in-app | ✅ completo y verificado (2026-08-07) |
| 3.3 — Historial global de viajes | ✅ completo y verificado (2026-08-07) |
| 1.1 — Direcciones favoritas | ✅ completo y verificado (2026-08-07) |
| 1.2 — Compartir viaje en tiempo real | ✅ completo y verificado (2026-08-07) |
| 1.5 — Programar un viaje | ✅ completo y verificado (2026-08-07) |
