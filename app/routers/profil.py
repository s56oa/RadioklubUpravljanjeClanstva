import io

import pyotp
import segno
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Uporabnik
from ..auth import require_login, hash_geslo, preveri_geslo, preveri_zahteve_gesla
from ..csrf import get_csrf_token, csrf_protect

router = APIRouter(prefix="/profil")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


@router.get("", response_class=HTMLResponse)
async def profil_stran(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    u = db.query(Uporabnik).filter(Uporabnik.id == user["id"]).first()
    if not u:
        return RedirectResponse(url="/logout", status_code=302)

    return templates.TemplateResponse(
        "profil/index.html",
        {
            "request": request,
            "user": user,
            "u": u,
            "ime_shranjeno": request.query_params.get("ime") == "1",
            "geslo_spremenjeno": request.query_params.get("geslo") == "1",
            "tfa_aktivirana": request.query_params.get("2fa") == "1",
            "tfa_onemogocena": request.query_params.get("2fa_off") == "1",
        },
    )


@router.post("/ime", response_class=HTMLResponse)
async def shrani_ime(
    request: Request,
    ime_priimek: str = Form(""),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    u = db.query(Uporabnik).filter(Uporabnik.id == user["id"]).first()
    if not u:
        return RedirectResponse(url="/logout", status_code=302)

    u.ime_priimek = ime_priimek.strip() or None
    db.commit()

    # Posodobi prikazno ime v aktivni seji
    request.session["uporabnik"]["ime"] = u.ime_priimek or u.uporabnisko_ime

    return RedirectResponse(url="/profil?ime=1", status_code=302)


@router.post("/geslo", response_class=HTMLResponse)
async def spremeni_geslo(
    request: Request,
    staro_geslo: str = Form(...),
    novo_geslo: str = Form(...),
    novo_geslo2: str = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    u = db.query(Uporabnik).filter(Uporabnik.id == user["id"]).first()
    if not u:
        return RedirectResponse(url="/logout", status_code=302)

    def vrni_napako(napaka: str):
        return templates.TemplateResponse(
            "profil/index.html",
            {
                "request": request,
                "user": user,
                "u": u,
                "napaka_geslo": napaka,
            },
        )

    if not preveri_geslo(staro_geslo, u.geslo_hash):
        return vrni_napako("Trenutno geslo ni pravilno.")

    if novo_geslo != novo_geslo2:
        return vrni_napako("Novi gesli se ne ujemata.")

    napaka_politike = preveri_zahteve_gesla(novo_geslo)
    if napaka_politike:
        return vrni_napako(napaka_politike)

    u.geslo_hash = hash_geslo(novo_geslo)
    db.commit()

    return RedirectResponse(url="/profil?geslo=1", status_code=302)


def _generiraj_qr_svg(skrivnost: str, uporabnisko_ime: str, klub_ime: str) -> str:
    """Vrne inline SVG QR kode za TOTP provisioning URI."""
    uri = pyotp.TOTP(skrivnost).provisioning_uri(
        name=uporabnisko_ime,
        issuer_name=klub_ime or "Radio klub",
    )
    buf = io.BytesIO()
    segno.make(uri).save(buf, kind="svg", scale=6, xmldecl=False, svgns=True, nl=False)
    return buf.getvalue().decode("utf-8")


@router.get("/2fa-nastavi", response_class=HTMLResponse)
async def tfa_nastavi_stran(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    u = db.query(Uporabnik).filter(Uporabnik.id == user["id"]).first()
    if not u:
        return RedirectResponse(url="/logout", status_code=302)

    skrivnost = pyotp.random_base32()
    request.session["_2fa_nova_skrivnost"] = skrivnost

    klub_ime = getattr(request.state, "klub_ime", "") or ""
    qr_svg = _generiraj_qr_svg(skrivnost, u.uporabnisko_ime, klub_ime)

    return templates.TemplateResponse(
        "profil/2fa-nastavi.html",
        {
            "request": request,
            "user": user,
            "u": u,
            "qr_svg": qr_svg,
            "skrivnost": skrivnost,
        },
    )


@router.post("/2fa-potrdi", response_class=HTMLResponse)
async def tfa_potrdi(
    request: Request,
    koda: str = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    skrivnost = request.session.get("_2fa_nova_skrivnost")
    if not skrivnost:
        return RedirectResponse(url="/profil", status_code=302)

    u = db.query(Uporabnik).filter(Uporabnik.id == user["id"]).first()
    if not u:
        return RedirectResponse(url="/logout", status_code=302)

    if pyotp.TOTP(skrivnost).verify(koda.strip(), valid_window=1):
        u.totp_skrivnost = skrivnost
        u.totp_aktiven = True
        db.commit()
        request.session.pop("_2fa_nova_skrivnost", None)
        return RedirectResponse(url="/profil?2fa=1", status_code=302)

    # Napaka – QR regeneriramo iz iste skrivnosti
    klub_ime = getattr(request.state, "klub_ime", "") or ""
    qr_svg = _generiraj_qr_svg(skrivnost, u.uporabnisko_ime, klub_ime)

    return templates.TemplateResponse(
        "profil/2fa-nastavi.html",
        {
            "request": request,
            "user": user,
            "u": u,
            "qr_svg": qr_svg,
            "skrivnost": skrivnost,
            "napaka": "Napačna koda. Preverite čas na napravi in poskusite znova.",
        },
    )


@router.post("/2fa-onemogoči", response_class=HTMLResponse)
async def tfa_onemogoči(
    request: Request,
    koda: str = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(csrf_protect),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    u = db.query(Uporabnik).filter(Uporabnik.id == user["id"]).first()
    if not u:
        return RedirectResponse(url="/logout", status_code=302)

    if u.totp_skrivnost and pyotp.TOTP(u.totp_skrivnost).verify(koda.strip(), valid_window=1):
        u.totp_skrivnost = None
        u.totp_aktiven = False
        db.commit()
        return RedirectResponse(url="/profil?2fa_off=1", status_code=302)

    return templates.TemplateResponse(
        "profil/index.html",
        {
            "request": request,
            "user": user,
            "u": u,
            "napaka_2fa": "Napačna koda. 2FA ni bila onemogočena.",
        },
    )
