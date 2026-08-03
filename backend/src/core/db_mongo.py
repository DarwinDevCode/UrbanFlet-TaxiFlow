from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        # w="majority" a nivel de conexión: sostiene el contrato de write-ahead
        # de la bitácora (CU-O17) sin depender de una opción por-llamada.
        _client = AsyncIOMotorClient(get_settings().mongo_uri, w="majority")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_mongo_client()[get_settings().mongo_db_name]


async def close_mongo_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


# Índices mínimos declarados en diseno_base_datos.md §2.1.
# write_concern por defecto de la conexión es "majority"; la bitácora (core/audit.py)
# lo exige explícitamente para cumplir el write-ahead de CU-O17.
async def ensure_indexes() -> None:
    db = get_database()

    # sparse=True: el registro ahora acepta teléfono O correo (a elección del
    # usuario) — muchas cuentas comparten "no tengo teléfono" o "no tengo
    # correo", y un índice único no-sparse trataría esos `null`/ausentes
    # como el mismo valor duplicado a partir de la segunda cuenta así.
    await db.usuarios.create_index("telefono", unique=True, sparse=True)
    await db.usuarios.create_index("email", unique=True, sparse=True)

    await db.viajes.create_index([("pasajero_id", 1), ("ts_solicitud", 1)])
    await db.viajes.create_index([("conductor_id", 1), ("ts_solicitud", 1)])
    await db.viajes.create_index(
        "estado",
        partialFilterExpression={
            "estado": {"$in": ["SOLICITADO", "OFERTADO", "ASIGNADO", "EN_CAMINO", "EN_CURSO"]}
        },
    )
    # Índice separado para el panel táctico de Despacho
    # (`listar_sin_conductor_y_cancelados_hoy`, GET
    # /viajes/panel-tactico/sin-conductor-cancelados): SIN_CONDUCTOR/CANCELADO
    # no están cubiertos por el índice parcial de arriba (ese es solo para
    # estados activos). Sin este índice, la query hace collection scan
    # completo -- detectado tras sembrar ~1.3M viajes históricos (dataset
    # NYC, ver CLAUDE.md): el endpoint pasó de <50ms a ~1.15s. Partial
    # porque solo estos 2 estados importan para este filtro.
    await db.viajes.create_index(
        [("estado", 1), ("ts_solicitud", -1)],
        partialFilterExpression={"estado": {"$in": ["SIN_CONDUCTOR", "CANCELADO"]}},
    )
    # Índice para `listar_bandeja_discrepancias` (CU-O09 A4, VIAJE_SIN_PAGO):
    # filtra viajes FINALIZADO con ts_fin viejo -- mismo problema que el
    # índice de arriba, FINALIZADO tampoco está en el parcial de estados
    # activos. Confirmado con explain() tras la siembra NYC: COLLSCAN sobre
    # 1.33M documentos para encontrar 3 -- 902ms.
    await db.viajes.create_index(
        [("estado", 1), ("ts_fin", 1)],
        partialFilterExpression={"estado": "FINALIZADO"},
    )

    await db.ofertas.create_index([("conductor_id", 1), ("ts_emision", 1)])

    await db.pagos.create_index("viaje_id", unique=True)
    await db.pagos.create_index("estado")
    await db.movimientos.create_index("liquidacion_id")
    await db.movimientos.create_index("viaje_id")

    # CU-O11: consolidar por socio los viajes PAGADO de un periodo (por
    # ts_fin, no ts_solicitud — el periodo de liquidación es sobre cuándo se
    # cerró y cobró el viaje, no cuándo se pidió).
    await db.viajes.create_index([("conductor_id", 1), ("estado", 1), ("ts_fin", 1)])

    await db.liquidaciones.create_index([("conductor_id", 1), ("periodo_fin", -1)])
    await db.liquidaciones.create_index("estado")
    # Chequeo de idempotencia de generar_liquidaciones(): ¿ya existe una
    # liquidación de este socio para este periodo?
    await db.liquidaciones.create_index([("conductor_id", 1), ("periodo_inicio", 1)], unique=True)
    await db.movimientos.create_index([("liquidacion_id", 1), ("ts", 1)])

    await db.documentos.create_index("fecha_vencimiento")

    await db.bitacora.create_index([("actor_id", 1), ("ts", 1)])

    await db.posiciones.create_index([("vehiculo_id", 1), ("ts_servidor", 1)])
    await db.posiciones.create_index("ts_servidor", expireAfterSeconds=7 * 24 * 60 * 60)

    await db.solicitudes.create_index("estado")
    await db.solicitudes.create_index("usuario_id")
    await db.solicitudes.create_index([("cedula", 1), ("estado", 1)])

    await db.vehiculos.create_index("placa", unique=True)
    await db.vehiculos.create_index("propietario_id")
    await db.usuarios.create_index("conductor.cedula")

    await db.ordenes.create_index("estado")
    await db.ordenes.create_index("vehiculo_id")

    await db.parametros.create_index([("tipo", 1), ("vigente_desde", -1)])
