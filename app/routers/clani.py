import io
import os
import re
from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from fpdf import FPDF
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clan, Clanarina, EmailPredloga
from ..auth import get_user, require_login, is_editor, is_admin
from ..config import get_tipi_clanstva, get_operaterski_razredi, get_vloge_clanov, get_nastavitev
from ..csrf import get_csrf_token, csrf_protect
from ..audit_log import log_akcija
from ..email import posli_email, get_smtp_nastavitve

router = APIRouter(prefix="/clani")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token

_FONT_PATH      = os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "DejaVuSans.ttf")
_FONT_BOLD_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "DejaVuSans-Bold.ttf")

_KARTICA_POLJA_LABELE: dict[str, str] = {
    "tip_clanstva":       "Tip",
    "operaterski_razred": "Razred",
    "es_stevilka":        "ES",
    "veljavnost_rd":      "Veljavnost RD",
}

_KARTICA_POLJA_PRIVZETO = "klicni_znak,tip_clanstva,operaterski_razred,es_stevilka,veljavnost_rd"


def _generiraj_kartico_pdf(clan: Clan, leto: int, klub_ime: str,
                            klub_oznaka: str, polja: list[str]) -> bytes:
    """Generira PDF člansko kartico formata 85.6 × 54 mm."""
    W, H = 85.6, 54.0
    BLUE      = (0, 70, 127)
    BLUE_DARK = (0, 50, 100)
    LIGHT_BG  = (240, 246, 252)   # zelo svetlo modra za KZ box
    GRAY_TEXT = (120, 120, 120)
    FOOTER_BG = (245, 245, 245)

    pdf = FPDF(unit="mm", format=(W, H))
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(False)
    pdf.add_font("DejaVu",     style="",  fname=_FONT_PATH)
    pdf.add_font("DejaVuBold", style="",  fname=_FONT_BOLD_PATH)
    pdf.add_page()

    # Geometrija
    HEADER_H  = 12.5   # višina headerja
    KZ_BOX_X  = W - 27
    KZ_BOX_W  = 23
    KZ_BOX_Y  = HEADER_H + 1
    KZ_BOX_H  = 16
    SEP_Y     = HEADER_H + KZ_BOX_H + 1.5   # ~30
    FIELDS_Y  = SEP_Y + 1.5                  # ~31.5
    ROW_H     = 7.5    # label 3 + vrednost 4 + 0.5 mm vrzel
    FOOTER_Y  = H - 7

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
        # "klicni znak" labela
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_font("DejaVu", size=6)
        pdf.set_xy(KZ_BOX_X, KZ_BOX_Y + 1.5)
        pdf.cell(KZ_BOX_W, 3.5, "klicni znak", align="C")
        # KZ vrednost
        pdf.set_text_color(*BLUE)
        pdf.set_font("DejaVuBold", size=12)
        pdf.set_xy(KZ_BOX_X, KZ_BOX_Y + 5.5)
        pdf.cell(KZ_BOX_W, 8, kz[:10], align="C")

    # ── Priimek in ime (levo, dve vrstici) ──────────────────────────────────
    ime_w = (KZ_BOX_X - 6) if kz else (W - 8)
    # Priimek – poudarjen
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("DejaVuBold", size=11)
    pdf.set_xy(4, HEADER_H + 2)
    pdf.cell(ime_w, 6.5, clan.priimek[:22])
    # Ime – malo manjši
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

    col_w = (W - 8) / 2    # ~38.8 mm na stolpec
    for i, (label, vrednost) in enumerate(aktivna_polja[:4]):
        col = i % 2
        row = i // 2
        x = 4 + col * col_w
        y = FIELDS_Y + row * ROW_H
        if y + ROW_H > FOOTER_Y:
            break
        # Labela – siva, manjša
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_font("DejaVu", size=6.5)
        pdf.set_xy(x, y)
        pdf.cell(col_w, 3, f"{label}:")
        # Vrednost – temna
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


def _normaliziraj_clan(priimek, ime, klicni_znak, elektronska_posta, tip_clanstva, dovoljeni_tipi):
    """Normalizira in validira polja. Vrne (priimek, ime, kz, email, tip, napaka|None)."""
    priimek = priimek.strip().title()
    ime = ime.strip().title()
    kz = klicni_znak.strip().upper() or None
    email = elektronska_posta.strip().lower() or None
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return priimek, ime, kz, email, tip_clanstva, "Neveljaven e-poštni naslov."
    if tip_clanstva and tip_clanstva not in dovoljeni_tipi:
        tip_clanstva = dovoljeni_tipi[0] if dovoljeni_tipi else tip_clanstva
    return priimek, ime, kz, email, tip_clanstva, None


