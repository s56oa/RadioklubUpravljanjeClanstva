import re
from datetime import date

from app.auth import hash_geslo
from app.models import Uporabnik, Clan, Clanarina, Aktivnost


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _login(client, db, vloga="admin"):
    """Ustvari testnega uporabnika in ga prijavi. Vrne ime."""
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
# Osnovni testi
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Testi za /aktivnosti
# ---------------------------------------------------------------------------

def test_get_aktivnosti_brez_seje(client):
    resp = client.get("/aktivnosti", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_get_aktivnosti_z_sejo(client, db):
    _login(client, db)
    resp = client.get("/aktivnosti")
    assert resp.status_code == 200
    assert "Evidenca aktivnosti" in resp.text


def test_get_aktivnosti_filtri(client, db):
    _login(client, db)
    for filtr in ("leto", "2leti", "10let", "vse"):
        resp = client.get(f"/aktivnosti?filter={filtr}")
        assert resp.status_code == 200


def test_get_aktivnosti_z_podatki(client, db):
    _login(client, db)
    # Ustvari testnega člana in aktivnost
    clan = Clan(priimek="Testni", ime="Član", tip_clanstva="Osebni", aktiven=True)
    db.add(clan)
    db.commit()
    db.refresh(clan)
    akt = Aktivnost(clan_id=clan.id, leto=date.today().year, opis="Testna aktivnost", delovne_ure=2.0)
    db.add(akt)
    db.commit()

    resp = client.get("/aktivnosti?filter=leto")
    assert resp.status_code == 200
    assert "Testna aktivnost" in resp.text
    assert "Testni" in resp.text


# ---------------------------------------------------------------------------
# Testi za /clanarine
# ---------------------------------------------------------------------------

def test_get_clanarine_brez_seje(client):
    resp = client.get("/clanarine", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_get_clanarine_z_sejo(client, db):
    _login(client, db)
    resp = client.get("/clanarine")
    assert resp.status_code == 200
    assert "Evidenca plačil" in resp.text


def test_get_clanarine_filtri(client, db):
    _login(client, db)
    for filtr in ("leto", "2leti", "10let", "vse"):
        resp = client.get(f"/clanarine?filter={filtr}")
        assert resp.status_code == 200


def test_get_clanarine_z_podatki(client, db):
    _login(client, db)
    clan = Clan(priimek="Plačnik", ime="Janez", tip_clanstva="Osebni", aktiven=True)
    db.add(clan)
    db.commit()
    db.refresh(clan)
    c = Clanarina(
        clan_id=clan.id,
        leto=date.today().year,
        datum_placila=date.today(),
        znesek="25.00",
    )
    db.add(c)
    db.commit()

    resp = client.get("/clanarine?filter=leto")
    assert resp.status_code == 200
    assert "Plačnik" in resp.text


# ---------------------------------------------------------------------------
# Testi za /dashboard
# ---------------------------------------------------------------------------

def test_get_dashboard_brez_seje(client):
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_get_dashboard_z_sejo(client, db):
    _login(client, db)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "dashboard" in resp.text.lower()


def test_get_dashboard_z_clani(client, db):
    _login(client, db)
    # Ustvari testne podatke
    for priimek in ("Alfa", "Beta", "Gama"):
        c = Clan(priimek=priimek, ime="Test", tip_clanstva="Osebni", aktiven=True)
        db.add(c)
    db.commit()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    # Stat cards should show counts
    assert "3" in resp.text


# ---------------------------------------------------------------------------
# Testi za neplačniki filter na /clani
# ---------------------------------------------------------------------------

def test_clani_filter_leto_placila(client, db):
    _login(client, db)
    clan = Clan(priimek="Tester", ime="Filter", tip_clanstva="Osebni", aktiven=True)
    db.add(clan)
    db.commit()
    db.refresh(clan)

    leto_zdaj = date.today().year
    c = Clanarina(
        clan_id=clan.id,
        leto=leto_zdaj,
        datum_placila=date.today(),
        znesek="25.00",
    )
    db.add(c)
    db.commit()

    # Filter na plačane za tekoče leto
    resp = client.get(f"/clani?placal=da&leto_placila={leto_zdaj}")
    assert resp.status_code == 200
    assert "Tester" in resp.text

    # Filter na neplačane za tekoče leto – clan je plačal, ne sme biti prikazan
    resp = client.get(f"/clani?placal=ne&leto_placila={leto_zdaj}")
    assert resp.status_code == 200
    assert "Tester" not in resp.text

    # Filter na neplačane za preteklo leto – ni plačila, mora biti prikazan
    resp = client.get(f"/clani?placal=ne&leto_placila={leto_zdaj - 1}")
    assert resp.status_code == 200
    assert "Tester" in resp.text
