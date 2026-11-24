# Plan de Pruebas — UrbanFleet TaxiFlow

Este plan cubre **lo que el sistema hace hoy**. No incluye funcionalidad planificada ni casos
inventados para tener algo que probar: cada caso de abajo se puede ejecutar contra el sistema real
tal como está. Donde una función tiene una limitación conocida, el caso lo dice y explica cuál es
el resultado correcto (que a veces es "no aparece nada" — y eso está bien).

El documento tiene 5 partes. Las partes 2 y 3 comprueban **si el sistema funciona**; la parte 4
comprueba **si una persona puede usarlo**, que es una pregunta distinta y se responde con otro
método.

---

## 1. Plan general de testing

### 1.1 Alcance

| Portal | Puerto | Quién lo usa | Qué se prueba |
|---|---|---|---|
| `web-pasajero` | 5173 | Pasajeros | Registro, pedir/programar/compartir/cancelar viaje, calificar, historial propio **con mapa del recorrido**, direcciones favoritas, perfil y ajustes |
| `web-conductor` | 5174 | Socios conductores | Postulación **con carga de documentos**, turno, aceptar/ejecutar/finalizar viaje, cobro, reportar fallas, documentos propios, liquidaciones propias, perfil y ajustes |
| `web-interno` | 5175 | Personal de la cooperativa | 3 niveles organizacionales: operativo (6 procesos), táctico (10 tableros), estratégico (9 + Tablero Ejecutivo), y transversales (8 módulos de Administración) |

### 1.2 Qué está cubierto de forma automatizada hoy

| Suite | Cómo se corre | Cobertura real |
|---|---|---|
| Backend (pytest) | `docker compose exec -T backend python -m pytest -q` | **476 pruebas** sobre 28 módulos de dominio (auth, captación, viajes, recaudación, mantenimiento, cumplimiento, usuarios, preferencias, reportes de falla, archivos, respaldos, etc.) |
| `web-pasajero` (vitest) | `npm run test -w @urbanflet/web-pasajero` | 10 pruebas |
| `web-conductor` (vitest) | `npm run test -w @urbanflet/web-conductor` | 6 pruebas |
| `web-interno` (vitest) | `npm run test -w @urbanflet/web-interno` | 27 pruebas |
| Tipos y estilo | `npm run build` + `npm run lint` (por app), `ruff check src/ tests/` (backend) | Compilación y reglas de estilo |

> **Aviso importante sobre pytest.** El contenedor monta `backend/src` pero **no** `backend/tests`:
> los tests vienen horneados en la imagen. Si no se hace `docker cp backend/tests
> urbanflet-taxiflow-backend-1:/app/` antes de correr la suite, se ejecutan tests viejos y el
> resultado no significa nada. Alternativa: correr pytest desde el venv local. Está pendiente
> agregar el bind mount que lo resuelve de raíz.

**Qué NO cubre lo automatizado**, y por eso necesita verificación manual:
- Todo lo visual (que algo se vea bien, que el texto sea legible, que un color comunique lo que debe).
- Los flujos que cruzan dos portales en tiempo real (pasajero y conductor en paralelo durante un viaje).
- Los mapas (Leaflet no se renderiza igual en el entorno de pruebas automatizadas).
- La subida real de archivos (fotos de perfil, evidencia de fallas, documentos de postulación).
- Los tableros táctico/estratégico contra datos reales de ClickHouse (las pruebas usan datos simulados).
- **Todo lo de la parte 4**: ninguna prueba automatizada puede decir si una persona entiende una pantalla.

### 1.3 Frecuencia recomendada

| Cuándo | Qué correr |
|---|---|
| Antes de cada commit que toca código | Las 4 suites automatizadas (backend + 3 frontends) |
| Antes de una entrega o demostración | Automatizadas + Parte 2 completa (pruebas de desarrollador) |
| Después de un cambio visual o de navegación | Automatizadas + Parte 4.4 (comprobaciones puntuales) |
| Antes de mostrar el sistema a un tercero | Parte 3 completa, ejecutada por alguien que no lo construyó |
| Al cerrar un bloque grande de funcionalidad, o antes de una evaluación | **Parte 4 completa** (escenarios de tarea real) — es la más cara de ejecutar y la que más información nueva aporta |

### 1.4 Cómo levantar el entorno antes de probar

```bash
docker compose up -d
```

```bash
npm run dev -w @urbanflet/web-pasajero
```

```bash
npm run dev -w @urbanflet/web-conductor
```

```bash
npm run dev -w @urbanflet/web-interno
```

Puertos: pasajero 5173, conductor 5174, interno 5175. Si Airflow no responde en
http://localhost:8080 tras un arranque normal: `docker compose up -d --force-recreate airflow-webserver`.

### 1.5 Credenciales de prueba

| Portal / nivel | Identificador | Contraseña |
|---|---|---|
| Pasajero | `+593980018` (Ryan White) | `UsuarioDemo123!` |
| Conductor (vehículo habilitado) | `+593980010` (Christopher Anderson) | `UsuarioDemo123!` |
| Interno — operativo y táctico | `+593900000001` (Staff Verificación) | `VerifDash123!` |
| Interno — estratégico | `+593900000010` (Gerencia Demo) | `Gerencia123!` |
| Interno — administración | `+593900000099` (Admin Sistema QA) | `AdminSistema123!` |

### 1.6 Datos de prueba con los que ya cuenta el entorno

Para no toparse con pantallas vacías. Verificado contra la base real:

| Necesito… | Usar |
|---|---|
| Un viaje **con recorrido real** en el mapa | Pasajero Ryan White → "Mis viajes" → **17/8/2026 03:44:32**, destino *El Paseo Shopping* (18 puntos de traza) |
| El viaje con **más recorrido** de todo el sistema | `web-interno` → Historial de viajes → buscar **"Darwin Sanchez"** → fila del **19/8/2026 00:56:17** (264 puntos) |
| Un viaje **sin recorrido registrado** | Pasajero Ryan White → **23/8/2026 15:15:43**, "Origen QA icono conductor" (sin conductor asignado) |
| Un viaje **sin destino registrado** | `web-interno` → Historial de viajes → buscar **"Pasajera Slice1"** → fila del **30/7/2026 02:51:50** |
| Una **solicitud de postulación pendiente** | 23 en `ENVIADA` + 20 en `EN_VERIFICACION` (ver aviso en 4.5 sobre sus documentos) |
| Una solicitud con **documentos que se ven de verdad** | Cédula `0977700077` ("Postulante Documental QA"), ya `APROBADA` — o crear una nueva desde `web-conductor` |
| Un **reporte de falla pendiente** | 3 sobre la placa **FIC-0010** (avería mecánica, falla eléctrica, neumático) |
| Órdenes de mantenimiento en curso | 29 `ABIERTA` + 23 `EN_TALLER` |

---

## 2. Pruebas funcionales para desarrolladores

Nivel de detalle: pasos concretos, dato de entrada y resultado esperado verificable (en pantalla,
en la red o en la base de datos).

### PD-01 — Ciclo de vida completo del viaje

| Campo | Contenido |
|---|---|
| **Precondición** | Un conductor con vehículo `HABILITADO` y turno iniciado. Dos pestañas abiertas: pasajero (5173) y conductor (5174). |
| **Pasos** | 1. Conductor: "Mi turno" → "Iniciar turno" (aceptar permiso de ubicación).<br>2. Pasajero: tocar el mapa para fijar destino → "Solicitar taxi".<br>3. Conductor: en la oferta entrante, "Aceptar".<br>4. Conductor: "Voy en camino" → "He llegado" → "Iniciar viaje".<br>5. Conductor: "Finalizar viaje".<br>6. Conductor: ingresar el monto exacto de la tarifa → "Confirmar pago recibido".<br>7. Ambos: calificar con estrellas → "Enviar calificación". |
| **Datos de entrada** | Monto cobrado = tarifa final mostrada (ej. `1.75`). |
| **Resultado esperado** | El estado avanza `SOLICITADO → OFERTADO → ASIGNADO → EN_CAMINO → EN_CURSO → FINALIZADO → PAGADO`. Al finalizar, ambos portales muestran el desglose: Arrancada + Distancia + Espera = Subtotal; si el subtotal no llega al mínimo, aparece además "Carrera mínima aplicada". El viaje queda en "Mis viajes" de ambas cuentas y en Historial de viajes de `web-interno`. |
| **Verificación técnica** | En Mongo: `db.viajes.findOne({_id:"<id>"})` con `estado:"PAGADO"`, `desglose_tarifa` poblado y ambas calificaciones. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-02 — Postulación de conductor con documentos y aprobación

