from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-int-1", telefono="+593900001100", roles=["admin_sistema"])
    return auth_headers("admin-int-1", ["admin_sistema"])


async def test_solo_admin_sistema_gestiona_credenciales(client, db):
    await crear_usuario_activo(
        db, usuario_id="cumpl-int-1", telefono="+593900001101", roles=["supervisor_cumplimiento"]
    )
    headers = auth_headers("cumpl-int-1", ["supervisor_cumplimiento"])

    resp = await client.post("/integraciones/credenciales", headers=headers, json={"nombre": "Municipio"})
    assert resp.status_code == 403


async def test_crear_credencial_devuelve_el_secreto_una_sola_vez(client, db):
    headers = await _admin(db)

    creada = await client.post(
        "/integraciones/credenciales",
        headers=headers,
        json={"nombre": "Municipio de Quevedo", "alcance": "indicadores de servicio"},
    )
    assert creada.status_code == 201
    body = creada.json()
    assert len(body["secreto"]) > 20

    listado = await client.get("/integraciones/credenciales", headers=headers)
    assert listado.status_code == 200
    items = listado.json()
    assert len(items) == 1
    assert "secreto" not in items[0]
    assert "hash_secreto" not in items[0]
    assert items[0]["usos_registrados"] == 0
    assert items[0]["revocada"] is False

    evento = await db.bitacora.find_one({"accion": "INTEGRACION_CREDENCIAL_CREACION", "entidad_id": body["id"]})
    assert evento is not None
    assert evento["datos_posteriores"]["nombre"] == "Municipio de Quevedo"

    doc = await db.credenciales_integracion.find_one({"_id": body["id"]})
    assert doc["hash_secreto"] != body["secreto"]


async def test_revocar_credencial_es_inmediata_y_no_se_puede_revocar_dos_veces(client, db):
    headers = await _admin(db)
    creada = await client.post("/integraciones/credenciales", headers=headers, json={"nombre": "Prueba"})
    credencial_id = creada.json()["id"]

    revocada = await client.post(f"/integraciones/credenciales/{credencial_id}/revocar", headers=headers)
    assert revocada.status_code == 200
    assert revocada.json()["revocada"] is True
    assert revocada.json()["vigente_hasta"] is not None

    de_nuevo = await client.post(f"/integraciones/credenciales/{credencial_id}/revocar", headers=headers)
    assert de_nuevo.status_code == 409
    assert de_nuevo.json()["code"] == "CREDENCIAL_YA_REVOCADA"

    evento = await db.bitacora.find_one({"accion": "INTEGRACION_CREDENCIAL_REVOCACION", "entidad_id": credencial_id})
    assert evento["datos_previos"] == {"revocada": False}
    assert evento["datos_posteriores"]["revocada"] is True


async def test_revocar_credencial_inexistente_devuelve_404(client, db):
    headers = await _admin(db)
    resp = await client.post("/integraciones/credenciales/no-existe/revocar", headers=headers)
    assert resp.status_code == 404


async def test_servicios_externos_google_maps_sin_configurar(client, db):
    headers = await _admin(db)
    resp = await client.get("/integraciones/servicios-externos", headers=headers)

    assert resp.status_code == 200
    servicios = {s["nombre"]: s for s in resp.json()}
    assert set(servicios) == {"google_maps", "sms", "s3"}
    assert servicios["sms"]["estado"] == "no_configurado"
    assert servicios["s3"]["estado"] == "no_configurado"
    # Sin env var ni override en Mongo en el entorno de test -> no_configurado.
    assert servicios["google_maps"]["estado"] == "no_configurado"


async def test_rotar_google_maps_key_tiene_efecto_real_sin_reiniciar(client, db):
    from src.integraciones.service import obtener_google_maps_api_key

    headers = await _admin(db)
    resp = await client.post(
        "/integraciones/servicios-externos/google_maps/rotar", headers=headers, json={"api_key": "AIzaClaveDePrueba123"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "activo"
    assert resp.json()["key_enmascarada"] == "••••a123"

    # La key real (no la enmascarada) queda disponible para el resto del
    # sistema de inmediato -- lo mismo que consulta viajes/service.py.
    key_real = await obtener_google_maps_api_key(db)
    assert key_real == "AIzaClaveDePrueba123"

    listado = await client.get("/integraciones/servicios-externos", headers=headers)
    google = next(s for s in listado.json() if s["nombre"] == "google_maps")
    assert google["estado"] == "activo"

    evento = await db.bitacora.find_one({"accion": "INTEGRACION_SERVICIO_ROTACION"})
    assert evento is not None
    assert evento["datos_posteriores"]["key_enmascarada"] == "••••a123"
