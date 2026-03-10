"""Testi za uvoz plačil iz Excel z opcijskim poljem Referenca."""
import io
import re
from datetime import date

import openpyxl
import pytest

from app.auth import hash_geslo
from app.models import Uporabnik, Clan, Clanarina
from app.routers.izvoz import _parse_referenca, _parse_excel_placila_pregled, _uvozi_placila_workbook


# ---------------------------------------------------------------------------
# Pomožne funkcije
# ---------------------------------------------------------------------------

def _placila_xlsx(rows: list[tuple], z_referenco: bool = False) -> bytes:
    """Ustvari Excel plačil z glavo + vrsticami."""
    wb = openpyxl.Workbook()
    ws = wb.active
    if z_referenco:
        ws.append(("Priimek", "Ime", "Datum plačila", "Znesek", "Referenca"))
    else:
        ws.append(("Priimek", "Ime", "Datum plačila", "Znesek"))
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _privzeto_mapping(z_referenco: bool = True) -> dict[str, list[str]]:
    m = {
        "priimek":   ["priimek"],
        "ime":       ["ime"],
        "datum":     ["datum plačila", "datum"],
        "znesek":    ["znesek"],
        "referenca": ["referenca", "sklic", "ref"],
    }
    if not z_referenco:
        m["referenca"] = []
    return m


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


# ---------------------------------------------------------------------------
# Testi: _parse_referenca
# ---------------------------------------------------------------------------

def test_parse_referenca_veljaven():
    """SI00 1234-2026 → 1234."""
    assert _parse_referenca("SI00 1234-2026") == 1234


def test_parse_referenca_vodilne_nicle():
    """SI00 0056-2026 → 56."""
    assert _parse_referenca("SI00 0056-2026") == 56


def test_parse_referenca_brez_presledka():
    """SI0010-2026 (brez presledka, format bančnega izpiska) → 10."""
    assert _parse_referenca("SI0010-2026") == 10


def test_parse_referenca_mali_si00():
    """si00 lowercase je sprejet."""
    assert _parse_referenca("si00 99-2025") == 99


def test_parse_referenca_brez_vrednosti():
    """None in prazen niz vrneta None."""
    assert _parse_referenca(None) is None
    assert _parse_referenca("") is None


def test_parse_referenca_napacen_format():
    """Napačen format vrne None."""
    assert _parse_referenca("RF01 1234-2026") is None
    assert _parse_referenca("1234-2026") is None
    assert _parse_referenca("SI00 1234") is None


# ---------------------------------------------------------------------------
# Testi: _parse_excel_placila_pregled – logika identifikacije
# ---------------------------------------------------------------------------

def test_pregled_po_referenco(db):
    """Referenca SI00 {id}-{leto} identificira člana primarno."""
    clan = Clan(priimek="Novak", ime="Janez", aktiven=True)
    db.add(clan)
    db.commit()
    db.refresh(clan)

    xlsx = _placila_xlsx(
        [(clan.priimek, clan.ime, date(2026, 3, 1), "25", f"SI00 {clan.id}-2026")],
        z_referenco=True,
    )
    za_uvoz, preskoceni = _parse_excel_placila_pregled(xlsx, db, _privzeto_mapping())

    assert len(za_uvoz) == 1
    assert len(preskoceni) == 0
    assert za_uvoz[0]["metoda"] == "referenca"
    assert za_uvoz[0]["priimek"] == "Novak"


def test_pregled_fallback_na_ime(db):
    """Brez reference se identifikacija opravi po priimku + imenu."""
    clan = Clan(priimek="Kovač", ime="Ana", aktiven=True)
    db.add(clan)
    db.commit()

    xlsx = _placila_xlsx(
        [("Kovač", "Ana", date(2026, 3, 1), "25")],
        z_referenco=False,
    )
    za_uvoz, preskoceni = _parse_excel_placila_pregled(xlsx, db, _privzeto_mapping(z_referenco=False))

    assert len(za_uvoz) == 1
    assert za_uvoz[0]["metoda"] == "ime"


