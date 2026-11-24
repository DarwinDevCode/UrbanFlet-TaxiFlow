"""Corrección puntual: consolidación de duplicados en `parametros` (tipo="comision").

Encontrados 2 documentos con `vigente_hasta: null` simultáneos para la misma
serie (`comision-v1`, `com-browser-01`), ambos con `porcentaje: 0.2` -- IDs que
no siguen el patrón real del servicio (`uuid4()`), es decir, inserciones
manuales directas a Mongo de una sesión anterior, nunca pasos reales por
`parametros.service.crear_parametro_comision`. Confirmado antes de tocar nada
que los 2 coincidían en el mismo porcentaje -- si hubieran divergido, la
corrección se habría detenido ahí en vez de decidir cuál es "el correcto".

La corrección de datos en sí YA se aplicó (no la repite este script, para no
crear una tercera versión ni duplicar el borrado):
  1. `POST /parametros/comisiones` real (porcentaje=0.2, vigente_desde
     preservada en 2020-01-01T00:00:00Z -- el mismo inicio de cobertura que
     ya tenían los 2 duplicados, para no dejar sin porcentaje vigente ningún
     viaje ya finalizado y aún sin pagar) -- generó un id real via `uuid4()`
     y, como efecto correcto de `_crear_version`, cerró los 2 documentos
     manuales (`vigente_hasta` = `vigente_desde`, ventana de ancho cero,
     inertes).
  2. `db.parametros.deleteMany({_id: {$in: ["comision-v1", "com-browser-01"]}})`
     -- confirmado en Mongo: queda exactamente 1 documento vigente.

Este script solo dedja el registro en la bitácora de auditoría de la
corrección -- la propia llamada a `crear_parametro_comision` ya escribió su
evento `PARAMETRO_CAMBIO` de rutina (cambio de porcentaje), pero ese evento
no explica que en realidad fue una consolidación de duplicados ni deja
constancia del borrado de los 2 documentos manuales. Se agrega un segundo
evento explícito para eso, con `datos_previos` listando los 2 documentos
eliminados.

Uso: python -m scripts.consolidar_parametro_comision
"""

import asyncio

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.db_mongo import get_database

_DOCUMENTOS_MANUALES_ELIMINADOS = [
    {
        "_id": "comision-v1",
        "tipo": "comision",
        "valores": {"porcentaje": 0.2},
        "vigente_desde": "2020-01-01T00:00:00Z",
        "vigente_hasta": None,
    },
    {
        "_id": "com-browser-01",
        "tipo": "comision",
        "valores": {"porcentaje": 0.2},
        "vigente_desde": "2020-01-01T00:00:00Z",
        "vigente_hasta": None,
    },
]

_DOCUMENTO_REAL_CONSOLIDADO_ID = "b93a36e8-aa79-4ff0-b75f-e183c882d25b"


async def main() -> None:
    db = get_database()

    # Guarda de idempotencia: si este script se corre dos veces, no duplica
    # el evento de corrección.
    ya_registrado = await db.bitacora.find_one(
        {
            "accion": AccionAuditoria.PARAMETRO_CAMBIO.value,
            "datos_posteriores.motivo": "consolidacion_duplicados_comision",
        }
    )
    if ya_registrado:
        print("Ya existe un evento de esta corrección en la bitácora -- no se duplica.")
        return

    await write_audit_event(
        db,
        actor_id=None,
        rol="admin_plataforma,gerencia",
        accion=AccionAuditoria.PARAMETRO_CAMBIO,
        entidad="parametros",
        entidad_id=_DOCUMENTO_REAL_CONSOLIDADO_ID,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"tipo": "comision", "documentos_eliminados": _DOCUMENTOS_MANUALES_ELIMINADOS},
        datos_posteriores={
            "motivo": "consolidacion_duplicados_comision",
            "tipo": "comision",
            "porcentaje": 0.2,
            "vigente_desde": "2020-01-01T00:00:00Z",
            "documento_vigente_id": _DOCUMENTO_REAL_CONSOLIDADO_ID,
            "detalle": (
                "2 documentos con vigente_hasta:null simultaneos (comision-v1, "
                "com-browser-01), insertados manualmente fuera del servicio real "
                "(IDs no uuid4), consolidados en un unico documento creado via "
                "crear_parametro_comision (POST /parametros/comisiones). Ambos "
                "duplicados coincidian en porcentaje=0.2 antes de eliminarlos."
            ),
        },
    )
    print("Evento de corrección registrado en la bitácora.")


if __name__ == "__main__":
    asyncio.run(main())
