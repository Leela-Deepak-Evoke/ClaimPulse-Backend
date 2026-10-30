from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from claimpulse.config import get_settings

NEW_USER = {
    "full_name": "Kiran Kumar",
    "email": "kiran.kumar@claimpulse.example.com",
    "password": "Password1",
    "role": "BILLER",
}


def _login(client: TestClient, email: str, password: str):  # type: ignore[no-untyped-def]
    return client.post("/auth/login", data={"username": email, "password": password})


def test_login_success(client: TestClient) -> None:
    response = _login(client, "admin@test.io", "Password1")
    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["user"]["role"] == "ADMIN"
    assert "password" not in str(body["user"])


def test_login_wrong_password_and_unknown_email_look_the_same(client: TestClient) -> None:
    wrong = _login(client, "admin@test.io", "WrongPass1")
    unknown = _login(client, "ghost@test.io", "Password1")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_login_inactive_user(client: TestClient) -> None:
    response = _login(client, "inactive@test.io", "Password1")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_login_missing_field_is_validation_error(client: TestClient) -> None:
    response = client.post("/auth/login", data={"username": "admin@test.io"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_overlong_password_is_rejected(client: TestClient) -> None:
    assert _login(client, "admin@test.io", "a1" * 40).status_code == 401


def test_me(client: TestClient, biller: dict[str, str]) -> None:
    response = client.get("/auth/me", headers=biller)
    assert response.status_code == 200
    assert response.json()["email"] == "biller@test.io"


def test_me_without_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_with_garbage_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer nonsense"})
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


def test_me_with_expired_token(client: TestClient) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "1", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_me_with_token_for_missing_user(client: TestClient) -> None:
    token = jwt.encode(
        {"sub": "999", "exp": datetime.now(UTC) + timedelta(hours=1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


def test_create_user_as_admin(client: TestClient, admin: dict[str, str]) -> None:
    response = client.post("/auth/users", json=NEW_USER, headers=admin)
    assert response.status_code == 201
    assert response.json()["role"] == "BILLER"
    assert "password" not in response.text
    assert _login(client, NEW_USER["email"], "Password1").status_code == 200


def test_create_user_duplicate_email(client: TestClient, admin: dict[str, str]) -> None:
    client.post("/auth/users", json=NEW_USER, headers=admin)
    response = client.post(
        "/auth/users", json={**NEW_USER, "email": NEW_USER["email"].upper()}, headers=admin
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_create_user_as_biller_is_forbidden(client: TestClient, biller: dict[str, str]) -> None:
    response = client.post("/auth/users", json=NEW_USER, headers=biller)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_create_user_weak_password(client: TestClient, admin: dict[str, str]) -> None:
    response = client.post("/auth/users", json={**NEW_USER, "password": "password"}, headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "password"


def test_list_users_filters(client: TestClient, admin: dict[str, str]) -> None:
    everyone = client.get("/users", headers=admin).json()
    assert everyone["total"] == 3
    billers = client.get("/users?role=BILLER&is_active=true", headers=admin).json()
    assert [u["email"] for u in billers["items"]] == ["biller@test.io"]
    found = client.get("/users?search=ada", headers=admin).json()
    assert found["total"] == 1
    paged = client.get("/users?size=2&page=2", headers=admin).json()
    assert len(paged["items"]) == 1


def test_list_users_biller_forbidden(client: TestClient, biller: dict[str, str]) -> None:
    assert client.get("/users", headers=biller).status_code == 403


def test_patch_user_role_and_active(client: TestClient, admin: dict[str, str]) -> None:
    response = client.patch("/users/2", json={"role": "ADMIN", "is_active": False}, headers=admin)
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"
    assert response.json()["is_active"] is False


def test_patch_user_errors(client: TestClient, admin: dict[str, str]) -> None:
    assert client.patch("/users/999", json={"is_active": False}, headers=admin).status_code == 404
    assert client.patch("/users/2", json={}, headers=admin).status_code == 422
    for body in ({"is_active": False}, {"role": "BILLER"}):
        response = client.patch("/users/1", json=body, headers=admin)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CANNOT_MODIFY_SELF"
    assert client.patch("/users/1", json={"role": "ADMIN"}, headers=admin).status_code == 200


def test_lookups(client: TestClient, biller: dict[str, str]) -> None:
    body = client.get("/lookups", headers=biller).json()
    assert body["claim_statuses"] == ["SUBMITTED", "PAID", "DENIED", "RESUBMITTED"]
    assert "Not covered" in body["denial_reasons"]
    assert body["roles"] == ["ADMIN", "BILLER"]
    assert client.get("/lookups").status_code == 401
