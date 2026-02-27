import os
import time
import hashlib
import secrets
import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

import pyotp
from fastapi import FastAPI, Request, Form, Depends
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from sqlalchemy import inspect as sa_inspect
from .database import engine, SessionLocal, get_db
from .models import Base, Uporabnik, Nastavitev, ZaupljivaNaprava, LoginPoizkus, TIPI_CLANSTVA_PRIVZETO, OPERATERSKI_RAZREDI_PRIVZETO
from .auth import hash_geslo, preveri_geslo
from .csrf import get_csrf_token, csrf_protect
from .audit_log import log_akcija
from .routers import clani, clanarine, izvoz, uporabniki, nastavitve, profil, aktivnosti, skupine, audit, dashboard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Varnostne nastavitve
# ---------------------------------------------------------------------------

APP_VERSION = "1.14"
APP_RELEASE_DATE = "2026-02-27"

# Preberi LICENSE ob zagonu (enkrat, ne ob vsaki zahtevi)
try:
    _license_path = os.path.join(os.path.dirname(__file__), "..", "LICENSE")
    with open(_license_path, "r", encoding="utf-8") as _f:
        APP_LICENSE = _f.read().strip()
except Exception:
    APP_LICENSE = "Licenca ni dostopna."

PRIVZETE_NASTAVITVE = {
    "klub_ime": ("", "Polno ime kluba"),
    "klub_oznaka": ("", "Klicni znak / oznaka kluba"),
    "klub_naslov": ("", "Naslov kluba (ulica in hišna številka)"),
    "klub_posta": ("", "Poštna številka in kraj"),
    "klub_email": ("", "E-poštni naslov kluba"),
    "tipi_clanstva": ("\n".join(TIPI_CLANSTVA_PRIVZETO), "Tipi članstva (ena vrednost na vrstico)"),
    "operaterski_razredi": ("\n".join(OPERATERSKI_RAZREDI_PRIVZETO), "Operaterski razredi (ena vrednost na vrstico)"),
}

_MAX_ATTEMPTS = 10        # max neuspešnih prijav
_LOCKOUT_SECONDS = 900    # zaklepanje 15 minut
_INACTIVITY_SECONDS = 30 * 60  # iztok seje ob neaktivnosti (30 min)
_MAX_BODY_BYTES = 1 * 1024 * 1024  # max velikost normalnega POST zahtevka (1 MB)


# ---------------------------------------------------------------------------
# Varnostni headers middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    """Zavrne POST/PUT/PATCH zahteve z body > 1 MB (razen /izvoz/ ki ima lastno omejitev)."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            if not request.url.path.startswith("/izvoz/"):
                content_length = request.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > _MAX_BODY_BYTES:
                            from fastapi.responses import PlainTextResponse
                            return PlainTextResponse(
                                "Zahtevek je prevelik (max 1 MB).", status_code=413
                            )
                    except ValueError:
                        pass
        return await call_next(request)


class InactivityTimeoutMiddleware(BaseHTTPMiddleware):
    """Odjavi uporabnika po 30 minutah neaktivnosti."""

    _SKIP_PATHS_EXACT = {"/login", "/login/2fa", "/logout", "/health"}
    _SKIP_PATHS_PREFIX = ("/static",)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        skip = path in self._SKIP_PATHS_EXACT or any(
            path.startswith(p) for p in self._SKIP_PATHS_PREFIX
        )
        if not skip and request.session.get("uporabnik"):
            last_active = request.session.get("_last_active")
            if last_active is not None and time.time() - last_active > _INACTIVITY_SECONDS:
                request.session.clear()
                return RedirectResponse(url="/login?timeout=1", status_code=302)
            request.session["_last_active"] = time.time()
        return await call_next(request)


