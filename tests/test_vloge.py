import re
from datetime import date, timedelta

from app.auth import hash_geslo
from app.models import Uporabnik, Clan, ClanVloga


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _login(client, db, vloga="admin") -> str:
    """Ustvari testnega uporabnika, ga prijavi in vrne svež CSRF token po loginu.

    session.clear() pri loginu zbriše stari _csrf_token, zato po loginu
    naredimo GET /profil, ki sproži get_csrf_token() in vrne svež token.
    """
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
    csrf_login = match.group(1)
    client.post(
        "/login",
        data={
            "csrf_token": csrf_login,
            "uporabnisko_ime": "testuser",
            "geslo": "Veljavno1234!ab",
        },
        follow_redirects=False,
    )
    # Po loginu session.clear() zbriše stari token – pridobi svežega iz /profil
    resp = client.get("/profil")
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    return match.group(1)


def _get_csrf_from_login_page(client) -> str:
    """Pridobi CSRF token iz login strani (brez prijave)."""
    resp = client.get("/login")
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    return match.group(1)


def _nov_clan(db, priimek="Testni", ime="Član"):
    c = Clan(priimek=priimek, ime=ime, tip_clanstva="Osebni", aktiven=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Prikaz vlog na strani člana
# ---------------------------------------------------------------------------

def test_detail_vsebuje_sekcijo_vloge(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    assert "Vloge in funkcije" in resp.text


def test_detail_brez_vlog_prikaze_placeholder(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    assert "Ni vpisanih vlog" in resp.text


def test_detail_prikaze_aktivno_vlogo(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    v = ClanVloga(
        clan_id=clan.id,
        naziv="Predsednik",
        datum_od=date(2020, 1, 1),
        datum_do=None,
    )
    db.add(v)
    db.commit()

    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    assert "Predsednik" in resp.text
    assert "brez poteka" in resp.text


def test_detail_prikaze_preteklo_vlogo(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    v = ClanVloga(
        clan_id=clan.id,
        naziv="Tajnik",
        datum_od=date(2015, 1, 1),
        datum_do=date(2019, 12, 31),
    )
    db.add(v)
    db.commit()

    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    assert "Tajnik" in resp.text
    assert "2019" in resp.text


def test_detail_aktivna_vloga_ima_green_badge(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    v = ClanVloga(
        clan_id=clan.id,
        naziv="Blagajnik",
        datum_od=date.today() - timedelta(days=365),
        datum_do=None,
    )
    db.add(v)
    db.commit()

    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    assert "bg-success" in resp.text


def test_detail_pretekla_vloga_ima_secondary_badge(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    v = ClanVloga(
        clan_id=clan.id,
        naziv="Predsednik NO",
        datum_od=date(2010, 1, 1),
        datum_do=date(2012, 12, 31),
    )
    db.add(v)
    db.commit()

    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    assert "bg-secondary" in resp.text


# ---------------------------------------------------------------------------
# Dodajanje vloge
# ---------------------------------------------------------------------------

def test_dodaj_vlogo_editor(client, db):
    token = _login(client, db, vloga="urednik")
    clan = _nov_clan(db)

    resp = client.post(
        "/vloge/dodaj",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Tajnik",
            "datum_od": "2022-01-01",
            "datum_do": "",
            "opombe": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert f"/clani/{clan.id}" in resp.headers["location"]

    vloga = db.query(ClanVloga).filter(ClanVloga.clan_id == clan.id).first()
    assert vloga is not None
    assert vloga.naziv == "Tajnik"
    assert vloga.datum_od == date(2022, 1, 1)
    assert vloga.datum_do is None


def test_dodaj_vlogo_z_datum_do(client, db):
    token = _login(client, db)
    clan = _nov_clan(db)

    client.post(
        "/vloge/dodaj",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Predsednik",
            "datum_od": "2018-01-01",
            "datum_do": "2022-12-31",
            "opombe": "Izvoljen na skupščini",
        },
        follow_redirects=False,
    )

    vloga = db.query(ClanVloga).filter(ClanVloga.clan_id == clan.id).first()
    assert vloga.datum_do == date(2022, 12, 31)
    assert vloga.opombe == "Izvoljen na skupščini"


def test_dodaj_vlogo_bralec_zavrnjeno(client, db):
    token = _login(client, db, vloga="bralec")
    clan = _nov_clan(db)

    resp = client.post(
        "/vloge/dodaj",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Tajnik",
            "datum_od": "2022-01-01",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Ni dodal vloge
    assert db.query(ClanVloga).filter(ClanVloga.clan_id == clan.id).count() == 0


def test_dodaj_vlogo_brez_seje(client, db):
    # Pridobi veljavni CSRF token brez prijave
    token = _get_csrf_from_login_page(client)
    clan = _nov_clan(db)
    resp = client.post(
        "/vloge/dodaj",
        data={"csrf_token": token, "clan_id": clan.id, "naziv": "Tajnik", "datum_od": "2022-01-01"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Brisanje vloge
# ---------------------------------------------------------------------------

def test_izbrisi_vlogo_admin(client, db):
    token = _login(client, db, vloga="admin")
    clan = _nov_clan(db)
    v = ClanVloga(clan_id=clan.id, naziv="Blagajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    resp = client.post(
        f"/vloge/izbrisi/{v.id}",
        data={"csrf_token": token, "clan_id": clan.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.query(ClanVloga).filter(ClanVloga.id == v.id).first() is None


def test_izbrisi_vlogo_urednik_zavrnjeno(client, db):
    token = _login(client, db, vloga="urednik")
    clan = _nov_clan(db)
    v = ClanVloga(clan_id=clan.id, naziv="Blagajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    resp = client.post(
        f"/vloge/izbrisi/{v.id}",
        data={"csrf_token": token, "clan_id": clan.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Vloga mora ostati v bazi
    assert db.query(ClanVloga).filter(ClanVloga.id == v.id).first() is not None


def test_izbrisi_vlogo_brez_seje(client, db):
    # Pridobi veljavni CSRF token brez prijave
    token = _get_csrf_from_login_page(client)
    clan = _nov_clan(db)
    v = ClanVloga(clan_id=clan.id, naziv="Tajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    resp = client.post(
        f"/vloge/izbrisi/{v.id}",
        data={"csrf_token": token, "clan_id": clan.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Kaskadno brisanje (brisanje člana zbriše tudi vloge)
# ---------------------------------------------------------------------------

def test_brisanje_clana_zbrise_vloge(db):
    clan = _nov_clan(db)
    v = ClanVloga(clan_id=clan.id, naziv="Predsednik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    vloga_id = v.id

    db.delete(clan)
    db.commit()
    assert db.query(ClanVloga).filter(ClanVloga.id == vloga_id).first() is None


# ---------------------------------------------------------------------------
# Nastavitve – vloge_clanov v dropdown
# ---------------------------------------------------------------------------

def test_detail_vsebuje_vloge_clanov_v_dropdownu(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    # Privzete vloge morajo biti v selectu
    assert "Predsednik" in resp.text
    assert "Blagajnik" in resp.text
    assert "Častni član" in resp.text


# ---------------------------------------------------------------------------
# C1: validacija datuma – napačen format → redirect, ne 500
# ---------------------------------------------------------------------------

def test_dodaj_vlogo_napacen_datum_od(client, db):
    """POST /vloge/dodaj z neveljavnim datum_od → redirect, vloga ni dodana."""
    token = _login(client, db, vloga="urednik")
    clan = _nov_clan(db)
    resp = client.post(
        "/vloge/dodaj",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Tajnik",
            "datum_od": "ni-datum",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Vloga ne sme biti dodana
    assert db.query(ClanVloga).filter(ClanVloga.clan_id == clan.id).count() == 0


def test_dodaj_vlogo_napacen_datum_do(client, db):
    """POST /vloge/dodaj z veljavnim datum_od in neveljavnim datum_do → redirect, vloga ni dodana."""
    token = _login(client, db, vloga="urednik")
    clan = _nov_clan(db)
    resp = client.post(
        "/vloge/dodaj",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Tajnik",
            "datum_od": "2022-01-01",
            "datum_do": "ni-datum",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.query(ClanVloga).filter(ClanVloga.clan_id == clan.id).count() == 0


# ---------------------------------------------------------------------------
# Urejanje vloge
# ---------------------------------------------------------------------------

def test_uredi_vlogo_post(client, db):
    """POST /vloge/{id}/uredi → posodobi vrednosti v DB in preusmeri."""
    token = _login(client, db, vloga="urednik")
    clan = _nov_clan(db)
    v = ClanVloga(clan_id=clan.id, naziv="Tajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    resp = client.post(
        f"/vloge/{v.id}/uredi",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Blagajnik",
            "datum_od": "2021-03-01",
            "datum_do": "2023-12-31",
            "opombe": "Sprememba",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert f"/clani/{clan.id}" in resp.headers["location"]

    db.refresh(v)
    assert v.naziv == "Blagajnik"
    assert v.datum_od == date(2021, 3, 1)
    assert v.datum_do == date(2023, 12, 31)
    assert v.opombe == "Sprememba"


def test_uredi_vlogo_neveljavni_datum(client, db):
    """POST /vloge/{id}/uredi z napačnim datumom → redirect (ne 500), vrednosti nespremenjene."""
    token = _login(client, db, vloga="urednik")
    clan = _nov_clan(db)
    v = ClanVloga(clan_id=clan.id, naziv="Tajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    resp = client.post(
        f"/vloge/{v.id}/uredi",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Predsednik",
            "datum_od": "ni-datum",
            "datum_do": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.refresh(v)
    assert v.naziv == "Tajnik"  # ni spremenjen


def test_uredi_vlogo_brez_pravic(client, db):
    """Bralec ne sme urejati vloge → redirect, vrednosti nespremenjene."""
    token = _login(client, db, vloga="bralec")
    clan = _nov_clan(db)
    v = ClanVloga(clan_id=clan.id, naziv="Tajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    resp = client.post(
        f"/vloge/{v.id}/uredi",
        data={
            "csrf_token": token,
            "clan_id": clan.id,
            "naziv": "Predsednik",
            "datum_od": "2021-01-01",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.refresh(v)
    assert v.naziv == "Tajnik"  # ni spremenjen


# ---------------------------------------------------------------------------
# IDOR zaščita
# ---------------------------------------------------------------------------

def test_uredi_vlogo_idor_blokiran(client, db):
    """Urednik ne sme urejati vloge, ki ne pripada podanemu clan_id (IDOR zaščita)."""
    token = _login(client, db, vloga="urednik")
    clan_a = _nov_clan(db, "ClanA", "Test")
    clan_b = _nov_clan(db, "ClanB", "Test")
    v = ClanVloga(clan_id=clan_a.id, naziv="Tajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    # Pošljemo pravilen vloga_id, a napačen clan_id (clan_b namesto clan_a)
    resp = client.post(
        f"/vloge/{v.id}/uredi",
        data={
            "csrf_token": token,
            "clan_id": clan_b.id,
            "naziv": "Predsednik",
            "datum_od": "2022-01-01",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db.refresh(v)
    assert v.naziv == "Tajnik"  # ni spremenjen


def test_izbrisi_vlogo_idor_blokiran(client, db):
    """Admin ne sme brisati vloge drugega člana z napačnim clan_id (IDOR zaščita)."""
    token = _login(client, db, vloga="admin")
    clan_a = _nov_clan(db, "ClanA", "Test")
    clan_b = _nov_clan(db, "ClanB", "Test")
    v = ClanVloga(clan_id=clan_a.id, naziv="Blagajnik", datum_od=date(2020, 1, 1))
    db.add(v)
    db.commit()
    db.refresh(v)

    # Pošljemo pravilen vloga_id, a napačen clan_id
    resp = client.post(
        f"/vloge/izbrisi/{v.id}",
        data={"csrf_token": token, "clan_id": clan_b.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Vloga mora ostati v bazi
    assert db.query(ClanVloga).filter(ClanVloga.id == v.id).first() is not None
