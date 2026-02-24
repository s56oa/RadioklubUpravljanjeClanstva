from datetime import date

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clanarina
from ..auth import require_login, is_editor
from ..csrf import csrf_protect

router = APIRouter(prefix="/clanarine")


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
    if obstoječa:
        obstoječa.datum_placila = date.fromisoformat(datum_placila) if datum_placila else None
        obstoječa.znesek = znesek.strip() or None
        obstoječa.opombe = opombe.strip() or None
    else:
        clanarina = Clanarina(
            clan_id=clan_id,
            leto=leto,
            datum_placila=date.fromisoformat(datum_placila) if datum_placila else None,
            znesek=znesek.strip() or None,
            opombe=opombe.strip() or None,
        )
        db.add(clanarina)
    db.commit()
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

    c = db.query(Clanarina).filter(Clanarina.id == clanarina_id).first()
    if c:
        db.delete(c)
        db.commit()
    return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)
