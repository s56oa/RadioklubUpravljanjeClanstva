import io
from datetime import datetime

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, Response
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog
from ..auth import require_login, is_admin
from ..csrf import get_csrf_token

router = APIRouter(prefix="/audit")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["csrf_token"] = get_csrf_token


@router.get("", response_class=HTMLResponse)
async def audit_seznam(
    request: Request,
    akcija: str = "",
    db: Session = Depends(get_db),
) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    query = db.query(AuditLog).order_by(AuditLog.cas.desc())
    if akcija:
        query = query.filter(AuditLog.akcija == akcija)
    vnosi = query.limit(500).all()

    akcije = [
        r[0]
        for r in db.query(AuditLog.akcija).distinct().order_by(AuditLog.akcija).all()
    ]

    return templates.TemplateResponse(
        "audit/seznam.html",
        {
            "request": request,
            "user": user,
            "vnosi": vnosi,
            "akcija": akcija,
            "akcije": akcije,
            "is_admin": True,
        },
    )


@router.get("/izvoz")
async def audit_izvoz(request: Request, db: Session = Depends(get_db)) -> Response:
    user, redirect = require_login(request)
    if redirect:
        return redirect
    if not is_admin(user):
        return RedirectResponse(url="/clani", status_code=302)

    vnosi = db.query(AuditLog).order_by(AuditLog.cas.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Audit log"
    from openpyxl.styles import Font
    ws.append(["Čas", "Uporabnik", "IP", "Akcija", "Opis"])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for v in vnosi:
        ws.append([
            v.cas.isoformat() if v.cas else "",
            v.uporabnik or "",
            v.ip or "",
            v.akcija,
            v.opis or "",
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    today = datetime.today().date().isoformat()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="audit_log_{today}.xlsx"'},
    )
