# Plan técnico (retroactivo): Captación y Talento

## Backend

- `backend/src/captacion/` (`router.py`/`service.py`/`schemas.py`): `crear_solicitud`,
  `enviar_solicitud_con_documentos`, `tomar_solicitud`, `decidir_solicitud`, `registrar_pasajero`.
- `backend/src/archivos/`: infraestructura genérica de subida (contexto `documento_postulacion`),
  reutilizada tal cual — no se construyó un mecanismo de subida paralelo para este módulo.
- Colecciones Mongo: `solicitudes`, `usuarios`, `vehiculos`, `documentos` (esta última compartida
  con Cumplimiento — mismo esquema, mismo consumidor en los paneles tácticos/estratégicos).

## Frontend

- `apps/web-conductor/src/App.tsx` — `PostulacionForm` (con la sección "Documentos" agregada en la
  ronda de gestión documental) y `DocumentoPostulacion` (subcomponente de archivo + fecha).
- `apps/web-pasajero/src/App.tsx` — formulario de registro directo.
- `apps/web-interno/src/sections/Solicitudes.tsx` — WorkPanel estándar (RN-SIS-010), con el bloque
  "Documentos enviados" (visor real + semáforo de vigencia) agregado en la misma ronda.

## Decisión de arquitectura: por qué el flujo de postulación es de 3 pasos y no 1

`POST /archivos` exige un actor autenticado; la cuenta del postulante recién existe después de crear
la solicitud. Se descartó pedir el login por separado del formulario — la sesión que se abre para
subir los archivos es puramente instrumental y se cierra en el mismo flujo (el postulante nunca ve
un estado de "sesión iniciada").

Ver `CLAUDE.md` §26.3 para el detalle completo, incluido el hallazgo real de que el backend de este
flujo ya estaba construido de una sesión anterior sin documentar — solo faltaba el frontend.
