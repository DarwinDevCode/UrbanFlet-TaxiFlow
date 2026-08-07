from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo, reportar_posicion_en_cache


async def _pasajero_headers(db, usuario_id="p1", telefono="+593960000001"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


async def _sembrar_conductor_disponible(
    db, redis, *, conductor_id, telefono, vehiculo_id, placa, lat=-0.1801, lon=-78.5001
):
    await crear_conductor_con_vehiculo(
        db,
        conductor_id=conductor_id,
        telefono=telefono,
        vehiculo_id=vehiculo_id,
        placa=placa,
        estado_servicio="DISPONIBLE",
    )
    await reportar_posicion_en_cache(redis, vehiculo_id=vehiculo_id, lat=lat, lon=lon)


async def test_solicitar_viaje_sin_destino_no_calcula_tarifa(client, db, redis):
    headers = await _pasajero_headers(db)
    await _sembrar_conductor_disponible(
        db, redis, conductor_id="c000001", telefono="+593970000001", vehiculo_id="v000001", placa="PBA0001"
    )

    resp = await client.post(
        "/viajes",
        headers=headers,
        json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Av. Siempre Viva 123"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "OFERTADO"
    assert body["tarifa_estimada"] is None


async def test_solicitar_viaje_con_destino_calcula_tarifa_estimada(client, db):
    headers = await _pasajero_headers(db, usuario_id="p2", telefono="+593960000002")
    headers_admin = await _admin_headers(db)
    await client.post(
        "/parametros/tarifas",
        headers=headers_admin,
        json={
            "franja": "DIURNA",
            "arrancada": 0.5,
            "costo_km": 0.35,
            "costo_min_espera": 0.07,
            "carrera_minima": 1.5,
            "vigente_desde": "2020-01-01T00:00:00Z",
        },
    )
    await client.post(
        "/parametros/tarifas",
        headers=headers_admin,
        json={
            "franja": "NOCTURNA",
            "arrancada": 0.6,
            "costo_km": 0.4,
            "costo_min_espera": 0.09,
            "carrera_minima": 1.75,
            "vigente_desde": "2020-01-01T00:00:00Z",
        },
    )

    resp = await client.post(
        "/viajes",
        headers=headers,
        json={
            "origen_lat": -0.18,
            "origen_lon": -78.5,
            "origen_direccion": "Origen",
            "destino_lat": -0.20,
            "destino_lon": -78.52,
            "destino_direccion": "Destino",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["tarifa_estimada"] is not None
    assert body["tarifa_estimada"] > 0


async def _admin_headers(db):
    await crear_usuario_activo(db, usuario_id="admin-tarifa", telefono="+593960099999", roles=["admin_plataforma"])
    return auth_headers("admin-tarifa", ["admin_plataforma"])


async def test_solicitar_segundo_viaje_activo_devuelve_409(client, db, redis):
    headers = await _pasajero_headers(db, usuario_id="p3", telefono="+593960000003")
    await _sembrar_conductor_disponible(
        db, redis, conductor_id="c000003", telefono="+593970000003", vehiculo_id="v000003", placa="PBA0003"
    )
    payload = {"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"}
    await client.post("/viajes", headers=headers, json=payload)

    resp = await client.post("/viajes", headers=headers, json=payload)

    assert resp.status_code == 409
    assert resp.json()["code"] == "TRIP_ALREADY_ACTIVE"


async def test_obtener_viaje_activo(client, db, redis):
    headers = await _pasajero_headers(db, usuario_id="p4", telefono="+593960000004")
    await _sembrar_conductor_disponible(
        db, redis, conductor_id="c000004", telefono="+593970000004", vehiculo_id="v000004", placa="PBA0004"
    )
    creado = await client.post(
        "/viajes", headers=headers, json={"origen_lat": -0.18, "origen_lon": -78.5, "origen_direccion": "Origen"}
    )

    resp = await client.get("/viajes/activo", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["id"] == creado.json()["id"]


async def test_sin_viaje_activo_devuelve_200_vacio(client, db):
    # No tener viaje activo es un estado normal, no un error — 200 con
    # cuerpo vacío, nunca 404 (corregido tras hallazgo en pruebas reales).
    headers = await _pasajero_headers(db, usuario_id="p5", telefono="+593960000005")

    resp = await client.get("/viajes/activo", headers=headers)

    assert resp.status_code == 200
    assert resp.json() is None


# CU-O04 P3, corregido tras hallazgo en pruebas reales: Directions API de
# Google no envía cabeceras CORS, así que ahora se pide siempre desde el
# backend (nunca desde el navegador). Estos tests no golpean la red real —
# mockean `get_settings`/`httpx.AsyncClient.get` para que el resultado sea
# determinístico en CI.

async def test_estimacion_ruta_sin_key_configurada_usa_linea_recta(client, db, monkeypatch):
    from src.integraciones import service as integraciones_service

    class _SettingsSinKey:
        google_maps_api_key = ""

    # Módulo 4.2 de admin_sistema: la key se resuelve vía
    # `integraciones.service.obtener_google_maps_api_key` (override en
    # Mongo si se rotó, si no cae a `Settings`) -- el mock apunta ahí, no a
    # `viajes.service`.
    monkeypatch.setattr(integraciones_service, "get_settings", lambda: _SettingsSinKey())
    headers = await _pasajero_headers(db, usuario_id="p6", telefono="+593960000006")

    resp = await client.get(
        "/viajes/estimacion-ruta?origen_lat=-0.18&origen_lon=-78.46&destino_lat=-0.19&destino_lon=-78.47",
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["origen_directions"] is False
    assert body["distancia_km"] > 0
    assert len(body["ruta"]) == 2


class _RespuestaFalsa:
    def json(self):
        return {
            "status": "OK",
            "routes": [
                {
                    "overview_polyline": {"points": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                    "legs": [{"distance": {"value": 5300}, "duration": {"value": 720}}],
                }
            ],
        }


class _ClienteFalso:
    """Reemplaza `httpx.AsyncClient` SOLO dentro del namespace de
    `viajes.service` (`monkeypatch.setattr(viajes_service, "httpx", ...)`),
    nunca la clase real — parchear `httpx.AsyncClient` globalmente rompe el
    `client` de pruebas de FastAPI, que también es un httpx.AsyncClient por
    debajo (hallazgo real durante la escritura de este test)."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None):
        if _ClienteFalso.falla:
            raise _ClienteFalso.falla
        return _RespuestaFalsa()

    falla: Exception | None = None


class _HttpxFalso:
    import httpx as _httpx_real

    AsyncClient = _ClienteFalso
    HTTPError = _httpx_real.HTTPError


async def test_estimacion_ruta_con_respuesta_real_de_google(client, db, monkeypatch):
    from src.integraciones import service as integraciones_service
    from src.viajes import service as viajes_service

    class _SettingsConKey:
        google_maps_api_key = "fake-key-para-test"

    _ClienteFalso.falla = None
    monkeypatch.setattr(integraciones_service, "get_settings", lambda: _SettingsConKey())
    monkeypatch.setattr(viajes_service, "httpx", _HttpxFalso)
    headers = await _pasajero_headers(db, usuario_id="p7", telefono="+593960000007")

    resp = await client.get(
        "/viajes/estimacion-ruta?origen_lat=-0.18&origen_lon=-78.46&destino_lat=-0.19&destino_lon=-78.47",
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["origen_directions"] is True
    assert body["distancia_km"] == 5.3
    assert body["duracion_min"] == 12.0
    assert len(body["ruta"]) > 2


async def test_estimacion_ruta_google_falla_cae_a_linea_recta(client, db, monkeypatch):
    import httpx

    from src.integraciones import service as integraciones_service
    from src.viajes import service as viajes_service

    class _SettingsConKey:
        google_maps_api_key = "fake-key-para-test"

    _ClienteFalso.falla = httpx.ConnectTimeout("simulado")
    monkeypatch.setattr(integraciones_service, "get_settings", lambda: _SettingsConKey())
    monkeypatch.setattr(viajes_service, "httpx", _HttpxFalso)
    headers = await _pasajero_headers(db, usuario_id="p8", telefono="+593960000008")

    resp = await client.get(
        "/viajes/estimacion-ruta?origen_lat=-0.18&origen_lon=-78.46&destino_lat=-0.19&destino_lon=-78.47",
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["origen_directions"] is False
