from fastapi.testclient import TestClient

from claimpulse.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_swagger_ui_and_openapi_served() -> None:
    assert client.get("/docs").status_code == 200
    assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]


def test_root_redirects_to_swagger_ui() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"