def _filtriraj_clane(
    db: Session,
    q: str = "",
    tip: List[str] = None,
    aktiven: str = "",
    rd: List[str] = None,
    operaterski_razred: List[str] = None,
    danes: date = None,
    kmalu_meja: date = None,
) -> list:
    """Vrne seznam članov z apliciranimi filtri (brez placal filtra)."""
    if danes is None:
        danes = date.today()
    if kmalu_meja is None:
        kmalu_meja = danes + timedelta(days=180)
    tip = tip or []
    rd = rd or []
    operaterski_razred = operaterski_razred or []

    query = db.query(Clan)

    if aktiven == "da":
        query = query.filter(Clan.aktiven == True)
    elif aktiven == "ne":
        query = query.filter(Clan.aktiven == False)

    if q:
        query = query.filter(
            or_(
                Clan.priimek.ilike(f"%{q}%"),
                Clan.ime.ilike(f"%{q}%"),
                Clan.klicni_znak.ilike(f"%{q}%"),
            )
        )

    if tip:
        query = query.filter(Clan.tip_clanstva.in_(tip))

    if operaterski_razred:
        query = query.filter(Clan.operaterski_razred.in_(operaterski_razred))

    if rd:
        rd_conds = []
        for r in rd:
            if r == "potekla":
                rd_conds.append(and_(Clan.veljavnost_rd != None, Clan.veljavnost_rd < danes))
            elif r == "kmalu":
                rd_conds.append(and_(Clan.veljavnost_rd >= danes, Clan.veljavnost_rd <= kmalu_meja))
            elif r == "veljavna":
                rd_conds.append(Clan.veljavnost_rd > kmalu_meja)
            elif r == "brez":
                rd_conds.append(Clan.veljavnost_rd == None)
        if rd_conds:
            query = query.filter(or_(*rd_conds))

    return query.order_by(Clan.priimek, Clan.ime).all()


