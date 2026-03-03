from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Nastavitev
from ..auth import require_login, is_admin
from ..config import get_seznam, get_tipi_clanstva, get_operaterski_razredi
from ..models import TIPI_CLANSTVA_PRIVZETO, OPERATERSKI_RAZREDI_PRIVZETO, VLOGE_CLANOV_PRIVZETO
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
    ("klub_iban", "IBAN bančnega računa (za UPN QR)"),
]

# Polja ki so seznami (ena vrednost na vrstico)
KLJUCI_SEZNAM = [
    ("tipi_clanstva", "Tipi članstva", TIPI_CLANSTVA_PRIVZETO),
    ("operaterski_razredi", "Operaterski razredi", OPERATERSKI_RAZREDI_PRIVZETO),
    ("vloge_clanov", "Vloge in funkcije članov", VLOGE_CLANOV_PRIVZETO),
    ("clanarina_zneski", "Zneski članarine za UPN QR (Tip=Znesek, ena vrstica na tip)",
     ["Osebni=25.00", "Mladi=10.00", "Družinski=35.00", "Simpatizerji=15.00", "Invalid=10.00"]),
]

# UPN QR predloge
KLJUCI_UPN = [
    ("upn_referenca_predloga", "Predloga reference (spremenljivke: {leto}, {es})"),
    ("upn_namen", "Koda namena (4 znaki, npr. MEMB)"),
    ("upn_opis_predloga", "Predloga opisa plačila (spremenljivka: {leto})"),
]

# SMTP nastavitve za e-poštno pošiljanje
KLJUCI_SMTP = [
    ("smtp_host", "SMTP strežnik (npr. smtp.gmail.com)"),
    ("smtp_port", "SMTP vrata (587 = STARTTLS, 465 = SSL, 25 = plain)"),
    ("smtp_nacin", "SMTP način (starttls / ssl / plain)"),
    ("smtp_uporabnik", "SMTP uporabniško ime"),
    ("smtp_geslo", "SMTP geslo"),
    ("smtp_od", "Pošiljatelj (npr. klub@s59dgo.org)"),
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

    # UPN predloge – privzete vrednosti
    upn_privzeto = {
        "upn_referenca_predloga": "SI00 5-{leto}",
        "upn_namen": "MEMB",
        "upn_opis_predloga": "Članarina {leto}",
    }
    for k, v in upn_privzeto.items():
        if k not in nas or not nas[k]:
            nas[k] = v

    return templates.TemplateResponse(
        request,
        "nastavitve/index.html",
        {
            "request": request,
            "user": user,
            "nas": nas,
            "kljuci_klub": KLJUCI_KLUB,
            "kljuci_seznam": KLJUCI_SEZNAM,
            "kljuci_upn": KLJUCI_UPN,
            "kljuci_smtp": KLJUCI_SMTP,
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

    vse_kljuce = [k for k, _ in KLJUCI_KLUB] + [k for k, _, _ in KLJUCI_SEZNAM] + [k for k, _ in KLJUCI_UPN] + [k for k, _ in KLJUCI_SMTP]
    for kljuc in vse_kljuce:
        vrednost = str(form.get(kljuc, "")).strip()
        n = db.query(Nastavitev).filter(Nastavitev.kljuc == kljuc).first()
        if n:
            n.vrednost = vrednost
        else:
            db.add(Nastavitev(kljuc=kljuc, vrednost=vrednost))
    db.commit()
    return RedirectResponse(url="/nastavitve?shranjen=1", status_code=302)
