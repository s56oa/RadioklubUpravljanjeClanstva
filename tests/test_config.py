from app.config import get_nastavitev, get_seznam, get_tipi_clanstva
from app.models import Nastavitev, TIPI_CLANSTVA_PRIVZETO


def test_get_nastavitev_obstojechi(db):
    db.add(Nastavitev(kljuc="test_kljuc", vrednost="test_vrednost"))
    db.commit()
    assert get_nastavitev(db, "test_kljuc") == "test_vrednost"


def test_get_nastavitev_privzeta(db):
    assert get_nastavitev(db, "neobstojeci_kljuc", "privzeto") == "privzeto"


def test_get_seznam_iz_baze(db):
    db.add(Nastavitev(kljuc="seznam_test", vrednost="A\nB\nC"))
    db.commit()
    result = get_seznam(db, "seznam_test", [])
    assert result == ["A", "B", "C"]


def test_get_tipi_clanstva_privzeti(db):
    result = get_tipi_clanstva(db)
    assert result == TIPI_CLANSTVA_PRIVZETO
