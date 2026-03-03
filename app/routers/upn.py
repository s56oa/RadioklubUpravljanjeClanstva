from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Clan
from ..auth import require_login
from ..config import get_nastavitev, get_clanarina_zneski
from ..upn import generiraj_upn_svg, generiraj_upn_png

router = APIRouter(prefix="/upn")


@router.get("/{clan_id}/{leto}")
async def upn_qr(
    request: Request,
    clan_id: int,
    leto: int,
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return RedirectResponse(url="/clani", status_code=302)

    iban = get_nastavitev(db, "klub_iban", "")
    ime_kluba = get_nastavitev(db, "klub_ime", "")
    ulica_kluba = get_nastavitev(db, "klub_naslov", "")
    kraj_kluba = get_nastavitev(db, "klub_posta", "")
    ref_predloga = get_nastavitev(db, "upn_referenca_predloga", "SI00 5-{leto}")
    namen = get_nastavitev(db, "upn_namen", "OTHR")
    opis_predloga = get_nastavitev(db, "upn_opis_predloga", "Članarina {leto}")

    referenca = ref_predloga.replace("{leto}", str(leto)).replace(
        "{id}", str(clan.id)
    ).replace(
        "{es}", str(clan.es_stevilka) if clan.es_stevilka else ""
    )
    opis = opis_predloga.replace("{leto}", str(leto))

    zneski = get_clanarina_zneski(db)
    znesek = zneski.get(clan.tip_clanstva) if clan.tip_clanstva else None

    svg = generiraj_upn_svg(
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
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/{clan_id}/{leto}/png")
async def upn_qr_png(
    request: Request,
    clan_id: int,
    leto: int,
    db: Session = Depends(get_db),
) -> Response:
    """PNG različica UPN QR kode (za tiskanje / pošiljanje po emailu)."""
    user, redirect = require_login(request)
    if redirect:
        return redirect

    clan = db.query(Clan).filter(Clan.id == clan_id).first()
    if not clan:
        return Response(content=b"", status_code=404)

    iban = get_nastavitev(db, "klub_iban", "")
    ime_kluba = get_nastavitev(db, "klub_ime", "")
    ulica_kluba = get_nastavitev(db, "klub_naslov", "")
    kraj_kluba = get_nastavitev(db, "klub_posta", "")
    ref_predloga = get_nastavitev(db, "upn_referenca_predloga", "SI00 5-{leto}")
    namen = get_nastavitev(db, "upn_namen", "OTHR")
    opis_predloga = get_nastavitev(db, "upn_opis_predloga", "Članarina {leto}")

    referenca = ref_predloga.replace("{leto}", str(leto)).replace(
        "{id}", str(clan.id)
    ).replace(
        "{es}", str(clan.es_stevilka) if clan.es_stevilka else ""
    )
    opis = opis_predloga.replace("{leto}", str(leto))

    zneski = get_clanarina_zneski(db)
    znesek = zneski.get(clan.tip_clanstva) if clan.tip_clanstva else None

    png = generiraj_upn_png(
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
    es = clan.es_stevilka or str(clan.id)
    filename = f"{es}_{leto}.png"
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