| Campo | Contenido |
|---|---|
| **Precondición** | Ninguna. Requiere cédula, teléfono y placa no usados antes, y dos imágenes (JPG/PNG/WEBP, < 5 MB). |
| **Pasos** | 1. `web-conductor` → "Postula aquí" → completar nombre, teléfono, contraseña (mín. 8), cédula, licencia, placa, año, marca, modelo, color, capacidad.<br>2. En la sección "Documentos": adjuntar licencia de conducir y matrícula del vehículo, cada una con su fecha de caducidad.<br>3. "Enviar solicitud".<br>4. `web-interno` (Staff Verificación) → "Solicitudes" → localizar la fila `ENVIADA` → "Ver" → revisar los documentos → "Tomar".<br>5. Elegir "Aprobar" → "Aceptar decisión". |
| **Datos de entrada** | Cédula, teléfono y placa nuevos; marca/color pueden usar la opción "Otro" con texto libre. Fechas de caducidad futuras. |
| **Resultado esperado** | Los 4 botones de "Enviar solicitud" quedan deshabilitados hasta que ambos documentos y ambas fechas estén completos. La solicitud pasa `ENVIADA → EN_VERIFICACION → APROBADA`. En el detalle de Captación se ven las **dos imágenes reales**, su fecha de caducidad y un semáforo de vigencia. La aprobación crea el usuario conductor, su vehículo y **dos registros reales de documento**. |
| **Verificación técnica** | En la red: `POST /captacion/solicitudes` (201) → `POST /auth/login` (200) → `POST /archivos` ×2 (201) → `POST /captacion/solicitudes/mia/documentos` (200). En Mongo, `db.documentos.find({propietario_id:"<usuario_id>"})` devuelve la licencia, y la matrícula queda asociada al vehículo nuevo. |
| **Caso borde** | Si se corta el proceso entre el paso 1 y el 3, la solicitud queda en `BORRADOR` — invisible para Captación. Nunca debe quedar una solicitud `ENVIADA` sin documentos. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-03 — Orden de mantenimiento con todos sus estados

| Campo | Contenido |
|---|---|
| **Precondición** | `web-interno` con rol Jefe de Mantenimiento. Existen órdenes `ABIERTA` en el entorno. |
| **Pasos** | 1. "Mantenimiento" → pestaña "Órdenes" → "Nuevo" → buscar vehículo por placa → seleccionar → completar km de entrada, taller, fecha programada, repuestos estimados y mano de obra → "Crear orden".<br>2. Abrir la orden → "En taller".<br>3. "Esperar repuesto" con un motivo → verificar el estado.<br>4. "Reanudar" → volver a `EN_TALLER`.<br>5. "Cerrar" con trabajos realizados, costo real, horas de taller, km de salida y repuestos consumidos. |
| **Datos de entrada** | Costo estimado ≠ costo real (ej. estimado `$55`, real `$72`) para provocar una desviación visible. |
| **Resultado esperado** | Estados: `ABIERTA → EN_TALLER → ESPERANDO_REPUESTO → EN_TALLER → CERRADA`. Al cerrar, un mensaje muestra la próxima intervención preventiva proyectada (en km) y el porcentaje de desviación de costo (ej. `+30.9%`). Las transiciones quedan registradas solas en la cronología de actividad de la orden. |
| **Verificación técnica** | El vehículo vuelve a `HABILITADO`. El evento `ORDEN_MANTENIMIENTO_CIERRE` lleva costo estimado y real. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-04 — Reporte de falla desde los dos orígenes

| Campo | Contenido |
|---|---|
| **Precondición** | Conductor con vehículo asignado; Jefe de Mantenimiento en `web-interno`. |
| **Pasos** | 1. `web-conductor` → "Fallas del vehículo" → "Reportar una falla" → tipo de falla + descripción + foto opcional → enviar.<br>2. `web-interno` → "Mantenimiento" → pestaña "Reportes de falla" → "Nuevo" → buscar vehículo por placa → tipo de falla + descripción → "Crear reporte".<br>3. Sobre cualquiera de los dos: "Convertir en orden" (km, taller, fecha) o "Descartar" con motivo. |
| **Resultado esperado** | Ambos reportes aparecen en **la misma bandeja**, sin ninguna marca visual que sugiera que uno vale más que el otro. El reportado por el conductor lleva su ubicación real; el creado internamente toma la última posición conocida del vehículo. Ambos ofrecen "Convertir en orden" y "Descartar". |
| **Verificación técnica** | En `db.reportes_falla`, ambos documentos tienen `estado:"PENDIENTE"`; el interno tiene `viaje_id:null` e `impide_continuar:false`. El evento de bitácora del interno lleva `origen:"personal_interno"`. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-05 — Catálogos: alta, edición y baja lógica

| Campo | Contenido |
|---|---|
| **Precondición** | `web-interno` con rol Administrador del Sistema. |
| **Pasos** | 1. "Catálogos" → pestaña "Talleres" → "Nuevo" → nombre + datos → guardar.<br>2. Abrir el registro creado → cambiar el nombre → guardar.<br>3. Abrir de nuevo → desmarcar "Activo" → guardar.<br>4. Ir a "Mantenimiento" → "Nuevo" (orden) → abrir el selector de taller. |
| **Resultado esperado** | El taller creado aparece en Catálogos. Tras desactivarlo, **sigue visible en Catálogos con estado INACTIVO** (para poder reactivarlo) pero **ya no aparece en el selector de taller** de Mantenimiento. El botón "Eliminar" está deshabilitado con un mensaje que explica que se desactiva, no se elimina. |
| **Verificación técnica** | `GET /catalogos/talleres` no lo devuelve; `GET /catalogos/talleres?incluir_inactivos=true` sí. En Mongo el documento sigue existiendo con `activo:false` (nunca se borra). |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-06 — Baja lógica de una cuenta y sus casos borde

| Campo | Contenido |
|---|---|
| **Precondición** | `web-interno` con rol Administrador del Sistema. Crear una cuenta de prueba desde "Usuarios" → "Nuevo". |
| **Pasos** | 1. Confirmar que la cuenta nueva puede iniciar sesión.<br>2. "Usuarios" → buscarla → "Ver" → "Dar de baja" → leer la advertencia → escribir un motivo → "Confirmar baja".<br>3. Intentar iniciar sesión con esa cuenta.<br>4. Buscarla con el filtro Estado = "Baja". |
| **Datos de entrada** | Motivo: texto de al menos 3 caracteres. |
| **Resultado esperado** | Antes de confirmar se muestra una advertencia que explica qué pasa con el historial y con un vehículo habilitado a su nombre. Tras la baja: **el login falla (401)**, la cuenta **sigue existiendo** con estado `BAJA` y su motivo, y todo su historial permanece visible. |
| **Caso borde** | Con un viaje en curso (`SOLICITADO`…`EN_CURSO`), la baja se **rechaza con un 409** y un mensaje que indica qué viaje hay que cerrar primero. |
| **Verificación técnica** | `db.usuarios.countDocuments({telefono:"<tel>"})` sigue en `1` (no hubo borrado físico). El evento `USUARIO_BAJA` incluye `vehiculos_habilitados_pendientes`. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-07 — Foto de perfil y preferencias por cuenta

