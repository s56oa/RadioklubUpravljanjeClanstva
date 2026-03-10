"""E-poštno pošiljanje z embedded UPN QR kodo.

Podprti načini SMTP: starttls (port 587), ssl (port 465), plain (port 25).
"""
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2.sandbox import SandboxedEnvironment
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


def _qr_png_bytes(clan: Clan, leto: int, db: Session) -> bytes:
    """Generira UPN QR PNG in vrne raw bytes (za CID inline attachment)."""
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

    return generiraj_upn_png(
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


def _clan_context(clan: Clan, leto: int, qr_img_tag: str = "",
                  klub_ime: str = "", klub_oznaka: str = "") -> dict:
    """Vrne Jinja2 kontekst za predlogo (skupen za telo in zadevo)."""
    return {
        "ime": clan.ime or "",
        "priimek": clan.priimek or "",
        "klicni_znak": clan.klicni_znak or "",
        "leto": leto,
        "qr_koda": qr_img_tag,
        "naslov_ulica": clan.naslov_ulica or "",
        "naslov_posta": clan.naslov_posta or "",
        "tip_clanstva": clan.tip_clanstva or "",
        "klicni_znak_nosilci": clan.klicni_znak_nosilci or "",
        "operaterski_razred": clan.operaterski_razred or "",
        "mobilni_telefon": clan.mobilni_telefon or "",
        "telefon_doma": clan.telefon_doma or "",
        "elektronska_posta": clan.elektronska_posta or "",
        "veljavnost_rd": clan.veljavnost_rd.strftime("%d. %m. %Y") if clan.veljavnost_rd else "",
        "es_stevilka": str(clan.es_stevilka) if clan.es_stevilka else "",
        "opombe": clan.opombe or "",
        "klub_ime": klub_ime,
        "klub_oznaka": klub_oznaka,
    }


def _render_predloga(telo_html: str, clan: Clan, leto: int, qr_img_tag: str) -> str:
    """Renderira HTML predlogo z Jinja2 spremenljivkami.

    Uporablja SandboxedEnvironment, ki preprečuje dostop do nevarnih Python
    atributov in metod iz user-supplied predlog (template injection zaščita).
    autoescape=False je namerno – predloge vsebujejo HTML (vključno z embedded PNG).

    Dostopne spremenljivke: ime, priimek, klicni_znak, leto, qr_koda,
    naslov_ulica, naslov_posta, tip_clanstva, klicni_znak_nosilci,
    operaterski_razred, mobilni_telefon, telefon_doma, elektronska_posta,
    veljavnost_rd (DD. MM. LLLL ali ""), es_stevilka, opombe.
    """
    env = SandboxedEnvironment(autoescape=False)
    return env.from_string(telo_html).render(**_clan_context(clan, leto, qr_img_tag))


def posli_email(
    clan: Clan,
    zadeva_predloga: str,
    telo_predloga: str,
    leto: int,
    smtp_nastavitve: dict,
    db: Session,
    vkljuci_qr: bool = False,
    priponke: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """Pošlje personalizirani e-mail, opcijsko z embedded UPN QR kodo in/ali priponkami.

    priponke: seznam (ime_datoteke, vsebina_bytes, mime_tip) – npr. PDF kartica.
    Vrže smtplib.SMTPException ali ValueError ob napaki pri pošiljanju.
    """
    klub_ime = get_nastavitev(db, "klub_ime", "")
    klub_oznaka = get_nastavitev(db, "klub_oznaka", "")

    if vkljuci_qr:
        qr_bytes = _qr_png_bytes(clan, leto, db)
        # CID referenca – email odjemalci (Gmail, Outlook, Apple Mail) ne prikazujejo
        # data: URI slik, podpirajo pa CID inline attachmente (RFC 2392)
        qr_img_tag = '<img src="cid:qr_koda" alt="UPN QR koda" style="max-width:200px;">'
    else:
        qr_bytes = None
        qr_img_tag = ""
    html_telo = _render_predloga(telo_predloga, clan, leto, qr_img_tag)

    # Render zadeve (iste spremenljivke kot telo, brez qr_koda)
    env = SandboxedEnvironment(autoescape=False)
    ctx = _clan_context(clan, leto, klub_ime=klub_ime, klub_oznaka=klub_oznaka)
    zadeva = env.from_string(zadeva_predloga).render(**ctx)
    # Zaščita pred email header injection: odstrani CR/LF iz zadeve in naslovov
    zadeva = zadeva.replace("\r", "").replace("\n", " ").strip()
    od = smtp_nastavitve["od"].replace("\r", "").replace("\n", "").strip()
    na = (clan.elektronska_posta or "").replace("\r", "").replace("\n", "").strip()

    # multipart/related omogoča CID inline attachmente (RFC 2387); brez QR zadostuje alternative
    content_part = MIMEMultipart("related" if vkljuci_qr else "alternative")
    content_part.attach(MIMEText(html_telo, "html", "utf-8"))

    if vkljuci_qr and qr_bytes:
        qr_img = MIMEImage(qr_bytes, "png")
        qr_img.add_header("Content-ID", "<qr_koda>")
        qr_img.add_header("Content-Disposition", "inline", filename="qr_koda.png")
        content_part.attach(qr_img)

    # Ko so priponke prisotne, zaovijemo vsebino v multipart/mixed (RFC 2183)
    if priponke:
        send_msg = MIMEMultipart("mixed")
        send_msg.attach(content_part)
        for ime_dat, vsebina, mime_tip in priponke:
            maintype, subtype = mime_tip.split("/", 1)
            att = MIMEBase(maintype, subtype)
            att.set_payload(vsebina)
            encoders.encode_base64(att)
            att.add_header("Content-Disposition", "attachment", filename=ime_dat)
            send_msg.attach(att)
    else:
        send_msg = content_part

    send_msg["Subject"] = zadeva
    send_msg["From"] = od
    send_msg["To"] = na

    host = smtp_nastavitve["host"]
    port = smtp_nastavitve["port"]
    nacin = smtp_nastavitve["nacin"]
    uporabnik = smtp_nastavitve["uporabnik"]
    geslo = smtp_nastavitve["geslo"]

    if nacin == "ssl":
        with smtplib.SMTP_SSL(host, port) as server:
            if uporabnik:
                server.login(uporabnik, geslo)
            server.send_message(send_msg)
    elif nacin == "plain":
        with smtplib.SMTP(host, port) as server:
            if uporabnik:
                server.login(uporabnik, geslo)
            server.send_message(send_msg)
    else:  # starttls (privzeto)
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if uporabnik:
                server.login(uporabnik, geslo)
            server.send_message(send_msg)
