from datetime import date

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clan, Clanarina, Aktivnost
from ..auth import require_login, is_admin
from ..csrf import get_csrf_token

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


@router.get("", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    leto_zdaj = date.today().year

    # Stat cards
    clani_aktivni = db.query(Clan).filter(Clan.aktiven == True).count()
    clani_skupaj = db.query(Clan).count()

    placali_letos = (
        db.query(Clanarina)
        .filter(Clanarina.leto == leto_zdaj, Clanarina.datum_placila != None)
        .count()
    )

    aktivnosti_letos = (
        db.query(Aktivnost).filter(Aktivnost.leto == leto_zdaj).count()
    )

    ure_raw = (
        db.query(func.sum(Aktivnost.delovne_ure))
        .filter(Aktivnost.leto == leto_zdaj, Aktivnost.delovne_ure != None)
        .scalar()
    )
    ure_letos = round(float(ure_raw or 0), 1)

    # Plačila po letu – zadnjih 10 let
    leta = list(range(leto_zdaj - 9, leto_zdaj + 1))
    placila_po_letu = []
    for y in leta:
        count = (
            db.query(Clanarina)
            .filter(Clanarina.leto == y, Clanarina.datum_placila != None)
            .count()
        )
        placila_po_letu.append(count)

    # Tipi členstva – aktivni člani
    tipi_rows = (
        db.query(Clan.tip_clanstva, func.count(Clan.id))
        .filter(Clan.aktiven == True)
        .group_by(Clan.tip_clanstva)
        .order_by(func.count(Clan.id).desc())
        .all()
    )
    tipi_labele = [r[0] or "Neznan" for r in tipi_rows]
    tipi_vrednosti = [r[1] for r in tipi_rows]

    # Delovne ure po letu – zadnjih 10 let
    ure_po_letu = []
    for y in leta:
        ure = (
            db.query(func.sum(Aktivnost.delovne_ure))
            .filter(Aktivnost.leto == y, Aktivnost.delovne_ure != None)
            .scalar()
        )
        ure_po_letu.append(round(float(ure or 0), 1))

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "clani_aktivni": clani_aktivni,
            "clani_skupaj": clani_skupaj,
            "placali_letos": placali_letos,
            "neplacali_letos": clani_aktivni - placali_letos,
            "aktivnosti_letos": aktivnosti_letos,
            "ure_letos": ure_letos,
            "leta": leta,
            "placila_po_letu": placila_po_letu,
            "tipi_labele": tipi_labele,
            "tipi_vrednosti": tipi_vrednosti,
            "ure_po_letu": ure_po_letu,
            "leto_zdaj": leto_zdaj,
            "is_admin": is_admin(user),
        },
    )
