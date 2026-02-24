import secrets
import string

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Uporabnik, VLOGE
from ..auth import require_login, is_admin, hash_geslo, preveri_zahteve_gesla
from ..csrf import get_csrf_token, csrf_protect


def _generiraj_geslo(dolzina: int = 12) -> str:
    """Generira varno naključno geslo (črke + številke, brez zmedenih znakov)."""
    znaki = string.ascii_letters + string.digits
    # Odstrani znake ki so vizualno podobni (0/O, 1/l/I)
    znaki = znaki.translate(str.maketrans("", "", "0O1lI"))
    return "".join(secrets.choice(znaki) for _ in range(dolzina))


router = APIRouter(prefix="/uporabniki")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


@router.get("", response_class=HTMLResponse)
async def seznam(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    uporabniki = db.query(Uporabnik).order_by(Uporabnik.ime_priimek).all()
    return templates.TemplateResponse(
        "uporabniki/seznam.html",
        {
            "request": request,
            "user": user,
            "uporabniki": uporabniki,
            "is_admin": True,
        },
    )


@router.get("/nov", response_class=HTMLResponse)
async def nov_form(request: Request) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)
    return templates.TemplateResponse(
        "uporabniki/form.html",
        {
            "request": request,
            "user": user,
            "u": None,
            "vloge": VLOGE,
            "is_admin": True,
        },
    )


@router.post("/nov")
async def nov_shrani(
    request: Request,
    uporabnisko_ime: str = Form(...),
    geslo: str = Form(...),
    ime_priimek: str = Form(""),
    vloga: str = Form("bralec"),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    napaka_geslo = preveri_zahteve_gesla(geslo)
    if napaka_geslo:
        return templates.TemplateResponse(
            "uporabniki/form.html",
            {
                "request": request,
                "user": user,
                "u": None,
                "vloge": VLOGE,
                "is_admin": True,
                "napaka": napaka_geslo,
            },
        )

    if db.query(Uporabnik).filter(Uporabnik.uporabnisko_ime == uporabnisko_ime).first():
        return templates.TemplateResponse(
            "uporabniki/form.html",
            {
                "request": request,
                "user": user,
                "u": None,
                "vloge": VLOGE,
                "is_admin": True,
                "napaka": f"Uporabnik '{uporabnisko_ime}' že obstaja.",
            },
        )

    u = Uporabnik(
        uporabnisko_ime=uporabnisko_ime.strip(),
        geslo_hash=hash_geslo(geslo),
        ime_priimek=ime_priimek.strip() or None,
        vloga=vloga,
        aktiven=True,
    )
    db.add(u)
    db.commit()
    return RedirectResponse(url="/uporabniki", status_code=302)


@router.get("/{uid}/uredi", response_class=HTMLResponse)
async def uredi_form(request: Request, uid: int, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    u = db.query(Uporabnik).filter(Uporabnik.id == uid).first()
    if not u:
        return RedirectResponse(url="/uporabniki", status_code=302)

    # Preberi enkratno flash sporočilo z generiranim geslom
    zacasno_geslo = request.session.pop("zacasno_geslo", None)

    return templates.TemplateResponse(
        "uporabniki/form.html",
        {
            "request": request,
            "user": user,
            "u": u,
            "vloge": VLOGE,
            "is_admin": True,
            "zacasno_geslo": zacasno_geslo,
        },
    )


@router.post("/{uid}/reset-geslo")
async def reset_geslo(request: Request, uid: int, db: Session = Depends(get_db), _csrf: None = Depends(csrf_protect)) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    u = db.query(Uporabnik).filter(Uporabnik.id == uid).first()
    if not u:
        return RedirectResponse(url="/uporabniki", status_code=302)

    novo_geslo = _generiraj_geslo(12)
    u.geslo_hash = hash_geslo(novo_geslo)
    db.commit()

    # Shrani geslo enkrat v session – prikazano na naslednji strani, nato izbrisano
    request.session["zacasno_geslo"] = novo_geslo
    return RedirectResponse(url=f"/uporabniki/{uid}/uredi", status_code=302)


@router.post("/{uid}/uredi")
async def uredi_shrani(
    request: Request,
    uid: int,
    ime_priimek: str = Form(""),
    vloga: str = Form("bralec"),
    novo_geslo: str = Form(""),
    aktiven: str = Form("da"),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    u = db.query(Uporabnik).filter(Uporabnik.id == uid).first()
    if not u:
        return RedirectResponse(url="/uporabniki", status_code=302)

    if novo_geslo.strip():
        napaka_geslo = preveri_zahteve_gesla(novo_geslo)
        if napaka_geslo:
            return templates.TemplateResponse(
                "uporabniki/form.html",
                {
                    "request": request,
                    "user": user,
                    "u": u,
                    "vloge": VLOGE,
                    "is_admin": True,
                    "napaka": napaka_geslo,
                },
            )
        u.geslo_hash = hash_geslo(novo_geslo)

    u.ime_priimek = ime_priimek.strip() or None
    u.vloga = vloga
    u.aktiven = aktiven == "da"
    db.commit()
    return RedirectResponse(url="/uporabniki", status_code=302)


@router.post("/{uid}/izbrisi")
async def izbrisi(request: Request, uid: int, db: Session = Depends(get_db), _csrf: None = Depends(csrf_protect)) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    # Ne dovolimo izbrisa samega sebe
    if user.get("id") == uid:
        return RedirectResponse(url="/uporabniki", status_code=302)

    u = db.query(Uporabnik).filter(Uporabnik.id == uid).first()
    if u:
        db.delete(u)
        db.commit()
    return RedirectResponse(url="/uporabniki", status_code=302)
