# UrbanFleet TaxiFlow — Especificaciones reconstruidas (Spec-Driven Development)

Este directorio es una **ingeniería inversa** del sistema ya construido, organizada según el
enfoque de Spec-Driven Development / Spec Kit: si el proyecto se hubiera desarrollado con esa
metodología desde el inicio, esta es la estructura de especificaciones que debería existir para
representar correctamente lo que **hoy** está implementado y funcionando.

## Qué es y qué no es este directorio

- **Es** una reconstrucción documental del comportamiento real del sistema, verificada contra el
  código (`backend/src/`, `apps/*/src/`), la base de datos y, cuando fue necesario, ejecución real
  en navegador.
- **No es** un historial de que este proyecto usó Spec Kit durante su desarrollo — no lo usó. No
  hay propuestas, `speckit-clarify` ni `speckit-analyze` ejecutados en el pasado; lo que hay es la
  especificación que **debería haberse escrito primero**, redactada ahora a partir de lo que ya
  existe.
- **No** documenta funcionalidad planificada, pendiente, ni presente solo en specs antiguas que
  nunca se construyeron. Cuando un documento previo describía algo que el código no respalda, se
  documentó el comportamiento real y se dejó constancia de la diferencia.

## Fuentes usadas, en orden de prioridad

1. Comportamiento real observado (navegador, base de datos).
2. Código actual (`backend/src/`, `apps/*/src/`).
3. Artefactos funcionales ya elaborados en este proyecto — principalmente
   [`DOCUMENTACION_ORGANIZACIONAL.md`](../DOCUMENTACION_ORGANIZACIONAL.md) (ya reconstruye la
   estructura de niveles/departamentos/objetivos/casos de uso a partir del sistema real) y
   [`AUDITORIA_FUNCIONAL_OPERATIVO.md`](../AUDITORIA_FUNCIONAL_OPERATIVO.md) (verificación manual
   punta a punta de cada flujo operativo).
4. Documentación histórica (`specs/nivel-operativo/*.md`, auditorías de conformidad) — usada para
   contexto y numeración de casos de uso, nunca como fuente de verdad sobre si algo existe.
5. El documento metodológico de Spec-Driven Development proporcionado — guía de **forma**, nunca
   de contenido.

## Estructura

```
speckit/
├── constitucion.md              — reglas generales que todo el sistema respeta
├── 000-sistema-general/
│   └── spec.md                  — especificación general, alto nivel
└── operativo/
    ├── 01-captacion-y-talento/spec.md
    ├── 02-operaciones-y-despacho/spec.md
    ├── 03-coordinacion-de-flota/spec.md
    ├── 04-mantenimiento/spec.md
    ├── 05-control-financiero/spec.md
    └── 06-cumplimiento-regulatorio/spec.md
```

Cada carpeta de departamento corresponde a una de las 6 unidades del nivel operativo definidas en
`DOCUMENTACION_ORGANIZACIONAL.md` §1.3 y §3 (OP1-OP6). El séptimo departamento de esa tabla
("Inteligencia de Negocio y Plataforma") no tiene funcionalidad de **nivel operativo**: su objetivo
operativo equivalente (el proceso de datos que alimenta los tableros) es, por diseño, una capacidad
transversal que sostiene a los tres niveles, no una operación diaria de cara al negocio de la
cooperativa — se documentará en un bloque transversal aparte cuando corresponda, no aquí.

## Convención de identificadores

`RF-[MOD]-NNN` (requisito funcional), `RN-[MOD]-NNN` (regla de negocio), `RNF-[MOD]-NNN` (requisito
no funcional, solo donde aplica de verdad), `CA-[MOD]-NNN` (criterio de aceptación). `[MOD]` es el
código corto del departamento:

| Código | Departamento |
|---|---|
| `CAP` | Captación y Talento |
| `DESP` | Operaciones y Despacho |
| `FLOT` | Coordinación de Flota |
| `MANT` | Mantenimiento |
| `FIN` | Control Financiero |
| `CUMP` | Cumplimiento Regulatorio |

## Estado de avance

- [x] Nivel operativo (6 departamentos) — este bloque.
- [ ] Nivel táctico.
- [ ] Nivel estratégico.
- [ ] Capa transversal (bitácora, notificaciones, autoservicio, proceso de datos, administración
      del sistema).

## Hallazgos reales encontrados al reconstruir (discrepancias documento-vs-código)

Registrados aquí porque afectan directamente el contenido de las especificaciones de este bloque —
ver el detalle en la especificación de cada departamento:

- **CU-O09 (control de vigencia documental)**: `DOCUMENTACION_ORGANIZACIONAL.md` describe la
  revisión diaria como "programada" además de manual. El código
  (`backend/src/cumplimiento/router.py`) solo implementa el disparo manual — no existe ningún cron
  ni DAG de Airflow que lo ejecute automáticamente todavía. Se documentó como manual, con la
  automatización como capacidad prevista pero no construida.
