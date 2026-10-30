from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.auth.policies import Principal
from app.models.auth_session import AuthSession
from app.models.enums import UserStatus
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    digest = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    from app.db.session import get_session_factory

    with get_session_factory()() as db:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.access_token_digest == digest,
                AuthSession.revoked_at.is_(None),
                AuthSession.access_expires_at > now,
            )
        )
        if session is None:
            raise HTTPException(
                status_code=401,
                detail="Access token is invalid or expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = db.get(User, session.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=401,
                detail="Account is disabled.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return Principal(
            user_id=user.id,
            role=user.role,
            institution_id=user.institution_id,
            student_identity_reference_id=user.student_identity_reference_id,
            auth_session_id=session.id,
        )


def require_roles(*roles):
    allowed = frozenset(roles)

    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:  # noqa: B008
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail="This role cannot access the resource.")
        return principal

    return dependency
