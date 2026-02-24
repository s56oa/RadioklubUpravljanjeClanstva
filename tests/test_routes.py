import re

from app.auth import hash_geslo
from app.models import Uporabnik


def test_get_login(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_get_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_clani_brez_seje(client):
    resp = client.get("/clani", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_login_ok(client, db):
    # Ročno ustvari admin uporabnika (lifespan ne teče nad testno DB)
    u = Uporabnik(
        uporabnisko_ime="testadmin",
        geslo_hash=hash_geslo("Veljavno1234!ab"),
        vloga="admin",
        ime_priimek="Test Admin",
        aktiven=True,
    )
    db.add(u)
    db.commit()

    # Pridobi CSRF token iz GET /login
    resp = client.get("/login")
    assert resp.status_code == 200
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    assert match, "CSRF token not found in login form"
    csrf_token = match.group(1)

    # Pošlji login z CSRF tokenom
    resp = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "uporabnisko_ime": "testadmin",
            "geslo": "Veljavno1234!ab",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/clani" in resp.headers["location"]


def test_login_fail(client):
    # Pridobi CSRF token
    resp = client.get("/login")
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    assert match
    csrf_token = match.group(1)

    resp = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "uporabnisko_ime": "neobstaja",
            "geslo": "napacnoGeslo123!",
        },
        follow_redirects=False,
    )
    # Ostane na /login s statusom 200
    assert resp.status_code == 200
