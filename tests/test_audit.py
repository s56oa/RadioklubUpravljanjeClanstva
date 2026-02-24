from unittest.mock import MagicMock

from app.audit_log import log_akcija
from app.models import AuditLog


def test_log_akcija_shrani(db):
    log_akcija(db, "admin", "test_akcija", "opis test", ip="127.0.0.1")
    entry = db.query(AuditLog).filter(AuditLog.akcija == "test_akcija").first()
    assert entry is not None
    assert entry.uporabnik == "admin"
    assert entry.opis == "opis test"
    assert entry.ip == "127.0.0.1"


def test_log_akcija_brez_opisa(db):
    log_akcija(db, "admin", "akcija_brez_opisa")
    entry = db.query(AuditLog).filter(AuditLog.akcija == "akcija_brez_opisa").first()
    assert entry is not None
    assert entry.opis is None


def test_log_akcija_napaka_ne_propagira(db):
    db.commit = MagicMock(side_effect=Exception("DB napaka"))
    # Ne sme vreči exception
    log_akcija(db, "admin", "test_napaka")
