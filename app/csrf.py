import secrets

from fastapi import Form, HTTPException, Request


def get_csrf_token(request: Request) -> str:
    """Get or create CSRF token for this session. Used as Jinja2 template global."""
    token = request.session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.session["_csrf_token"] = token
    return token


async def csrf_protect(request: Request, csrf_token: str = Form("")):
    """FastAPI dependency: validates CSRF token from POST form submissions."""
    stored = request.session.get("_csrf_token")
    if not stored or not secrets.compare_digest(stored, csrf_token):
        raise HTTPException(status_code=403, detail="Neveljaven CSRF žeton.")