| Campo | Contenido |
|---|---|
| **Precondición** | Cualquier cuenta, en cualquiera de los 3 portales. |
| **Pasos** | 1. "Ajustes" → "Cambiar foto" → elegir un JPG/PNG/WEBP de menos de 5 MB.<br>2. Cambiar "Tema" a Oscuro y "Tamaño de texto" a Muy grande.<br>3. Recargar la página completa (F5).<br>4. Iniciar sesión con **otra** cuenta distinta. |
| **Resultado esperado** | La foto aparece de inmediato en el encabezado y en "Mi cuenta", sin recargar. Tema y tamaño de texto se aplican al instante y **sobreviven a la recarga**. La otra cuenta conserva sus propios valores (las preferencias son por cuenta, no globales). |
| **Verificación técnica** | `GET /preferencias` con el token de cada cuenta devuelve valores distintos. En el navegador, `--font-scale` vale `1.3` con "Muy grande" y `1` con "Normal". |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-08 — Orden de las tablas (más reciente primero)

| Campo | Contenido |
|---|---|
| **Precondición** | Ninguna. |
| **Pasos** | Abrir y mirar la primera fila de: Solicitudes, Mantenimiento → Órdenes, Historial de viajes (`web-interno`); "Mis viajes" (`web-pasajero`); "Fallas del vehículo" (`web-conductor`). |
| **Resultado esperado** | En todas, el registro **más reciente aparece primero**. En Solicitudes se ordena por fecha de envío; en Órdenes por fecha programada; en Historial y Mis viajes por fecha de solicitud; en Fallas por fecha del reporte. |
| **Limitación conocida** | La búsqueda de vehículos por placa se ordena alfabéticamente, no por fecha: `vehiculos` no tiene ningún campo de fecha de alta. No es un fallo. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-09 — Mapa del recorrido en el historial, en sus 3 estados

| Campo | Contenido |
|---|---|
| **Precondición** | Ninguna. Usar los viajes de la tabla 1.6. |
| **Pasos** | 1. `web-pasajero` (Ryan White) → "Mis viajes" → "Ver" en el viaje del **17/8/2026 03:44:32** (con recorrido).<br>2. Volver y abrir el del **23/8/2026 15:15:43** (sin recorrido).<br>3. `web-interno` → Historial de viajes → buscar "Pasajera Slice1" → abrir la fila del **30/7/2026 02:51:50** (sin destino).<br>4. `web-conductor` (Christopher Anderson) → "Mis viajes" → abrir cualquiera con recorrido. |
| **Resultado esperado** | **Con recorrido**: se dibuja una línea ámbar siguiendo el trayecto real, con un círculo hueco en la recogida y uno sólido en el destino, y la nota "Recorrido real del vehículo según su traza GPS (N puntos registrados)".<br>**Sin recorrido**: se ven los dos marcadores y **ninguna línea**, con una nota que dice que no hay dato real y que por eso no se dibuja una ruta inventada.<br>**Sin destino**: solo el marcador de recogida, y la leyenda de abajo dice "Sin destino registrado". |
| **Verificación técnica** | En la red, el detalle (`GET /viajes/{id}` o `GET /viajes/historial-global/{id}`) trae `traza`; la **lista** (`GET /viajes`) trae `traza: null` en todas las filas — la traza nunca viaja en un listado. |
| **Limitación conocida** | Un viaje con **un solo punto** de traza se muestra como "sin traza": con un punto no se puede trazar una línea. El texto dice "no dejó traza GPS", que es impreciso para ese caso. No marcar como fallo. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

### PD-10 — Documentación del socio de punta a punta

| Campo | Contenido |
|---|---|
| **Precondición** | Haber completado PD-02 (existe un socio aprobado con sus 2 documentos). |
| **Pasos** | 1. `web-interno` (Admin Sistema) → "Usuarios" → buscar al socio → "Ver" → mirar el bloque "Estado documental del socio".<br>2. `web-interno` (Staff Verificación) → "Cumplimiento" → "Ejecutar control de vigencia" y anotar el número de "Revisados".<br>3. `web-conductor`, entrando como ese socio → "Mis documentos". |
| **Resultado esperado** | Los 2 documentos aparecen en las 3 pantallas con la misma fecha de caducidad y el mismo semáforo. El contador de "Revisados" del control de vigencia **sube exactamente en 2** respecto de una corrida anterior: los documentos de una postulación entran solos al barrido diario. |
| **Verificación de la advertencia** | Cambiando la fecha de caducidad a una pasada, aparece un aviso rojo tanto en "Mis documentos" del conductor como en la ficha de Usuarios — y **ninguna acción queda bloqueada**: el bloqueo por documentación vencida es una decisión pendiente de la cooperativa, no está activado. |
| Resultado | ☐ Aprobado ☐ Fallido |
| Observaciones | |

---

## 3. Pruebas funcionales para usuarios sin conocimiento técnico

Estas pruebas están escritas para ejecutarse **sin ayuda y sin saber programar**. Si en algún paso
no encuentra lo que el texto describe, eso ya es un resultado: márquelo como fallido y anote qué vio.

> Diferencia con la parte 4: **aquí sí se le dice a la persona dónde pulsar.** Lo que se comprueba
> es que el sistema responde como el texto promete. En la parte 4 se hace lo contrario: no se le
> dice nada y se observa si lo encuentra sola.

### PU-01 — Pedir un taxi de principio a fin

**Qué vamos a comprobar:** que una persona puede pedir un taxi y que el conductor lo recibe.

**Necesita:** dos ventanas del navegador abiertas al mismo tiempo.

1. En la primera ventana entre a `http://localhost:5174` (la del conductor) e inicie sesión con
   el teléfono `+593980010` y la contraseña `UsuarioDemo123!`.
2. Pulse **"Iniciar turno"**. Si el navegador le pide permiso para conocer su ubicación, acéptelo.
   Debe aparecer un mapa y el texto "Posición reportada" con la hora.
3. En la segunda ventana entre a `http://localhost:5173` (la del pasajero) e inicie sesión con
   el teléfono `+593980018` y la contraseña `UsuarioDemo123!`.
4. Toque cualquier punto del mapa: ahí quiere ir. Debe aparecer la distancia, la duración y el
   precio aproximado.
5. Pulse **"Solicitar taxi"**.
6. Vuelva a la ventana del conductor: debe aparecer un aviso de viaje nuevo. Pulse **"Aceptar"**.
7. En la misma ventana del conductor pulse, uno tras otro: **"Voy en camino"**, **"He llegado"**,
   **"Iniciar viaje"**.
8. Mire la ventana del pasajero: el texto va cambiando solo, sin que usted toque nada.
9. En la ventana del conductor pulse **"Finalizar viaje"**.

**Lo que debe pasar:** las dos ventanas muestran el precio final separado por partes (lo que se
cobra por arrancar, por la distancia y por el tiempo de espera). Si el viaje fue muy corto, aparece
además una línea que dice "Carrera mínima aplicada".

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-02 — Cobrar el viaje y calificar

**Qué vamos a comprobar:** que se registra el cobro y que ambas personas pueden calificarse.

*(Continúa donde terminó la prueba anterior.)*

1. En la ventana del conductor, escriba en el recuadro el mismo monto que muestra el precio final
   (por ejemplo `1.75`).
2. Pulse **"Confirmar pago recibido"**.
3. Aparecen cinco estrellas. Elija las que quiera y pulse **"Enviar calificación"**.
4. Vaya a la ventana del pasajero y haga lo mismo.
5. En cualquiera de las dos ventanas, entre a **"Mis viajes"** en el menú de la izquierda.

**Lo que debe pasar:** el viaje que acaba de hacer aparece **el primero de la lista**, con el precio
y la calificación que puso.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-03 — Inscribirse como conductor, con documentos, y ser aprobado

