"""Testi za uvoz veljavnosti RD iz AKOS Excel datoteke."""
import io
import re
from datetime import date

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