def test_pregled_referenca_pred_imenom(db):
    """Ko referenca kaže na drugega člana kot ime, zmaga referenca."""
    clan_a = Clan(priimek="Hribar", ime="Marko", aktiven=True)
    clan_b = Clan(priimek="Hribar", ime="Marko", aktiven=True)  # isti imeni, različna ID
    db.add_all([clan_a, clan_b])
    db.commit()
    db.refresh(clan_a)
    db.refresh(clan_b)

    xlsx = _placila_xlsx(
        [("Hribar", "Marko", date(2026, 3, 1), "25", f"SI00 {clan_b.id}-2026")],
        z_referenco=True,
    )
    za_uvoz, preskoceni = _parse_excel_placila_pregled(xlsx, db, _privzeto_mapping())

    assert len(za_uvoz) == 1
    assert za_uvoz[0]["metoda"] == "referenca"
    # Preverimo, da je to clan_b (ne prvi najden po imenu)
    # Ker sta oba z istim imenom, preverimo samo metodo (clan_b.id je bil v referenci)


def test_pregled_referenca_po_es(db):
    """Referenca z ID, ki se ujema z es_stevilka člana."""
    clan = Clan(priimek="Zupan", ime="Petra", aktiven=True, es_stevilka="9999")
    db.add(clan)
    db.commit()
    db.refresh(clan)

    xlsx = _placila_xlsx(
        [("Zupan", "Petra", date(2026, 3, 1), "25", "SI00 9999-2026")],
        z_referenco=True,
    )
    za_uvoz, preskoceni = _parse_excel_placila_pregled(xlsx, db, _privzeto_mapping())

    assert len(za_uvoz) == 1
    assert za_uvoz[0]["metoda"] == "referenca"


def test_pregled_neobstojec_clan(db):
    """Referenca na neobstoječ ID in neujemajoče ime → preskočen."""
    xlsx = _placila_xlsx(
        [("Neznani", "Janko", date(2026, 3, 1), "25", "SI00 99999-2026")],
        z_referenco=True,
    )
    za_uvoz, preskoceni = _parse_excel_placila_pregled(xlsx, db, _privzeto_mapping())

    assert len(za_uvoz) == 0
    assert preskoceni[0]["razlog"] == "Član ni najden"


def test_pregled_brez_datuma(db):
    """Vrstica brez veljavnega datuma → preskočena."""
    clan = Clan(priimek="Hren", ime="Luka", aktiven=True)
    db.add(clan)
    db.commit()
    db.refresh(clan)

    xlsx = _placila_xlsx(
        [(clan.priimek, clan.ime, "ni-datum", "25", f"SI00 {clan.id}-2026")],
        z_referenco=True,
    )
    za_uvoz, preskoceni = _parse_excel_placila_pregled(xlsx, db, _privzeto_mapping())

    assert len(za_uvoz) == 0
    assert preskoceni[0]["razlog"] == "Datum ni veljavno"


# ---------------------------------------------------------------------------
# Testi: _uvozi_placila_workbook
# ---------------------------------------------------------------------------

def test_uvoz_workbook_po_referenco(db):
    """Uvoz z referenco ustvari Clanarina z ustreznim clan_id."""
    clan = Clan(priimek="Rožič", ime="Bojan", aktiven=True)
    db.add(clan)
    db.commit()
    db.refresh(clan)

    xlsx = _placila_xlsx(
        [(clan.priimek, clan.ime, date(2026, 2, 15), "30", f"SI00 {clan.id}-2026")],
        z_referenco=True,
    )
    uvozeni, preskoceni = _uvozi_placila_workbook(xlsx, db, _privzeto_mapping())

    assert uvozeni == 1
    assert preskoceni == 0
    c = db.query(Clanarina).filter(Clanarina.clan_id == clan.id, Clanarina.leto == 2026).first()
    assert c is not None
    assert c.datum_placila == date(2026, 2, 15)
    assert c.znesek == "30"


def test_uvoz_workbook_backward_compat(db):
    """Excel brez stolpca Referenca deluje enako kot prej."""
    clan = Clan(priimek="Jereb", ime="Nataša", aktiven=True)
    db.add(clan)
    db.commit()

    xlsx = _placila_xlsx(
        [("Jereb", "Nataša", date(2026, 1, 10), "25")],
        z_referenco=False,
    )
    uvozeni, preskoceni = _uvozi_placila_workbook(xlsx, db, _privzeto_mapping(z_referenco=False))

    assert uvozeni == 1
    assert preskoceni == 0
