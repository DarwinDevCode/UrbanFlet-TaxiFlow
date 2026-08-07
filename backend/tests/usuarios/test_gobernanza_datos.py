from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-gob-1", telefono="+593900000800", roles=["admin_sistema"])
    return auth_headers("admin-gob-1", ["admin_sistema"])


async def _crear_usuario_a_anonimizar(db, headers, client) -> str:
    resp = await client.post(
        "/usuarios",
        headers=headers,
        json={
            "nombre": "Persona Real Con Datos",
            "telefono": "+593900000801",
            "email": "persona.real@example.com",
            "password": "clave-larga-123",
            "roles": ["jefe_mantenimiento"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_anonimizar_requiere_admin_sistema(client, db):
    await crear_usuario_activo(
        db, usuario_id="cumpl-gob-1", telefono="+593900000802", roles=["supervisor_cumplimiento"]
    )
    headers_no_admin = auth_headers("cumpl-gob-1", ["supervisor_cumplimiento"])
    headers_admin = await _admin(db)
    usuario_id = await _crear_usuario_a_anonimizar(db, headers_admin, client)

    resp = await client.post(
        f"/usuarios/{usuario_id}/anonimizar", headers=headers_no_admin, json={"confirmacion": "ANONIMIZAR"}
    )
    assert resp.status_code == 403


async def test_anonimizar_exige_el_texto_de_confirmacion_exacto(client, db):
    headers = await _admin(db)
    usuario_id = await _crear_usuario_a_anonimizar(db, headers, client)

    resp = await client.post(f"/usuarios/{usuario_id}/anonimizar", headers=headers, json={"confirmacion": "si"})
    assert resp.status_code == 422


async def test_anonimizar_purga_datos_personales_y_es_irreversible(client, db):
    headers = await _admin(db)
    usuario_id = await _crear_usuario_a_anonimizar(db, headers, client)

    resp = await client.post(f"/usuarios/{usuario_id}/anonimizar", headers=headers, json={"confirmacion": "ANONIMIZAR"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["nombre"] == f"Usuario Anonimizado {usuario_id[:8]}"
    assert body["telefono"] is None
    assert body["email"] is None
    assert body["anonimizado"] is True

    doc = await db.usuarios.find_one({"_id": usuario_id})
    assert "telefono" not in doc
    assert "email" not in doc
    assert doc["nombre"] != "Persona Real Con Datos"

    # Idempotente-protegido: no se puede anonimizar dos veces (no hay
    # operación inversa, ni endpoint que la ofrezca).
    de_nuevo = await client.post(
        f"/usuarios/{usuario_id}/anonimizar", headers=headers, json={"confirmacion": "ANONIMIZAR"}
    )
    assert de_nuevo.status_code == 409


async def test_evento_de_anonimizacion_no_expone_el_dato_personal_purgado(client, db):
    headers = await _admin(db)
    usuario_id = await _crear_usuario_a_anonimizar(db, headers, client)

    await client.post(f"/usuarios/{usuario_id}/anonimizar", headers=headers, json={"confirmacion": "ANONIMIZAR"})

    evento = await db.bitacora.find_one({"accion": "USUARIO_ANONIMIZACION", "entidad_id": usuario_id})
    assert evento is not None
    assert evento["datos_previos"] == {"anonimizado": False}
    assert evento["datos_posteriores"]["anonimizado"] is True
    # El evento documenta que ocurrió, nunca el nombre/teléfono/correo real
    # que se está purgando -- `bitacora` es insert-only y ese evento
    # quedaría para siempre, derrotando el propósito de la anonimización.
    contenido_evento = str(evento)
    assert "Persona Real Con Datos" not in contenido_evento
    assert "+593900000801" not in contenido_evento
    assert "persona.real@example.com" not in contenido_evento


async def test_politica_retencion_reporta_ttl_real_de_posiciones(client, db):
    headers = await _admin(db)

    resp = await client.get("/sistema/politica-retencion", headers=headers)

    assert resp.status_code == 200
    items = {i["coleccion"]: i for i in resp.json()}
    assert items["posiciones"]["fuente"] == "indice_ttl_real"
    assert "7 días" in items["posiciones"]["retencion"]
    assert items["bitacora"]["fuente"] == "documentado"
