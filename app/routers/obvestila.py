"""Router za upravljanje e-poštnih predlog in pošiljanje obvestil."""
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clan, Clanarina, EmailPredloga
from ..auth import require_login, is_admin, is_editor as _is_editor
from ..csrf import get_csrf_token, csrf_protect
from ..email import get_smtp_nastavitve, posli_email
from ..audit_log import log_akcija

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/obvestila")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


def _require_editor(request: Request):
    """Vrne (user, redirect) – editor+ dostop ali redirect na /login."""
    user, redirect = require_login(request)
    if redirect:
        return None, redirect
    if not _is_editor(user):
        return None, RedirectResponse(url="/clani", status_code=302)
    return user, None


# ---------------------------------------------------------------------------
# Seznam predlog
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
async def obvestila_seznam(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    predloge = db.query(EmailPredloga).order_by(EmailPredloga.id).all()
    flash = request.session.pop("obv_flash", None)
    flash_tip = request.session.pop("obv_flash_tip", "success")
    return templates.TemplateResponse(
        request,
        "obvestila/seznam.html",
        {
            "request": request,
            "user": user,
            "predloge": predloge,
            "is_admin": is_admin(user),
            "is_editor": True,
            "flash": flash,
            "flash_tip": flash_tip,
        },
    )


# ---------------------------------------------------------------------------
# Nova predloga
# ---------------------------------------------------------------------------

@router.get("/nova", response_class=HTMLResponse)
async def nova_predloga_get(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request,
        "obvestila/forma.html",
        {
            "request": request,
            "user": user,
            "predloga": None,
            "is_admin": is_admin(user),
            "is_editor": True,
            "naslov": "Nova predloga",
            "action": "/obvestila/nova",
        },
    )


@router.post("/nova")
async def nova_predloga_post(
    request: Request,
    naziv: str = Form(...),
    zadeva: str = Form(...),
    telo_html: str = Form(...),
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    from datetime import datetime
    predloga = EmailPredloga(
        naziv=naziv.strip(),
        zadeva=zadeva.strip(),
        telo_html=telo_html,
        je_privzeta=False,
        created_at=datetime.utcnow(),
    )
    db.add(predloga)
    db.commit()
    log_akcija(db, user.get("uporabnisko_ime"), "email_predloga_nova", f"Nova predloga: {naziv}")
    request.session["obv_flash"] = f"Predloga \"{naziv}\" je bila dodana."
    request.session["obv_flash_tip"] = "success"
    return RedirectResponse(url="/obvestila", status_code=302)


# ---------------------------------------------------------------------------
# Urejanje predloge
# ---------------------------------------------------------------------------

@router.get("/{predloga_id}/uredi", response_class=HTMLResponse)
async def uredi_predloga_get(
    request: Request,
    predloga_id: int,
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    predloga = db.query(EmailPredloga).filter(EmailPredloga.id == predloga_id).first()
    if not predloga:
        return RedirectResponse(url="/obvestila", status_code=302)

    return templates.TemplateResponse(
        request,
        "obvestila/forma.html",
        {
            "request": request,
            "user": user,
            "predloga": predloga,
            "is_admin": is_admin(user),
            "is_editor": True,
            "naslov": "Uredi predlogo",
            "action": f"/obvestila/{predloga_id}/uredi",
        },
    )


@router.post("/{predloga_id}/uredi")
async def uredi_predloga_post(
    request: Request,
    predloga_id: int,
    naziv: str = Form(...),
    zadeva: str = Form(...),
    telo_html: str = Form(...),
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    predloga = db.query(EmailPredloga).filter(EmailPredloga.id == predloga_id).first()
    if not predloga:
        return RedirectResponse(url="/obvestila", status_code=302)

    predloga.naziv = naziv.strip()
    predloga.zadeva = zadeva.strip()
    predloga.telo_html = telo_html
    db.commit()
    log_akcija(db, user.get("uporabnisko_ime"), "email_predloga_uredi", f"Predloga urejena: {naziv}")
    request.session["obv_flash"] = f"Predloga \"{naziv}\" je bila posodobljena."
    request.session["obv_flash_tip"] = "success"
    return RedirectResponse(url="/obvestila", status_code=302)


# ---------------------------------------------------------------------------
# Brisanje predloge
# ---------------------------------------------------------------------------

@router.post("/{predloga_id}/izbrisi")
async def izbrisi_predloga(
    request: Request,
    predloga_id: int,
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    predloga = db.query(EmailPredloga).filter(EmailPredloga.id == predloga_id).first()
    if not predloga:
        return RedirectResponse(url="/obvestila", status_code=302)

    if predloga.je_privzeta:
        request.session["obv_flash"] = "Privzetih predlog ni mogoče izbrisati."
        request.session["obv_flash_tip"] = "danger"
        return RedirectResponse(url="/obvestila", status_code=302)

    naziv = predloga.naziv
    db.delete(predloga)
    db.commit()
    log_akcija(db, user.get("uporabnisko_ime"), "email_predloga_izbrisi", f"Predloga izbrisana: {naziv}")
    request.session["obv_flash"] = f"Predloga \"{naziv}\" je bila izbrisana."
    request.session["obv_flash_tip"] = "success"
    return RedirectResponse(url="/obvestila", status_code=302)


# ---------------------------------------------------------------------------
# Pošiljanje
# ---------------------------------------------------------------------------

@router.get("/posli", response_class=HTMLResponse)
async def posli_get(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    predloge = db.query(EmailPredloga).order_by(EmailPredloga.id).all()
    leto_zdaj = date.today().year

    # Predinizializacija iz query parametrov (klik iz detail.html ali seznam.html)
    clan_id_str = request.query_params.get("clan_id", "")
    clan_id = int(clan_id_str) if clan_id_str.isdigit() else None
    izbran_clan = db.query(Clan).filter(Clan.id == clan_id).first() if clan_id else None

    flash = request.session.pop("obv_flash", None)
    flash_tip = request.session.pop("obv_flash_tip", "danger")
    return templates.TemplateResponse(
        request,
        "obvestila/posli.html",
        {
            "request": request,
            "user": user,
            "predloge": predloge,
            "is_admin": is_admin(user),
            "is_editor": True,
            "leto_zdaj": leto_zdaj,
            "izbran_clan": izbran_clan,
            "flash": flash,
            "flash_tip": flash_tip,
        },
    )


@router.post("/posli")
async def posli_post(
    request: Request,
    predloga_id: int = Form(...),
    zadeva: str = Form(...),
    telo_html: str = Form(...),
    leto: int = Form(...),
    clan_id: str = Form(""),
    bulk_filter: str = Form("neplacniki"),
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    predloga = db.query(EmailPredloga).filter(EmailPredloga.id == predloga_id).first()

    # Preveri SMTP nastavitve
    try:
        smtp_nas = get_smtp_nastavitve(db)
    except ValueError as e:
        request.session["obv_flash"] = str(e)
        request.session["obv_flash_tip"] = "danger"
        return RedirectResponse(url="/obvestila/posli", status_code=302)

    poslano = 0
    preskoceno = 0

    if clan_id and clan_id.strip().isdigit():
        # Pošlji posamezniku
        clan = db.query(Clan).filter(Clan.id == int(clan_id)).first()
        if clan and clan.elektronska_posta and "@" in clan.elektronska_posta:
            try:
                posli_email(clan, zadeva, telo_html, leto, smtp_nas, db)
                poslano = 1
                log_akcija(db, user.get("uporabnisko_ime"), "email_poslan",
                           f"Email poslan: {clan.priimek} {clan.ime} ({clan.elektronska_posta}), leto {leto}")
            except Exception as e:
                logger.error(f"Napaka pri pošiljanju emaila za {clan.elektronska_posta}: {e}")
                request.session["obv_flash"] = f"Napaka pri pošiljanju: {e}"
                request.session["obv_flash_tip"] = "danger"
                return RedirectResponse(url="/obvestila/posli", status_code=302)
        else:
            preskoceno = 1
    else:
        # Bulk: filter določa skupino prejemnikov
        danes = date.today()
        if bulk_filter == "rd_potekla":
            # Aktivni člani s potečeno veljavnostjo RD
            clani = (
                db.query(Clan)
                .filter(Clan.aktiven == True, Clan.veljavnost_rd < danes)
                .order_by(Clan.priimek, Clan.ime)
                .all()
            )
        elif bulk_filter == "rd_kmalu":
            # Aktivni člani, katerim RD poteče v naslednjih 180 dneh
            meja = danes + timedelta(days=180)
            clani = (
                db.query(Clan)
                .filter(Clan.aktiven == True, Clan.veljavnost_rd >= danes, Clan.veljavnost_rd <= meja)
                .order_by(Clan.priimek, Clan.ime)
                .all()
            )
        elif bulk_filter == "vsi_aktivni":
            # Vsi aktivni člani
            clani = (
                db.query(Clan)
                .filter(Clan.aktiven == True)
                .order_by(Clan.priimek, Clan.ime)
                .all()
            )
        elif bulk_filter == "vsi":
            # Vsi člani (aktivni in neaktivni)
            clani = (
                db.query(Clan)
                .order_by(Clan.priimek, Clan.ime)
                .all()
            )
        else:
            # Privzeto: vsi aktivni neplačniki za izbrano leto
            clan_ids_placali = db.query(Clanarina.clan_id).filter(Clanarina.leto == leto)
            clani = (
                db.query(Clan)
                .filter(Clan.aktiven == True, ~Clan.id.in_(clan_ids_placali))
                .order_by(Clan.priimek, Clan.ime)
                .all()
            )
        napake = []
        for clan in clani:
            if not clan.elektronska_posta or "@" not in clan.elektronska_posta:
                preskoceno += 1
                continue
            try:
                posli_email(clan, zadeva, telo_html, leto, smtp_nas, db)
                poslano += 1
            except Exception as e:
                logger.error(f"Napaka pri pošiljanju emaila za {clan.elektronska_posta}: {e}")
                napake.append(clan.elektronska_posta)
                preskoceno += 1

        if napake:
            log_akcija(db, user.get("uporabnisko_ime"), "email_bulk_napaka",
                       f"Napake pri bulk pošiljanju: {', '.join(napake[:5])}")

        log_akcija(db, user.get("uporabnisko_ime"), "email_bulk_poslan",
                   f"Bulk email ({bulk_filter}): {poslano} poslanih, {preskoceno} preskočenih, leto {leto}")

    request.session["obv_rezultat_poslano"] = poslano
    request.session["obv_rezultat_preskoceno"] = preskoceno
    return RedirectResponse(url="/obvestila/rezultat", status_code=302)


@router.get("/rezultat", response_class=HTMLResponse)
async def posli_rezultat(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = _require_editor(request)
    if redirect:
        return redirect

    poslano = request.session.pop("obv_rezultat_poslano", 0)
    preskoceno = request.session.pop("obv_rezultat_preskoceno", 0)

    return templates.TemplateResponse(
        request,
        "obvestila/rezultat.html",
        {
            "request": request,
            "user": user,
            "is_admin": is_admin(user),
            "is_editor": True,
            "poslano": poslano,
            "preskoceno": preskoceno,
        },
    )
