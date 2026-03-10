"""Testi za /clani router – vključno z iskanje endpoint."""
import re

from app.auth import hash_geslo
from app.models import Uporabnik, Clan


def _login(client, db, vloga="urednik"):
    """Ustvari testnega uporabnika, ga prijavi."""
    u = Uporabnik(
        uporabnisko_ime="testuser",
        geslo_hash=hash_geslo("Veljavno1234!ab"),
        vloga=vloga,
        ime_priimek="Test User",
        aktiven=True,
    )
    db.add(u)
    db.commit()

    resp = client.get("/login")
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    csrf_token = match.group(1)
    client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "uporabnisko_ime": "testuser",
            "geslo": "Veljavno1234!ab",
        },
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Testi za /clani/iskanje
# ---------------------------------------------------------------------------

def test_iskanje_po_imenu(client, db):
    _login(client, db)
    c = Clan(priimek="Novak", ime="Janez", tip_clanstva="Osebni", aktiven=True)
    db.add(c)
    db.commit()
    resp = client.get("/clani/iskanje?q=Nov")
    assert resp.status_code == 200
    assert any(r["priimek"] == "Novak" for r in resp.json())


def test_iskanje_po_klicnem_znaku(client, db):
    _login(client, db)
    c = Clan(priimek="Kos", ime="Ana", klicni_znak="S56OA", tip_clanstva="Osebni", aktiven=True)
    db.add(c)
    db.commit()
    resp = client.get("/clani/iskanje?q=S56")
    assert resp.status_code == 200
    assert any(r["klicni_znak"] == "S56OA" for r in resp.json())


def test_iskanje_brez_seje(client, db):
    resp = client.get("/clani/iskanje?q=Jan", follow_redirects=False)
    assert resp.status_code in (302, 401)
