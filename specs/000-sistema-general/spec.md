# Especificación general: UrbanFleet TaxiFlow

> **Documento retroactivo.** Describe el sistema tal como existe y funciona hoy, verificado contra
> el código real y contra `AUDITORIA_FUNCIONAL_OPERATIVO.md`, `AUDITORIA_FUNCIONAL_TACTICO.md`,
> `AUDITORIA_FUNCIONAL_ESTRATEGICO.md`, `FUNCIONALIDADES_TRANSVERSALES.md` y `CLAUDE.md` (bitácora
> histórica — verificado contra el código real donde había duda). No es una propuesta de cambio.

## 1. Nombre del sistema

**UrbanFleet TaxiFlow**

## 2. Objetivo general

Sistema de gestión de flota para una **cooperativa de taxis**, 100% web (sin apps nativas), que
cubre el ciclo completo del negocio: captación de socios conductores y pasajeros, despacho y
ejecución de viajes, cobro y liquidación financiera, mantenimiento de vehículos, cumplimiento
documental/regulatorio, e indicadores de gestión en 3 niveles organizacionales (operativo, táctico,
estratégico).

## 3. Contexto

Una cooperativa de taxis necesita coordinar simultáneamente: conductores que trabajan de forma
independiente pero afiliados a una organización común, pasajeros que esperan un servicio confiable,
un parque vehicular que hay que mantener, dinero que hay que cobrar y liquidar de forma justa y
verificable, y obligaciones documentales/legales que hay que vigilar. Sin un sistema centralizado,
cada una de estas funciones se gestiona de forma manual y desconectada, sin trazabilidad ni
indicadores agregados para la toma de decisiones.

## 4. Actores principales

El sistema define **13 roles reales** (`backend/src/core/rbac.py::ROLES`), cada uno con acceso
exactamente a las pantallas y acciones que le corresponden (RBAC estricto, ver `reglas.md`):

| Rol | Naturaleza | Nivel(es) donde actúa |
|---|---|---|
| `pasajero` | Autorregistro público | Operativo (solicitar/pagar/calificar/gestionar su propio viaje) |
| `conductor` | Autorregistro con verificación (postulación) | Operativo (turno, ejecución de viaje, reporte de fallas, documentos propios) |
| `admin_captacion` | Personal interno | Operativo + Táctico (Captación) |
| `coordinador_operaciones` | Personal interno | Operativo + Táctico + Estratégico (Operaciones/Despacho) |
| `coordinador_flota` | Personal interno | Operativo + Táctico (Coordinación de Flota) |
| `jefe_mantenimiento` | Personal interno | Operativo + Táctico (Mantenimiento) |
| `admin_financiero` | Personal interno | Operativo + Táctico (Control Financiero) |
| `supervisor_cumplimiento` | Personal interno | Operativo + Táctico + Estratégico (Cumplimiento) |
| `responsable_plataforma` | Personal interno | Táctico (Inteligencia de Negocio y Plataforma) |
| `admin_plataforma` | Personal interno | Táctico (acceso ampliado a Flota/Auditoría/Plataforma vía OR-gate) |
| `gerencia` | Dirección | Estratégico (único rol que ve el Tablero Ejecutivo consolidado, Rentabilidad y Gobernanza de Datos) |
| `admin_sistema` | Gobierno de la plataforma técnica | Transversal (los 8 módulos de Administración del Sistema, separado de `admin_plataforma` por mínimo privilegio) |
| `integracion_externa` | Acceso máquina-a-máquina | Sin pantalla propia en `web-interno` — pensado para integraciones API, no para el portal |

## 5. Módulos del sistema (estructura de esta documentación retroactiva)

```
specs/
├── 000-sistema-general/        (este documento + glosario + reglas transversales)
├── 001-estrategico/            (1 módulo: Dirección General — los 9 paneles + Tablero Ejecutivo)
├── 002-tactico/                (7 módulos, uno por departamento)
├── 003-operativo/              (6 módulos, uno por departamento — ver nota de alcance abajo)
└── 004-transversal/            (4 módulos: infraestructura que sostiene a los 3 niveles)
```

