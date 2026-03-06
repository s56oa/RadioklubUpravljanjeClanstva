import re
from datetime import date

from app.auth import hash_geslo
from app.models import Uporabnik, Clan, Clanarina, Aktivnost


def _login_csrf(client, db, vloga="admin") -> str:
    """Ustvari uporabnika, ga prijavi in vrne svež CSRF token."""
    u = Uporabnik(
        uporabnisko_ime="testuser2",
        geslo_hash=hash_geslo("Veljavno1234!ab"),
        vloga=vloga,
        ime_priimek="Test User2",
        aktiven=True,
    )
    db.add(u)
    db.commit()
    resp = client.get("/login")
    csrf = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text).group(1)
    client.post("/login", data={"csrf_token": csrf, "uporabnisko_ime": "testuser2",
                                "geslo": "Veljavno1234!ab"}, follow_redirects=False)
    resp = client.get("/profil")
    return re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text).group(1)


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


def test_verzijska_znacka_vsebuje_verzijo(client, db):
    _login(client, db)
    resp = client.get("/clani")
    assert resp.status_code == 200
    assert "1.20" in resp.text


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


# ---------------------------------------------------------------------------
# V1: backup-excel – samo admin
# ---------------------------------------------------------------------------

def test_backup_excel_admin(client, db):
    """Admin dobi 200 in Excel vsebino."""
    _login(client, db, vloga="admin")
    resp = client.get("/izvoz/backup-excel")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers.get("content-type", "")


def test_backup_excel_urednik_zavrnjen(client, db):
    """Urednik dobi redirect – ne sme imeti dostopa."""
    _login(client, db, vloga="urednik")
    resp = client.get("/izvoz/backup-excel", follow_redirects=False)
    assert resp.status_code == 302
    assert "/izvoz" in resp.headers["location"]


def test_backup_excel_bralec_zavrnjen(client, db):
    """Bralec dobi redirect."""
    _login(client, db, vloga="bralec")
    resp = client.get("/izvoz/backup-excel", follow_redirects=False)
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# V2: clanarina izbrisi – IDOR zaščita (clan_id mora ujemati)
# ---------------------------------------------------------------------------

def test_clanarina_izbrisi_idor_blokiran(client, db):
    """Brisanje z napačnim clan_id ne izbriše clanarine drugega člana."""
    token = _login_csrf(client, db, vloga="urednik")
    clan_a = Clan(priimek="A", ime="Clan", tip_clanstva="Osebni", aktiven=True)
    clan_b = Clan(priimek="B", ime="Clan", tip_clanstva="Osebni", aktiven=True)
    db.add_all([clan_a, clan_b])
    db.commit()
    db.refresh(clan_a)
    db.refresh(clan_b)

    c = Clanarina(clan_id=clan_a.id, leto=2025, datum_placila=date(2025, 1, 1))
    db.add(c)
    db.commit()
    db.refresh(c)
    cid = c.id

    # Napadalec pošlje clan_id=clan_b.id, ampak clanarina_id pripada clan_a
    resp = client.post(
        f"/clanarine/izbrisi/{cid}",
        data={"csrf_token": token, "clan_id": clan_b.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Clanarina mora ostati – clan_id se ni ujemal
    assert db.query(Clanarina).filter(Clanarina.id == cid).first() is not None


def test_clanarina_izbrisi_pravilno(client, db):
    """Brisanje z ujemajočim clan_id uspešno zbriše clanarina."""
    token = _login_csrf(client, db, vloga="urednik")
    clan = Clan(priimek="Del", ime="Clan", tip_clanstva="Osebni", aktiven=True)
    db.add(clan)
    db.commit()
    db.refresh(clan)

    c = Clanarina(clan_id=clan.id, leto=2025, datum_placila=date(2025, 1, 1))
    db.add(c)
    db.commit()
    db.refresh(c)
    cid = c.id

    resp = client.post(
        f"/clanarine/izbrisi/{cid}",
        data={"csrf_token": token, "clan_id": clan.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.query(Clanarina).filter(Clanarina.id == cid).first() is None


# ---------------------------------------------------------------------------
# C1+C2: validacija vnosa – napačen datum / es_stevilka → 200 z napako, ne 500
# ---------------------------------------------------------------------------

def test_clan_nov_napacen_datum_rd(client, db):
    """POST /clani/nov z neveljavnim datumom RD vrne 200 z napako, ne 500."""
    token = _login_csrf(client, db, vloga="urednik")
    resp = client.post(
        "/clani/nov",
        data={
            "csrf_token": token,
            "priimek": "Test",
            "ime": "Clan",
            "tip_clanstva": "Osebni",
            "veljavnost_rd": "ni-datum",
            "es_stevilka": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Napačen format" in resp.text or "napak" in resp.text.lower()


def test_clan_nov_napacna_es_stevilka(client, db):
    """POST /clani/nov z neštevilčno E.S. številko vrne 200 z napako, ne 500."""
    token = _login_csrf(client, db, vloga="urednik")
    resp = client.post(
        "/clani/nov",
        data={
            "csrf_token": token,
            "priimek": "Test",
            "ime": "Clan",
            "tip_clanstva": "Osebni",
            "veljavnost_rd": "",
            "es_stevilka": "abc",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Napačen format" in resp.text or "napak" in resp.text.lower()
