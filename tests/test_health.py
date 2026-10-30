from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_swagger_ui_and_openapi_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]


def test_root_redirects_to_swagger_ui(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/nope", headers={"X-Request-ID": "abc-123"})
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": "Not Found",
        "requestId": "abc-123",
    }
    assert response.headers["X-Request-ID"] == "abc-123"
