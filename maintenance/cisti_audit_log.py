#!/usr/bin/env python3
"""
Čiščenje tabele audit_log – odstrani vnose starejše od X dni.

Minimalno dovoljeno obdobje: 30 dni.

Uporaba:
    python3 maintenance/cisti_audit_log.py
    python3 maintenance/cisti_audit_log.py --dni 365
    python3 maintenance/cisti_audit_log.py --dni 90 --dry-run
    python3 maintenance/cisti_audit_log.py --dni 90 -y          # brez potrditve (cron)
    python3 maintenance/cisti_audit_log.py --db /pot/do/baze.db

Okoljska spremenljivka DATABASE_URL (privzeto: sqlite:///./data/clanstvo.db).

Izhodni kodi:
    0 – uspeh (ali ni vnosov za brisanje)
    1 – napaka (neveljavni argumenti, manjkajoča baza, napaka SQLite)
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

MIN_DNI = 30
PRIVZETI_DNI = 90


def _db_pot_iz_url(database_url: str) -> Path:
    """Izvleče absolutno pot SQLite datoteke iz DATABASE_URL niza."""
    url = database_url.strip()
    if not url.startswith("sqlite:///"):
        raise ValueError(
            f"Nepodprt DATABASE_URL format: {url!r}  (pričakovano sqlite:///...)"
        )
    # sqlite:///./data/clanstvo.db  →  ./data/clanstvo.db
    # sqlite:////abs/path.db        →  /abs/path.db
    return Path(url[len("sqlite:///"):])


def _doloci_db_pot(arg_db: str | None) -> Path:
    if arg_db:
        return Path(arg_db)
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/clanstvo.db")
    return _db_pot_iz_url(database_url)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Čiščenje audit_log – odstrani vnose starejše od X dni.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Minimalna vrednost --dni: {MIN_DNI}",
    )
    parser.add_argument(
        "--dni",
        type=int,
        default=PRIVZETI_DNI,
        metavar="DNI",
        help=f"Starost vnosov za brisanje v dneh (privzeto: {PRIVZETI_DNI}, minimum: {MIN_DNI})",
    )
    parser.add_argument(
        "--db",
        default=None,
        metavar="POT",
        help="Pot do SQLite datoteke (privzeto: DATABASE_URL ali data/clanstvo.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pokaži koliko vnosov bi izbrisali, ne briši",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Brez interaktivne potrditve (za cron)",
    )
    args = parser.parse_args()

    # --- Validacija ---
    if args.dni < MIN_DNI:
        print(
            f"NAPAKA: --dni mora biti vsaj {MIN_DNI} dni (podano: {args.dni}).",
            file=sys.stderr,
        )
        return 1

    try:
        db_pot = _doloci_db_pot(args.db)
    except ValueError as e:
        print(f"NAPAKA: {e}", file=sys.stderr)
        return 1

    if not db_pot.exists():
        print(f"NAPAKA: Datoteka baze ne obstaja: {db_pot}", file=sys.stderr)
        return 1

    # --- Povezi in analiziraj ---
    try:
        conn = sqlite3.connect(str(db_pot))
    except sqlite3.Error as e:
        print(f"NAPAKA: Ne morem odpreti baze {db_pot}: {e}", file=sys.stderr)
        return 1

    try:
        cur = conn.cursor()

        # Skupno število vnosov
        cur.execute("SELECT COUNT(*) FROM audit_log")
        skupaj = cur.fetchone()[0]

        # Vnosi za brisanje
        cur.execute(
            "SELECT COUNT(*) FROM audit_log WHERE cas < datetime('now', ?)",
            (f"-{args.dni} days",),
        )
        za_brisanje = cur.fetchone()[0]

        # Razpon datumov vnosov za brisanje
        cur.execute(
            "SELECT MIN(cas), MAX(cas) FROM audit_log WHERE cas < datetime('now', ?)",
            (f"-{args.dni} days",),
        )
        razpon = cur.fetchone()
        cas_od, cas_do = (razpon[0], razpon[1]) if razpon and razpon[0] else (None, None)

        # --- Izpis ---
        print(f"Baza:            {db_pot.resolve()}")
        print(f"Skupaj vnosov:   {skupaj}")
        print(f"Meja brisanja:   starejše od {args.dni} dni")
        print(f"Vnosov za bris.: {za_brisanje}", end="")
        if cas_od:
            print(f"  ({cas_od[:10]}  →  {cas_do[:10]})")
        else:
            print()

        if za_brisanje == 0:
            print("Ni vnosov za brisanje.")
            return 0

        if args.dry_run:
            print("[DRY RUN] Brisanje preskočeno.")
            return 0

        # --- Potrditev ---
        if not args.yes:
            try:
                odgovor = input(f"\nIzbriši {za_brisanje} vnosov iz audit_log? [d/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nPrekinjeno.")
                return 0
            if odgovor not in ("d", "da", "y", "yes"):
                print("Prekinjeno.")
                return 0

        # --- Briši ---
        cur.execute(
            "DELETE FROM audit_log WHERE cas < datetime('now', ?)",
            (f"-{args.dni} days",),
        )
        conn.commit()
        print(f"Izbrisano {cur.rowcount} vnosov. Preostalih: {skupaj - cur.rowcount}.")
        return 0

    except sqlite3.Error as e:
        print(f"NAPAKA SQLite: {e}", file=sys.stderr)
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
