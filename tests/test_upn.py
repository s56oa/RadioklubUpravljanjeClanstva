import re

from app.auth import hash_geslo
from app.models import Uporabnik, Clan, Nastavitev
from app.upn import _znesek_v_cente, _kontrolna_vsota, _upn_vsebina, generiraj_upn_svg
from app.config import get_clanarina_zneski


# ---------------------------------------------------------------------------
# Unit testi – UPN format
# ---------------------------------------------------------------------------

def test_znesek_v_cente_normalen():
    assert _znesek_v_cente(25.0) == "00000002500"


def test_znesek_v_cente_decimalen():
    assert _znesek_v_cente(12.50) == "00000001250"


def test_znesek_v_cente_brez():
    assert _znesek_v_cente(None) == ""
    assert _znesek_v_cente(0) == ""


def test_upn_vsebina_struktura():
    vsebina = _upn_vsebina(
        ime_placnika="Janez Novak",
        ulica_placnika="Testna 1",
        kraj_placnika="1000 Ljubljana",
        iban_prejemnika="SI56610000021234567",
        referenca="SI00 5-2026",
        ime_prejemnika="Radio klub",
        ulica_prejemnika="Klubska 2",
        kraj_prejemnika="6250 Ilirska Bistrica",
        opis="Članarina 2026",
        znesek_eur=25.0,
        namen="OTHR",
    )
    vrstice = vsebina.split("\n")
    assert vrstice[0] == "UPNQR"
    assert vrstice[5] == "Janez Novak"       # 6 – ime plačnika
    assert vrstice[8] == "00000002500"        # 9 – znesek
    assert vrstice[10] == ""                  # 11 – nujno (vedno prazno)
    assert vrstice[11] == "OTHR"              # 12 – koda namena
    assert vrstice[12] == "Članarina 2026"    # 13 – namen/opis plačila
    assert vrstice[13] == ""                  # 14 – rok plačila deadline (vedno prazno)
    assert vrstice[14] == "SI56610000021234567"  # 15 – IBAN prejemnika brez presledkov
    assert vrstice[15] == "SI00 5-2026"       # 16 – referenca
    assert vrstice[18] == "6250 Ilirska Bistrica"  # 19 – kraj prejemnika (zadnje)
    assert vsebina.endswith("\n")             # trailing \n doda prazen [19]


def test_upn_vsebina_iban_brez_presledkov():
    vsebina = _upn_vsebina(
        ime_placnika="Test",
        ulica_placnika="",
        kraj_placnika="",
        iban_prejemnika="SI56 6100 0002 1234 567",  # z presledki
        referenca="SI00 5-2026",
        ime_prejemnika="Klub",
        ulica_prejemnika="",
        kraj_prejemnika="",
        opis="Test",
    )
    vrstice = vsebina.split("\n")
    assert " " not in vrstice[14]  # 15 – IBAN prejemnika brez presledkov


def test_upn_vsebina_obreži_predolga_polja():
    vsebina = _upn_vsebina(
        ime_placnika="A" * 50,   # > 33
        ulica_placnika="",
        kraj_placnika="",
        iban_prejemnika="",
        referenca="",
        ime_prejemnika="",
        ulica_prejemnika="",
        kraj_prejemnika="",
        opis="B" * 50,           # > 42
    )
    vrstice = vsebina.split("\n")
    assert len(vrstice[5]) == 33   # 6 – ime plačnika
    assert len(vrstice[12]) == 42  # 13 – namen/opis plačila


def test_kontrolna_vsota_format():
    vsota = _kontrolna_vsota("TEST\n")
    assert len(vsota) == 3
    assert vsota.isdigit()


def test_kontrolna_vsota_vrednost():
    # "A\n" → polja=["A"], vsota dolžin=1, rezultat=19+1=20 → "020"
    assert _kontrolna_vsota("A\n") == "020"


def test_generiraj_upn_svg_vrne_svg():
    svg = generiraj_upn_svg(
        ime_placnika="Janez Novak",
        ulica_placnika="Testna 1",
        kraj_placnika="1000 Ljubljana",
        iban_prejemnika="SI56610000021234567",
        referenca="SI00 5-2026",
        ime_prejemnika="Radio klub",
        ulica_prejemnika="Klubska 2",
        kraj_prejemnika="6250 Ilirska Bistrica",
        opis="Članarina 2026",
        znesek_eur=25.0,
    )
    assert svg.startswith("<?xml") or "<svg" in svg
    assert "svg" in svg.lower()


# ---------------------------------------------------------------------------
# Unit testi – config.get_clanarina_zneski
# ---------------------------------------------------------------------------

def test_get_clanarina_zneski(db):
    db.add(Nastavitev(
        kljuc="clanarina_zneski",
        vrednost="Osebni=25.00\nMladi=10.00\nDružinski=35.00",
    ))
    db.commit()
    zneski = get_clanarina_zneski(db)
    assert zneski["Osebni"] == 25.0
    assert zneski["Mladi"] == 10.0
    assert zneski["Družinski"] == 35.0


def test_get_clanarina_zneski_prazno(db):
    assert get_clanarina_zneski(db) == {}


# ---------------------------------------------------------------------------
# HTTP testi – /upn endpoint
# ---------------------------------------------------------------------------

def _login(client, db):
    u = Uporabnik(
        uporabnisko_ime="testuser",
        geslo_hash=hash_geslo("Veljavno1234!ab"),
        vloga="admin",
        ime_priimek="Test User",
        aktiven=True,
    )
    db.add(u)
    db.commit()
    resp = client.get("/login")
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    client.post("/login", data={
        "csrf_token": match.group(1),
        "uporabnisko_ime": "testuser",
        "geslo": "Veljavno1234!ab",
    }, follow_redirects=False)


def _nov_clan(db):
    c = Clan(priimek="Novak", ime="Janez", tip_clanstva="Osebni", aktiven=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_upn_endpoint_vrne_svg(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    resp = client.get(f"/upn/{clan.id}/2026")
    assert resp.status_code == 200
    assert "svg" in resp.headers["content-type"]
    assert "svg" in resp.text.lower()


def test_upn_endpoint_brez_seje(client, db):
    clan = _nov_clan(db)
    resp = client.get(f"/upn/{clan.id}/2026", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_upn_endpoint_neobstojeci_clan(client, db):
    _login(client, db)
    resp = client.get("/upn/9999/2026", follow_redirects=False)
    assert resp.status_code == 302
    assert "/clani" in resp.headers["location"]


def test_upn_endpoint_z_zneskom(client, db):
    _login(client, db)
    clan = _nov_clan(db)
    db.add(Nastavitev(kljuc="clanarina_zneski", vrednost="Osebni=25.00"))
    db.commit()
    resp = client.get(f"/upn/{clan.id}/2026")
    assert resp.status_code == 200
    assert "svg" in resp.text.lower()