class KlubContextMiddleware(BaseHTTPMiddleware):
    """Na vsako zahtevo doda request.state.klub_oznaka/klub_ime iz baze in statične app podatke."""
    async def dispatch(self, request: Request, call_next):
        db = SessionLocal()
        try:
            oznaka = db.query(Nastavitev).filter(Nastavitev.kljuc == "klub_oznaka").first()
            ime = db.query(Nastavitev).filter(Nastavitev.kljuc == "klub_ime").first()
            request.state.klub_oznaka = oznaka.vrednost if oznaka else ""
            request.state.klub_ime = ime.vrednost if ime else ""
        except Exception:
            request.state.klub_oznaka = ""
            request.state.klub_ime = ""
        finally:
            db.close()
        request.state.app_version = APP_VERSION
        request.state.app_release_date = APP_RELEASE_DATE
        request.state.app_license = APP_LICENSE
        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate limiting za prijavo
# ---------------------------------------------------------------------------

def _device_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _check_rate_limit(ip: str, db: Session) -> bool:
    """Vrne True če je IP dovoljen, False če je zaklenjen. Sproti čisti stare vnose."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_LOCKOUT_SECONDS)
    db.query(LoginPoizkus).filter(LoginPoizkus.cas < cutoff).delete(synchronize_session=False)
    db.commit()
    count = db.query(LoginPoizkus).filter(
        LoginPoizkus.ip == ip,
        LoginPoizkus.cas >= cutoff,
    ).count()
    return count < _MAX_ATTEMPTS


def _record_failed_login(ip: str, db: Session) -> None:
    db.add(LoginPoizkus(ip=ip, cas=datetime.now(timezone.utc)))
    db.commit()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _nastavi_logging() -> None:
    """Doda RotatingFileHandler na root logger (data/app.log, 5 MB × 5)."""
    log_path = os.path.join("data", "app.log")
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    root = logging.getLogger()
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(fmt)
        root.addHandler(handler)
        if root.level == logging.NOTSET:
            root.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# DB migracije (Alembic)
# ---------------------------------------------------------------------------

def _run_migrations() -> None:
    """Zažene Alembic migracije do najnovejše revizije.

    Obstoječe baze brez Alembic zgodovine avtomatsko označi kot revizijo 001
    (vse do v1.11 veljavne tabele), nato aplicira samo nove migracije.
    """
    ini_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    )
    cfg = AlembicConfig(ini_path)
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    if "alembic_version" not in tables and "clani" in tables:
        logger.info("Obstoječa baza brez Alembic zgodovine – označujem kot revizija 001")
        alembic_command.stamp(cfg, "001")
    alembic_command.upgrade(cfg, "head")
    logger.info("Alembic migracije uspešno zaključene")


# ---------------------------------------------------------------------------
# Aplikacija
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    _nastavi_logging()
    _run_migrations()
    db = SessionLocal()
    try:
        if db.query(Uporabnik).count() == 0:
            admin_geslo = os.getenv("ADMIN_GESLO", "admin123")
            admin = Uporabnik(
                uporabnisko_ime="admin",
                geslo_hash=hash_geslo(admin_geslo),
                vloga="admin",
                ime_priimek="Administrator",
            )
            db.add(admin)
            db.commit()
            # Geslo izpišemo samo v razvijalskem načinu, NIKOLI v produkciji
            if os.getenv("OKOLJE", "razvoj") == "razvoj":
                logger.warning("Admin ustvarjen. Takoj zamenjajte geslo po prvi prijavi!")
            else:
                logger.info("Admin uporabnik ustvarjen.")

        for kljuc, (vrednost_env, opis) in PRIVZETE_NASTAVITVE.items():
            if not db.query(Nastavitev).filter(Nastavitev.kljuc == kljuc).first():
                env_vrednost = os.getenv(kljuc.upper(), vrednost_env)
                db.add(Nastavitev(kljuc=kljuc, vrednost=env_vrednost, opis=opis))
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="Radio klub Člani", lifespan=lifespan)

# Varnostni headers (pred session middleware)
app.add_middleware(SecurityHeadersMiddleware)

# Inaktivni timeout – mora biti ZNOTRAJ SessionMiddleware (dostop do request.session)
app.add_middleware(InactivityTimeoutMiddleware)

# Session z varnostnimi zastavicami
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "radikoklub-dev-key-ZAMENJAJTE-v-produkciji"),
    max_age=3600,          # 1 ura (prej 24 ur)
    same_site="strict",    # Zaščita pred CSRF
    https_only=False,      # Ostane False tudi pri HTTPS (HSTS na reverse proxy-u zadostuje)
)

# Omejitev velikosti POST zahtevkov – zunaj Session, zavrne zgodaj
app.add_middleware(ContentSizeLimitMiddleware)

app.add_middleware(KlubContextMiddleware)

# Prebere X-Forwarded-For / X-Real-IP od reverse proxy-a (Synology, Nginx).
# trusted_hosts="*" je varno ker je port 8000 vezan samo na 127.0.0.1 – direkten
# dostop iz interneta ni možen; header lahko nastavi samo zaupljiv proxy.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token

app.include_router(clani.router)
app.include_router(clanarine.router)
app.include_router(izvoz.router)
app.include_router(uporabniki.router)
app.include_router(nastavitve.router)
app.include_router(profil.router)
app.include_router(aktivnosti.router)
app.include_router(skupine.router)
app.include_router(audit.router)
app.include_router(dashboard.router)


# ---------------------------------------------------------------------------
# Osnove poti
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> RedirectResponse:
    if not request.session.get("uporabnik"):
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/clani", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_stran(request: Request) -> Response:
    if request.session.get("uporabnik"):
        return RedirectResponse(url="/clani", status_code=302)
    timeout = request.query_params.get("timeout") == "1"
    return templates.TemplateResponse("login.html", {"request": request, "timeout": timeout})


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    uporabnisko_ime: str = Form(...),
    geslo: str = Form(...),
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not _check_rate_limit(ip, db):
        logger.warning(f"Preveč poskusov prijave z IP {ip}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "napaka": "Preveč neuspešnih poskusov. Počakajte 15 minut."},
        )

    u = (
        db.query(Uporabnik)
        .filter(
            Uporabnik.uporabnisko_ime == uporabnisko_ime,
            Uporabnik.aktiven == True,
        )
        .first()
    )

    # Vedno preverimo geslo (preprečimo timing attack)
    geslo_ok = preveri_geslo(geslo, u.geslo_hash) if u else False

    if u and geslo_ok:
        if u.totp_aktiven and u.totp_skrivnost:
            # Preveri ali je naprava zaupljiva (zapomni si me)
            device_token = request.cookies.get("_2fa_device")
            if device_token:
                token_hash = _device_token_hash(device_token)
                zdaj = datetime.now(timezone.utc)
                naprava = (
                    db.query(ZaupljivaNaprava)
                    .filter(
                        ZaupljivaNaprava.uporabnik_id == u.id,
                        ZaupljivaNaprava.token_hash == token_hash,
                        ZaupljivaNaprava.expires_at > zdaj,
                    )
                    .first()
                )
                if naprava:
                    request.session.clear()
                    request.session["uporabnik"] = {
                        "id": u.id,
                        "ime": u.ime_priimek or u.uporabnisko_ime,
                        "vloga": u.vloga,
                        "uporabnisko_ime": u.uporabnisko_ime,
                    }
                    log_akcija(db, uporabnisko_ime, "login_2fa_zaupljiva",
                               f"Prijava z zaupljivo napravo: {uporabnisko_ime}", ip=ip)
                    return RedirectResponse(url="/clani", status_code=302)
            # Ni zaupljive naprave – zahtevaj OTP kodo
            request.session.clear()
            request.session["_2fa_cakanje"] = u.uporabnisko_ime
            log_akcija(db, uporabnisko_ime, "login_2fa_caka", f"2FA čakanje: {uporabnisko_ime}", ip=ip)
            return RedirectResponse(url="/login/2fa", status_code=302)

        request.session.clear()  # Prepreči session fixation
        request.session["uporabnik"] = {
            "id": u.id,
            "ime": u.ime_priimek or u.uporabnisko_ime,
            "vloga": u.vloga,
            "uporabnisko_ime": u.uporabnisko_ime,
        }
        logger.info(f"Uspešna prijava: {uporabnisko_ime} ({ip})")
        log_akcija(db, uporabnisko_ime, "login_ok", f"Prijava: {uporabnisko_ime}", ip=ip)
        return RedirectResponse(url="/clani", status_code=302)

    _record_failed_login(ip, db)
    logger.warning(f"Neuspešna prijava: {uporabnisko_ime} ({ip})")
    log_akcija(db, uporabnisko_ime, "login_fail", f"Neuspešna prijava: {uporabnisko_ime}", ip=ip)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "napaka": "Napačno uporabniško ime ali geslo."},
    )


@app.get("/login/2fa", response_class=HTMLResponse)
async def login_2fa_stran(request: Request) -> Response:
    if not request.session.get("_2fa_cakanje"):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("login-2fa.html", {"request": request})


@app.post("/login/2fa", response_class=HTMLResponse)
async def login_2fa(
    request: Request,
    koda: str = Form(...),
    zapomni_naprava: str = Form(""),
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    uporabnisko_ime = request.session.get("_2fa_cakanje")
    if not uporabnisko_ime:
        return RedirectResponse(url="/login", status_code=302)

    ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(ip, db):
        return templates.TemplateResponse(
            "login-2fa.html",
            {"request": request, "napaka": "Preveč neuspešnih poskusov. Počakajte 15 minut."},
        )

    u = (
        db.query(Uporabnik)
        .filter(Uporabnik.uporabnisko_ime == uporabnisko_ime, Uporabnik.aktiven == True)
        .first()
    )

    if u and u.totp_skrivnost and pyotp.TOTP(u.totp_skrivnost).verify(koda.strip(), valid_window=1):
        request.session.pop("_2fa_cakanje", None)
        request.session["uporabnik"] = {
            "id": u.id,
            "ime": u.ime_priimek or u.uporabnisko_ime,
            "vloga": u.vloga,
            "uporabnisko_ime": u.uporabnisko_ime,
        }
        logger.info(f"Uspešna 2FA prijava: {uporabnisko_ime} ({ip})")
        log_akcija(db, uporabnisko_ime, "login_ok", f"Prijava (2FA): {uporabnisko_ime}", ip=ip)
        response = RedirectResponse(url="/clani", status_code=302)
        if zapomni_naprava == "1":
            token = secrets.token_urlsafe(32)
            token_hash = _device_token_hash(token)
            expires = datetime.now(timezone.utc) + timedelta(days=30)
            db.add(ZaupljivaNaprava(
                uporabnik_id=u.id,
                token_hash=token_hash,
                expires_at=expires,
                user_agent=request.headers.get("user-agent", "")[:200],
            ))
            db.commit()
            response.set_cookie(
                "_2fa_device", token,
                max_age=30 * 24 * 3600,
                httponly=True,
                samesite="strict",
            )
            log_akcija(db, uporabnisko_ime, "login_2fa_zaupljiva_nova", "Nova zaupljiva naprava shranjena", ip=ip)
        return response

    _record_failed_login(ip, db)
    logger.warning(f"Napačna 2FA koda: {uporabnisko_ime} ({ip})")
    log_akcija(db, uporabnisko_ime, "login_2fa_napaka", f"Napačna 2FA koda: {uporabnisko_ime}", ip=ip)
    return templates.TemplateResponse(
        "login-2fa.html",
        {"request": request, "napaka": "Napačna koda. Poskusite znova."},
    )


@app.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    uporabnik_info = request.session.get("uporabnik")
    username = uporabnik_info.get("uporabnisko_ime") if uporabnik_info else None
    ip = request.client.host if request.client else None
    request.session.clear()
    db = SessionLocal()
    try:
        log_akcija(db, username, "logout", ip=ip)
    finally:
        db.close()
    # Zaupljiva naprava (_2fa_device piškotek) se ob odjavi NE briše –
    # velja 30 dni ne glede na odjave. Uporabnik jo prekliče prek
    # Moj profil → Odjavi vse naprave ali ob onemogočanju 2FA.
    return RedirectResponse(url="/login", status_code=302)