@router.get("", response_class=HTMLResponse)
async def seznam(
    request: Request,
    q: str = "",
    tip: List[str] = Query(default=[]),
    aktiven: str = "da",
    placal: str = "",
    rd: List[str] = Query(default=[]),
    operaterski_razred: List[str] = Query(default=[]),
    leto_placila: int = 0,
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    danes = date.today()
    kmalu_meja = danes + timedelta(days=180)
    leto_zdaj = danes.year
    leto_ef = leto_placila if leto_placila else leto_zdaj

    clani = _filtriraj_clane(db, q=q, tip=tip, aktiven=aktiven, rd=rd,
                              operaterski_razred=operaterski_razred,
                              danes=danes, kmalu_meja=kmalu_meja)

    # Pripravi set članov ki so plačali za izbrano leto
    placali_ids = {
        c.clan_id
        for c in db.query(Clanarina).filter(Clanarina.leto == leto_ef).all()
        if c.datum_placila is not None
    }

    if placal == "da":
        clani = [c for c in clani if c.id in placali_ids]
    elif placal == "ne":
        clani = [c for c in clani if c.id not in placali_ids]

    return templates.TemplateResponse(
        request,
        "clani/seznam.html",
        {
            "request": request,
            "user": user,
            "clani": clani,
            "q": q,
            "tip": tip,
            "aktiven": aktiven,
            "placal": placal,
            "rd": rd,
            "operaterski_razred": operaterski_razred,
            "tipi_clanstva": get_tipi_clanstva(db),
            "operaterski_razredi": get_operaterski_razredi(db),
            "placali_ids": placali_ids,
            "leto": leto_ef,
            "leto_zdaj": leto_zdaj,
            "leto_placila": leto_placila,
            "danes": danes,
            "kmalu_meja": kmalu_meja,
            "is_editor": is_editor(user),
            "is_admin": is_admin(user),
        },
    )


@router.get("/nov", response_class=HTMLResponse)
async def nov_form(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url="/clani", status_code=302)
    return templates.TemplateResponse(
        request,
        "clani/form.html",
        {
            "request": request,
            "user": user,
            "clan": None,
            "tipi_clanstva": get_tipi_clanstva(db),
            "operaterski_razredi": get_operaterski_razredi(db),
            "is_admin": is_admin(user),
        },
    )


@router.post("/nov", response_class=HTMLResponse)
async def nov_shrani(
    request: Request,
    priimek: str = Form(...),
    ime: str = Form(...),
    klicni_znak: str = Form(""),
    naslov_ulica: str = Form(""),
    naslov_posta: str = Form(""),
    tip_clanstva: str = Form("Osebni"),
    klicni_znak_nosilci: str = Form(""),
    operaterski_razred: str = Form(""),
    mobilni_telefon: str = Form(""),
    telefon_doma: str = Form(""),
    elektronska_posta: str = Form(""),
    soglasje_op: str = Form(""),
    izjava: str = Form(""),
    veljavnost_rd: str = Form(""),
    es_stevilka: str = Form(""),
    opombe: str = Form(""),
    aktiven: str = Form("da"),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url="/clani", status_code=302)

    tipi = get_tipi_clanstva(db)
    priimek, ime, kz, email, tip_clanstva, napaka = _normaliziraj_clan(
        priimek, ime, klicni_znak, elektronska_posta, tip_clanstva, tipi
    )
    if napaka:
        return templates.TemplateResponse(
            request,
            "clani/form.html",
            {
                "request": request,
                "user": user,
                "clan": None,
                "tipi_clanstva": tipi,
                "operaterski_razredi": get_operaterski_razredi(db),
                "is_admin": is_admin(user),
                "napaka": napaka,
            },
        )

    try:
        vrd = date.fromisoformat(veljavnost_rd) if veljavnost_rd else None
        es_st = int(es_stevilka) if es_stevilka.strip() else None
    except ValueError:
        napaka = "Napačen format datuma veljavnosti RD ali številke E.S. kartice."
        return templates.TemplateResponse(
            request,
            "clani/form.html",
            {
                "request": request,
                "user": user,
                "clan": None,
                "tipi_clanstva": tipi,
                "operaterski_razredi": get_operaterski_razredi(db),
                "is_admin": is_admin(user),
                "napaka": napaka,
            },
        )

    clan = Clan(
        priimek=priimek,
        ime=ime,
        klicni_znak=kz,
        naslov_ulica=naslov_ulica.strip() or None,
        naslov_posta=naslov_posta.strip() or None,
        tip_clanstva=tip_clanstva,
        klicni_znak_nosilci=klicni_znak_nosilci.strip().upper() or None,
        operaterski_razred=operaterski_razred.strip() or None,
        mobilni_telefon=mobilni_telefon.strip() or None,
        telefon_doma=telefon_doma.strip() or None,
        elektronska_posta=email,
        soglasje_op=soglasje_op.strip() or None,
        izjava=izjava.strip() or None,
        veljavnost_rd=vrd,
        es_stevilka=es_st,
        opombe=opombe.strip() or None,
        aktiven=(aktiven == "da"),
    )
    db.add(clan)
    db.commit()
    db.refresh(clan)
    ip = request.client.host if request.client else None
    log_akcija(db, user.get("uporabnisko_ime") if user else None, "clan_dodan",
               f"{clan.priimek} {clan.ime}", ip=ip)
    return RedirectResponse(url=f"/clani/{clan.id}", status_code=302)


@router.get("/{clan_id}", response_class=HTMLResponse)
async def detail(request: Request, clan_id: int, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return RedirectResponse(url="/clani", status_code=302)

    ip = request.client.host if request.client else None
    log_akcija(db, user.get("uporabnisko_ime") if user else None, "clan_ogled",
               f"{clan.priimek} {clan.ime} (ID {clan_id})", ip=ip)

    # Vse clanarine za tega clana, plus prikaz neplacanih let
    clanarine_dict = {c.leto: c for c in clan.clanarine}
    leto_zdaj = date.today().year
    # Prikaži leta od 2017 do trenutnega
    vsa_leta = list(range(leto_zdaj, 2016, -1))

    flash_success = request.session.pop("flash_success", None)
    flash_warning = request.session.pop("flash_warning", None)

    return templates.TemplateResponse(
        request,
        "clani/detail.html",
        {
            "request": request,
            "user": user,
            "clan": clan,
            "clanarine_dict": clanarine_dict,
            "vsa_leta": vsa_leta,
            "leto_zdaj": leto_zdaj,
            "today": date.today(),
            "aktivnosti": clan.aktivnosti,
            "vloge_clanov": get_vloge_clanov(db),
            "is_editor": is_editor(user),
            "is_admin": is_admin(user),
            "flash_success": flash_success,
            "flash_warning": flash_warning,
        },
    )


@router.get("/{clan_id}/uredi", response_class=HTMLResponse)
async def uredi_form(request: Request, clan_id: int, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return RedirectResponse(url="/clani", status_code=302)

    return templates.TemplateResponse(
        request,
        "clani/form.html",
        {
            "request": request,
            "user": user,
            "clan": clan,
            "tipi_clanstva": get_tipi_clanstva(db),
            "operaterski_razredi": get_operaterski_razredi(db),
            "is_admin": is_admin(user),
        },
    )


@router.post("/{clan_id}/uredi", response_class=HTMLResponse)
async def uredi_shrani(
    request: Request,
    clan_id: int,
    priimek: str = Form(...),
    ime: str = Form(...),
    klicni_znak: str = Form(""),
    naslov_ulica: str = Form(""),
    naslov_posta: str = Form(""),
    tip_clanstva: str = Form("Osebni"),
    klicni_znak_nosilci: str = Form(""),
    operaterski_razred: str = Form(""),
    mobilni_telefon: str = Form(""),
    telefon_doma: str = Form(""),
    elektronska_posta: str = Form(""),
    soglasje_op: str = Form(""),
    izjava: str = Form(""),
    veljavnost_rd: str = Form(""),
    es_stevilka: str = Form(""),
    opombe: str = Form(""),
    aktiven: str = Form("da"),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return RedirectResponse(url="/clani", status_code=302)

    tipi = get_tipi_clanstva(db)
    priimek, ime, kz, email, tip_clanstva, napaka = _normaliziraj_clan(
        priimek, ime, klicni_znak, elektronska_posta, tip_clanstva, tipi
    )
    if napaka:
        return templates.TemplateResponse(
            request,
            "clani/form.html",
            {
                "request": request,
                "user": user,
                "clan": clan,
                "tipi_clanstva": tipi,
                "operaterski_razredi": get_operaterski_razredi(db),
                "is_admin": is_admin(user),
                "napaka": napaka,
            },
        )

    try:
        vrd = date.fromisoformat(veljavnost_rd) if veljavnost_rd else None
        es_st = int(es_stevilka) if es_stevilka.strip() else None
    except ValueError:
        napaka = "Napačen format datuma veljavnosti RD ali številke E.S. kartice."
        return templates.TemplateResponse(
            request,
            "clani/form.html",
            {
                "request": request,
                "user": user,
                "clan": clan,
                "tipi_clanstva": tipi,
                "operaterski_razredi": get_operaterski_razredi(db),
                "is_admin": is_admin(user),
                "napaka": napaka,
            },
        )

    clan.priimek = priimek
    clan.ime = ime
    clan.klicni_znak = kz
    clan.naslov_ulica = naslov_ulica.strip() or None
    clan.naslov_posta = naslov_posta.strip() or None
    clan.tip_clanstva = tip_clanstva
    clan.klicni_znak_nosilci = klicni_znak_nosilci.strip().upper() or None
    clan.operaterski_razred = operaterski_razred.strip() or None
    clan.mobilni_telefon = mobilni_telefon.strip() or None
    clan.telefon_doma = telefon_doma.strip() or None
    clan.elektronska_posta = email
    clan.soglasje_op = soglasje_op.strip() or None
    clan.izjava = izjava.strip() or None
    clan.veljavnost_rd = vrd
    clan.es_stevilka = es_st
    clan.opombe = opombe.strip() or None
    clan.aktiven = aktiven == "da"
    db.commit()
    ip = request.client.host if request.client else None
    log_akcija(db, user.get("uporabnisko_ime") if user else None, "clan_urejen",
               f"{clan.priimek} {clan.ime} (ID {clan_id})", ip=ip)
    return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)


@router.post("/{clan_id}/izbrisi")
async def izbrisi(request: Request, clan_id: int, db: Session = Depends(get_db), _csrf: None = Depends(csrf_protect)) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if clan:
        opis = f"{clan.priimek} {clan.ime} (ID {clan_id})"
        db.delete(clan)
        db.commit()
        ip = request.client.host if request.client else None
        log_akcija(db, user.get("uporabnisko_ime") if user else None, "clan_izbrisan",
                   opis, ip=ip)
    return RedirectResponse(url="/clani", status_code=302)


# ---------------------------------------------------------------------------
# Članska kartica
# ---------------------------------------------------------------------------

def _kartica_polja(db: Session) -> list[str]:
    """Prebere seznam polj za kartico iz nastavitev."""
    vrednost = get_nastavitev(db, "kartica_polja", _KARTICA_POLJA_PRIVZETO)
    return [p.strip() for p in vrednost.split(",") if p.strip()]


@router.get("/{clan_id}/kartica", response_class=HTMLResponse)
async def kartica_html(
    request: Request, clan_id: int,
    leto: int = 0, db: Session = Depends(get_db),
) -> Response:
    """Prikaže HTML stran za tisk/predogled članske kartice."""
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return RedirectResponse(url="/clani", status_code=302)

    if not leto:
        leto = date.today().year

    klub_ime = get_nastavitev(db, "klub_ime", "")
    klub_oznaka = get_nastavitev(db, "klub_oznaka", "")
    polja = _kartica_polja(db)

    return templates.TemplateResponse(
        request, "clani/kartica.html",
        {
            "request": request, "user": user,
            "clan": clan, "leto": leto,
            "klub_ime": klub_ime, "klub_oznaka": klub_oznaka,
            "polja": polja,
            "polja_labele": _KARTICA_POLJA_LABELE,
        },
    )


@router.get("/{clan_id}/kartica.pdf")
async def kartica_pdf(
    request: Request, clan_id: int,
    leto: int = 0, db: Session = Depends(get_db),
) -> Response:
    """Vrne PDF datoteko članske kartice."""
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return RedirectResponse(url="/clani", status_code=302)

    if not leto:
        leto = date.today().year

    klub_ime = get_nastavitev(db, "klub_ime", "")
    klub_oznaka = get_nastavitev(db, "klub_oznaka", "")
    polja = _kartica_polja(db)

    pdf_bytes = _generiraj_kartico_pdf(clan, leto, klub_ime, klub_oznaka, polja)
    kz_raw = clan.klicni_znak or str(clan_id)
    # Sanitizacija: pusti samo alfanumerične znake in pomišljaj (varno za HTTP header)
    kz_safe = re.sub(r"[^A-Za-z0-9\-]", "_", kz_raw)
    filename = f"kartica_{kz_safe}_{leto}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{clan_id}/posli-kartico")
async def posli_kartico(
    request: Request, clan_id: int,
    leto: int = Form(...),
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    """Pošlje PDF kartico na email člana."""
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    if not (2000 <= leto <= 2100):
        request.session["flash_warning"] = "Neveljavno leto."
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return RedirectResponse(url="/clani", status_code=302)

    if not clan.elektronska_posta:
        request.session["flash_warning"] = "Član nima vpisanega e-poštnega naslova."
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    # Preveri pogoje pred generacijo PDF (hitro odpove brez dela)
    predloga = db.query(EmailPredloga).filter(
        EmailPredloga.naziv == "Pošiljanje članske kartice"
    ).first()
    if not predloga:
        request.session["flash_warning"] = "Predloga 'Pošiljanje članske kartice' ni najdena. Zaženi aplikacijo znova za inicializacijo predlog."
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    try:
        smtp = get_smtp_nastavitve(db)
    except ValueError as e:
        request.session["flash_warning"] = str(e)
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    klub_ime = get_nastavitev(db, "klub_ime", "")
    klub_oznaka = get_nastavitev(db, "klub_oznaka", "")
    polja = _kartica_polja(db)

    pdf_bytes = _generiraj_kartico_pdf(clan, leto, klub_ime, klub_oznaka, polja)
    kz_raw = clan.klicni_znak or str(clan_id)
    kz_safe = re.sub(r"[^A-Za-z0-9\-]", "_", kz_raw)
    filename = f"kartica_{kz_safe}_{leto}.pdf"

    try:
        posli_email(
            clan=clan,
            zadeva_predloga=predloga.zadeva,
            telo_predloga=predloga.telo_html,
            leto=leto,
            smtp_nastavitve=smtp,
            db=db,
            vkljuci_qr=False,
            priponke=[(filename, pdf_bytes, "application/pdf")],
        )
        ip = request.client.host if request.client else None
        log_akcija(db, user.get("uporabnisko_ime") if user else None,
                   "kartica_poslana",
                   f"{clan.priimek} {clan.ime} (ID {clan_id}), leto {leto}", ip=ip)
        request.session["flash_success"] = f"Kartica za leto {leto} je bila poslana na {clan.elektronska_posta}."
    except Exception as e:
        request.session["flash_warning"] = f"Napaka pri pošiljanju kartice: {e}"

    return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)
