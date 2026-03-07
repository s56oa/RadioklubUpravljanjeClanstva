from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Clanarina, Clan
from ..auth import require_login, is_editor, is_admin
from ..csrf import get_csrf_token, csrf_protect
from ..audit_log import log_akcija

router = APIRouter(prefix="/clanarine")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


@router.get("", response_class=HTMLResponse)
async def seznam(
    request: Request,
    filter: str = "leto",
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    leto_zdaj = date.today().year
    query = db.query(Clanarina).options(joinedload(Clanarina.clan))

    if filter == "leto":
        query = query.filter(Clanarina.leto == leto_zdaj)
    elif filter == "2leti":
        query = query.filter(Clanarina.leto >= leto_zdaj - 1)
    elif filter == "10let":
        query = query.filter(Clanarina.leto >= leto_zdaj - 9)
    # filter == "vse": no year filter

    clanarine = query.order_by(Clanarina.leto.desc()).all()

    # Seštevki po letu (samo plačane)
    sestevki: dict = defaultdict(lambda: {"stevilo_placanih": 0, "skupaj": 0.0})
    for c in clanarine:
        if c.datum_placila:
            sestevki[c.leto]["stevilo_placanih"] += 1
            if c.znesek:
                try:
                    val = float(c.znesek.replace(",", ".").replace("€", "").strip())
                    sestevki[c.leto]["skupaj"] += val
                except ValueError:
                    pass
    sestevki_sorted = sorted(sestevki.items(), reverse=True)

    return templates.TemplateResponse(
        request,
        "clanarine/seznam.html",
        {
            "request": request,
            "user": user,
            "clanarine": clanarine,
            "filter": filter,
            "leto_zdaj": leto_zdaj,
            "sestevki_sorted": sestevki_sorted,
            "is_admin": is_admin(user),
        },
    )


@router.post("/dodaj")
async def dodaj(
    request: Request,
    clan_id: int = Form(...),
    leto: int = Form(...),
    datum_placila: str = Form(""),
    znesek: str = Form(""),
    opombe: str = Form(""),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    # Preveri ali že obstaja vnos za to leto
    obstoječa = (
        db.query(Clanarina)
        .filter(Clanarina.clan_id == clan_id, Clanarina.leto == leto)
        .first()
    )
    try:
        datum_p = date.fromisoformat(datum_placila) if datum_placila else None
    except ValueError:
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    if obstoječa:
        obstoječa.datum_placila = datum_p
        obstoječa.znesek = znesek.strip() or None
        obstoječa.opombe = opombe.strip() or None
    else:
        clanarina = Clanarina(
            clan_id=clan_id,
            leto=leto,
            datum_placila=datum_p,
            znesek=znesek.strip() or None,
            opombe=opombe.strip() or None,
        )
        db.add(clanarina)
    db.commit()
    ip = request.client.host if request.client else None
    log_akcija(db, user.get("uporabnisko_ime") if user else None, "clanarina_dodana",
               f"Clanarina za clan_id {clan_id}, leto {leto}", ip=ip)
    return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)


@router.post("/uredi/{clanarina_id}")
async def uredi(
    request: Request,
    clanarina_id: int,
    clan_id: int = Form(...),
    datum_placila: str = Form(""),
    znesek: str = Form(""),
    opombe: str = Form(""),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    c = db.query(Clanarina).filter(
        Clanarina.id == clanarina_id,
        Clanarina.clan_id == clan_id,
    ).first()
    if not c:
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    try:
        c.datum_placila = date.fromisoformat(datum_placila) if datum_placila.strip() else None
    except ValueError:
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    c.znesek = znesek.strip() or None
    c.opombe = opombe.strip() or None
    db.commit()
    ip = request.client.host if request.client else None
    log_akcija(db, user.get("uporabnisko_ime") if user else None, "clanarina_uredi",
               f"Clanarina {clanarina_id} za clan_id {clan_id}", ip=ip)
    return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)


@router.post("/izbrisi/{clanarina_id}")
async def izbrisi(
    request: Request,
    clanarina_id: int,
    clan_id: int = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    c = db.query(Clanarina).filter(
        Clanarina.id == clanarina_id,
        Clanarina.clan_id == clan_id,
    ).first()
    if c:
        db.delete(c)
        db.commit()
        ip = request.client.host if request.client else None
        log_akcija(db, user.get("uporabnisko_ime") if user else None, "clanarina_izbrisana",
                   f"Clanarina {clanarina_id} izbrisana za clan_id {clan_id}", ip=ip)
    return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)
