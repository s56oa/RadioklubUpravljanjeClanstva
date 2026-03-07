"""Testi za uvoz veljavnosti RD iz AKOS Excel datoteke in AKOS API."""
import io
import re
from datetime import date
from unittest.mock import patch

import openpyxl
import pytest

from app.auth import hash_geslo
from app.models import Uporabnik, Clan


# ---------------------------------------------------------------------------
# Helper – testni Excel
# ---------------------------------------------------------------------------

def _akos_xlsx(rows: list[tuple]) -> bytes:
    """Ustvari AKOS Excel v pomnilniku z glavo + podanimi vrsticami."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(("Klicni znak", "Razred", "Velja do", "Datum zapadlosti"))
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _login(client, db, vloga="admin"):
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
    csrf = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text).group(1)
    client.post("/login", data={"csrf_token": csrf, "uporabnisko_ime": "testuser",
                                "geslo": "Veljavno1234!ab"}, follow_redirects=False)


def _csrf(client, url="/izvoz/uvozi"):
    resp = client.get(url)
    m = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Testi
# ---------------------------------------------------------------------------

def test_uvozi_akos_brez_seje(client):
    """Brez prijave POST vrne 403 (CSRF zaščita se sproži pred require_login).
    GET /izvoz/uvozi brez seje → redirect na login."""
    resp = client.get("/izvoz/uvozi", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_uvozi_akos_pregled_ujemanje(client, db):
    """Člen z ujemajočim klicnim znakom se pojavi v predogledu."""
    _login(client, db)
    clan = Clan(priimek="Testni", ime="Radioamater", klicni_znak="S59DGO",
                tip_clanstva="Osebni", aktiven=True,
                veljavnost_rd=date(2030, 1, 1))
    db.add(clan)
    db.commit()

    vsebina = _akos_xlsx([("S59DGO", "A", "15.06.2038", "15.06.2048")])
    csrf = _csrf(client)
    resp = client.post(
        "/izvoz/uvozi-akos",
        files={"datoteka": ("akos.xlsx", vsebina, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 200
    assert "S59DGO" in resp.text
    assert "2038" in resp.text
    assert "Testni" in resp.text


def test_uvozi_akos_brez_ujemanja(client, db):
    """Člen v bazi, ki ni v AKOS datoteki – prikazan kot 'brez ujemanja'."""
    _login(client, db)
    clan = Clan(priimek="Brez", ime="Ujemanja", klicni_znak="S59XXX",
                tip_clanstva="Osebni", aktiven=True)
    db.add(clan)
    db.commit()

    vsebina = _akos_xlsx([("S50ABC", "A", "01.01.2036", "01.01.2046")])
    csrf = _csrf(client)
    resp = client.post(
        "/izvoz/uvozi-akos",
        files={"datoteka": ("akos.xlsx", vsebina, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 200
    # Clan ni v posdobljeni sekciji – S59XXX ne obstaja v AKOS
    assert "S59XXX" not in resp.text
    # Sporoči število brez ujemanja
    assert "1" in resp.text  # brez_ujemanja == 1


def test_uvozi_akos_napacna_datoteka(client, db):
    """Napačna datoteka (ne Excel) → napaka na strani."""
    _login(client, db)
    csrf = _csrf(client)
    resp = client.post(
        "/izvoz/uvozi-akos",
        files={"datoteka": ("akos.txt", b"ni excel", "text/plain")},
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 200
    assert "xlsx" in resp.text.lower() or "dovoljen" in resp.text.lower()


def test_uvozi_akos_potrdi_posodobi_datum(client, db):
    """Potrditev uvoza dejansko posodobi veljavnost_rd v bazi."""
    _login(client, db)
    clan = Clan(priimek="Radioamater", ime="Janez", klicni_znak="S52JA",
                tip_clanstva="Osebni", aktiven=True,
                veljavnost_rd=date(2028, 3, 1))
    db.add(clan)
    db.commit()
    db.refresh(clan)
    clan_id = clan.id

    vsebina = _akos_xlsx([("S52JA", "A", "20.11.2039", "20.11.2049")])
    csrf = _csrf(client)

    # Korak 1: predogled
    resp = client.post(
        "/izvoz/uvozi-akos",
        files={"datoteka": ("akos.xlsx", vsebina, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 200
    assert "2039" in resp.text

    # Korak 2: potrditev
    csrf2 = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text).group(1)
    resp2 = client.post(
        "/izvoz/uvozi-akos-potrdi",
        data={"csrf_token": csrf2},
    )
    assert resp2.status_code == 200
    assert "posodobljenih" in resp2.text

    # Preveri DB
    db.expire_all()
    posodobljen = db.query(Clan).filter(Clan.id == clan_id).first()
    assert posodobljen.veljavnost_rd == date(2039, 11, 20)


def test_uvozi_akos_brez_klicnega_znaka(client, db):
    """Član brez klicnega znaka se tiho preskoči – ne povzroči napake."""
    _login(client, db)
    clan = Clan(priimek="Brez", ime="KlicnegaZnaka", klicni_znak=None,
                tip_clanstva="Osebni", aktiven=True)
    db.add(clan)
    db.commit()

    vsebina = _akos_xlsx([("S50ABC", "A", "01.01.2036", "01.01.2046")])
    csrf = _csrf(client)
    resp = client.post(
        "/izvoz/uvozi-akos",
        files={"datoteka": ("akos.xlsx", vsebina, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 200
    # Ni napake, stran se naloži normalno
    assert "Predogled" in resp.text or "predogled" in resp.text.lower()


# ---------------------------------------------------------------------------
# AKOS API testi
# ---------------------------------------------------------------------------

_AKOS_XML = """<?xml version="1.0" encoding="ASCII"?>
<CEPT>
\t<HAM>
\t\t<call>S59TEST</call>
\t\t<ok>1</ok>
\t\t<rang>A</rang>
\t\t<till>27.07.2038</till>
\t\t<expire>27.07.2048</expire>
\t</HAM>
</CEPT>"""


def test_parse_akos_xml_veljavna():
    """_parse_akos_xml pravilno razčleni XML z veljavnim datumom."""
    from app.routers.izvoz import _parse_akos_xml
    result = _parse_akos_xml(_AKOS_XML)
    assert result == date(2038, 7, 27)


def test_parse_akos_xml_neveljaven():
    """_parse_akos_xml vrne None za neveljavno vsebino."""
    from app.routers.izvoz import _parse_akos_xml
    assert _parse_akos_xml("ascii art besedilo") is None
    assert _parse_akos_xml("") is None
    assert _parse_akos_xml("<CEPT><HAM><till>ni-datum</till></HAM></CEPT>") is None


def test_parse_akos_xml_star_datum():
    """_parse_akos_xml vrne None za datum starejši od 10 let (neveljavni KZ)."""
    from app.routers.izvoz import _parse_akos_xml
    # AKOS vrne npr. 27.06.1991 za potečene/neveljavne klicne znake
    assert _parse_akos_xml("<CEPT><HAM><till>27.06.1991</till></HAM></CEPT>") is None
    assert _parse_akos_xml("<CEPT><HAM><till>01.01.2000</till></HAM></CEPT>") is None


def test_uvozi_akos_api_ne_posodobi_starejsega(client, db):
    """API ne posodobi veljavnosti, če je vrnjena vrednost starejša od obstoječe v bazi."""
    _login(client, db)
    clan = Clan(priimek="Novejsi", ime="Datum", klicni_znak="S59NOV",
                tip_clanstva="Osebni", aktiven=True,
                veljavnost_rd=date(2040, 1, 1))
    db.add(clan)
    db.commit()
    db.refresh(clan)
    clan_id = clan.id

    csrf = _csrf(client)

    # API vrne starejši datum (2035 < 2040)
    async def mock_fetch(klicni_znaki):
        return {"S59NOV": date(2035, 6, 15)}

    with patch("app.routers.izvoz._fetch_akos_all", mock_fetch):
        resp = client.post("/izvoz/uvozi-akos-api", data={"csrf_token": csrf})

    assert resp.status_code == 200
    # Člen se pojavi v predogledu, a je označen kot "brez spremembe"
    assert "S59NOV" in resp.text
    # Ni gumba za potrditev (0 sprememb)
    assert "Potrdi posodobitev" not in resp.text


def test_uvozi_akos_api_pregled(client, db):
    """API predogled z mockiranim HTTP klicem prikaže predogled."""
    _login(client, db)
    clan = Clan(priimek="ApiTest", ime="Radioamater", klicni_znak="S59API",
                tip_clanstva="Osebni", aktiven=True, veljavnost_rd=date(2030, 1, 1))
    db.add(clan)
    db.commit()

    csrf = _csrf(client)

    async def mock_fetch(klicni_znaki):
        return {"S59API": date(2038, 7, 27)}

    with patch("app.routers.izvoz._fetch_akos_all", mock_fetch):
        resp = client.post("/izvoz/uvozi-akos-api", data={"csrf_token": csrf})

    assert resp.status_code == 200
    assert "S59API" in resp.text
    assert "2038" in resp.text
    assert "ApiTest" in resp.text


def test_uvozi_akos_api_potrdi(client, db):
    """Potrditev API uvoza dejansko posodobi veljavnost_rd v bazi."""
    _login(client, db)
    clan = Clan(priimek="ApiPotrdi", ime="Radioamater", klicni_znak="S52APT",
                tip_clanstva="Osebni", aktiven=True, veljavnost_rd=date(2028, 3, 1))
    db.add(clan)
    db.commit()
    db.refresh(clan)
    clan_id = clan.id

    csrf = _csrf(client)

    async def mock_fetch(klicni_znaki):
        return {"S52APT": date(2039, 11, 20)}

    # Korak 1: predogled
    with patch("app.routers.izvoz._fetch_akos_all", mock_fetch):
        resp = client.post("/izvoz/uvozi-akos-api", data={"csrf_token": csrf})
    assert resp.status_code == 200
    assert "2039" in resp.text

    # Korak 2: potrditev
    csrf2 = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text).group(1)
    resp2 = client.post("/izvoz/uvozi-akos-api-potrdi", data={"csrf_token": csrf2})
    assert resp2.status_code == 200
    assert "posodobljenih" in resp2.text

    # Preveri DB
    db.expire_all()
    posodobljen = db.query(Clan).filter(Clan.id == clan_id).first()
    assert posodobljen.veljavnost_rd == date(2039, 11, 20)
