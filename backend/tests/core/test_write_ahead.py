"""Verifica el contrato de write-ahead (CU-O17) de punta a punta, a través de
un endpoint real, no solo a nivel de la función `write_audit_event` (eso ya
lo cubre tests/core/test_audit.py). Si la bitácora no puede escribirse, el
efecto de negocio no debe ejecutarse en absoluto."""

from pymongo.errors import PyMongoError


async def test_bitacora_caida_impide_el_efecto_de_negocio_en_registro(client, db, monkeypatch):
    async def _insert_one_falla(*args, **kwargs):
        raise PyMongoError("Mongo caído")

    # Se parchea a nivel de clase: cada `db.bitacora` devuelve una instancia
    # nueva de Collection (ver nota equivalente en tests/core/test_audit.py).
    monkeypatch.setattr(type(db.bitacora), "insert_one", _insert_one_falla)

    resp = await client.post(
        "/auth/registro",
        json={"nombre": "Nunca Creado", "telefono": "+593900200300", "password": "clave-larga-123"},
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"

    usuario = await db.usuarios.find_one({"telefono": "+593900200300"})
    assert usuario is None, "el registro no debe persistirse si la bitácora falló (write-ahead)"
