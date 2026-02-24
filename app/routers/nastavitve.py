from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Nastavitev
from ..auth import require_login, is_admin
from ..config import get_seznam, get_tipi_clanstva, get_operaterski_razredi
from ..models import TIPI_CLANSTVA_PRIVZETO, OPERATERSKI_RAZREDI_PRIVZETO
from ..csrf import get_csrf_token, csrf_protect

router = APIRouter(prefix="/nastavitve")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token

# Polja kluba (enostavni tekst)
KLJUCI_KLUB = [
    ("klub_ime", "Ime kluba"),
    ("klub_oznaka", "Klicni znak / oznaka"),
    ("klub_naslov", "Naslov (ulica in hišna številka)"),
    ("klub_posta", "Poštna številka in kraj"),
    ("klub_email", "E-poštni naslov kluba"),
]

# Polja ki so seznami (ena vrednost na vrstico)
KLJUCI_SEZNAM = [
    ("tipi_clanstva", "Tipi članstva", TIPI_CLANSTVA_PRIVZETO),
    ("operaterski_razredi", "Operaterski razredi", OPERATERSKI_RAZREDI_PRIVZETO),
]


@router.get("", response_class=HTMLResponse)
async def nastavitve_stran(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    nas = {n.kljuc: n.vrednost for n in db.query(Nastavitev).all()}

    # Za sezname zagotovi privzete vrednosti če še niso shranjene
    for kljuc, _, privzeto in KLJUCI_SEZNAM:
        if kljuc not in nas or not nas[kljuc]:
            nas[kljuc] = "\n".join(privzeto)

    return templates.TemplateResponse(
        "nastavitve/index.html",
        {
            "request": request,
            "user": user,
            "nas": nas,
            "kljuci_klub": KLJUCI_KLUB,
            "kljuci_seznam": KLJUCI_SEZNAM,
            "is_admin": True,
            "shranjen": request.query_params.get("shranjen") == "1",
        },
    )


@router.post("")
async def nastavitve_shrani(request: Request, db: Session = Depends(get_db), _csrf: None = Depends(csrf_protect)) -> RedirectResponse:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    form = await request.form()

    vse_kljuce = [k for k, _ in KLJUCI_KLUB] + [k for k, _, _ in KLJUCI_SEZNAM]
    for kljuc in vse_kljuce:
        vrednost = str(form.get(kljuc, "")).strip()
        n = db.query(Nastavitev).filter(Nastavitev.kljuc == kljuc).first()
        if n:
            n.vrednost = vrednost
        else:
            db.add(Nastavitev(kljuc=kljuc, vrednost=vrednost))
    db.commit()
    return RedirectResponse(url="/nastavitve?shranjen=1", status_code=302)