**Qué vamos a comprobar:** que una persona nueva puede postularse adjuntando su licencia y la
matrícula, y que la cooperativa las revisa antes de aprobarla.

**Necesita:** dos fotos cualesquiera en su computadora (JPG o PNG, menos de 5 MB cada una).

1. Entre a `http://localhost:5174` y pulse **"¿Eres postulante nuevo? Postula aquí"**.
2. Complete todos los datos. Use un número de teléfono, una cédula y una placa que no haya usado
   antes (invente valores distintos a los de otras pruebas). La contraseña debe tener al menos
   8 letras o números.
3. Más abajo, en **"Documentos"**, adjunte una foto para la **licencia de conducir** y otra para la
   **matrícula del vehículo**, y escriba la fecha de caducidad de cada una.
4. Pulse **"Enviar solicitud"**. Debe aparecer un mensaje de que la solicitud fue enviada.
5. Abra otra ventana en `http://localhost:5175` e inicie sesión con `+593900000001` y
   `VerifDash123!`.
6. En el menú de la izquierda entre a **"Solicitudes"**. La solicitud que acaba de crear debe estar
   **la primera de la lista**.
7. Pulse **"Ver"** en esa fila. Debe ver **las dos fotos que subió**, cada una con su fecha de
   caducidad y una etiqueta que dice si está vigente.
8. Pulse **"Tomar"**, luego **"Aprobar"** y por último **"Aceptar decisión"**.

**Lo que debe pasar:** la solicitud queda como "APROBADA". La persona ya puede entrar a
`http://localhost:5174` con el teléfono y la contraseña que puso al inscribirse, y en
**"Mis documentos"** ve la licencia y la matrícula que subió.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-04 — Llevar un vehículo al taller

**Qué vamos a comprobar:** que se puede registrar y seguir una reparación.

1. Entre a `http://localhost:5175` con `+593900000001` y `VerifDash123!`.
2. En el menú entre a **"Mantenimiento"**.
3. Pulse **"Nuevo"**. Escriba una placa en el recuadro de búsqueda (por ejemplo `DEM`) y pulse
   **"Buscar"**. Elija un vehículo de la lista.
4. Complete el kilometraje, elija un taller y una fecha, y pulse **"Crear orden"**.
5. Busque la orden que creó en la lista y pulse **"Ver"**.
6. Pulse **"En taller"**. Después pulse **"Esperar repuesto"**, escriba un motivo y confirme.
7. Pulse **"Reanudar"** y luego **"Cerrar"**. Complete lo que se pide (qué se hizo, cuánto costó,
   horas de taller, kilometraje de salida).

**Lo que debe pasar:** al cerrar aparece un mensaje que dice cuándo toca el próximo mantenimiento
y cuánto se pasó (o se ahorró) respecto de lo estimado.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-05 — Reportar que el vehículo falló

**Qué vamos a comprobar:** que un conductor puede avisar de una avería y que la cooperativa la recibe.

1. Entre a `http://localhost:5174` con `+593980010` y `UsuarioDemo123!`.
2. En el menú entre a **"Fallas del vehículo"** y pulse **"Reportar una falla"**.
3. Elija un tipo de falla de la lista, escriba qué pasó y, si quiere, adjunte una foto.
4. Pulse **"Enviar reporte"**.
5. Ahora entre a `http://localhost:5175` con `+593900000001` y `VerifDash123!`, vaya a
   **"Mantenimiento"** y pulse la pestaña **"Reportes de falla"**.

**Lo que debe pasar:** el reporte que acaba de enviar aparece en la lista, con la foto si la puso.
Desde ahí se puede convertir en una orden de taller o descartarlo explicando por qué.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-06 — Cambiar cómo se ve el sistema

**Qué vamos a comprobar:** que cada persona puede ajustar el sistema a su gusto y que se le queda guardado.

1. Entre a cualquiera de los tres portales con cualquiera de las cuentas de prueba.
2. En el menú entre a **"Ajustes"**.
3. Cambie **"Tema"** a *Oscuro*. La pantalla debe oscurecerse al instante.
4. Cambie **"Tamaño de texto"** a *Muy grande*. Las letras deben crecer al instante.
5. Pulse **"Cambiar foto"** y elija una imagen suya. Debe aparecer arriba a la derecha enseguida.
6. Recargue la página (tecla F5).
7. Cierre sesión y entre con **otra** cuenta distinta.

**Lo que debe pasar:** al recargar, sus ajustes siguen puestos. Al entrar con otra cuenta, esa otra
cuenta tiene **sus propios** ajustes: lo que usted cambió no le afectó.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-07 — Marcar las secciones que más usa

**Qué vamos a comprobar:** que se puede tener a mano lo que uno usa todos los días.
*(Solo aplica al portal interno, `http://localhost:5175`.)*

1. Entre con `+593900000099` y `AdminSistema123!`.
2. En el menú de la izquierda, pase el cursor por cualquier sección: al lado del nombre hay una
   **estrella vacía (☆)**.
3. Pulse la estrella de dos o tres secciones que le interesen.
4. Recargue la página (F5).

**Lo que debe pasar:** aparece un grupo nuevo llamado **"FAVORITOS"** arriba de todo el menú, con
las secciones que marcó. Esas secciones **siguen también en su grupo original** (no se mueven de
sitio, solo se suman arriba). Tras recargar, sus favoritos siguen ahí.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-08 — Dar de baja a una persona

**Qué vamos a comprobar:** que al dar de baja a alguien deja de poder entrar, pero no se pierde su historial.

1. Entre a `http://localhost:5175` con `+593900000099` y `AdminSistema123!`.
2. Vaya a **"Usuarios"** y pulse **"Nuevo"**. Cree una cuenta de prueba con un nombre y teléfono
   inventados y una contraseña de al menos 8 caracteres. Elija cualquier rol.
3. Busque esa cuenta, pulse **"Ver"** y luego **"Dar de baja"**.
4. **Lea el aviso que aparece antes de confirmar.**
5. Escriba un motivo y pulse **"Confirmar baja"**.
6. Abra otra ventana e intente entrar con el teléfono y contraseña de esa cuenta.
7. Vuelva al portal interno, y en el filtro **"Estado"** elija *Baja*.

**Lo que debe pasar:** antes de confirmar, el sistema le explica qué va a pasar. Después, esa
persona **no puede entrar** (aparece "Credenciales inválidas"), pero **su ficha sigue existiendo**
con el estado "BAJA" y el motivo que usted escribió. No se borró nada.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

### PU-09 — Ver por dónde pasó un viaje

**Qué vamos a comprobar:** que se puede ver en un mapa el recorrido de un viaje que ya terminó, y
que el sistema avisa cuando ese dato no existe en vez de dibujar algo inventado.

1. Entre a `http://localhost:5173` con `+593980018` y `UsuarioDemo123!`.
2. En el menú entre a **"Mis viajes"**.
3. Busque la fila del **17 de agosto de 2026 a las 03:44**, cuyo destino es *El Paseo Shopping*, y
   pulse **"Ver"**.
