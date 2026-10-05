import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user
from ..database import get_db, utcnow
from ..models import User
from ..serializers import user_out
from ..settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_COOKIE = "valpal_oauth_state"


def frontend_redirect(path, **params):
    url = get_settings().frontend_url.rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    return RedirectResponse(url)


@router.get("/login")
def login():
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    response.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax")
    return response


@router.get("/callback")
def callback(request: Request, db: Session = Depends(get_db), code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return frontend_redirect("/login", error=error)
    expected_state = request.cookies.get(STATE_COOKIE)
    if not code or not state or not expected_state or not secrets.compare_digest(state, expected_state):
        return frontend_redirect("/login", error="invalid_state")

    settings = get_settings()
    try:
        with httpx.Client(timeout=15) as client:
            token_response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            userinfo_response = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
    except (httpx.HTTPError, KeyError, ValueError):
        return frontend_redirect("/login", error="google_error")

    email = (userinfo.get("email") or "").strip().lower()
    if not email or not userinfo.get("email_verified"):
        return frontend_redirect("/login", error="email_not_verified")

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        if db.scalar(select(func.count(User.id))) > 0:
            return frontend_redirect("/login", error="not_authorized", email=email)
        # Very first login: this user becomes the (permanent) administrator
        user = User(email=email, name=userinfo.get("name") or "", is_admin=True, is_owner=True)
        db.add(user)
    elif not user.name and userinfo.get("name"):
        user.name = userinfo["name"]
    user.last_login_at = utcnow()
    db.commit()

    response = RedirectResponse(get_settings().frontend_url.rstrip("/") + "/auth/callback#token=" + create_access_token(user))
    response.delete_cookie(STATE_COOKIE)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
