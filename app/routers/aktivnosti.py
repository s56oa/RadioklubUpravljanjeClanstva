from datetime import date

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Aktivnost
from ..auth import require_login, is_editor
from ..csrf import csrf_protect

router = APIRouter(prefix="/aktivnosti")


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
