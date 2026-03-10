"""Testi za /clani/{id}/kartica – PDF download, HTML tisk, email pošiljanje."""
import re
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.auth import hash_geslo
from app.models import Uporabnik, Clan, EmailPredloga, Nastavitev, AuditLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, db, vloga="urednik") -> str:
    """Ustvari uporabnika, ga prijavi, vrne svež CSRF token."""
    u = Uporabnik(
        uporabnisko_ime="karttest",
        geslo_hash=hash_geslo("Veljavno1234!ab"),
        vloga=vloga,
        ime_priimek="Kart Test",
        aktiven=True,
    )
    db.add(u)
    db.commit()
    resp = client.get("/login")
    csrf = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text).group(1)
    client.post("/login", data={"csrf_token": csrf, "uporabnisko_ime": "karttest",
                                "geslo": "Veljavno1234!ab"}, follow_redirects=False)
    resp = client.get("/profil")
    return re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', resp.text).group(1)


def _nov_clan(db, email="janez@test.si") -> Clan:
    c = Clan(
        priimek="Novak",
        ime="Janez",
        klicni_znak="S59DGO",
        tip_clanstva="Osebni",
        aktiven=True,
        elektronska_posta=email,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _nastavi_smtp(db):
    for kljuc, vrednost in [
        ("smtp_host", "smtp.test.si"),
        ("smtp_port", "587"),
        ("smtp_nacin", "starttls"),
        ("smtp_od", "klub@test.si"),
        ("smtp_uporabnik", ""),
        ("smtp_geslo", ""),
    ]:
        db.add(Nastavitev(kljuc=kljuc, vrednost=vrednost))
    db.commit()


def _nova_kartica_predloga(db) -> EmailPredloga:
    p = EmailPredloga(
        naziv="Pošiljanje članske kartice",
        zadeva="Članska izkaznica {{ leto }} – {{ klub_oznaka }}",
        telo_html="<p>Spoštovani {{ priimek }} {{ ime }},</p><p>v priponki najdete vašo <strong>člansko izkaznico za leto {{ leto }}</strong>.</p>",
        je_privzeta=True,
        vkljuci_qr=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Testi
# ---------------------------------------------------------------------------

def test_kartica_pdf_download(client, db):
    """GET /clani/{id}/kartica.pdf → 200 + application/pdf."""
    _login(client, db)
    clan = _nov_clan(db)
    resp = client.get(f"/clani/{clan.id}/kartica.pdf?leto=2026", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    # PDF začne z %PDF
    assert resp.content[:4] == b"%PDF"


def test_kartica_html(client, db):
    """GET /clani/{id}/kartica → 200, vsebuje ime člana."""
    _login(client, db)
    clan = _nov_clan(db)
    resp = client.get(f"/clani/{clan.id}/kartica?leto=2026")
    assert resp.status_code == 200
    assert "Novak" in resp.text
    assert "Janez" in resp.text


def test_kartica_brez_pravic(client, db):
    """Bralec nima dostopa do kartice → redirect."""
    _login(client, db, vloga="bralec")
    clan = _nov_clan(db)
    resp = client.get(f"/clani/{clan.id}/kartica.pdf", follow_redirects=False)
    assert resp.status_code == 302


def test_posli_kartico_brez_emaila(client, db):
    """Pošiljanje kartice članu brez e-pošte → redirect s flash opozorilom."""
    token = _login(client, db)
    clan = _nov_clan(db, email=None)
    _nova_kartica_predloga(db)
    _nastavi_smtp(db)

    resp = client.post(
        f"/clani/{clan.id}/posli-kartico",
        data={"csrf_token": token, "leto": "2026"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "e-poštnega" in resp.text or "e-pošt" in resp.text or "nima" in resp.text


def test_posli_kartico_mock_smtp(client, db):
    """Pošiljanje kartice z mock SMTP → 302, audit log kartica_poslana."""
    token = _login(client, db)
    clan = _nov_clan(db, email="janez@test.si")
    _nova_kartica_predloga(db)
    _nastavi_smtp(db)

    with patch("app.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            f"/clani/{clan.id}/posli-kartico",
            data={"csrf_token": token, "leto": "2026"},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    # Preveri audit log
    log = db.query(AuditLog).filter(AuditLog.akcija == "kartica_poslana").first()
    assert log is not None
    assert str(clan.id) in log.opis
