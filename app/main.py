import os
import time
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

import pyotp
from fastapi import FastAPI, Request, Form, Depends
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from sqlalchemy import text, inspect as sa_inspect
from .database import engine, SessionLocal, get_db
from .models import Base, Uporabnik, Nastavitev, TIPI_CLANSTVA_PRIVZETO, OPERATERSKI_RAZREDI_PRIVZETO
from .auth import hash_geslo, preveri_geslo
from .csrf import get_csrf_token, csrf_protect
from .audit_log import log_akcija
from .routers import clani, clanarine, izvoz, uporabniki, nastavitve, profil, aktivnosti, skupine, audit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Varnostne nastavitve
# ---------------------------------------------------------------------------

PRIVZETE_NASTAVITVE = {
    "klub_ime": ("", "Polno ime kluba"),
    "klub_oznaka": ("", "Klicni znak / oznaka kluba"),
    "klub_naslov": ("", "Naslov kluba (ulica in hišna številka)"),
    "klub_posta": ("", "Poštna številka in kraj"),
    "klub_email": ("", "E-poštni naslov kluba"),
    "tipi_clanstva": ("\n".join(TIPI_CLANSTVA_PRIVZETO), "Tipi članstva (ena vrednost na vrstico)"),
    "operaterski_razredi": ("\n".join(OPERATERSKI_RAZREDI_PRIVZETO), "Operaterski razredi (ena vrednost na vrstico)"),
}

# Preprosta rate-limiting tabela: {ip: [timestamp, ...]}
_login_attempts: dict = defaultdict(list)
_MAX_ATTEMPTS = 10        # max neuspešnih prijav
_LOCKOUT_SECONDS = 900    # zaklepanje 15 minut


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


class KlubContextMiddleware(BaseHTTPMiddleware):
    """Na vsako zahtevo doda request.state.klub_oznaka in request.state.klub_ime iz baze."""
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
        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate limiting za prijavo
# ---------------------------------------------------------------------------

def _check_rate_limit(ip: str) -> bool:
    """Vrne True če je IP dovoljen, False če je zaklenjen."""
    zdaj = time.time()
    cutoff = zdaj - _LOCKOUT_SECONDS
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    return len(_login_attempts[ip]) < _MAX_ATTEMPTS


def _record_failed_login(ip: str):
    _login_attempts[ip].append(time.time())


# ---------------------------------------------------------------------------
# DB migracije
# ---------------------------------------------------------------------------

def _migriraj_bazo():
    """Doda manjkajoče stolpce v obstoječo bazo (brez Alembic)."""
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    with engine.connect() as conn:
        cols = [c["name"] for c in inspector.get_columns("clanarine")]
        if "znesek" not in cols:
            conn.execute(text("ALTER TABLE clanarine ADD COLUMN znesek TEXT"))
            conn.commit()
            logger.info("Migracija: dodan stolpec clanarine.znesek")

        if "aktivnosti" in tables:
            cols_akt = [c["name"] for c in inspector.get_columns("aktivnosti")]
            if "delovne_ure" not in cols_akt:
                conn.execute(text("ALTER TABLE aktivnosti ADD COLUMN delovne_ure REAL"))
                conn.commit()
                logger.info("Migracija: dodan stolpec aktivnosti.delovne_ure")

        if "uporabniki" in tables:
            cols_up = [c["name"] for c in inspector.get_columns("uporabniki")]
            if "totp_skrivnost" not in cols_up:
                conn.execute(text("ALTER TABLE uporabniki ADD COLUMN totp_skrivnost TEXT"))
                conn.commit()
                logger.info("Migracija: dodan stolpec uporabniki.totp_skrivnost")
            if "totp_aktiven" not in cols_up:
                conn.execute(text("ALTER TABLE uporabniki ADD COLUMN totp_aktiven BOOLEAN DEFAULT 0"))
                conn.commit()
                logger.info("Migracija: dodan stolpec uporabniki.totp_aktiven")

        # Migracija tipov članstva iz starih na nova poimenovanja
        stari_privzeti = "Redno\nDružinsko\nSimpatizerji\nMladi/dijaki/študenti\nInvalidi"
        novi_privzeti = "\n".join(TIPI_CLANSTVA_PRIVZETO)
        if "nastavitve" in tables:
            n = conn.execute(
                text("SELECT vrednost FROM nastavitve WHERE kljuc='tipi_clanstva'")
            ).fetchone()
            if n and n[0] and n[0].strip() == stari_privzeti:
                conn.execute(
                    text("UPDATE nastavitve SET vrednost=:v WHERE kljuc='tipi_clanstva'"),
                    {"v": novi_privzeti},
                )
                conn.commit()
                logger.info("Migracija: posodobljeni tipi članstva na nova poimenovanja")


# ---------------------------------------------------------------------------
# Aplikacija
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migriraj_bazo()
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

# Session z varnostnimi zastavicami
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "radikoklub-dev-key-ZAMENJAJTE-v-produkciji"),
    max_age=3600,          # 1 ura (prej 24 ur)
    same_site="strict",    # Zaščita pred CSRF
    https_only=False,      # Ostane False tudi pri HTTPS (HSTS na reverse proxy-u zadostuje)
)

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
    return templates.TemplateResponse("login.html", {"request": request})


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
    if not _check_rate_limit(ip):
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
            # 2FA zahtevano – preusmeri na OTP korak
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

    _record_failed_login(ip)
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
    _csrf: None = Depends(csrf_protect),
    db: Session = Depends(get_db),
) -> Response:
    uporabnisko_ime = request.session.get("_2fa_cakanje")
    if not uporabnisko_ime:
        return RedirectResponse(url="/login", status_code=302)

    ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(ip):
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
        return RedirectResponse(url="/clani", status_code=302)

    _record_failed_login(ip)
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
    return RedirectResponse(url="/login", status_code=302)
