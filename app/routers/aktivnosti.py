from datetime import date

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Aktivnost, Clan
from ..auth import require_login, is_editor, is_admin
from ..csrf import get_csrf_token, csrf_protect

router = APIRouter(prefix="/aktivnosti")
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
    query = db.query(Aktivnost).options(joinedload(Aktivnost.clan))

    if filter == "leto":
        query = query.filter(Aktivnost.leto == leto_zdaj)
    elif filter == "2leti":
        query = query.filter(Aktivnost.leto >= leto_zdaj - 1)
    elif filter == "10let":
        query = query.filter(Aktivnost.leto >= leto_zdaj - 9)
    # filter == "vse": no year filter

    aktivnosti = query.order_by(Aktivnost.leto.desc(), Aktivnost.datum.desc()).all()
    ure_skupaj = round(sum(a.delovne_ure for a in aktivnosti if a.delovne_ure), 1)

    return templates.TemplateResponse(
        "aktivnosti/seznam.html",
        {
            "request": request,
            "user": user,
            "aktivnosti": aktivnosti,
            "filter": filter,
            "leto_zdaj": leto_zdaj,
            "ure_skupaj": ure_skupaj,
            "is_admin": is_admin(user),
        },
    )


@router.post("/dodaj")
async def dodaj(
    request: Request,
    clan_id: int = Form(...),
    leto: int = Form(...),
    datum: str = Form(""),
    opis: str = Form(...),
    delovne_ure: str = Form(""),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    opis = opis.strip()[:1000]
    if not opis:
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    ure: float | None = None
    if delovne_ure.strip():
        try:
            ure = float(delovne_ure.replace(",", "."))
        except ValueError:
            pass

    a = Aktivnost(
        clan_id=clan_id,
        leto=leto,
        datum=date.fromisoformat(datum) if datum else None,
        opis=opis,
        delovne_ure=ure,
    )
    db.add(a)
    db.commit()
    return RedirectResponse(url=f"/clani/{clan_id}#aktivnosti", status_code=302)


@router.post("/izbrisi/{aktivnost_id}")
async def izbrisi(
    request: Request,
    aktivnost_id: int,
    clan_id: int = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    a = db.query(Aktivnost).filter(Aktivnost.id == aktivnost_id).first()
    if a:
        db.delete(a)
        db.commit()
    return RedirectResponse(url=f"/clani/{clan_id}#aktivnosti", status_code=302)
