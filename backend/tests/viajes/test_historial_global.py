from datetime import UTC, datetime, timedelta

from tests.utils import auth_headers, crear_usuario_activo


def _viaje_terminal(*, viaje_id, pasajero_id, conductor_id, conductor_nombre, estado, ts_solicitud):
    return {
        "_id": viaje_id,
        "pasajero_id": pasajero_id,
        "conductor_id": conductor_id,
        "vehiculo_id": "veh-hg" if conductor_id else None,
        "estado": estado,
        "origen_lat": -0.18,
        "origen_lon": -78.5,
        "origen_direccion": "Origen",
        "destino_lat": None,
        "destino_lon": None,
        "destino_direccion": None,
        "franja": "DIURNA",
        "ts_solicitud": ts_solicitud,
        "ts_asignacion": None,
        "ts_llegada_origen": None,
        "ts_inicio": None,
        "ts_fin": None,
        "km_recorridos": None,
        "min_espera": None,
        "tarifa_estimada": None,
        "tarifa_final": None,
        "motivo_cancelacion": None,
        "conductor_nombre": conductor_nombre,
        "conductor_calificacion": None,
        "vehiculo_placa": None,
        "vehiculo_marca": None,
        "vehiculo_color": None,
        "calificacion_pasajero_a_conductor": None,
        "calificacion_conductor_a_pasajero": None,
    }


async def _coordinador(db):
    await crear_usuario_activo(db, usuario_id="coord-hg-1", telefono="+593900003000", roles=["coordinador_operaciones"])
    return auth_headers("coord-hg-1", ["coordinador_operaciones"])


async def test_historial_global_requiere_rol_autorizado(client, db):
    await crear_usuario_activo(db, usuario_id="pasajero-hg-1", telefono="+593900003001", roles=["pasajero"])
    headers = auth_headers("pasajero-hg-1", ["pasajero"])

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 403


async def test_historial_global_incluye_viajes_de_cualquier_pasajero(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-a", telefono="+593900003002", roles=["pasajero"])
    await crear_usuario_activo(db, usuario_id="p-hg-b", telefono="+593900003003", roles=["pasajero"])
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="hg-1", pasajero_id="p-hg-a", conductor_id="c-hg-1", conductor_nombre="Juan Pérez",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
            _viaje_terminal(
                viaje_id="hg-2", pasajero_id="p-hg-b", conductor_id="c-hg-2", conductor_nombre="Pedro Ruiz",
                estado="CANCELADO", ts_solicitud=ahora - timedelta(hours=1),
            ),
        ]
    )

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = {v["id"] for v in body["viajes"]}
    assert ids == {"hg-1", "hg-2"}


async def test_historial_global_filtra_por_estado(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-c", telefono="+593900003004", roles=["pasajero"])
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="hg-3", pasajero_id="p-hg-c", conductor_id="c-hg-3", conductor_nombre="Ana Sosa",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
            _viaje_terminal(
                viaje_id="hg-4", pasajero_id="p-hg-c", conductor_id="c-hg-3", conductor_nombre="Ana Sosa",
                estado="SIN_CONDUCTOR", ts_solicitud=ahora,
            ),
        ]
    )

    resp = await client.get("/viajes/historial-global", headers=headers, params={"estado": "SIN_CONDUCTOR"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["viajes"][0]["id"] == "hg-4"


async def test_historial_global_busca_por_texto_de_pasajero_o_conductor(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-maria", telefono="+593900003005", roles=["pasajero"])
    await db.usuarios.update_one({"_id": "p-hg-maria"}, {"$set": {"nombre": "María Fernanda Torres"}})
    await crear_usuario_activo(db, usuario_id="p-hg-otro", telefono="+593900003006", roles=["pasajero"])
    ahora = datetime.now(UTC)
    await db.viajes.insert_many(
        [
            _viaje_terminal(
                viaje_id="hg-5", pasajero_id="p-hg-maria", conductor_id="c-hg-5", conductor_nombre="Luis Vera",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
            _viaje_terminal(
                viaje_id="hg-6", pasajero_id="p-hg-otro", conductor_id="c-hg-6", conductor_nombre="Otro Conductor",
                estado="FINALIZADO", ts_solicitud=ahora,
            ),
        ]
    )

    resp = await client.get("/viajes/historial-global", headers=headers, params={"texto": "María"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["viajes"][0]["id"] == "hg-5"
    assert body["viajes"][0]["pasajero_nombre"] == "María"


async def test_historial_global_nunca_expone_telefono_del_pasajero(client, db):
    headers = await _coordinador(db)
    await crear_usuario_activo(db, usuario_id="p-hg-tel", telefono="+593900003007", roles=["pasajero"])
    await db.viajes.insert_one(
        _viaje_terminal(
            viaje_id="hg-7", pasajero_id="p-hg-tel", conductor_id="c-hg-7", conductor_nombre="Chofer Uno",
            estado="FINALIZADO", ts_solicitud=datetime.now(UTC),
        )
    )

    resp = await client.get("/viajes/historial-global", headers=headers)

    assert resp.status_code == 200
    assert "pasajero_telefono" not in resp.json()["viajes"][0]
    assert "+593900003007" not in resp.text


async def test_supervisor_cumplimiento_y_gerencia_tambien_pueden_ver(client, db):
    await crear_usuario_activo(db, usuario_id="cumpl-hg-1", telefono="+593900003008", roles=["supervisor_cumplimiento"])
    headers_cumplimiento = auth_headers("cumpl-hg-1", ["supervisor_cumplimiento"])
    resp1 = await client.get("/viajes/historial-global", headers=headers_cumplimiento)
    assert resp1.status_code == 200

    await crear_usuario_activo(db, usuario_id="gerencia-hg-1", telefono="+593900003009", roles=["gerencia"])
    headers_gerencia = auth_headers("gerencia-hg-1", ["gerencia"])
    resp2 = await client.get("/viajes/historial-global", headers=headers_gerencia)
    assert resp2.status_code == 200
