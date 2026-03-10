"""Generiranje PDF članske kartice (85.6 × 54 mm)."""
import os
import re

from fpdf import FPDF
from sqlalchemy.orm import Session

from .config import get_nastavitev
from .models import Clan

_FONT_PATH      = os.path.join(os.path.dirname(__file__), "static", "fonts", "DejaVuSans.ttf")
_FONT_BOLD_PATH = os.path.join(os.path.dirname(__file__), "static", "fonts", "DejaVuSans-Bold.ttf")

_KARTICA_POLJA_LABELE: dict[str, str] = {
    "tip_clanstva":       "Tip",
    "operaterski_razred": "Razred",
    "es_stevilka":        "ES",
    "veljavnost_rd":      "Veljavnost RD",
}

_KARTICA_POLJA_PRIVZETO = "klicni_znak,tip_clanstva,operaterski_razred,es_stevilka,veljavnost_rd"


def get_kartica_polja(db: Session) -> list[str]:
    """Prebere seznam polj za kartico iz nastavitev."""
    vrednost = get_nastavitev(db, "kartica_polja", _KARTICA_POLJA_PRIVZETO)
    return [p.strip() for p in vrednost.split(",") if p.strip()]


def kartica_filename(clan: Clan, clan_id: int, leto: int) -> str:
    """Vrne sanitizirano ime PDF datoteke za kartico."""
    kz_raw = clan.klicni_znak or str(clan_id)
    kz_safe = re.sub(r"[^A-Za-z0-9\-]", "_", kz_raw)
    return f"kartica_{kz_safe}_{leto}.pdf"


def generiraj_kartico_pdf(clan: Clan, leto: int, klub_ime: str,
                           klub_oznaka: str, polja: list[str]) -> bytes:
    """Generira PDF člansko kartico formata 85.6 × 54 mm."""
    W, H = 85.6, 54.0
    BLUE      = (0, 70, 127)
    BLUE_DARK = (0, 50, 100)
    LIGHT_BG  = (240, 246, 252)
    GRAY_TEXT = (120, 120, 120)
    FOOTER_BG = (245, 245, 245)

    pdf = FPDF(unit="mm", format=(W, H))
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(False)
    pdf.add_font("DejaVu",     style="",  fname=_FONT_PATH)
    pdf.add_font("DejaVuBold", style="",  fname=_FONT_BOLD_PATH)
    pdf.add_page()

    HEADER_H = 12.5
    KZ_BOX_X = W - 27
    KZ_BOX_W = 23
    KZ_BOX_Y = HEADER_H + 1
    KZ_BOX_H = 16
    SEP_Y    = HEADER_H + KZ_BOX_H + 1.5
    FIELDS_Y = SEP_Y + 1.5
    ROW_H    = 7.5
    FOOTER_Y = H - 7

    # ── Header ──────────────────────────────────────────────────────────────
    pdf.set_fill_color(*BLUE)
    pdf.rect(0, 0, W, HEADER_H, "F")
    pdf.set_draw_color(*BLUE_DARK)
    pdf.set_line_width(0.3)
    pdf.line(0, HEADER_H, W, HEADER_H)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVuBold", size=8)
    pdf.set_xy(4, (HEADER_H - 5) / 2)
    pdf.cell(KZ_BOX_X - 6, HEADER_H, (klub_ime or "Radio klub").upper()[:36])
    if klub_oznaka:
        pdf.set_font("DejaVuBold", size=9)
        pdf.set_xy(W - 25, (HEADER_H - 5) / 2)
        pdf.cell(21, HEADER_H, klub_oznaka[:10], align="R")

    # ── Klicni znak – izstopajoč box (desno) ────────────────────────────────
    kz = clan.klicni_znak if clan.klicni_znak and clan.klicni_znak != "–" else None

    if kz:
        pdf.set_fill_color(*LIGHT_BG)
        pdf.set_draw_color(*BLUE)
        pdf.set_line_width(0.5)
        pdf.rect(KZ_BOX_X, KZ_BOX_Y, KZ_BOX_W, KZ_BOX_H, "FD")
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_font("DejaVu", size=6)
        pdf.set_xy(KZ_BOX_X, KZ_BOX_Y + 1.5)
        pdf.cell(KZ_BOX_W, 3.5, "klicni znak", align="C")
        pdf.set_text_color(*BLUE)
        pdf.set_font("DejaVuBold", size=12)
        pdf.set_xy(KZ_BOX_X, KZ_BOX_Y + 5.5)
        pdf.cell(KZ_BOX_W, 8, kz[:10], align="C")

    # ── Priimek in ime (levo, dve vrstici) ──────────────────────────────────
    ime_w = (KZ_BOX_X - 6) if kz else (W - 8)
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("DejaVuBold", size=11)
    pdf.set_xy(4, HEADER_H + 2)
    pdf.cell(ime_w, 6.5, clan.priimek[:22])
    pdf.set_font("DejaVu", size=9.5)
    pdf.set_text_color(50, 50, 50)
    pdf.set_xy(4, HEADER_H + 8)
    pdf.cell(ime_w, 6, clan.ime[:22])

    # ── Ločilna črta ────────────────────────────────────────────────────────
    pdf.set_draw_color(190, 210, 230)
    pdf.set_line_width(0.25)
    pdf.line(4, SEP_Y, W - 4, SEP_Y)

    # ── Konfigurabilna polja ─────────────────────────────────────────────────
    aktivna_polja = []
    for polje in polja:
        if polje == "klicni_znak":
            continue
        vrednost = getattr(clan, polje, None)
        if polje == "veljavnost_rd" and vrednost:
            vrednost = vrednost.strftime("%-d. %-m. %Y")
        if not vrednost or vrednost == "–":
            continue
        label = _KARTICA_POLJA_LABELE.get(polje, polje)
        aktivna_polja.append((label, str(vrednost)))

    col_w = (W - 8) / 2
    for i, (label, vrednost) in enumerate(aktivna_polja[:4]):
        col = i % 2
        row = i // 2
        x = 4 + col * col_w
        y = FIELDS_Y + row * ROW_H
        if y + ROW_H > FOOTER_Y:
            break
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_font("DejaVu", size=6.5)
        pdf.set_xy(x, y)
        pdf.cell(col_w, 3, f"{label}:")
        pdf.set_text_color(20, 20, 20)
        pdf.set_font("DejaVu", size=7.5)
        pdf.set_xy(x, y + 3)
        pdf.cell(col_w, 4, vrednost[:24])

    # ── Footer ───────────────────────────────────────────────────────────────
    pdf.set_fill_color(*FOOTER_BG)
    pdf.rect(0, FOOTER_Y, W, 7, "F")
    pdf.set_draw_color(200, 205, 215)
    pdf.set_line_width(0.2)
    pdf.line(0, FOOTER_Y, W, FOOTER_Y)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_font("DejaVu", size=6.5)
    pdf.set_xy(4, FOOTER_Y + 1.5)
    pdf.cell(0, 4, f"Članska izkaznica {leto}")

    return bytes(pdf.output())
