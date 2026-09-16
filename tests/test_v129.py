"""Testi za v1.29 – varnostni pregled (XSS v JS atributih, validacija sej, FK, CSP/SRI, TOTP replay ...)."""
import html
import os
import re
import tempfile
from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pyotp
import pytest
from sqlalchemy import text

from app.auth import hash_geslo
from app.models import (
    Uporabnik, Clan, ClanVloga, Clanarina, Aktivnost, Skupina, EmailPredloga,
    Nastavitev, AuditLog, ZaupljivaNaprava,
)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "templates")
XSS = "a');alert(document.cookie);//"


# ---------------------------------------------------------------------------
# Pomožne funkcije
# ---------------------------------------------------------------------------

def _csrf(text_: str) -> str:
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', text_).group(1)


def _login(client, db, vloga="admin", ime="testuser") -> tuple[Uporabnik, str]:
    u = Uporabnik(uporabnisko_ime=ime, geslo_hash=hash_geslo("Veljavno1234!ab"),
                  vloga=vloga, ime_priimek="Test", aktiven=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    resp = client.get("/login")
    client.post("/login", data={"csrf_token": _csrf(resp.text), "uporabnisko_ime": ime,
                                "geslo": "Veljavno1234!ab"}, follow_redirects=False)
    resp = client.get("/profil")
    return u, _csrf(resp.text)


def _clan(db, priimek="Novak", ime="Janez", **kw) -> Clan:
    c = Clan(priimek=priimek, ime=ime, tip_clanstva=kw.pop("tip_clanstva", "Osebni"),
             aktiven=True, **kw)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# 1. Shranjeni XSS v JS atributih (onsubmit/onclick s confirm())
# ---------------------------------------------------------------------------

def test_predloge_nimajo_inline_event_handlerjev():
    """Noben template ne sme vsebovati on*="..." atributov (CSP + XSS v JS kontekstu)."""
    krsitve = []
    for root, _, files in os.walk(TEMPLATES_DIR):
        for f in files:
            if not f.endswith(".html"):
                continue
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if re.search(r'\son[a-z]+="', line):
                        krsitve.append(f"{f}:{i}")
    assert krsitve == []


def test_xss_naziv_vloge_ne_pride_v_js_kontekst(client, db):
    _, _ = _login(client, db)
    clan = _clan(db)
    db.add(ClanVloga(clan_id=clan.id, naziv=XSS, datum_od=date(2024, 1, 1)))
    db.commit()
    resp = client.get(f"/clani/{clan.id}")
    assert resp.status_code == 200
    assert "onsubmit=" not in resp.text
    m = re.search(r'data-confirm="([^"]*)"[^>]*action="/vloge/izbrisi/', resp.text) or \
        re.search(r'action="/vloge/izbrisi/[^"]*"[^>]*data-confirm="([^"]*)"', resp.text)
    assert m, "obrazec za brisanje vloge mora imeti data-confirm"
    assert html.unescape(m.group(1)) == f"Izbriši vlogo {XSS}?"


def test_xss_ime_skupine_ne_pride_v_js_kontekst(client, db):
    _login(client, db, vloga="urednik")
    clan = _clan(db)
    sk = Skupina(ime=XSS)
    sk.clani.append(clan)
    db.add(sk)
    db.commit()
    db.refresh(sk)
    resp = client.get(f"/skupine/{sk.id}")
    assert resp.status_code == 200
    assert "onsubmit=" not in resp.text
    assert "data-confirm=" in resp.text


def test_xss_naziv_predloge_ne_pride_v_js_kontekst(client, db):
    _login(client, db, vloga="urednik")
    db.add(EmailPredloga(naziv=XSS, zadeva="z", telo_html="t", created_at=datetime.now(timezone.utc)))
    db.commit()
    resp = client.get("/obvestila")
    assert resp.status_code == 200
    assert "onclick=" not in resp.text
    assert "data-confirm=" in resp.text


def test_xss_uporabnisko_ime_ne_pride_v_js_kontekst(client, db):
    _login(client, db)
    db.add(Uporabnik(uporabnisko_ime=XSS, geslo_hash=hash_geslo("Veljavno1234!ab"), vloga="bralec", aktiven=True))
    db.commit()
    resp = client.get("/uporabniki")
    assert resp.status_code == 200
    assert "onsubmit=" not in resp.text
    uid = db.query(Uporabnik).filter(Uporabnik.uporabnisko_ime == XSS).first().id
    resp = client.get(f"/uporabniki/{uid}/uredi")
    assert "onsubmit=" not in resp.text
    assert "data-confirm=" in resp.text


# ---------------------------------------------------------------------------
# 2. CSP + nonce + SRI
# ---------------------------------------------------------------------------

def test_csp_header_z_nonce_na_vseh_inline_skriptah(client, db):
    _login(client, db)
    for url in ("/clani", "/dashboard", "/profil", "/obvestila/posli"):
        resp = client.get(url)
        assert resp.status_code == 200
        csp = resp.headers.get("content-security-policy", "")
        m = re.search(r"'nonce-([A-Za-z0-9_\-]+)'", csp)
        assert m, f"{url}: CSP header brez nonce"
        nonce = m.group(1)
        assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
        inline = re.findall(r"<script(?![^>]*\ssrc=)[^>]*>", resp.text)
        assert inline, f"{url}: pričakovan vsaj en inline script"
        for tag in inline:
            assert f'nonce="{nonce}"' in tag, f"{url}: inline script brez nonce: {tag}"


def test_csp_header_na_login_strani(client):
    resp = client.get("/login")
    assert "default-src 'self'" in resp.headers.get("content-security-policy", "")


def test_csp_nonce_je_enkraten(client):
    n1 = re.search(r"'nonce-([^']+)'", client.get("/login").headers["content-security-policy"]).group(1)
    n2 = re.search(r"'nonce-([^']+)'", client.get("/login").headers["content-security-policy"]).group(1)
    assert n1 != n2


def test_cdn_viri_imajo_sri(client, db):
    _login(client, db)
    for url in ("/clani", "/dashboard", "/login"):
        resp = client.get(url)
        tags = re.findall(r'<(?:script|link)[^>]+(?:src|href)="https://[^"]+"[^>]*>', resp.text)
        assert tags
        for t in tags:
            assert 'integrity="sha384-' in t, f"{url}: brez SRI: {t}"
            assert 'crossorigin="anonymous"' in t, f"{url}: brez crossorigin: {t}"


# ---------------------------------------------------------------------------
# 3. Validacija sej proti bazi
# ---------------------------------------------------------------------------

def test_deaktiviran_uporabnik_je_odjavljen(client, db):
    u, _ = _login(client, db, vloga="urednik")
    u.aktiven = False
    db.commit()
    resp = client.get("/clani", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_izbrisan_uporabnik_je_odjavljen(client, db):
    u, tok = _login(client, db, vloga="urednik")
    clan = _clan(db)
    db.delete(u)
    db.commit()
    resp = client.post(f"/clani/{clan.id}/uredi",
                       data={"csrf_token": tok, "priimek": "Spremenjen", "ime": "Janez", "tip_clanstva": "Osebni"},
                       follow_redirects=False)
    assert resp.status_code in (302, 403)
    db.expire_all()
    assert db.get(Clan, clan.id).priimek == "Novak"


def test_sprememba_vloge_velja_takoj(client, db):
    u, _ = _login(client, db, vloga="admin")
    assert client.get("/uporabniki").status_code == 200
    u.vloga = "bralec"
    db.commit()
    resp = client.get("/uporabniki", follow_redirects=False)
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# 4. Admin ne more degradirati/deaktivirati samega sebe
# ---------------------------------------------------------------------------

def test_admin_ne_more_spremeniti_lastne_vloge(client, db):
    u, tok = _login(client, db)
    resp = client.post(f"/uporabniki/{u.id}/uredi",
                       data={"csrf_token": tok, "ime_priimek": "X", "vloga": "bralec", "aktiven": "ne"},
                       follow_redirects=False)
    assert resp.status_code == 200
    assert "lastne" in resp.text.lower()
    db.expire_all()
    assert db.get(Uporabnik, u.id).vloga == "admin"
    assert db.get(Uporabnik, u.id).aktiven is True


# ---------------------------------------------------------------------------
# 5. Audit log
# ---------------------------------------------------------------------------

def test_reset_gesla_zapise_audit_log(client, db):
    _, tok = _login(client, db)
    drugi = Uporabnik(uporabnisko_ime="drugi", geslo_hash=hash_geslo("Veljavno1234!ab"), vloga="bralec", aktiven=True)
    db.add(drugi)
    db.commit()
    db.refresh(drugi)
    resp = client.post(f"/uporabniki/{drugi.id}/reset-geslo", data={"csrf_token": tok}, follow_redirects=False)
    assert resp.status_code == 302
    log = db.query(AuditLog).filter(AuditLog.akcija == "geslo_ponastavljeno").first()
    assert log is not None and "drugi" in log.opis


def test_skupina_crud_zapise_audit_log(client, db):
    _, tok = _login(client, db)
    resp = client.post("/skupine/nova", data={"csrf_token": tok, "ime": "Testna"}, follow_redirects=False)
    assert resp.status_code == 302
    assert db.query(AuditLog).filter(AuditLog.akcija == "skupina_dodana").count() == 1


def test_zrs_in_uvoz_nastavitve_zapisejo_audit_log(client, db):
    _, tok = _login(client, db)
    client.post("/izvoz/zrs-nastavitve", data={"csrf_token": tok, "zrs_uppercase": "1"}, follow_redirects=False)
    client.post("/izvoz/uvozi-nastavitve", data={"csrf_token": tok}, follow_redirects=False)
    client.post("/izvoz/uvozi-placila-nastavitve", data={"csrf_token": tok}, follow_redirects=False)
    akcije = {r[0] for r in db.query(AuditLog.akcija).all()}
    assert {"zrs_nastavitve_urejene", "uvoz_nastavitve_urejene", "uvoz_placila_nastavitve_urejene"} <= akcije


# ---------------------------------------------------------------------------
# 6. Skupine – brisanje samo admin
# ---------------------------------------------------------------------------

def test_urednik_ne_more_izbrisati_skupine(client, db):
    _, tok = _login(client, db, vloga="urednik")
    sk = Skupina(ime="S")
    db.add(sk)
    db.commit()
    db.refresh(sk)
    resp = client.get(f"/skupine/{sk.id}")
    assert "Izbriši skupino" not in resp.text
    client.post(f"/skupine/{sk.id}/izbrisi", data={"csrf_token": tok}, follow_redirects=False)
    assert db.query(Skupina).filter(Skupina.id == sk.id).first() is not None


def test_admin_izbrise_skupino_s_clani(client, db):
    _, tok = _login(client, db)
    sk = Skupina(ime="S")
    sk.clani.append(_clan(db))
    db.add(sk)
    db.commit()
    db.refresh(sk)
    resp = client.post(f"/skupine/{sk.id}/izbrisi", data={"csrf_token": tok}, follow_redirects=False)
    assert resp.status_code == 302
    assert db.query(Skupina).filter(Skupina.id == sk.id).first() is None
    assert db.query(AuditLog).filter(AuditLog.akcija == "skupina_izbrisana").count() == 1


# ---------------------------------------------------------------------------
# 7. Tuji ključi
# ---------------------------------------------------------------------------

def test_pragma_foreign_keys_vklopljen(engine):
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


@pytest.mark.parametrize("pot,data", [
    ("/clanarine/dodaj", {"clan_id": 99999, "leto": 2026, "datum_placila": "2026-01-01"}),
    ("/aktivnosti/dodaj", {"clan_id": 99999, "leto": 2026, "opis": "x"}),
    ("/vloge/dodaj", {"clan_id": 99999, "naziv": "Tajnik", "datum_od": "2026-01-01"}),
])
def test_vnos_za_neobstojecega_clana_zavrnjen(client, db, pot, data):
    _, tok = _login(client, db, vloga="urednik")
    resp = client.post(pot, data={"csrf_token": tok, **data}, follow_redirects=False)
    assert resp.status_code == 302
    assert db.query(Clanarina).count() == 0
    assert db.query(Aktivnost).count() == 0
    assert db.query(ClanVloga).count() == 0


def test_izbris_uporabnika_z_zaupljivo_napravo(client, db):
    _, tok = _login(client, db)
    drugi = Uporabnik(uporabnisko_ime="drugi", geslo_hash=hash_geslo("Veljavno1234!ab"), vloga="bralec", aktiven=True)
    db.add(drugi)
    db.commit()
    db.refresh(drugi)
    db.add(ZaupljivaNaprava(uporabnik_id=drugi.id, token_hash="h",
                            expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
    db.commit()
    resp = client.post(f"/uporabniki/{drugi.id}/izbrisi", data={"csrf_token": tok}, follow_redirects=False)
    assert resp.status_code == 302
    assert db.query(Uporabnik).filter(Uporabnik.id == drugi.id).first() is None
    assert db.query(ZaupljivaNaprava).count() == 0


def test_izbris_clana_pobrise_povezane_vrstice(client, db):
    _, tok = _login(client, db)
    clan = _clan(db)
    sk = Skupina(ime="S")
    sk.clani.append(clan)
    db.add(sk)
    db.add(Clanarina(clan_id=clan.id, leto=2025, datum_placila=date(2025, 1, 1)))
    db.add(Aktivnost(clan_id=clan.id, leto=2025, opis="x"))
    db.add(ClanVloga(clan_id=clan.id, naziv="Tajnik", datum_od=date(2025, 1, 1)))
    db.commit()
    resp = client.post(f"/clani/{clan.id}/izbrisi", data={"csrf_token": tok}, follow_redirects=False)
    assert resp.status_code == 302
    assert db.query(Clan).count() == 0
    assert db.execute(text("SELECT COUNT(*) FROM clan_skupina")).scalar() == 0


# ---------------------------------------------------------------------------
# 8. Alembic migracije
# ---------------------------------------------------------------------------

def _alembic_engine(tmp_path):
    from alembic.config import Config
    from alembic import command
    import app.database as database
    from sqlalchemy import create_engine
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    e = create_engine(url, connect_args={"check_same_thread": False})
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    with patch.object(database, "engine", e), patch.object(database, "DATABASE_URL", url):
        return e, cfg, command


def test_migracije_skladne_z_modeli(tmp_path):
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app.models import Base
    import app.database as database
    e, cfg, command = _alembic_engine(tmp_path)
    with patch.object(database, "engine", e), patch.object(database, "DATABASE_URL", cfg.get_main_option("sqlalchemy.url")):
        command.upgrade(cfg, "head")
    with e.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_migracija_010_pocisti_sirote(tmp_path):
    import app.database as database
    e, cfg, command = _alembic_engine(tmp_path)
    url = cfg.get_main_option("sqlalchemy.url")
    with patch.object(database, "engine", e), patch.object(database, "DATABASE_URL", url):
        command.upgrade(cfg, "009")
        # Sirote vstavimo z izklopljenimi tujimi ključi (stanje baz pred v1.29)
        raw = e.raw_connection()
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("INSERT INTO clani (id, priimek, ime, tip_clanstva, aktiven) VALUES (1, 'A', 'B', 'Osebni', 1)")
        raw.execute("INSERT INTO clanarine (clan_id, leto) VALUES (1, 2025), (999, 2025)")
        raw.execute("INSERT INTO aktivnosti (clan_id, leto, opis) VALUES (999, 2025, 'x')")
        raw.execute("INSERT INTO clan_vloge (clan_id, naziv, datum_od) VALUES (999, 'T', '2025-01-01')")
        raw.execute("INSERT INTO zaupljive_naprave (uporabnik_id, token_hash, expires_at) VALUES (999, 'h', '2030-01-01')")
        raw.commit()
        raw.close()
        command.upgrade(cfg, "head")
    with e.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM clanarine")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM aktivnosti")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM clan_vloge")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM zaupljive_naprave")).scalar() == 0


# ---------------------------------------------------------------------------
# 9. Izvoz / uvoz
# ---------------------------------------------------------------------------

def test_zrs_izvoz_z_ne_ascii_oznako(client, db):
    _login(client, db)
    db.add(Nastavitev(kljuc="klub_oznaka", vrednost="Š59DGO"))
    db.commit()
    resp = client.get("/izvoz/zrs?leto=2026", follow_redirects=False)
    assert resp.status_code == 200
    resp.headers["content-disposition"].encode("latin-1")


def test_zrs_izvoz_privzeto_leto_je_tekoce(client, db):
    _login(client, db)
    with patch("app.routers.izvoz.date") as d:
        d.today.return_value.year = 2031
        resp = client.get("/izvoz/zrs", follow_redirects=False)
    assert resp.status_code == 200
    assert "2031" in resp.headers["content-disposition"]


def test_akos_klicni_znak_je_url_kodiran():
    import asyncio
    from app.routers.izvoz import _fetch_akos_all
    klici = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, timeout=None):
            klici.append(url)
            return MagicMock(text="")

    with patch("app.routers.izvoz.httpx.AsyncClient", FakeClient):
        asyncio.run(_fetch_akos_all(["S5/9?X#Y"]))
    assert klici == ["https://cept.akos-rs.si/S5%2F9%3FX%23Y"]


