import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.csrf import get_csrf_token, csrf_protect


def _mock_request(session=None):
    req = MagicMock()
    req.session = session if session is not None else {}
    return req


def test_get_csrf_token_ustvari():
    req = _mock_request()
    token = get_csrf_token(req)
    assert len(token) == 64  # 32 bytes hex = 64 chars
    assert req.session["_csrf_token"] == token


def test_get_csrf_token_obstojechi():
    req = _mock_request({"_csrf_token": "abc123"})
    token = get_csrf_token(req)
    assert token == "abc123"


def test_csrf_protect_ok():
    req = _mock_request({"_csrf_token": "token123"})
    # Mora se izvesti brez napake
    asyncio.run(csrf_protect(req, csrf_token="token123"))


def test_csrf_protect_napacen_token():
    req = _mock_request({"_csrf_token": "token123"})
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(csrf_protect(req, csrf_token="napacen"))
    assert exc_info.value.status_code == 403


def test_csrf_protect_brez_tokena():
    req = _mock_request({})
    with pytest.raises(HTTPException):
        asyncio.run(csrf_protect(req, csrf_token=""))
