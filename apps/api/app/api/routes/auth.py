from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.auth.passwords import verify_password
from app.auth.policies import Principal
from app.auth.throttle import login_throttle
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.auth_session import AuthSession
from app.models.enums import UserStatus
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])
ACCESS_TTL_SECONDS = 900
REFRESH_TTL_SECONDS = 8 * 60 * 60
REFRESH_COOKIE = "weave_refresh"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=REFRESH_TTL_SECONDS,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path=f"{settings.api_base_path}/auth",
    )


def _user_payload(user: User) -> dict[str, str | None]:
    labels = {
        "regulator_admin": "AICTE Administrator",
        "regulator_officer": "AICTE Officer",
        "institution_admin": "Institution Administrator",
        "institution_operator": "Institution Operator",
        "auditor": "Auditor",
        "student": "Student",
        "external_verifier": "External Verifier",
    }
    institution = user.institution
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.display_name,
        "role": user.role.value,
        "roleLabel": labels[user.role.value],
        "institution_id": str(user.institution_id) if user.institution_id else None,
        "institution_name": institution.name if institution else None,
        "scopeDescription": "Server-authorized access; permissions are enforced by the API.",
    }


@router.post("/login", operation_id="login")
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    remote = request.client.host if request.client else "unknown"
    if login_throttle.is_blocked(remote, payload.email):
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Try again later.",
            headers={"Retry-After": str(login_throttle.block_seconds)},
        )

    user = db.scalar(select(User).where(func.lower(User.email) == payload.email))
    valid = verify_password(payload.password, user.password_hash if user else None)
    if user is None or not valid or user.status != UserStatus.ACTIVE:
        login_throttle.record_failure(remote, payload.email)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")

    login_throttle.clear(remote, payload.email)
    access = _new_token()
    refresh = _new_token()
    now = datetime.now(UTC)
    session = AuthSession(
        user_id=user.id,
        access_token_digest=_digest(access),
        access_expires_at=now + timedelta(seconds=ACCESS_TTL_SECONDS),
        refresh_token_digest=_digest(refresh),
        refresh_expires_at=now + timedelta(seconds=REFRESH_TTL_SECONDS),
    )
    db.add(session)
    db.commit()
    _set_refresh_cookie(response, refresh)
    return {
        "environment": get_settings().app_env.upper(),
        "access_token": access,
        "token_type": "bearer",
        "expires_in": ACCESS_TTL_SECONDS,
        "user": _user_payload(user),
    }


@router.post("/refresh", operation_id="refreshAccessToken")
def refresh_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    refresh = request.cookies.get(REFRESH_COOKIE)
    if not refresh:
        raise HTTPException(status_code=401, detail="Refresh session is required.")

    now = datetime.now(UTC)
    session = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.refresh_token_digest == _digest(refresh),
            AuthSession.revoked_at.is_(None),
            AuthSession.refresh_expires_at > now,
        )
        .with_for_update()
    )
    if session is None:
        response.delete_cookie(REFRESH_COOKIE, path=f"{get_settings().api_base_path}/auth")
        raise HTTPException(status_code=401, detail="Refresh session is invalid or expired.")
    user = db.get(User, session.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        session.revoked_at = now
        db.commit()
        response.delete_cookie(REFRESH_COOKIE, path=f"{get_settings().api_base_path}/auth")
        raise HTTPException(status_code=401, detail="Account is disabled.")

    access, next_refresh = _new_token(), _new_token()
    session.access_token_digest = _digest(access)
    session.access_expires_at = now + timedelta(seconds=ACCESS_TTL_SECONDS)
    session.refresh_token_digest = _digest(next_refresh)
    session.refresh_expires_at = now + timedelta(seconds=REFRESH_TTL_SECONDS)
    db.commit()
    _set_refresh_cookie(response, next_refresh)
    return {
        "environment": get_settings().app_env.upper(),
        "access_token": access,
        "token_type": "bearer",
        "expires_in": ACCESS_TTL_SECONDS,
    }


@router.post("/logout", status_code=204, operation_id="logout")
def logout(
    response: Response,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
) -> Response:
    from app.db.session import get_session_factory

    db = get_session_factory()()
    session = db.get(AuthSession, principal.auth_session_id) if principal.auth_session_id else None
    if session is not None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
    db.close()
    response.delete_cookie(REFRESH_COOKIE, path=f"{get_settings().api_base_path}/auth")
    response.status_code = 204
    return response


@router.get("/me", operation_id="getCurrentUser")
def get_current_user(
    principal: Principal = Depends(get_current_principal),  # noqa: B008
) -> dict[str, str | None]:
    from app.db.session import get_session_factory

    db = get_session_factory()()
    user = db.get(User, principal.user_id)
    try:
        if user is None:
            raise HTTPException(status_code=401, detail="Account is unavailable.")
        return _user_payload(user)
    finally:
        db.close()
