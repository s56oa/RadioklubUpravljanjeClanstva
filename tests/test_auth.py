from app.auth import hash_geslo, preveri_geslo, preveri_zahteve_gesla, is_admin, is_editor


def test_hash_geslo_vrne_hash():
    h = hash_geslo("test123")
    assert h != "test123"
    assert h.startswith("$2b$")


def test_preveri_geslo_pravilno():
    h = hash_geslo("geslo123")
    assert preveri_geslo("geslo123", h) is True


def test_preveri_geslo_napacno():
    h = hash_geslo("geslo123")
    assert preveri_geslo("napacno", h) is False


def test_preveri_zahteve_gesla_prekratko():
    assert preveri_zahteve_gesla("Abc123!") is not None


def test_preveri_zahteve_gesla_brez_malih():
    assert preveri_zahteve_gesla("ABC123!@#$DEFGH") is not None


def test_preveri_zahteve_gesla_brez_velikih():
    assert preveri_zahteve_gesla("abc123!@#$defgh") is not None


def test_preveri_zahteve_gesla_brez_stevilke():
    assert preveri_zahteve_gesla("Abcdef!@#$GHIJK") is not None


def test_preveri_zahteve_gesla_brez_posebnega():
    assert preveri_zahteve_gesla("Abcdef123GHIJKL") is not None


def test_preveri_zahteve_gesla_veljavno():
    assert preveri_zahteve_gesla("Veljavno1234!ab") is None


def test_is_admin():
    assert is_admin({"vloga": "admin"}) is True
    assert is_admin({"vloga": "urednik"}) is False
    assert is_admin(None) is False


def test_is_editor():
    assert is_editor({"vloga": "admin"}) is True
    assert is_editor({"vloga": "urednik"}) is True
    assert is_editor({"vloga": "bralec"}) is False
