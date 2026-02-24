from app.routers.clani import _normaliziraj_clan

TIPI = ["Osebni", "Družinski", "Simpatizerji"]


def test_title_case_priimek_ime():
    p, i, *_ = _normaliziraj_clan("NOVAK", "JANEZ", "", "", "Osebni", TIPI)
    assert p == "Novak"
    assert i == "Janez"


def test_upper_klicni_znak():
    _, _, kz, *_ = _normaliziraj_clan("Novak", "Janez", "s59abc", "", "Osebni", TIPI)
    assert kz == "S59ABC"


def test_prazni_klicni_znak_vrne_none():
    _, _, kz, *_ = _normaliziraj_clan("Novak", "Janez", "  ", "", "Osebni", TIPI)
    assert kz is None


def test_napacen_email():
    *_, napaka = _normaliziraj_clan("Novak", "Janez", "", "ni-email", "Osebni", TIPI)
    assert napaka is not None


def test_veljaven_email():
    *_, napaka = _normaliziraj_clan("Novak", "Janez", "", "janez@test.si", "Osebni", TIPI)
    assert napaka is None


def test_neznan_tip_clanstva_se_popravi():
    _, _, _, _, tip, _ = _normaliziraj_clan("Novak", "Janez", "", "", "Neznano", TIPI)
    assert tip == "Osebni"
