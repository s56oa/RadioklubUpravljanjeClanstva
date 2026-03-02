from datetime import date

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ClanVloga
from ..auth import require_login, is_editor, is_admin
from ..csrf import csrf_protect

router = APIRouter(prefix="/vloge")


@router.post("/dodaj")
async def dodaj(
    request: Request,
    clan_id: int = Form(...),
    naziv: str = Form(...),
    datum_od: str = Form(...),
    datum_do: str = Form(""),
    opombe: str = Form(""),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_editor(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    naziv = naziv.strip()
    if not naziv or not datum_od:
        return RedirectResponse(url=f"/clani/{clan_id}#vloge", status_code=302)

    vloga = ClanVloga(
        clan_id=clan_id,
        naziv=naziv,
        datum_od=date.fromisoformat(datum_od),
        datum_do=date.fromisoformat(datum_do) if datum_do.strip() else None,
        opombe=opombe.strip() or None,
    )
    db.add(vloga)
    db.commit()
    return RedirectResponse(url=f"/clani/{clan_id}#vloge", status_code=302)


@router.post("/izbrisi/{vloga_id}")
async def izbrisi(
    request: Request,
    vloga_id: int,
    clan_id: int = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url=f"/clani/{clan_id}", status_code=302)

    v = db.query(ClanVloga).filter(ClanVloga.id == vloga_id).first()
    if v:
        db.delete(v)
        db.commit()
    return RedirectResponse(url=f"/clani/{clan_id}#vloge", status_code=302)
