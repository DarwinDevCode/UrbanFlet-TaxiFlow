from tests.utils import auth_headers, crear_usuario_activo


async def _pasajero(db, usuario_id="pasajero-dir-1", telefono="+593900004000"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono=telefono, roles=["pasajero"])
    return auth_headers(usuario_id, ["pasajero"])


def _direccion_json(etiqueta="Casa", direccion="Dirección de prueba"):
    return {"etiqueta": etiqueta, "direccion": direccion, "lat": -1.0, "lon": -79.4}


async def test_listar_direcciones_vacio_por_defecto(client, db):
    headers = await _pasajero(db)

    resp = await client.get("/direcciones", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_crear_y_listar_direccion(client, db):
    headers = await _pasajero(db)

    creada = await client.post(
        "/direcciones", headers=headers, json=_direccion_json(direccion="Av. Siempre Viva 123")
    )
    assert creada.status_code == 201
    assert creada.json()["etiqueta"] == "Casa"

    listado = await client.get("/direcciones", headers=headers)
    assert listado.status_code == 200
    assert len(listado.json()) == 1
    assert listado.json()[0]["direccion"] == "Av. Siempre Viva 123"


async def test_eliminar_direccion_propia(client, db):
    headers = await _pasajero(db)
    creada = await client.post(
        "/direcciones", headers=headers, json=_direccion_json(etiqueta="Trabajo", direccion="Oficina Central")
    )
    direccion_id = creada.json()["id"]

    resp = await client.delete(f"/direcciones/{direccion_id}", headers=headers)
    assert resp.status_code == 204

    listado = await client.get("/direcciones", headers=headers)
    assert listado.json() == []


async def test_no_puede_eliminar_direccion_de_otro_pasajero(client, db):
    headers_a = await _pasajero(db, usuario_id="pasajero-dir-a", telefono="+593900004001")
    headers_b = await _pasajero(db, usuario_id="pasajero-dir-b", telefono="+593900004002")
    creada = await client.post("/direcciones", headers=headers_a, json=_direccion_json(direccion="Casa de A"))
    direccion_id = creada.json()["id"]

    resp = await client.delete(f"/direcciones/{direccion_id}", headers=headers_b)
    assert resp.status_code == 404

    listado_a = await client.get("/direcciones", headers=headers_a)
    assert len(listado_a.json()) == 1


async def test_limite_de_direcciones_favoritas(client, db):
    headers = await _pasajero(db)
    for i in range(10):
        payload = _direccion_json(etiqueta="Otro", direccion=f"Lugar {i}")
        resp = await client.post("/direcciones", headers=headers, json=payload)
        assert resp.status_code == 201

    excedente = await client.post(
        "/direcciones", headers=headers, json=_direccion_json(etiqueta="Otro", direccion="Lugar 11")
    )
    assert excedente.status_code == 409
    assert excedente.json()["code"] == "LIMITE_DIRECCIONES_ALCANZADO"


async def test_solo_pasajero_puede_usar_direcciones_favoritas(client, db):
    await crear_usuario_activo(db, usuario_id="conductor-dir-1", telefono="+593900004003", roles=["conductor"])
    headers = auth_headers("conductor-dir-1", ["conductor"])

    resp = await client.get("/direcciones", headers=headers)
    assert resp.status_code == 403


async def test_anonimizar_cuenta_purga_direcciones_favoritas(client, db):
    await crear_usuario_activo(db, usuario_id="admin-dir-1", telefono="+593900004004", roles=["admin_sistema"])
    headers_admin = auth_headers("admin-dir-1", ["admin_sistema"])
    headers_pasajero = await _pasajero(db, usuario_id="pasajero-dir-anon", telefono="+593900004005")

    await client.post("/direcciones", headers=headers_pasajero, json=_direccion_json(direccion="Casa Real"))
    assert (await db.direcciones_favoritas.count_documents({"usuario_id": "pasajero-dir-anon"})) == 1

    resp = await client.post(
        "/usuarios/pasajero-dir-anon/anonimizar", headers=headers_admin, json={"confirmacion": "ANONIMIZAR"}
    )
    assert resp.status_code == 200

    assert (await db.direcciones_favoritas.count_documents({"usuario_id": "pasajero-dir-anon"})) == 0