4. Mire el mapa y lea la frase que aparece justo debajo.
5. Cierre y ahora abra el viaje del **23 de agosto de 2026 a las 15:15** ("Origen QA icono
   conductor"), que no llegó a tener conductor.
6. Mire otra vez el mapa y lea la frase de abajo.

**Lo que debe pasar:** en el primero se dibuja una línea de color siguiendo el camino que hizo el
auto, y abajo dice cuántos puntos de recorrido se registraron. En el segundo **no hay ninguna
línea**, solo los dos puntos de inicio y fin, y una frase que explica que ese viaje no dejó
recorrido registrado y que por eso no se dibuja una ruta inventada.

☐ Todo salió como dice el texto ☐ Algo no salió así

**¿Qué vio?** _______________________________________________

---

## 4. Pruebas de usabilidad basadas en tareas reales

### 4.1 Por qué esta parte es distinta

Las partes 2 y 3 responden *"¿el sistema hace lo que promete?"*. Esta parte responde otra pregunta:
***"¿una persona que nunca lo vio puede hacer su trabajo con él?"***.

Por eso aquí **no se dan instrucciones de dónde pulsar**. Se plantea una tarea como se la
plantearía la vida real ("necesitás llegar al hospital, conseguí un taxi") y se observa qué hace la
persona. Un botón puede funcionar perfectamente y aun así la prueba falla, porque nadie lo
encuentra. Ese es exactamente el defecto que esta sección busca.

### 4.2 Cómo se ejecuta cada escenario

Hacen falta **dos personas**: quien prueba y quien observa. Quien observa **no ayuda**, solo anota.

1. **Preparar.** Quien observa deja el portal abierto en la pantalla de inicio de sesión y entrega
   solo las credenciales. Nada más: ni el nombre de la sección, ni dónde está el botón.
2. **Predecir.** Antes de tocar nada, quien observa lee el escenario en voz alta y pregunta:
   *"¿en qué opción del menú harías clic primero para lograr esto?"*. Se anota la respuesta **antes**
   de que empiece. Esto mide si la navegación se entiende **antes** de aprenderla por prueba y error;
   una vez que la persona explora, ese dato ya no se puede recuperar.
3. **Observar en silencio.** Quien prueba trabaja sola. Quien observa cronometra y anota:
   - ¿En qué pantalla se detuvo a leer o dudó?
   - ¿Entró a alguna sección equivocada antes de la correcta? ¿A cuál?
   - ¿Tuvo que volver atrás? ¿Cuántas veces?
   - ¿Preguntó algo, o buscó ayuda fuera del sistema?
   - ¿Dijo en voz alta algo del tipo "¿y ahora qué?" o "¿esto qué significa?"? Anotar la frase textual.
4. **Cerrar.** Al terminar (o al rendirse), quien observa pregunta: *"¿qué te resultó más confuso?"*
   y anota la respuesta con las palabras de la persona.
5. **Calificar** con tres niveles, nunca dos:

| Nivel | Cuándo se marca |
|---|---|
| **Lo logró sin ayuda** | Cumplió el criterio de éxito por su cuenta, sin entrar a secciones equivocadas ni preguntar |
| **Lo logró con dificultad** | Terminó la tarea, pero se perdió, tuvo que volver atrás, entró a la sección equivocada o dudó de forma visible. **Obligatorio anotar dónde y por qué** |
| **No lo logró** | Se rindió, hizo algo distinto de lo pedido, o necesitó que alguien le dijera dónde estaba la opción |

> Una tarea completada tras entrar a tres secciones equivocadas **no es "aprobado"**. Es "logró con
> dificultad", y la causa concreta es el hallazgo valioso de la prueba.

### 4.3 Los 10 criterios que se observan

No hace falta una pregunta por criterio en cada tarea. Cada escenario está diseñado para que estos
10 se puedan observar; al final de la sección hay una grilla para consolidarlos.

| # | Criterio | Se observa sobre todo en |
|---|---|---|
| 1 | Intuitividad general | La predicción del paso 2 |
| 2 | Facilidad para encontrar opciones | Cuántas secciones equivocadas visitó |
| 3 | Navegación sin perderse | Cuántas veces volvió atrás |
| 4 | Claridad de la organización de los menús | Si el grupo del menú donde buscó fue el correcto |
| 5 | Claridad de nombres de botones, opciones y formularios | Las frases textuales de duda que anotó el observador |
| 6 | Autonomía sin instrucciones constantes | Si preguntó, y cuántas veces |
| 7 | Pasos innecesarios | Si hizo algo que después resultó no hacer falta, o si el sistema le exigió un paso que no esperaba |
| 8 | Comprensión de mensajes y estados | Si supo decir qué estaba pasando cuando la pantalla cambió sola |
| 9 | Claridad de qué hacer en cada pantalla | Las pausas largas sin tocar nada |
| 10 | Fluidez sin confusión | El tiempo total contra el criterio de éxito |

---

### TU-01 — Pasajero: conseguir un taxi por primera vez, hasta calificar

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien que nunca usó el sistema. No hace falta que sepa de tecnología. |
| **Preparación** | Dos ventanas: la del pasajero (`http://localhost:5173`) para quien prueba, y la del conductor (`http://localhost:5174`, ya con turno iniciado por el observador) fuera de su vista. Entregar solo: teléfono `+593980018`, contraseña `UsuarioDemo123!`. |
| **Escenario (leer tal cual)** | *"Estás en la calle y necesitás llegar a otro punto de la ciudad. Tenés esta aplicación en el teléfono y una cuenta ya creada. Conseguí un taxi, hacé el viaje, y al final dejale una opinión al conductor. Nadie te va a explicar cómo — hacelo como lo harías si acabaras de instalarla."* |
| **Predicción previa** | *"Sin tocar nada todavía: ¿qué harías primero para pedir el taxi?"* Anotar textual. |
| **Criterio de éxito** | El viaje queda solicitado y el pasajero **entiende** que el sistema está buscando conductor, en menos de **2 minutos** desde que inicia sesión, sin salir de la pantalla inicial más de una vez. Y al terminar el viaje, envía una calificación **sin que se le diga que existe esa opción**. |
| **Qué observar en particular** | ¿Entiende que **tocar el mapa** es la forma de elegir el destino, o busca un campo de texto para escribirlo? ¿Interpreta bien "Buscando conductor…"? Cuando el conductor acepta y la pantalla cambia sola, ¿sabe decir qué pasó? Al finalizar, ¿encuentra las estrellas o cierra la pantalla antes de calificar? |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **Si hubo dificultad, ¿dónde y por qué?** | |
| **Frases textuales de duda** | |
| **Tiempo hasta "Solicitar taxi"** | ______ | 

---

### TU-02 — Pasajero: cancelar una solicitud y volver a intentarlo

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Puede ser la misma persona de TU-01, ya con algo de experiencia. |
| **Preparación** | Ventana del pasajero. El conductor **no** debe tener turno iniciado, para que la solicitud se quede buscando. |
| **Escenario (leer tal cual)** | *"Pediste un taxi pero te avisaron que ya te pasan a buscar por otro lado, así que ya no lo necesitás. Cancelá la solicitud. Al rato cambian los planes otra vez y sí lo necesitás: volvé a pedirlo."* |
| **Predicción previa** | *"¿Dónde creés que está la opción para cancelar?"* |
| **Criterio de éxito** | Cancela la solicitud eligiendo un motivo, y después consigue dejar una solicitud nueva activa. Sin ayuda y sin recargar la página. |
| **Qué observar en particular** | El sistema **exige elegir un motivo** antes de dejar confirmar: ¿le resulta razonable o lo vive como un obstáculo? ¿Encuentra la opción "Otro" si ningún motivo de la lista le sirve? Para volver a pedir, ¿entiende que tiene que empezar de cero, o busca un botón de "repetir"? |
| **Variante recomendada** | Si la solicitud llega a agotar la búsqueda y queda **sin conductor**, observar si descubre el botón **"Reintentar búsqueda"** por su cuenta. Ese botón reusa el mismo origen y destino: ¿lo entiende, o vuelve a fijar el destino a mano? |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **Si hubo dificultad, ¿dónde y por qué?** | |
| **Frases textuales de duda** | |

---

### TU-03 — Pasajero: encontrar un viaje concreto en su historial

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien que ya hizo TU-01, o alguien nuevo (ambos casos son informativos). |
| **Preparación** | Cuenta Ryan White (`+593980018`), que tiene 16 viajes repartidos en 2 páginas. |
| **Escenario (leer tal cual)** | *"Necesitás saber cuánto pagaste por el viaje que hiciste al Paseo Shopping. Fue hace unos días. Averigualo."* |
| **Predicción previa** | *"¿Por dónde empezarías a buscarlo?"* |
| **Criterio de éxito** | Encuentra la fila del **17/8/2026 03:44** con destino *El Paseo Shopping* y dice el monto correcto, en menos de **90 segundos**. |
| **Qué observar en particular** | **Este escenario está diseñado para exponer una fricción concreta**: el historial del pasajero solo se puede filtrar por *estado* y por *rango de fechas* — **no hay búsqueda por destino ni por texto**. ¿La persona busca una lupa o un campo de búsqueda y no lo encuentra? ¿Recurre a pasar páginas a mano? ¿Se le ocurre usar el filtro de fechas? Anotar cuál de los tres caminos toma y cuánto tarda. |
| **Observación adicional** | Con el viaje abierto, preguntar: *"¿qué te está mostrando este mapa?"*. Se busca que diga algo como "por dónde fue el auto" y no "dónde queda el destino". |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **Si hubo dificultad, ¿dónde y por qué?** | |
| **¿Buscó un campo de búsqueda que no existe?** | ☐ Sí ☐ No |

---

### TU-04 — Conductor: un turno completo, de iniciar a cobrar

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien que nunca vio el portal del conductor. |
| **Preparación** | Ventana del conductor (`http://localhost:5174`) con `+593980010` / `UsuarioDemo123!`. El observador maneja la ventana del pasajero, fuera de su vista, para generar la solicitud cuando corresponda. |
| **Escenario (leer tal cual)** | *"Sos socio conductor de la cooperativa y hoy empezás tu jornada. Ponete disponible para recibir viajes, tomá el que te llegue, llevá al pasajero, y cobrale al final. Nadie te va a ir indicando los pasos."* |
| **Predicción previa** | *"¿Qué harías primero para empezar a recibir viajes?"* |
| **Criterio de éxito** | Completa la secuencia **iniciar turno → aceptar la oferta → en camino → llegada → iniciar viaje → finalizar → registrar el cobro**, sin que se le indique ningún botón. Se acepta que pregunte **una** vez; dos o más preguntas ya es "con dificultad". |
| **Qué observar en particular** | ¿Entiende que hay que **iniciar turno** antes de recibir ofertas, o espera que lleguen solas? ¿La oferta entrante se ve lo suficiente, o hay que avisarle que llegó? La secuencia de 3 botones seguidos ("Voy en camino" → "He llegado" → "Iniciar viaje") es el punto más denso del flujo: ¿duda en alguno? Al cobrar, ¿entiende que debe escribir el monto que efectivamente recibió y no otro? |
| **Nota para el observador** | La oferta entrante expira a los **20 segundos** (valor por defecto, configurable en Administración → Parámetros globales). Para alguien que ve la pantalla por primera vez ese margen es muy ajustado: es **muy probable** que se le venza mientras lee. Eso **es un hallazgo válido, no un error de la prueba** — anotarlo y volver a generar la solicitud. Si se quiere medir el resto del flujo sin este obstáculo, subir el valor a 60 s antes de empezar y dejarlo anotado. |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **Si hubo dificultad, ¿dónde y por qué?** | |
| **¿Se le venció alguna oferta por dudar?** | ☐ Sí ☐ No |

---

### TU-05 — Conductor: reportar una falla del vehículo

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien que ya hizo TU-04 (conoce el portal, pero nunca usó esta función). |
| **Preparación** | Ventana del conductor, sesión iniciada, **sin viaje en curso**. |
| **Escenario (leer tal cual)** | *"Terminaste tu último viaje y notás que el auto hace un ruido raro en el motor. Querés dejar constancia en la cooperativa para que lo revisen. Hacelo."* |
| **Predicción previa** | **Este es el dato más importante de este escenario.** Preguntar: *"¿en qué opción del menú harías clic para avisar de esto?"* y anotar la respuesta textual **antes** de que toque nada. |
| **Criterio de éxito** | Llega a **"Fallas del vehículo" → "Reportar una falla"**, elige un tipo, describe el problema y lo envía, **en el primer intento de navegación**. |
| **Por qué existe este escenario** | Esta función **se movió de sitio hace poco**: antes era un botón suelto dentro de la pantalla del viaje, y ahora tiene su propia sección en el menú. La predicción de arriba mide directamente **si ese cambio fue acertado**. Si la mayoría de las personas predice "Mi turno" o busca dentro del viaje, la reubicación no funcionó. |
| **Qué observar en particular** | ¿Busca primero dentro de "Mi turno"? ¿Confunde "Fallas del vehículo" con "Mis documentos"? El formulario pide elegir un **tipo de falla de una lista cerrada**: ¿encuentra uno que le sirva para "ruido en el motor", o se traba buscando una opción libre? |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **Predicción textual** | |
| **¿La predicción coincidió con el camino real?** | ☐ Sí ☐ No |
| **Si hubo dificultad, ¿dónde y por qué?** | |

---

### TU-06 — Mantenimiento: convertir una falla reportada en una orden de taller

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien con perfil administrativo, sin conocimiento previo del sistema. |
| **Preparación** | `http://localhost:5175` con `+593900000001` / `VerifDash123!`. En el entorno ya hay **3 reportes pendientes sobre la placa FIC-0010**. |
| **Escenario (leer tal cual)** | *"Sos el jefe de mantenimiento de la cooperativa. Un conductor reportó que su auto tiene una avería mecánica. Tu trabajo es abrir la orden de taller que corresponde a ese reporte, para que el mecánico sepa qué hacer."* |
| **Predicción previa** | *"¿Dónde creés que vas a encontrar el reporte que hizo el conductor?"* |
| **Criterio de éxito** | Localiza el reporte de avería mecánica de **FIC-0010** y lo convierte en orden **desde el propio reporte**, completando kilometraje, taller y fecha. En menos de **4 minutos**. |
| **Qué observar en particular** | **Punto crítico de este escenario**: la sección "Mantenimiento" tiene **tres pestañas** (Órdenes / Reportes de falla / Vehículos) y abre en "Órdenes" por defecto. ¿Descubre las pestañas, o intenta crear la orden desde cero con "Nuevo" sin mirar el reporte? Crear una orden suelta **también funciona**, pero pierde el vínculo con el reporte: si toma ese camino, es **"lo logró con dificultad"**, y hay que anotar que las pestañas no se vieron. |
| **Observación adicional** | Al convertir, el sistema **arrastra solo** el vehículo, el tipo de falla y la descripción. Preguntar después: *"¿notaste que algunos datos ya venían puestos?"*. Si no lo notó, el ahorro de trabajo existe pero es invisible. |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **¿Encontró las pestañas por su cuenta?** | ☐ Sí ☐ No |
| **Si hubo dificultad, ¿dónde y por qué?** | |

---

### TU-07 — Captación: revisar una postulación con documentos y decidir

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien con perfil administrativo, sin conocimiento previo del sistema. |
| **Preparación** | **Ejecutar antes TU-05 o PU-03 para que exista una solicitud con documentos reales**, o crear una desde `web-conductor`. Ver el aviso de 4.5 sobre las solicitudes de ejemplo. Entregar `+593900000001` / `VerifDash123!`. |
| **Escenario (leer tal cual)** | *"Sos quien recibe a los nuevos socios en la cooperativa. Una persona se postuló para trabajar como conductor y adjuntó su licencia y la matrícula del auto. Revisá si la documentación está en orden y tomá la decisión que corresponda: aceptarla, o devolverla con una observación si algo no está bien."* |
| **Predicción previa** | *"¿En qué parte del menú buscarías las postulaciones?"* |
| **Criterio de éxito** | Abre la solicitud, **mira las dos imágenes** y sus fechas de caducidad, y deja la solicitud en un estado final coherente (`APROBADA` u `OBSERVADA` con un motivo escrito). |
| **Qué observar en particular** | **Fricción conocida y esperada aquí**: una solicitud recién enviada está en estado `ENVIADA` y **solo ofrece el botón "Tomar"** — los botones de decisión no aparecen hasta pulsarlo. Es intencional (refleja "me hago cargo de esta revisión"), pero es un paso que nadie predice. Observar: ¿busca "Aprobar" y no lo encuentra? ¿Cuánto tarda en probar "Tomar"? ¿Entiende qué significa esa palabra en este contexto? |
| **Observación adicional** | Preguntar señalando el semáforo de vigencia: *"¿qué te dice esta etiqueta sobre el documento?"*. Se busca que distinga *vigente* / *por vencer* / *vencido* sin ayuda. |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **¿Encontró "Tomar" sin ayuda?** | ☐ Sí ☐ No ☐ Lo encontró pero no entendió la palabra |
| **Si hubo dificultad, ¿dónde y por qué?** | |

---

### TU-08 — Gerencia: entender un indicador estratégico, no solo encontrarlo

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien con perfil directivo o docente. **No** debe haber visto antes los tableros. |
| **Preparación** | `http://localhost:5175` con `+593900000010` / `Gerencia123!`. Nada más. |
| **Escenario (leer tal cual)** | *"Sos parte de la gerencia de la cooperativa y entrás al sistema por primera vez. Te preguntan en una reunión cómo está la cooperativa respecto del cumplimiento de la documentación legal de sus socios y vehículos. Buscá ese dato y explicá con tus palabras qué significa."* |
| **Predicción previa** | *"¿Por dónde empezarías a buscar un dato de ese tipo?"* |
| **Criterio de éxito — dos partes** | **(a) Navegación:** llega al panel de *Cumplimiento Normativo* (o al Tablero Ejecutivo y desde ahí baja al detalle) en menos de **3 minutos**.<br>**(b) Comprensión — lo importante:** explica **con sus propias palabras** que alrededor de la **mitad** de los documentos está vigente, que hay **decenas vencidos**, y que **la licencia de conducir es el tipo más expuesto**. No hace falta que use los términos exactos. |
| **Valores reales en el entorno** | Documentación vigente **51,9 %** · documentos vencidos **77** · tipo más expuesto **Licencia de conducir** (45 % vigente, 44 vencidos de 80). Si los números difieren, es porque el proceso de datos volvió a correr: lo que se evalúa es la explicación, no la cifra exacta. |
| **Qué observar en particular** | ¿Entra primero al Tablero Ejecutivo o va directo al panel? ¿Distingue el grupo "Panel Estratégico" del "Panel Táctico" en el menú? Al ver un porcentaje, ¿sabe decir **de qué** es porcentaje? ¿Interpreta bien la variación (que bajó 2,33 puntos respecto del corte anterior) o la lee como "bajó un 2 %"? Descubre por su cuenta que **se puede pulsar la tarjeta del indicador** para ver la lista de documentos vencidos? |
| **Alternativa** | Si se prefiere otro indicador, usar **Confiabilidad del servicio** (91,3 % de flota activa). **No usar "Rentabilidad"**: ver el aviso en 4.5. |
| **Resultado navegación** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **Resultado comprensión** | ☐ Lo explicó correctamente ☐ Lo explicó a medias ☐ No supo qué significaba |
| **Explicación textual de la persona** | |

---

### TU-09 — Personal interno: reconstruir qué pasó en un viaje reclamado

| Campo | Contenido |
|---|---|
| **Perfil de quien prueba** | Alguien con perfil administrativo, sin conocimiento previo. |
| **Preparación** | `http://localhost:5175` con `+593900000001` / `VerifDash123!`. |
| **Escenario (leer tal cual)** | *"Un pasajero llamó a reclamar por un viaje que hizo hace unos días: dice que el conductor dio muchas vueltas. El viaje lo hizo una pasajera de apellido Slice1. Averiguá qué pasó en ese viaje y contame qué ves."* |
| **Predicción previa** | *"¿En qué sección buscarías un viaje de otra persona?"* |
| **Criterio de éxito** | Encuentra el historial global, localiza el viaje de *Pasajera Slice1* del **30/7/2026 02:51**, lo abre y **se da cuenta por su cuenta de que ese viaje no tiene destino registrado**, sin que nadie se lo diga. |
| **Qué observar en particular** | Este escenario prueba una situación de dato incompleto, que es donde un sistema honesto se distingue de uno que disimula. ¿Lee la leyenda "Sin destino registrado" y la interpreta bien, o asume que el mapa está roto? ¿Entiende que la línea del mapa es el recorrido real y no una ruta sugerida? Anotar si dice algo del tipo *"esto está fallando"* — sería señal de que el estado se comunica mal. |
| **Resultado** | ☐ Lo logró sin ayuda ☐ Lo logró con dificultad ☐ No lo logró |
| **¿Interpretó bien el dato faltante?** | ☐ Sí ☐ Creyó que era un error del sistema |
| **Si hubo dificultad, ¿dónde y por qué?** | |

---

### 4.4 Comprobaciones puntuales (complemento, no reemplazo)

Estas sí son verificaciones de un comportamiento concreto. Son rápidas y conviene correrlas
**después** de los escenarios de tarea, nunca antes: si quien prueba ya recorrió el menú haciendo
estas comprobaciones, la predicción de los escenarios queda contaminada.

| # | Qué se comprueba | Cómo | Esperado | Resultado |
|---|---|---|---|---|
| PUS-01 | Llegar a cualquier función desde cualquier pantalla | Desde una sección cualquiera, ir a otras 5 usando solo el menú lateral | Ninguna requiere volver atrás ni recargar; el menú está siempre visible | ☐ OK ☐ Falla |
| PUS-02 | Saber siempre dónde se está | Recorrer 5 secciones mirando el encabezado y el menú | El título del encabezado coincide con la sección, y la del menú está resaltada con una marca de color | ☐ OK ☐ Falla |
| PUS-03 | Distinguir los 3 niveles organizacionales | Entrar con `+593900000001` y mirar el menú | Los grupos "Panel Táctico" y "Panel Estratégico" se distinguen entre sí y del operativo, no solo por el texto | ☐ OK ☐ Falla |
| PUS-04 | Bajar del resumen al detalle | En el Tablero Ejecutivo (cuenta `gerencia`), pulsar "Ver detalle" en una tarjeta | Lleva al tablero completo de esa área sin recargar la página | ☐ OK ☐ Falla |
| PUS-05 | Ver el detalle de una cifra | En un tablero táctico, pulsar sobre una tarjeta de indicador que diga "Ver detalle →" | Se abre la lista de registros **en la misma pantalla**, sin perder dónde se estaba | ☐ OK ☐ Falla |
| PUS-06 | Uso con teclado | Recorrer una pantalla usando solo la tecla Tab | Se ve **siempre** un recuadro de foco alrededor del elemento activo, incluido dentro del menú lateral oscuro | ☐ OK ☐ Falla |
| PUS-07 | Menú en pantalla angosta | Reducir la ventana a menos de 900 px de ancho | Aparece el botón ☰ y el menú se abre y cierra correctamente | ☐ OK ☐ Falla |
| PUS-08 | Aviso antes de una acción irreversible | Iniciar la anonimización de una cuenta (Gobernanza de datos) | Exige escribir la palabra **ANONIMIZAR** exacta; no basta con pulsar un botón | ☐ OK ☐ Falla |
| PUS-09 | Motivo obligatorio en decisiones graves | Intentar rechazar una solicitud, observar una liquidación, descartar un reporte, cancelar un viaje o dar de baja una cuenta, dejando el motivo vacío | El botón de confirmar está **deshabilitado** hasta escribir o elegir un motivo | ☐ OK ☐ Falla |
| PUS-10 | Avisar antes de dar de baja | Pulsar "Dar de baja" en una cuenta | Antes de confirmar se explica qué pasa con el historial y con un vehículo habilitado a su nombre | ☐ OK ☐ Falla |
| PUS-11 | Bloquear lo que no debe hacerse | Intentar dar de baja a una cuenta con un viaje en curso | Se rechaza con un mensaje que dice **qué viaje** hay que cerrar primero, no un error genérico | ☐ OK ☐ Falla |
| PUS-12 | Botones que no aplican, explicados | Pasar el cursor por un botón "Eliminar" o "Nuevo" que esté apagado | Muestra un texto que explica **por qué** no aplica (ej. "las cuentas no se eliminan, se suspenden o se dan de baja") | ☐ OK ☐ Falla |
| PUS-13 | Errores comprensibles | Guardar un formulario con un número fuera de rango (ej. un umbral inválido en Políticas de seguridad) | El mensaje aparece **junto al campo** y en español, no un código técnico | ☐ OK ☐ Falla |
| PUS-14 | No ofrecer opciones retiradas | Desactivar un taller en Catálogos y luego abrir el selector de taller en Mantenimiento | El taller desactivado **ya no se puede elegir**, pero sigue visible en Catálogos para reactivarlo | ☐ OK ☐ Falla |
| PUS-15 | No ofrecer personas dadas de baja | Dar de baja una cuenta y buscarla como destinataria de alertas (Configuración de alertas) | La cuenta dada de baja **no aparece** entre los resultados | ☐ OK ☐ Falla |
| PUS-16 | Legibilidad ajustable | Poner "Tamaño de texto" en *Muy grande* y recorrer 3 pantallas con tablas | Todo el texto crece de forma proporcional; nada se superpone ni queda cortado | ☐ OK ☐ Falla |
| PUS-17 | El sistema no inventa datos | Abrir un viaje sin recorrido registrado (tabla 1.6) | Muestra los dos puntos y **explica** que no hay recorrido real, en vez de unir origen y destino con una línea que parecería la ruta | ☐ OK ☐ Falla |
| PUS-18 | Advertir sin bloquear | Ver un socio con documentación vencida, en "Usuarios" y en "Mis documentos" del propio conductor | Aparece un aviso rojo que además **dice explícitamente que no se bloquea ninguna operación** por ese motivo | ☐ OK ☐ Falla |

### 4.5 Limitaciones conocidas — NO son fallos de estas pruebas

Estos puntos ya están documentados y **no deben marcarse como fallidos**; se listan para que quien
pruebe no pierda tiempo investigándolos, y para que quien observa no los confunda con un problema
de usabilidad real.

| Punto | Estado real |
|---|---|
| **Las solicitudes de postulación de ejemplo muestran "No se pudo cargar la foto"** | Las 68 solicitudes pendientes del entorno vienen de una siembra que guardó rutas de archivo de ejemplo, no imágenes reales. El bloque de documentos, las fechas y el semáforo de vigencia **sí son correctos**. Para ver imágenes de verdad hay que crear una postulación nueva desde `web-conductor`, o abrir la cédula `0977700077`, que ya está aprobada. |
| **El indicador "Rentabilidad" muestra valores negativos enormes** | Es una consecuencia real de los datos de demostración, no un defecto de cálculo: hay ~130 órdenes de mantenimiento sembradas con costos reales, pero casi ningún viaje cobrado en el mes en curso (los 1,3 millones de viajes históricos son de 2021 y no generan cobros). Costo alto ÷ ingreso casi nulo = margen muy negativo. **No usar este indicador para la tarea TU-08.** |
| Un viaje con **un solo punto** de recorrido se muestra como "sin traza" | Con un punto no se puede dibujar una línea. El texto dice "no dejó traza GPS", que es impreciso para ese caso concreto. Pendiente de ajuste de redacción. |
| Los modales no se cierran con la tecla Escape ni atrapan el foco dentro | Gap conocido de accesibilidad, documentado en la auditoría de diseño. Pendiente, no roto. |
| "Cerrar sesión" no pide confirmación | No hay confirmación en ningún punto del sistema para esta acción. Documentado. |
| La bandeja "renovaciones pendientes" de Cumplimiento **ya no está siempre vacía** | Corrección respecto de versiones anteriores de este plan: el conductor sí puede subir una renovación desde "Mis documentos", y en el entorno hay **1 renovación pendiente real** para revisar. Solo se puede renovar un documento que ya exista, no crear uno nuevo desde ahí. |
| Ya no existen los KPIs "Crecimiento de demanda" (Crecimiento estratégico), "Avance de capacitación" (Capacidades y Plataforma estratégico, Plataforma táctico) ni "% de errores" (Auditoría táctico) | Corrección respecto de versiones anteriores de este plan: se quitaron de la interfaz — el último en la segunda pasada de correcciones de agosto 2026 — nunca tuvieron dato real disponible. Si un escenario de prueba anterior los menciona, ya no aplican. |
| "Tasa de cancelación" (Despacho táctico y Confiabilidad estratégico) ahora muestra un porcentaje real | Corrección respecto de versiones anteriores de este plan: el cálculo de origen tenía un defecto que la hacía mostrar siempre 100% (o "—"). Corregido en la ronda de agosto 2026 — el número que se ve hoy es real, verificado contra un conteo manual directo en Mongo. |
| La funcionalidad de zonas de despacho ya no existe en el sistema | Corrección respecto de versiones anteriores de este plan: antes había un filtro por zona deshabilitado en varios tableros (el dato nunca se resolvía en los viajes) y un catálogo "Zonas" en Administración → Catálogos. Ambos se eliminaron por completo en la segunda pasada de correcciones de agosto 2026 — era una funcionalidad descartada, no un dato faltante temporal. Si un escenario de prueba anterior los menciona, ya no aplican. |
| Los tableros muestran ~270.000 viajes por cada uno de 5 conductores | Es el volumen de prueba cargado para poder demostrar los tableros, no operación real. |
| El historial del pasajero no tiene búsqueda por texto | Solo filtra por estado y por rango de fechas. Es una carencia real (ver TU-03), no un error: no marcarla como fallo funcional, sí anotarla como hallazgo de usabilidad. |

### 4.6 Consolidado de los 10 criterios

Se completa **al terminar todos los escenarios**, mirando las anotaciones en conjunto.

| # | Criterio | Bien | Aceptable | Problemático | Evidencia (qué escenario y qué se observó) |
|---|---|---|---|---|---|
| 1 | Intuitividad general | ☐ | ☐ | ☐ | |
| 2 | Facilidad para encontrar opciones | ☐ | ☐ | ☐ | |
| 3 | Navegación sin perderse | ☐ | ☐ | ☐ | |
| 4 | Organización de los menús | ☐ | ☐ | ☐ | |
| 5 | Claridad de nombres | ☐ | ☐ | ☐ | |
| 6 | Autonomía sin instrucciones | ☐ | ☐ | ☐ | |
| 7 | Pasos innecesarios | ☐ | ☐ | ☐ | |
| 8 | Comprensión de mensajes y estados | ☐ | ☐ | ☐ | |
| 9 | Claridad de qué hacer en cada pantalla | ☐ | ☐ | ☐ | |
| 10 | Fluidez sin confusión | ☐ | ☐ | ☐ | |

**Predicciones acertadas:** ______ de 9 escenarios. *(Es el indicador más directo de si la
navegación se entiende sin aprenderla.)*

---

## 5. Registro de ejecución

| Fecha | Quién ejecutó | Secciones | Aprobados | Fallidos | Observaciones |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

### 5.1 Registro específico de la parte 4

| Fecha | Escenario | Quién probó (perfil) | Quién observó | Predicción acertada | Resultado | Hallazgo principal |
|---|---|---|---|---|---|---|
| | TU-01 | | | ☐ Sí ☐ No | | |
| | TU-02 | | | ☐ Sí ☐ No | | |
| | TU-03 | | | ☐ Sí ☐ No | | |
| | TU-04 | | | ☐ Sí ☐ No | | |
| | TU-05 | | | ☐ Sí ☐ No | | |
| | TU-06 | | | ☐ Sí ☐ No | | |
| | TU-07 | | | ☐ Sí ☐ No | | |
| | TU-08 | | | ☐ Sí ☐ No | | |
| | TU-09 | | | ☐ Sí ☐ No | | |
