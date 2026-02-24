import re
from datetime import date, timedelta

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clan, Clanarina
from ..auth import get_user, require_login, is_editor, is_admin
from ..config import get_tipi_clanstva, get_operaterski_razredi
from ..csrf import get_csrf_token, csrf_protect
from ..audit_log import log_akcija

router = APIRouter(prefix="/clani")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


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


@router.get("", response_class=HTMLResponse)
async def seznam(
    request: Request,
    q: str = "",
    tip: str = "",
    aktiven: str = "da",
    placal: str = "",
    rd: str = "",
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    danes = date.today()
    kmalu_meja = danes + timedelta(days=180)
    leto = danes.year
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
        query = query.filter(Clan.tip_clanstva == tip)

    # Filter po RD veljavnosti
    if rd == "potekla":
        query = query.filter(Clan.veljavnost_rd != None, Clan.veljavnost_rd < danes)
    elif rd == "kmalu":
        query = query.filter(Clan.veljavnost_rd >= danes, Clan.veljavnost_rd <= kmalu_meja)
    elif rd == "veljavna":
        query = query.filter(Clan.veljavnost_rd > kmalu_meja)
    elif rd == "brez":
        query = query.filter(Clan.veljavnost_rd == None)

    clani = query.order_by(Clan.priimek, Clan.ime).all()

    # Pripravi set članov ki so plačali za tekoče leto
    placali_ids = {
        c.clan_id
        for c in db.query(Clanarina).filter(Clanarina.leto == leto).all()
        if c.datum_placila is not None
    }

    if placal == "da":
        clani = [c for c in clani if c.id in placali_ids]
    elif placal == "ne":
        clani = [c for c in clani if c.id not in placali_ids]

    return templates.TemplateResponse(
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
            "tipi_clanstva": get_tipi_clanstva(db),
            "placali_ids": placali_ids,
            "leto": leto,
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
        veljavnost_rd=date.fromisoformat(veljavnost_rd) if veljavnost_rd else None,
        es_stevilka=int(es_stevilka) if es_stevilka.strip() else None,
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

    return templates.TemplateResponse(
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
            "is_editor": is_editor(user),
            "is_admin": is_admin(user),
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
    clan.veljavnost_rd = date.fromisoformat(veljavnost_rd) if veljavnost_rd else None
    clan.es_stevilka = int(es_stevilka) if es_stevilka.strip() else None
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
