from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clan, Skupina
from ..auth import require_login, is_editor, is_admin
from ..csrf import get_csrf_token, csrf_protect

router = APIRouter(prefix="/skupine")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


@router.get("", response_class=HTMLResponse)
async def seznam(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    skupine = db.query(Skupina).order_by(Skupina.ime).all()
    return templates.TemplateResponse(
        "skupine/seznam.html",
        {
            "request": request,
            "user": user,
            "skupine": skupine,
            "is_editor": is_editor(user),
            "is_admin": is_admin(user),
        },
    )


@router.get("/nova", response_class=HTMLResponse)
async def nova_form(request: Request) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url="/skupine", status_code=302)
    return templates.TemplateResponse(
        "skupine/form.html",
        {
            "request": request,
            "user": user,
            "skupina": None,
            "is_editor": True,
            "is_admin": is_admin(user),
        },
    )


@router.post("/nova")
async def nova_shrani(
    request: Request,
    ime: str = Form(...),
    opis: str = Form(""),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url="/skupine", status_code=302)

    s = Skupina(ime=ime.strip(), opis=opis.strip() or None)
    db.add(s)
    db.commit()
    db.refresh(s)
    return RedirectResponse(url=f"/skupine/{s.id}", status_code=302)


@router.get("/{skupid}", response_class=HTMLResponse)
async def detail(request: Request, skupid: int, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    skupina = db.query(Skupina).filter(Skupina.id == skupid).first()
    if not skupina:
        return RedirectResponse(url="/skupine", status_code=302)

    # Aktivni člani ki še niso v skupini
    obstoječi_ids = {c.id for c in skupina.clani}
    query = db.query(Clan).filter(Clan.aktiven == True)
    if obstoječi_ids:
        query = query.filter(~Clan.id.in_(obstoječi_ids))
    prosti_clani = query.order_by(Clan.priimek, Clan.ime).all()
    # Člani v skupini, razvrščeni po priimku
    clani_v_skupini = sorted(skupina.clani, key=lambda c: (c.priimek, c.ime))

    return templates.TemplateResponse(
        "skupine/detail.html",
        {
            "request": request,
            "user": user,
            "skupina": skupina,
            "clani_v_skupini": clani_v_skupini,
            "prosti_clani": prosti_clani,
            "is_editor": is_editor(user),
            "is_admin": is_admin(user),
        },
    )


@router.post("/{skupid}/uredi")
async def uredi(
    request: Request,
    skupid: int,
    ime: str = Form(...),
    opis: str = Form(""),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/skupine/{skupid}", status_code=302)

    skupina = db.query(Skupina).filter(Skupina.id == skupid).first()
    if not skupina:
        return RedirectResponse(url="/skupine", status_code=302)

    skupina.ime = ime.strip()
    skupina.opis = opis.strip() or None
    db.commit()
    return RedirectResponse(url=f"/skupine/{skupid}", status_code=302)


@router.post("/{skupid}/izbrisi")
async def izbrisi(
    request: Request,
    skupid: int,
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/skupine/{skupid}", status_code=302)

    skupina = db.query(Skupina).filter(Skupina.id == skupid).first()
    if skupina:
        db.delete(skupina)
        db.commit()
    return RedirectResponse(url="/skupine", status_code=302)


@router.post("/{skupid}/dodaj-clana")
async def dodaj_clana(
    request: Request,
    skupid: int,
    clan_id: int = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/skupine/{skupid}", status_code=302)

    skupina = db.query(Skupina).filter(Skupina.id == skupid).first()
    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if skupina and clan and clan not in skupina.clani:
        skupina.clani.append(clan)
        db.commit()
    return RedirectResponse(url=f"/skupine/{skupid}", status_code=302)


@router.post("/{skupid}/odstrani-clana/{clan_id}")
async def odstrani_clana(
    request: Request,
    skupid: int,
    clan_id: int,
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/skupine/{skupid}", status_code=302)

    skupina = db.query(Skupina).filter(Skupina.id == skupid).first()
    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if skupina and clan and clan in skupina.clani:
        skupina.clani.remove(clan)
        db.commit()
    return RedirectResponse(url=f"/skupine/{skupid}", status_code=302)
