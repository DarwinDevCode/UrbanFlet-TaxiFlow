from tests.utils import auth_headers, crear_usuario_activo


async def _admin(db):
    await crear_usuario_activo(db, usuario_id="admin-val-1", telefono="+593900000950", roles=["admin_sistema"])
    return auth_headers("admin-val-1", ["admin_sistema"])


async def test_422_de_pydantic_devuelve_codigo_y_mensaje_legible(client, db):
    """Repro exacto reportado: umbral_intentos_fallidos=1 (mínimo real es 3)
    antes devolvía `{"detail": [...]}` crudo, sin nada legible para la UI."""
    headers = await _admin(db)

    resp = await client.post(
        "/seguridad/politica-auth",
        headers=headers,
        json={
            "longitud_minima_password": 8,
            "umbral_intentos_fallidos": 1,
            "ventana_minutos": 15,
            "bloqueo_minutos": 15,
            "vigente_desde": "2026-01-01T00:00:00Z",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "umbral_intentos_fallidos" in body["message"]
    assert "3" in body["message"]
    assert body["errores"] == [{"campo": "umbral_intentos_fallidos", "mensaje": "Debe ser mayor o igual a 3"}]


async def test_422_con_varios_campos_invalidos_lista_todos(client, db):
    headers = await _admin(db)

    resp = await client.post(
        "/seguridad/politica-auth",
        headers=headers,
        json={
            "longitud_minima_password": 2,
            "umbral_intentos_fallidos": 1,
            "ventana_minutos": 15,
            "bloqueo_minutos": 15,
            "vigente_desde": "2026-01-01T00:00:00Z",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    campos = {e["campo"] for e in body["errores"]}
    assert campos == {"longitud_minima_password", "umbral_intentos_fallidos"}
    assert "2 campos" in body["message"]


async def test_422_por_campo_faltante_dice_obligatorio(client, db):
    headers = await _admin(db)

    resp = await client.post("/seguridad/politica-auth", headers=headers, json={})

    assert resp.status_code == 422
    body = resp.json()
    assert all(e["mensaje"] == "Este campo es obligatorio" for e in body["errores"])
