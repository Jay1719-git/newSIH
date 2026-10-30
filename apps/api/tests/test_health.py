from fastapi.testclient import TestClient

from app.main import create_app


def test_root_and_versioned_health_are_synthetic_and_database_independent() -> None:
    client = TestClient(create_app())
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "environment": "SYNTHETIC",
            "contract_version": "0.1.0",
        }
        assert response.headers.get("x-request-id")


def test_unknown_routes_use_structured_error_envelope() -> None:
    response = TestClient(create_app()).get("/api/v1/not-a-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"].startswith("req_")
