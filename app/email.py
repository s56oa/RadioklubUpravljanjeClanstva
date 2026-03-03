"""E-poštno pošiljanje z embedded UPN QR kodo.

Podprti načini SMTP: starttls (port 587), ssl (port 465), plain (port 25).
"""
import base64
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, Undefined
from sqlalchemy.orm import Session

from .config import get_nastavitev, get_clanarina_zneski
from .models import Clan
from .upn import generiraj_upn_png


def get_smtp_nastavitve(db: Session) -> dict:
    """Bere SMTP nastavitve iz Nastavitev tabele. Vrže ValueError če smtp_host prazen."""
    host = get_nastavitev(db, "smtp_host", "")
    if not host:
        raise ValueError("SMTP strežnik ni nastavljen. Konfigurirajte ga v /nastavitve.")
    return {
        "host": host,
        "port": int(get_nastavitev(db, "smtp_port", "587")),
        "nacin": get_nastavitev(db, "smtp_nacin", "starttls"),
        "uporabnik": get_nastavitev(db, "smtp_uporabnik", ""),
        "geslo": get_nastavitev(db, "smtp_geslo", ""),
        "od": get_nastavitev(db, "smtp_od", ""),
    }


def _qr_img_tag(clan: Clan, leto: int, db: Session) -> str:
    """Generira UPN QR PNG in vrne HTML <img> tag z base64 embedded sliko."""
    iban = get_nastavitev(db, "klub_iban", "")
    ime_kluba = get_nastavitev(db, "klub_ime", "")
    ulica_kluba = get_nastavitev(db, "klub_naslov", "")
    kraj_kluba = get_nastavitev(db, "klub_posta", "")
    ref_predloga = get_nastavitev(db, "upn_referenca_predloga", "SI00 {id}-{leto}")
    namen = get_nastavitev(db, "upn_namen", "OTHR")
    opis_predloga = get_nastavitev(db, "upn_opis_predloga", "Članarina {leto}")

    referenca = (
        ref_predloga
        .replace("{leto}", str(leto))
        .replace("{id}", str(clan.id))
        .replace("{es}", str(clan.es_stevilka) if clan.es_stevilka else "")
    )
    opis = opis_predloga.replace("{leto}", str(leto))

    zneski = get_clanarina_zneski(db)
    znesek = zneski.get(clan.tip_clanstva) if clan.tip_clanstva else None

    png_bytes = generiraj_upn_png(
        ime_placnika=f"{clan.priimek} {clan.ime}",
        ulica_placnika=clan.naslov_ulica or "",
        kraj_placnika=clan.naslov_posta or "",
        iban_prejemnika=iban,
        referenca=referenca,
        ime_prejemnika=ime_kluba,
        ulica_prejemnika=ulica_kluba,
        kraj_prejemnika=kraj_kluba,
        opis=opis,
        znesek_eur=znesek,
        namen=namen,
    )
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="UPN QR koda" style="max-width:200px;">'


def _render_predloga(telo_html: str, clan: Clan, leto: int, qr_img_tag: str) -> str:
    """Renderira HTML predlogo z Jinja2 spremenljivkami."""
    env = Environment(autoescape=False)
    tmpl = env.from_string(telo_html)
    return tmpl.render(
        ime=clan.ime,
        priimek=clan.priimek,
        klicni_znak=clan.klicni_znak or "",
        leto=leto,
        qr_koda=qr_img_tag,
    )


def posli_email(
    clan: Clan,
    zadeva_predloga: str,
    telo_predloga: str,
    leto: int,
    smtp_nastavitve: dict,
    db: Session,
) -> None:
    """Pošlje personalizirani e-mail z embedded UPN QR kodo.

    Vrže smtplib.SMTPException ali ValueError ob napaki pri pošiljanju.
    """
    qr_tag = _qr_img_tag(clan, leto, db)
    html_telo = _render_predloga(telo_predloga, clan, leto, qr_tag)

    # Render zadeve (enostavna string zamenjava)
    env = Environment(autoescape=False)
    zadeva = env.from_string(zadeva_predloga).render(
        ime=clan.ime,
        priimek=clan.priimek,
        klicni_znak=clan.klicni_znak or "",
        leto=leto,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = zadeva
    msg["From"] = smtp_nastavitve["od"]
    msg["To"] = clan.elektronska_posta
    msg.attach(MIMEText(html_telo, "html", "utf-8"))

    host = smtp_nastavitve["host"]
    port = smtp_nastavitve["port"]
    nacin = smtp_nastavitve["nacin"]
    uporabnik = smtp_nastavitve["uporabnik"]
    geslo = smtp_nastavitve["geslo"]

    if nacin == "ssl":
        with smtplib.SMTP_SSL(host, port) as server:
            if uporabnik:
                server.login(uporabnik, geslo)
            server.send_message(msg)
    elif nacin == "plain":
        with smtplib.SMTP(host, port) as server:
            if uporabnik:
                server.login(uporabnik, geslo)
            server.send_message(msg)
    else:  # starttls (privzeto)
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if uporabnik:
                server.login(uporabnik, geslo)
            server.send_message(msg)
