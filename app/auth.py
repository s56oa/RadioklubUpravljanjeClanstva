import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import pyotp
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def hash_geslo(geslo: str) -> str:
    return bcrypt.hashpw(geslo.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def preveri_zahteve_gesla(geslo: str) -> str | None:
    """Preveri politiko gesla. Vrne sporočilo o napaki ali None."""
    if len(geslo) < 14:
        return "Geslo mora biti dolgo vsaj 14 znakov."
    if not re.search(r"[a-z]", geslo):
        return "Geslo mora vsebovati vsaj en mali znak."
    if not re.search(r"[A-Z]", geslo):
        return "Geslo mora vsebovati vsaj en veliki znak."
    if not re.search(r"[0-9]", geslo):
        return "Geslo mora vsebovati vsaj eno številko."
    if not re.search(r"""[!@#$%^&*()\-_=+\[\]{};:'",.<>?/\\|`~]""", geslo):
        return "Geslo mora vsebovati vsaj en posebni znak (npr. !@#$%&*)."
    return None


def preveri_geslo(geslo: str, geslo_hash: str) -> bool:
    return bcrypt.checkpw(geslo.encode("utf-8"), geslo_hash.encode("utf-8"))


# Naključen hash za primerjavo, ko uporabnik ne obstaja – izenači čas odgovora
# (prepreči ugotavljanje obstoja uporabniškega imena prek merjenja časa).
DUMMY_GESLO_HASH = hash_geslo(secrets.token_urlsafe(24))

_TOTP_KORAK_SEKUND = 30


def preveri_totp(uporabnik, koda: str, zdaj: datetime | None = None) -> bool:
    """Preveri TOTP kodo (okno ±1 korak) in prepreči ponovno uporabo iste kode.

    Ob uspehu zapiše uporabljeni časovni korak v `uporabnik.totp_zadnji_korak`
    (klicatelj mora narediti commit). Koda iz koraka <= zadnjega je zavrnjena.
    """
    if not uporabnik or not uporabnik.totp_skrivnost:
        return False
    koda = (koda or "").strip().replace(" ", "")
    totp = pyotp.TOTP(uporabnik.totp_skrivnost)
    zdaj = zdaj or datetime.now(timezone.utc)
    for odmik in (0, -1, 1):
        cas = zdaj + timedelta(seconds=odmik * _TOTP_KORAK_SEKUND)
        if totp.verify(koda, for_time=cas, valid_window=0):
            korak = totp.timecode(cas)
            zadnji = uporabnik.totp_zadnji_korak
            if zadnji is not None and korak <= zadnji:
                return False
            uporabnik.totp_zadnji_korak = korak
            return True
    return False


def get_user(request: Request) -> dict | None:
    return request.session.get("uporabnik")


def require_login(request: Request):
    """Returns user dict or RedirectResponse to /login."""
    user = request.session.get("uporabnik")
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


def require_role(request: Request, *vloge: str):
    """Returns (user, None) if user has one of the required roles, else (None, response)."""
    user = request.session.get("uporabnik")
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    if user.get("vloga") not in vloge:
        return None, templates.TemplateResponse(
            request, "403.html", {"request": request, "user": user}, status_code=403
        )
    return user, None


def is_admin(user: dict | None) -> bool:
    return user is not None and user.get("vloga") == "admin"


def is_editor(user: dict | None) -> bool:
    return user is not None and user.get("vloga") in ("admin", "urednik")
