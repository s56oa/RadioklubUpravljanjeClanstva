from .models import AuditLog


def log_akcija(
    db,
    uporabnik: str | None,
    akcija: str,
    opis: str | None = None,
    ip: str | None = None,
):
    """Zapiše akcijo v audit log. Ob napaki tiho preskočimo (db rollback)."""
    try:
        entry = AuditLog(uporabnik=uporabnik, akcija=akcija, opis=opis, ip=ip)
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
