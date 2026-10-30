import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password
from app.auth.policies import Principal, authorize_external_verification
from app.db.session import get_db_session
from app.main import create_app
from app.models.auth_session import AuthSession
from app.models.enums import InstitutionStatus, UserRole, UserStatus
from app.models.institution import Institution
from app.models.user import User
from app.models.verifier_grant import ExternalVerifierGrant


@pytest.fixture
def auth_database(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE student_identity_references (id CHAR(32) PRIMARY KEY)")
        )
    Institution.__table__.create(engine)
    User.__table__.create(engine)
    AuthSession.__table__.create(engine)
    ExternalVerifierGrant.__table__.create(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: factory)

    institution_id = uuid.uuid4()
    with factory() as db:
        institution = Institution(
            id=institution_id,
            aicte_code="SYNTH-TEST",
            name="Synthetic Test Institute",
            state="Test State",
            tier="Synthetic",
            status=InstitutionStatus.ACTIVE,
        )
        db.add(institution)
        db.flush()
        db.add(
            User(
                email="operator@example.test",
                display_name="Synthetic Operator",
                role=UserRole.INSTITUTION_OPERATOR,
                status=UserStatus.ACTIVE,
                institution_id=institution_id,
                password_hash=hash_password("synthetic-test-password"),
            )
        )
        db.add(
            User(
                email="verifier@example.test",
                display_name="Synthetic Verifier",
                role=UserRole.EXTERNAL_VERIFIER,
                status=UserStatus.ACTIVE,
                password_hash=hash_password("synthetic-verifier-password"),
            )
        )
        db.add(
            User(
                email="admin@example.test",
                display_name="Synthetic AICTE Admin",
                role=UserRole.REGULATOR_ADMIN,
                status=UserStatus.ACTIVE,
                password_hash=hash_password("synthetic-admin-password"),
            )
        )
        db.commit()
    yield factory
    engine.dispose()


def test_protected_identity_endpoints_reject_missing_bearer_without_database() -> None:
    client = TestClient(create_app())
    for method, path in (("get", "/api/v1/auth/me"), ("post", "/api/v1/auth/logout")):
        response = getattr(client, method)(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert response.headers["www-authenticate"] == "Bearer"


def test_fastapi_openapi_marks_identity_routes_as_bearer_protected() -> None:
    schema = create_app().openapi()
    schemes = schema["components"]["securitySchemes"]
    scheme_name = next(iter(schemes))
    assert schemes[scheme_name]["type"] == "http"
    assert schemes[scheme_name]["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/auth/me"]["get"]["security"] == [{scheme_name: []}]
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]


def test_login_rejects_browser_supplied_role_or_institution() -> None:
    app = create_app()

    def no_database():
        yield None

    app.dependency_overrides[get_db_session] = no_database
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={
            "email": "person@example.test",
            "password": "never-log-this-password",
            "role": "regulator_admin",
            "institution_id": "other-tenant",
        },
    )
    assert response.status_code == 422
    assert "never-log-this-password" not in response.text
    assert "other-tenant" not in response.text


def test_login_refresh_logout_uses_expiring_opaque_sessions(auth_database) -> None:
    app = create_app()
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.test", "password": "synthetic-test-password"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["expires_in"] == 900
    assert body["user"]["role"] == "institution_operator"
    assert body["user"]["institution_id"]
    assert body["access_token"]
    assert login.headers["set-cookie"].lower().find("httponly") >= 0

    first_token = body["access_token"]
    with auth_database() as db:
        auth_session = db.query(AuthSession).one()
        assert auth_session.access_token_digest != first_token
        assert len(auth_session.access_token_digest) == 64
        assert auth_session.refresh_token_digest != client.cookies.get("weave_refresh")
    current_user = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {first_token}"})
    assert current_user.status_code == 200

    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    second_token = refreshed.json()["access_token"]
    assert second_token != first_token
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {first_token}"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {second_token}"}
        ).status_code
        == 200
    )

    logout = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {second_token}"})
    assert logout.status_code == 204
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {second_token}"}
        ).status_code
        == 401
    )


def test_login_failure_is_generic_and_throttled(auth_database) -> None:
    client = TestClient(create_app())
    body = {"email": "missing-account@example.test", "password": "bad-password"}
    first = client.post("/api/v1/auth/login", json=body)
    assert first.status_code == 401
    assert first.json()["error"]["code"] == "UNAUTHORIZED"
    assert "missing-account@example.test" not in first.text
    for _ in range(7):
        client.post("/api/v1/auth/login", json=body)
    limited = client.post("/api/v1/auth/login", json=body)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert limited.headers["retry-after"]


def test_external_verifier_grants_are_loaded_from_database(auth_database) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models.user import User

    with auth_database() as db:
        verifier = db.scalar(select(User).where(User.email == "verifier@example.test"))
        approver = db.scalar(select(User).where(User.email == "admin@example.test"))
        now = datetime.now(UTC)
        db.add(
            ExternalVerifierGrant(
                user_id=verifier.id,
                approved_by_user_id=approver.id,
                purpose="synthetic admissions review",
                permitted_claims=["enrolment_status"],
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()
        principal = Principal(verifier.id, verifier.role)
        authorize_external_verification(
            db,
            principal,
            purpose="synthetic admissions review",
            claims={"enrolment_status"},
            now=now,
        )
        with pytest.raises(HTTPException) as denied:
            authorize_external_verification(
                db,
                principal,
                purpose="other purpose",
                claims={"enrolment_status"},
                now=now,
            )
        assert denied.value.status_code == 403
