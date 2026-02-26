#!/usr/bin/env python3
"""
Live / hot backup SQLite baze podatkov z timestampom v imenu datoteke.

Ustvari konsistenten backup med delujočo aplikacijo brez zaklepanja baze
(SQLite Online Backup API – sqlite3.Connection.backup()).

Ime backupa: <osnova>_YYYYMMDD_HHMMSS.db  (lokalni čas naprave)

Uporaba:
    python3 maintenance/backup_baze.py
    python3 maintenance/backup_baze.py --mapa data/backups
    python3 maintenance/backup_baze.py --mapa /mnt/nas/backup --ohrani 30
    python3 maintenance/backup_baze.py --db data/clanstvo.db --mapa /backup

Okoljska spremenljivka DATABASE_URL (privzeto: sqlite:///./data/clanstvo.db).

Izhodni kodi:
    0 – uspeh, pot do backupa se izpiše na stdout
    1 – napaka
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def _db_pot_iz_url(database_url: str) -> Path:
    """Izvleče pot SQLite datoteke iz DATABASE_URL niza."""
    url = database_url.strip()
    if not url.startswith("sqlite:///"):
        raise ValueError(
            f"Nepodprt DATABASE_URL format: {url!r}  (pričakovano sqlite:///...)"
        )
    return Path(url[len("sqlite:///"):])


def _doloci_db_pot(arg_db: str | None) -> Path:
    if arg_db:
        return Path(arg_db)
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/clanstvo.db")
    return _db_pot_iz_url(database_url)


def _cisti_stare_backupe(mapa: Path, osnova: str, ohrani: int) -> list[Path]:
    """Odstrani najstarejše backupe, ohrani zadnjih `ohrani` datotek."""
    vzorec = f"{osnova}_????????_??????.db"
    vsi = sorted(mapa.glob(vzorec), key=lambda p: p.name)
    za_brisanje = vsi[: max(0, len(vsi) - ohrani)]
    odstranjeni = []
    for stara in za_brisanje:
        try:
            stara.unlink()
            odstranjeni.append(stara)
        except OSError as e:
            print(f"OPOZORILO: Ne morem izbrisati {stara.name}: {e}", file=sys.stderr)
    return odstranjeni


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live/hot backup SQLite baze z timestampom v imenu datoteke.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Primer za cron (dnevni backup ob 2:00, ohrani 30):\n"
            "  0 2 * * *  cd /opt/radioklub && python3 maintenance/backup_baze.py --ohrani 30"
        ),
    )
    parser.add_argument(
        "--db",
        default=None,
        metavar="POT",
        help="Pot do izvorne SQLite datoteke (privzeto: DATABASE_URL ali data/clanstvo.db)",
    )
    parser.add_argument(
        "--mapa",
        default=None,
        metavar="MAPA",
        help="Ciljna mapa za backup datoteke (privzeto: data/backups/)",
    )
    parser.add_argument(
        "--ohrani",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Ohrani samo zadnjih N backupov in izbriši starejše "
            "(0 = ohrani vse, privzeto: 0)"
        ),
    )
    args = parser.parse_args()

    # --- Validacija ---
    if args.ohrani < 0:
        print("NAPAKA: --ohrani mora biti 0 ali pozitivno celo število.", file=sys.stderr)
        return 1

    try:
        src_pot = _doloci_db_pot(args.db)
    except ValueError as e:
        print(f"NAPAKA: {e}", file=sys.stderr)
        return 1

    if not src_pot.exists():
        print(f"NAPAKA: Izvorna baza ne obstaja: {src_pot}", file=sys.stderr)
        return 1

    # --- Ciljna mapa ---
    if args.mapa:
        izh_mapa = Path(args.mapa)
    else:
        izh_mapa = src_pot.parent / "backups"

    try:
        izh_mapa.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"NAPAKA: Ne morem ustvariti mape {izh_mapa}: {e}", file=sys.stderr)
        return 1

    # --- Ime backup datoteke ---
    zdaj = datetime.now().strftime("%Y%m%d_%H%M%S")
    osnova = src_pot.stem          # "clanstvo" iz "clanstvo.db"
    dst_pot = izh_mapa / f"{osnova}_{zdaj}.db"

    print(f"Vir:    {src_pot.resolve()}")
    print(f"Backup: {dst_pot.resolve()}")

    # --- Hot backup (SQLite Online Backup API) ---
    src_conn: sqlite3.Connection | None = None
    dst_conn: sqlite3.Connection | None = None
    try:
        src_conn = sqlite3.connect(f"file:{src_pot}?mode=ro", uri=True)
        dst_conn = sqlite3.connect(str(dst_pot))
        # backup() je atomaren in konsistenten ne glede na WAL / journal mode
        src_conn.backup(dst_conn)
    except sqlite3.Error as e:
        print(f"NAPAKA SQLite: {e}", file=sys.stderr)
        if dst_pot.exists():
            dst_pot.unlink()          # počisti nepopoln backup
        return 1
    finally:
        if dst_conn:
            dst_conn.close()
        if src_conn:
            src_conn.close()

    # --- Poročilo o uspehu ---
    velikost_kb = dst_pot.stat().st_size / 1024
    print(f"Uspeh!  Velikost: {velikost_kb:.1f} KB  ({zdaj})")

    # --- Čiščenje starih backupov ---
    if args.ohrani > 0:
        odstranjeni = _cisti_stare_backupe(izh_mapa, osnova, args.ohrani)
        if odstranjeni:
            for p in odstranjeni:
                print(f"Odstranil star backup: {p.name}")
            print(f"Shranjenih zadnjih {args.ohrani} backupov.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
