import re
import bcrypt
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
            "403.html", {"request": request, "user": user}, status_code=403
        )
    return user, None


def is_admin(user: dict | None) -> bool:
    return user is not None and user.get("vloga") == "admin"


def is_editor(user: dict | None) -> bool:
    return user is not None and user.get("vloga") in ("admin", "urednik")
