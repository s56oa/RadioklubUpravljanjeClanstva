"""Pomožne funkcije za branje nastavitev iz baze."""
from sqlalchemy.orm import Session
from .models import Nastavitev, TIPI_CLANSTVA_PRIVZETO, OPERATERSKI_RAZREDI_PRIVZETO, VLOGE_CLANOV_PRIVZETO


def get_nastavitev(db: Session, kljuc: str, privzeto: str = "") -> str:
    n = db.query(Nastavitev).filter(Nastavitev.kljuc == kljuc).first()
    return n.vrednost if n and n.vrednost else privzeto


def get_seznam(db: Session, kljuc: str, privzeto: list) -> list:
    """Vrne seznam vrednosti (ena na vrstico) iz nastavitve."""
    n = db.query(Nastavitev).filter(Nastavitev.kljuc == kljuc).first()
    if n and n.vrednost and n.vrednost.strip():
        return [v.strip() for v in n.vrednost.splitlines() if v.strip()]
    return privzeto


def get_tipi_clanstva(db: Session) -> list:
    return get_seznam(db, "tipi_clanstva", TIPI_CLANSTVA_PRIVZETO)


def get_operaterski_razredi(db: Session) -> list:
    return get_seznam(db, "operaterski_razredi", OPERATERSKI_RAZREDI_PRIVZETO)


def get_vloge_clanov(db: Session) -> list:
    return get_seznam(db, "vloge_clanov", VLOGE_CLANOV_PRIVZETO)


def get_clanarina_zneski(db: Session) -> dict:
    """Vrne slovar {tip_clanstva: znesek_float} iz nastavitve 'clanarina_zneski'."""
    n = db.query(Nastavitev).filter(Nastavitev.kljuc == "clanarina_zneski").first()
    if not n or not n.vrednost:
        return {}
    result = {}
    for vrstica in n.vrednost.splitlines():
        vrstica = vrstica.strip()
        if "=" in vrstica:
            tip, zn_str = vrstica.split("=", 1)
            try:
                result[tip.strip()] = float(zn_str.strip())
            except ValueError:
                pass
    return result
