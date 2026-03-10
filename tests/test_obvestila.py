"""Testi za /obvestila router – upravljanje predlog in pošiljanje emailov."""
import re
from datetime import datetime, date, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.auth import hash_geslo
from app.models import Uporabnik, Clan, Clanarina, EmailPredloga, Nastavitev


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, db, vloga="admin") -> str:
    """Ustvari uporabnika, ga prijavi, vrne svež CSRF token."""
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
    resp = client.get("/profil")
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    return match.group(1)


def _nov_clan(db, ime="Janez", priimek="Novak", email="janez@test.si", aktiven=True):
    c = Clan(
        priimek=priimek,
        ime=ime,
        tip_clanstva="Osebni",
        aktiven=aktiven,
        elektronska_posta=email,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _nova_predloga(db, naziv="Testna predloga", je_privzeta=False):
    p = EmailPredloga(
        naziv=naziv,
        zadeva="Zadeva {{ leto }}",
        telo_html="<p>Pozdravljeni {{ priimek }}, leto {{ leto }}. {{ qr_koda }}</p>",
        je_privzeta=je_privzeta,
        created_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _nastavi_smtp(db):
    """Nastavi minimalne SMTP nastavitve v DB."""
    for kljuc, vrednost in [
        ("smtp_host", "smtp.test.si"),
        ("smtp_port", "587"),
        ("smtp_nacin", "starttls"),
        ("smtp_od", "klub@test.si"),
        ("smtp_uporabnik", ""),
        ("smtp_geslo", ""),
    ]:
        n = db.query(Nastavitev).filter(Nastavitev.kljuc == kljuc).first()
        if n:
            n.vrednost = vrednost
        else:
            db.add(Nastavitev(kljuc=kljuc, vrednost=vrednost))
    db.commit()


# ---------------------------------------------------------------------------
# Testi
# ---------------------------------------------------------------------------

def test_obvestila_brez_seje(client):
    """GET /obvestila brez seje → 302 redirect na login."""
    resp = client.get("/obvestila", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_obvestila_z_sejo(client, db):
    """GET /obvestila z admin → 200, vsebuje 'predlog'."""
    _login(client, db)
    _nova_predloga(db)
    resp = client.get("/obvestila")
    assert resp.status_code == 200
    assert "Testna predloga" in resp.text


def test_nova_predloga_get(client, db):
    """GET /obvestila/nova → 200."""
    _login(client, db)
    resp = client.get("/obvestila/nova")
    assert resp.status_code == 200
    assert "Nova predloga" in resp.text


def test_nova_predloga_post(client, db):
    """POST /obvestila/nova → nova predloga shranjena v DB."""
    token = _login(client, db)
    resp = client.post(
        "/obvestila/nova",
        data={
            "csrf_token": token,
            "naziv": "Moja predloga",
            "zadeva": "Zadeva",
            "telo_html": "<p>Vsebina</p>",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    p = db.query(EmailPredloga).filter(EmailPredloga.naziv == "Moja predloga").first()
    assert p is not None
    assert p.je_privzeta is False


def test_uredi_predloga(client, db):
    """GET + POST uredi predlogo → posodobljen naziv."""
    token = _login(client, db)
    p = _nova_predloga(db)

    resp = client.get(f"/obvestila/{p.id}/uredi")
    assert resp.status_code == 200

    resp = client.post(
        f"/obvestila/{p.id}/uredi",
        data={
            "csrf_token": token,
            "naziv": "Posodobljena predloga",
            "zadeva": "Nova zadeva",
            "telo_html": "<p>Novo telo</p>",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db.refresh(p)
    assert p.naziv == "Posodobljena predloga"


def test_izbrisi_privzeto_blokira(client, db):
    """Brisanje je_privzeta=True → redirect z napako, predloga ostane."""
    token = _login(client, db)
    p = _nova_predloga(db, je_privzeta=True)

    resp = client.post(
        f"/obvestila/{p.id}/izbrisi",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Predloga mora ostati
    assert db.query(EmailPredloga).filter(EmailPredloga.id == p.id).first() is not None


def test_izbrisi_neprivzeto(client, db):
    """Brisanje je_privzeta=False → predloga je izbrisana."""
    token = _login(client, db)
    p = _nova_predloga(db, je_privzeta=False)
    pid = p.id

    resp = client.post(
        f"/obvestila/{pid}/izbrisi",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.query(EmailPredloga).filter(EmailPredloga.id == pid).first() is None


def test_posli_get(client, db):
    """GET /obvestila/posli → 200."""
    _login(client, db)
    resp = client.get("/obvestila/posli")
    assert resp.status_code == 200
    assert "Pošlji" in resp.text


def test_posli_posamezniku(client, db):
    """POST /obvestila/posli z clan_id → 1 email poslan (mock SMTP)."""
    token = _login(client, db)
    clan = _nov_clan(db)
    p = _nova_predloga(db)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/obvestila/posli",
            data={
                "csrf_token": token,
                "predloga_id": p.id,
                "zadeva": "Zadeva {{ leto }}",
                "telo_html": "<p>Pozdravljeni {{ priimek }}. {{ qr_koda }}</p>",
                "leto": "2026",
                "clan_id": str(clan.id),
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    assert "1" in resp.text  # poslano = 1


def test_posli_bulk(client, db):
    """POST /obvestila/posli brez clan_id → N emailov poslanih (mock SMTP)."""
    token = _login(client, db)
    # 3 neplačniki z emailom, 1 brez emaila
    c1 = _nov_clan(db, ime="Ana", priimek="Kos", email="ana@test.si")
    c2 = _nov_clan(db, ime="Bor", priimek="Rok", email="bor@test.si")
    c3 = _nov_clan(db, ime="Eva", priimek="Bela", email="eva@test.si")
    c_brez = _nov_clan(db, ime="Fran", priimek="Mrak", email=None)
    p = _nova_predloga(db)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/obvestila/posli",
            data={
                "csrf_token": token,
                "predloga_id": p.id,
                "zadeva": "Zadeva {{ leto }}",
                "telo_html": "<p>Pozdravljeni {{ priimek }}. {{ qr_koda }}</p>",
                "leto": "2026",
                "clan_id": "",
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    # 3 poslani, 1 preskočen (brez emaila)
    assert "3" in resp.text
    assert "1" in resp.text


def test_posli_bulk_rd_potekla(client, db):
    """POST /obvestila/posli bulk_filter=rd_potekla → email poslan samo članu s potečeno RD."""
    token = _login(client, db)
    danes = date.today()
    # Član s potečeno RD
    c_potek = Clan(priimek="Stari", ime="Rok", tip_clanstva="Osebni", aktiven=True,
                   elektronska_posta="stari@test.si",
                   veljavnost_rd=danes - timedelta(days=30))
    # Član z veljavno RD
    c_velj = Clan(priimek="Mladi", ime="Ana", tip_clanstva="Osebni", aktiven=True,
                  elektronska_posta="mladi@test.si",
                  veljavnost_rd=danes + timedelta(days=200))
    # Aktiven brez RD
    c_brez_rd = Clan(priimek="Brez", ime="RD", tip_clanstva="Osebni", aktiven=True,
                     elektronska_posta="brezrd@test.si")
    db.add_all([c_potek, c_velj, c_brez_rd])
    db.commit()

    p = _nova_predloga(db)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/obvestila/posli",
            data={
                "csrf_token": token,
                "predloga_id": p.id,
                "zadeva": "Potečena RD – {{ priimek }}",
                "telo_html": "<p>Potečena RD: {{ veljavnost_rd }}</p>",
                "leto": "2026",
                "clan_id": "",
                "bulk_filter": "rd_potekla",
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    # Samo 1 poslan (c_potek), ostala 2 nimata potečene RD
    assert "1" in resp.text


def test_posli_bulk_vsi_aktivni(client, db):
    """bulk_filter=vsi_aktivni → email poslan vsem aktivnim, neaktivni preskočeni."""
    token = _login(client, db)
    c_akt = _nov_clan(db, ime="Aktiven", priimek="Clan", email="akt@test.si")
    c_neakt = _nov_clan(db, ime="Neaktiven", priimek="Clan", email="neakt@test.si", aktiven=False)
    p = _nova_predloga(db)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/obvestila/posli",
            data={
                "csrf_token": token,
                "predloga_id": p.id,
                "zadeva": "Zadeva",
                "telo_html": "<p>Test {{ priimek }}</p>",
                "leto": "2026",
                "clan_id": "",
                "bulk_filter": "vsi_aktivni",
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    # 1 poslan (aktiven), 0 preskočenih (neaktiven nima e-pošte, a ga filter sploh ne ujame)
    assert mock_smtp_cls.return_value.__enter__.return_value.send_message.call_count == 1


def test_posli_bulk_vsi(client, db):
    """bulk_filter=vsi → email poslan aktivnim in neaktivnim članom z e-pošto."""
    token = _login(client, db)
    c_akt = _nov_clan(db, ime="Aktiven", priimek="Clan", email="akt@test.si")
    c_neakt = _nov_clan(db, ime="Neaktiven", priimek="Clan", email="neakt@test.si", aktiven=False)
    p = _nova_predloga(db)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/obvestila/posli",
            data={
                "csrf_token": token,
                "predloga_id": p.id,
                "zadeva": "Zadeva",
                "telo_html": "<p>Test {{ priimek }}</p>",
                "leto": "2026",
                "clan_id": "",
                "bulk_filter": "vsi",
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    # 2 poslana (aktiven + neaktiven imata oba e-pošto)
    assert mock_smtp_cls.return_value.__enter__.return_value.send_message.call_count == 2


def test_posli_bulk_placniki(client, db):
    """bulk_filter=placniki → email poslan samo plačniku, neplačnik preskočen."""
    token = _login(client, db)
    # Plačnik
    c_placnik = _nov_clan(db, ime="Plačnik", priimek="Clan", email="placnik@test.si")
    db.add(Clanarina(clan_id=c_placnik.id, leto=2026, datum_placila=date.today(), znesek="25.00"))
    # Neplačnik (brez Clanarina za 2026)
    c_neplacnik = _nov_clan(db, ime="Neplačnik", priimek="Clan", email="neplacnik@test.si")
    db.commit()

    p = _nova_predloga(db)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/obvestila/posli",
            data={
                "csrf_token": token,
                "predloga_id": p.id,
                "zadeva": "Zahvala",
                "telo_html": "<p>Hvala {{ priimek }}</p>",
                "leto": "2026",
                "clan_id": "",
                "bulk_filter": "placniki",
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    # Samo 1 poslan (plačnik), neplačnik preskočen
    assert mock_smtp_cls.return_value.__enter__.return_value.send_message.call_count == 1


def test_posli_bulk_z_kartico(client, db):
    """Predloga z prilozi_kartico=True → vsak email dobi PDF priponko."""
    token = _login(client, db)
    c1 = _nov_clan(db, ime="Ana", priimek="Kos", email="ana@test.si")
    c2 = _nov_clan(db, ime="Bor", priimek="Rok", email="bor@test.si")
    # Predloga z rilozi_kartico=True
    p = EmailPredloga(
        naziv="Kartica predloga",
        zadeva="Kartica {{ leto }}",
        telo_html="<p>Kartica {{ priimek }}</p>",
        je_privzeta=False,
        vkljuci_qr=False,
        prilozi_kartico=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/obvestila/posli",
            data={
                "csrf_token": token,
                "predloga_id": p.id,
                "zadeva": "Kartica {{ leto }}",
                "telo_html": "<p>Kartica {{ priimek }}</p>",
                "leto": "2026",
                "clan_id": "",
                "bulk_filter": "vsi_aktivni",
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    # 2 emaila poslana (oba imata e-pošto)
    assert mock_smtp_cls.return_value.__enter__.return_value.send_message.call_count == 2
    # Vsak klic mora imeti priponko (PDF)
    for call_args in mock_smtp_cls.return_value.__enter__.return_value.send_message.call_args_list:
        msg = call_args[0][0]
        # Sporočilo mora biti multipart/mixed (ima priponke)
        assert msg.get_content_type() == "multipart/mixed"
        # Ena od delov mora biti application/pdf
        pdf_parts = [p for p in msg.walk() if p.get_content_type() == "application/pdf"]
        assert len(pdf_parts) == 1


def test_posli_brez_smtp(client, db):
    """POST /obvestila/posli brez SMTP konfiguracije → napaka/redirect z flash."""
    token = _login(client, db)
    clan = _nov_clan(db)
    p = _nova_predloga(db)
    # smtp_host ostane prazen (ni nastavljeno)

    resp = client.post(
        "/obvestila/posli",
        data={
            "csrf_token": token,
            "predloga_id": p.id,
            "zadeva": "Zadeva",
            "telo_html": "<p>Vsebina</p>",
            "leto": "2026",
            "clan_id": str(clan.id),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    # Flash napaka mora biti prikazana ali redirect na posli
    assert "SMTP" in resp.text or "nastavl" in resp.text.lower()


def test_posli_posameznik_brez_clan_id(client, db):
    """nacin=posameznik + clan_id="" → redirect z napako, ne bulk send."""
    token = _login(client, db)
    p = _nova_predloga(db)
    _nastavi_smtp(db)
    resp = client.post(
        "/obvestila/posli",
        data={
            "csrf_token": token,
            "predloga_id": p.id,
            "zadeva": "Z",
            "telo_html": "<p>T</p>",
            "leto": "2026",
            "nacin": "posameznik",
            "clan_id": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "člana" in resp.text.lower() or "izberite" in resp.text.lower()


def test_posli_neobstojeca_predloga(client, db):
    """predloga_id ki ne obstaja → redirect z napako."""
    token = _login(client, db)
    _nastavi_smtp(db)
    resp = client.post(
        "/obvestila/posli",
        data={
            "csrf_token": token,
            "predloga_id": 9999,
            "zadeva": "Z",
            "telo_html": "<p>T</p>",
            "leto": "2026",
            "nacin": "bulk",
            "clan_id": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "predloga" in resp.text.lower()