**Nota de alcance real, verificada, que aparta esta estructura de la propuesta inicial**: el nivel
operativo tiene **6** departamentos con operación diaria propia manejada por una persona
(Captación, Operaciones/Despacho, Coordinación de Flota, Mantenimiento, Control Financiero,
Cumplimiento), no 7. "Inteligencia de Negocio y Plataforma" **no tiene un departamento operativo
propio**: la ejecución diaria del proceso de datos (Bronze→Silver→Gold vía Airflow) es automática,
sin un actor humano operándola día a día, y su artefacto operativo real — el catálogo de informes
publicados — ya está documentado en `FUNCIONALIDADES_TRANSVERSALES.md` §1.2 como infraestructura
transversal ("no es en sí un proceso de negocio de la cooperativa: es la infraestructura de datos
que hace posibles los otros dos niveles"). Esta documentación retroactiva respeta esa clasificación
ya hecha en vez de reabrirla: **Plataforma vive en `004-transversal/auditoria-y-trazabilidad/`**
(junto a la Bitácora, con la que comparte naturaleza de infraestructura), y **no existe
`003-operativo/inteligencia-de-negocio-y-plataforma/`**. A nivel táctico sí existe un departamento
real y distinto (`002-tactico/inteligencia-de-negocio-y-plataforma/`) porque ahí hay un rol
(`responsable_plataforma`) que consume un dashboard propio de salud del proceso de datos como
función gerencial diferenciada — eso sí es una función departamental real, no infraestructura pura.

## 6. Los 3 niveles organizacionales

| Nivel | Pregunta que responde | Quién lo usa | Frecuencia |
|---|---|---|---|
| **Operativo** | "¿Qué está pasando ahora mismo, con este viaje/vehículo/socio concreto?" | Personal de cada departamento, pasajeros, conductores | Continua, transaccional |
| **Táctico** | "¿Cómo va mi departamento este período?" | Un responsable por departamento (10 dashboards en `web-interno` → "Panel Táctico") | Diaria/semanal |
| **Estratégico** | "¿Cómo va la cooperativa completa?" | `gerencia` principalmente (9 dashboards + Tablero Ejecutivo en `web-interno` → "Panel Estratégico") | Mensual/trimestral |

Los 3 niveles comparten los mismos datos de origen (MongoDB para operativo, ClickHouse agregado vía
Airflow para táctico/estratégico) — táctico y estratégico nunca inventan un cálculo nuevo por su
cuenta que el nivel operativo no pueda respaldar con datos reales.

## 7. Reglas generales

Ver [`reglas.md`](reglas.md) — principios transversales ya establecidos que aplican a todo el
sistema (equivalente a la "constitución" del proyecto).

## 8. Restricciones generales

- Todo acceso requiere autenticación con usuario+contraseña (login con teléfono o correo) — no hay
  OTP ni SMS en ningún flujo del sistema (decisión de arquitectura tomada y documentada, ver
  `reglas.md`).
- Mapas: siempre Leaflet + tiles OpenStreetMap — nunca el SDK de Google Maps (`specs-generales/
  arquitectura_software.md` lo exige explícitamente). Google solo se usa para Geocoding/Directions,
  vía el backend.
- Ninguna entidad transaccional (viajes, solicitudes, órdenes, cuentas) se borra físicamente — todas
  usan baja lógica por estado o campo `activo`/`estado` (ver `reglas.md`).
- El sistema no fabrica datos que no existen: donde un cálculo no tiene fuente real, la interfaz
  muestra "—" con una nota explicando por qué, nunca un número inventado.

## 9. Glosario

Ver [`glosario.md`](glosario.md).

## 10. Fuera de alcance a nivel de sistema completo

Decisiones ya tomadas y documentadas, no descuidos — no se implementan sin pedido explícito nuevo:

- Aplicaciones móviles nativas — el sistema es 100% web (PWA para pasajero/conductor).
- OTP/SMS para autenticación — se evaluó y se descartó en favor de usuario+contraseña.
- Pago electrónico/pasarela de pago — el único método de cobro implementado es efectivo.
- Chat o llamada en vivo entre pasajero y conductor.
- Comprobante de viaje en PDF con folio fiscal.
- Anonimización automática — existe el mecanismo (`004-transversal/administracion-del-sistema`)
  pero se ejecuta manualmente por `admin_sistema`, nunca de forma automática por vencimiento de
  plazo.
- Bloqueo operativo automático por documentación vencida — el sistema **advierte** (visible al
  conductor y a personal interno) pero **nunca bloquea ninguna acción** por este motivo; es una
  decisión operativa pendiente de la cooperativa, no una carencia técnica.
- Inteligencia artificial o predicción automática en cualquiera de los 3 niveles de indicadores.
- Cifrado en reposo de los respaldos de base de datos — declarado explícitamente como no
  implementado en `004-transversal/administracion-del-sistema`.

Cada módulo de nivel inferior documenta además sus propias exclusiones específicas en su sección
"Fuera de alcance".