def test_iskanje_clanov_escape_wildcard(client, db):
    _login(client, db, vloga="urednik")
    _clan(db)
    resp = client.get("/clani/iskanje?q=%25%25")
    assert resp.status_code == 200
    assert resp.json() == []


def test_backup_db_vrne_konsistentno_sqlite_datoteko(client, db):
    from app.database import sqlite_pot
    _login(client, db)
    resp = client.get("/izvoz/backup-db", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.content[:15] == b"SQLite format 3"
    # Backup mora izhajati iz baze v DATABASE_URL (ne iz hardkodirane data/clanstvo.db)
    assert len(resp.content) == os.path.getsize(sqlite_pot())


def test_seznam_clanov_znacke_tipov(client, db):
    _login(client, db)
    _clan(db, tip_clanstva="Mladi")
    resp = client.get("/clani")
    assert re.search(r'badge\s+bg-success[^>]*>\s*Mladi', resp.text)


# ---------------------------------------------------------------------------
# 10. Prijava
# ---------------------------------------------------------------------------

def test_login_neobstojec_uporabnik_preveri_geslo(client):
    resp = client.get("/login")
    with patch("app.main.preveri_geslo", return_value=False) as pg:
        client.post("/login", data={"csrf_token": _csrf(resp.text), "uporabnisko_ime": "nihce", "geslo": "x"},
                    follow_redirects=False)
    assert pg.call_count == 1


def test_login_uporabnisko_ime_omejeno_v_audit_logu(client, db):
    resp = client.get("/login")
    client.post("/login", data={"csrf_token": _csrf(resp.text), "uporabnisko_ime": "a" * 5000, "geslo": "x"},
                follow_redirects=False)
    log = db.query(AuditLog).filter(AuditLog.akcija == "login_fail").first()
    assert log is not None
    assert len(log.uporabnik) <= 150


def test_totp_koda_ni_ponovno_uporabna(client, db):
    skrivnost = pyotp.random_base32()
    u = Uporabnik(uporabnisko_ime="tfa", geslo_hash=hash_geslo("Veljavno1234!ab"), vloga="admin",
                  aktiven=True, totp_skrivnost=skrivnost, totp_aktiven=True)
    db.add(u)
    db.commit()
    koda = pyotp.TOTP(skrivnost).now()

    def prijava():
        resp = client.get("/login")
        client.post("/login", data={"csrf_token": _csrf(resp.text), "uporabnisko_ime": "tfa",
                                    "geslo": "Veljavno1234!ab"}, follow_redirects=False)
        resp = client.get("/login/2fa")
        return client.post("/login/2fa", data={"csrf_token": _csrf(resp.text), "koda": koda}, follow_redirects=False)

    assert prijava().status_code == 302
    client.cookies.clear()
    resp = prijava()
    assert resp.status_code == 200
    assert "Napačna koda" in resp.text


# ---------------------------------------------------------------------------
# 11. Produkcijske varnostne zahteve ob zagonu
# ---------------------------------------------------------------------------

def test_produkcija_zavrne_privzeti_secret_key():
    from app.main import preveri_produkcijske_nastavitve
    with pytest.raises(RuntimeError):
        preveri_produkcijske_nastavitve("produkcija", "radikoklub-dev-key-ZAMENJAJTE-v-produkciji", "X" * 20, False)
    with pytest.raises(RuntimeError):
        preveri_produkcijske_nastavitve("produkcija", "kratek", "X" * 20, False)


def test_produkcija_zavrne_privzeto_admin_geslo_ob_ustvarjanju():
    from app.main import preveri_produkcijske_nastavitve
    with pytest.raises(RuntimeError):
        preveri_produkcijske_nastavitve("produkcija", "k" * 40, "admin123", True)
    preveri_produkcijske_nastavitve("produkcija", "k" * 40, "admin123", False)
    preveri_produkcijske_nastavitve("razvoj", "radikoklub-dev-key-ZAMENJAJTE-v-produkciji", "admin123", True)


# ---------------------------------------------------------------------------
# 12. SMTP timeout
# ---------------------------------------------------------------------------

def test_smtp_klic_ima_timeout(db):
    from app.email import posli_email
    clan = _clan(db, elektronska_posta="j@test.si")
    for k, v in [("smtp_host", "smtp.test.si"), ("smtp_port", "587"), ("smtp_nacin", "starttls"), ("smtp_od", "k@t.si")]:
        db.add(Nastavitev(kljuc=k, vrednost=v))
    db.commit()
    with patch("app.email.smtplib.SMTP") as smtp:
        posli_email(clan, "z", "<p>t</p>", 2026,
                    {"host": "smtp.test.si", "port": 587, "nacin": "starttls", "uporabnik": "", "geslo": "", "od": "k@t.si"},
                    db)
    assert smtp.call_args.kwargs.get("timeout"), "smtplib.SMTP mora biti klican s timeout"


def test_app_engine_ima_fk_vklopljen_po_migracijah(client):
    """Migracije izklopijo PRAGMA foreign_keys; pooled povezava app engine-a mora ostati z ON."""
    from app.database import engine
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
