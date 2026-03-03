"""UPN QR koda – generiranje po ZBS standardu.

Format: https://www.zbs-giz.si/news/upn-qr
19 podatkovnih polj ločenih z \\n, kontrolna vsota = 19 + vsota dolžin polj (3 mesta).
Kodiranje: ISO-8859-2 (byte mode QR).
"""
import io
import segno


def _obreži(vrednost: str, max_d: int) -> str:
    return (vrednost or "").strip()[:max_d]


def _znesek_v_cente(znesek_eur: float | None) -> str:
    """Pretvori EUR znesek v 11-mestni niz centov. None/0 → '' (brez zneska)."""
    if not znesek_eur:
        return ""
    return f"{round(znesek_eur * 100):011d}"


def _upn_vsebina(
    ime_placnika: str,
    ulica_placnika: str,
    kraj_placnika: str,
    iban_prejemnika: str,
    referenca: str,
    ime_prejemnika: str,
    ulica_prejemnika: str,
    kraj_prejemnika: str,
    opis: str,
    znesek_eur: float | None = None,
    namen: str = "OTHR",
) -> str:
    """Sestavi vsebino UPN QR kode (19 polj, brez kontrolne vsote)."""
    polja = [
        "UPNQR",                                      # 1  – identifikator
        "",                                           # 2  – IBAN plačnika
        "",                                           # 3  – polog
        "",                                           # 4  – dvig
        "",                                           # 5  – referenca plačnika
        _obreži(ime_placnika, 33),                    # 6  – ime plačnika
        _obreži(ulica_placnika, 33),                  # 7  – ulica plačnika
        _obreži(kraj_placnika, 33),                   # 8  – kraj plačnika
        _znesek_v_cente(znesek_eur),                  # 9  – znesek
        "",                                           # 10 – datum plačila
        "",                                           # 11 – nujno (urgent flag)
        _obreži(namen, 4),                            # 12 – koda namena
        _obreži(opis, 42),                            # 13 – namen/opis plačila
        "",                                           # 14 – rok plačila (deadline)
        _obreži(iban_prejemnika.replace(" ", ""), 34),# 15 – IBAN prejemnika
        _obreži(referenca, 26),                       # 16 – referenca prejemnika
        _obreži(ime_prejemnika, 33),                  # 17 – ime prejemnika
        _obreži(ulica_prejemnika, 33),                # 18 – ulica prejemnika
        _obreži(kraj_prejemnika, 33),                 # 19 – kraj prejemnika
    ]
    return "\n".join(polja) + "\n"


def _kontrolna_vsota(vsebina: str) -> str:
    """Izračuna 3-mestno kontrolno vsoto: 19 + vsota dolžin vseh 19 polj."""
    polja = vsebina.rstrip("\n").split("\n")
    return f"{19 + sum(len(f) for f in polja):03d}"


def _generiraj_qr(vsebina: str) -> segno.QRCode:
    """Generira segno QR objekt iz UPN vsebine."""
    kv = _kontrolna_vsota(vsebina)
    qr_vsebina = vsebina + kv + "\n"   # trailing \n po ZBS spec
    qr_bytes = qr_vsebina.encode("iso-8859-2")
    try:
        return segno.make(qr_bytes, error="M")
    except Exception:
        return segno.make(qr_bytes, error="L")


def generiraj_upn_png(
    ime_placnika: str,
    ulica_placnika: str,
    kraj_placnika: str,
    iban_prejemnika: str,
    referenca: str,
    ime_prejemnika: str,
    ulica_prejemnika: str,
    kraj_prejemnika: str,
    opis: str,
    znesek_eur: float | None = None,
    namen: str = "OTHR",
) -> bytes:
    """Vrne PNG bajte z UPN QR kodo po ZBS standardu."""
    vsebina = _upn_vsebina(
        ime_placnika=ime_placnika,
        ulica_placnika=ulica_placnika,
        kraj_placnika=kraj_placnika,
        iban_prejemnika=iban_prejemnika,
        referenca=referenca,
        ime_prejemnika=ime_prejemnika,
        ulica_prejemnika=ulica_prejemnika,
        kraj_prejemnika=kraj_prejemnika,
        opis=opis,
        znesek_eur=znesek_eur,
        namen=namen,
    )
    qr = _generiraj_qr(vsebina)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=8, border=4)
    return buf.getvalue()


def generiraj_upn_svg(
    ime_placnika: str,
    ulica_placnika: str,
    kraj_placnika: str,
    iban_prejemnika: str,
    referenca: str,
    ime_prejemnika: str,
    ulica_prejemnika: str,
    kraj_prejemnika: str,
    opis: str,
    znesek_eur: float | None = None,
    namen: str = "OTHR",
) -> str:
    """Vrne SVG string z UPN QR kodo po ZBS standardu."""
    vsebina = _upn_vsebina(
        ime_placnika=ime_placnika,
        ulica_placnika=ulica_placnika,
        kraj_placnika=kraj_placnika,
        iban_prejemnika=iban_prejemnika,
        referenca=referenca,
        ime_prejemnika=ime_prejemnika,
        ulica_prejemnika=ulica_prejemnika,
        kraj_prejemnika=kraj_prejemnika,
        opis=opis,
        znesek_eur=znesek_eur,
        namen=namen,
    )
    qr = _generiraj_qr(vsebina)
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=6, border=4)
    return buf.getvalue().decode("utf-8")
