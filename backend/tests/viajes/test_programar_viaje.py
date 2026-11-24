from datetime import UTC, datetime, timedelta

from src.core.config import get_settings
from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _pasajero_headers(db, usuario_id="pp1", telefono="+593970400001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


def _ts_valido() -> str:
    return (datetime.now(UTC) + timedelta(hours=1)).isoformat()


def _headers_internos() -> dict:
    return {"X-Internal-Token": get_settings().internal_api_token}


async def test_solicitar_viaje_programado_queda_en_programado_sin_despachar(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="pc1",
        telefono="+593970400011",
        vehiculo_id="pv1",
        placa="PRG0001",
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id="pv1", lat=-0.1801, lon=-78.5001)

    resp = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={
            "origen_lat": -0.1801,
            "origen_lon": -78.5001,
            "origen_direccion": "Origen",
            "ts_programado": _ts_valido(),
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "PROGRAMADO"
    assert body["ts_programado"] is not None
    assert body["conductor_id"] is None

    # No debe haber disparado ningún despacho -- el conductor sigue libre.
    conductor_db = await db.usuarios.find_one({"_id": "pc1"})
    assert conductor_db["conductor"]["estado_servicio"] == "DISPONIBLE"


async def test_solicitar_viaje_programado_muy_pronto_devuelve_422(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    ts_muy_cerca = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()

    resp = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={
            "origen_lat": -0.1801,
            "origen_lon": -78.5001,
            "origen_direccion": "Origen",
            "ts_programado": ts_muy_cerca,
        },
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "TS_PROGRAMADO_INVALIDO"


async def test_solicitar_viaje_programado_muy_lejano_devuelve_422(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    ts_muy_lejos = (datetime.now(UTC) + timedelta(days=30)).isoformat()

    resp = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={
            "origen_lat": -0.1801,
            "origen_lon": -78.5001,
            "origen_direccion": "Origen",
            "ts_programado": ts_muy_lejos,
        },
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "TS_PROGRAMADO_INVALIDO"


async def test_viaje_programado_aparece_como_activo_y_bloquea_uno_nuevo(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={
            "origen_lat": -0.1801,
            "origen_lon": -78.5001,
            "origen_direccion": "Origen",
            "ts_programado": _ts_valido(),
        },
    )

    activo = await client.get("/viajes/activo", headers=headers_pasajero)
    assert activo.status_code == 200
    assert activo.json()["estado"] == "PROGRAMADO"

    otro = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": -0.1801, "origen_lon": -78.5001, "origen_direccion": "Origen"},
    )
    assert otro.status_code == 409
    assert otro.json()["code"] == "TRIP_ALREADY_ACTIVE"


async def test_cancelar_viaje_programado(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={
            "origen_lat": -0.1801,
            "origen_lon": -78.5001,
            "origen_direccion": "Origen",
            "ts_programado": _ts_valido(),
        },
    )

    resp = await client.post(
        "/viajes/activo/cancelar", headers=headers_pasajero, json={"motivo": "Cambié de planes"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "CANCELADO"


async def test_disparar_programado_sin_token_devuelve_403(client, db, redis):
    resp = await client.post("/viajes/algun-id/disparar-programado")
    assert resp.status_code == 403
    assert resp.json()["code"] == "TOKEN_INTERNO_INVALIDO"


async def test_disparar_programado_con_token_incorrecto_devuelve_403(client, db, redis):
    resp = await client.post("/viajes/algun-id/disparar-programado", headers={"X-Internal-Token": "token-incorrecto"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "TOKEN_INTERNO_INVALIDO"


async def test_disparar_programado_transiciona_a_solicitado_y_avanza_despacho(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="pc2",
        telefono="+593970400012",
        vehiculo_id="pv2",
        placa="PRG0002",
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id="pv2", lat=-0.1801, lon=-78.5001)

    creado = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={
            "origen_lat": -0.1801,
            "origen_lon": -78.5001,
            "origen_direccion": "Origen",
            "ts_programado": _ts_valido(),
        },
    )
    viaje_id = creado.json()["id"]

    resp = await client.post(f"/viajes/{viaje_id}/disparar-programado", headers=_headers_internos())

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "OFERTADO"

    viaje_db = await db.viajes.find_one({"_id": viaje_id})
    assert viaje_db["estado"] == "OFERTADO"
    assert viaje_db["ts_programado"] is not None


async def test_disparar_programado_sobre_viaje_no_programado_devuelve_404(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    creado = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={"origen_lat": -0.1801, "origen_lon": -78.5001, "origen_direccion": "Origen"},
    )
    viaje_id = creado.json()["id"]

    resp = await client.post(f"/viajes/{viaje_id}/disparar-programado", headers=_headers_internos())

    assert resp.status_code == 404
    assert resp.json()["code"] == "VIAJE_NO_PROGRAMADO"


async def test_disparar_programado_es_idempotente_ante_reintento(client, db, redis):
    headers_pasajero = await _pasajero_headers(db)
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="pc3",
        telefono="+593970400013",
        vehiculo_id="pv3",
        placa="PRG0003",
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id="pv3", lat=-0.1801, lon=-78.5001)

    creado = await client.post(
        "/viajes",
        headers=headers_pasajero,
        json={
            "origen_lat": -0.1801,
            "origen_lon": -78.5001,
            "origen_direccion": "Origen",
            "ts_programado": _ts_valido(),
        },
    )
    viaje_id = creado.json()["id"]

    primero = await client.post(f"/viajes/{viaje_id}/disparar-programado", headers=_headers_internos())
    segundo = await client.post(f"/viajes/{viaje_id}/disparar-programado", headers=_headers_internos())

    assert primero.status_code == 200
    assert segundo.status_code == 404
    assert segundo.json()["code"] == "VIAJE_NO_PROGRAMADO"
