from fastapi.testclient import TestClient

CLAIM = {
    "patient_id": 1,
    "payer_id": 2,
    "service_date": "2026-08-06",
    "cpt_code": "99203",
    "icd_code": "j06.9",
    "billed_amount": 220.00,
    "notes": "New patient visit",
}


def _create(client: TestClient, headers: dict[str, str], **overrides: object) -> dict[str, object]:
    response = client.post("/claims", json={**CLAIM, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def test_create_claim(client: TestClient, biller: dict[str, str]) -> None:
    claim = _create(client, biller)
    assert claim["status"] == "SUBMITTED"
    assert claim["claim_code"] == f"CLM-{claim['id']:04d}"
    assert claim["billed_amount"] == "220.00"
    assert claim["paid_amount"] is None
    assert claim["icd_code"] == "J06.9"
    assert claim["created_by"] == {"id": 2, "full_name": "Bill Biller"}
    assert claim["patient"]["full_name"] == "Emily Johnson"
    assert claim["payer"]["payer_name"] == "Aetna"


def test_create_claim_created_by_ignores_body(client: TestClient, biller: dict[str, str]) -> None:
    claim = _create(client, biller, created_by=1)
    assert claim["created_by"]["id"] == 2  # type: ignore[index]


def test_create_claim_validation(client: TestClient, biller: dict[str, str]) -> None:
    bad_bodies = [
        {"cpt_code": "123"},
        {"icd_code": "ab"},
        {"billed_amount": 0},
        {"billed_amount": 10.123},
        {"service_date": "2999-01-01"},
    ]
    for override in bad_bodies:
        response = client.post("/claims", json={**CLAIM, **override}, headers=biller)
        assert response.status_code == 422, override
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_claim_unknown_refs(client: TestClient, biller: dict[str, str]) -> None:
    patient = client.post("/claims", json={**CLAIM, "patient_id": 99}, headers=biller)
    assert patient.json()["error"]["code"] == "PATIENT_NOT_FOUND"
    payer = client.post("/claims", json={**CLAIM, "payer_id": 99}, headers=biller)
    assert payer.json()["error"]["code"] == "PAYER_NOT_FOUND"


def test_get_update_delete_claim(
    client: TestClient, biller: dict[str, str], admin: dict[str, str]
) -> None:
    claim_id = _create(client, biller)["id"]
    assert client.get(f"/claims/{claim_id}", headers=biller).status_code == 200
    assert client.get("/claims/999", headers=biller).json()["error"]["code"] == "CLAIM_NOT_FOUND"

    updated = client.put(f"/claims/{claim_id}", json={**CLAIM, "cpt_code": "99204"}, headers=biller)
    assert updated.status_code == 200
    assert updated.json()["cpt_code"] == "99204"
    assert client.put("/claims/999", json=CLAIM, headers=biller).status_code == 404
    bad_ref = client.put(f"/claims/{claim_id}", json={**CLAIM, "payer_id": 99}, headers=biller)
    assert bad_ref.status_code == 404

    assert client.delete(f"/claims/{claim_id}", headers=biller).status_code == 403
    assert client.delete(f"/claims/{claim_id}", headers=admin).status_code == 204
    assert client.delete(f"/claims/{claim_id}", headers=admin).status_code == 404


def test_status_lifecycle(client: TestClient, biller: dict[str, str]) -> None:
    claim_id = _create(client, biller)["id"]
    url = f"/claims/{claim_id}/status"

    denied = client.patch(
        url,
        json={"status": "DENIED", "denial_reason": "Not covered", "notes": "Not in policy"},
        headers=biller,
    )
    assert denied.status_code == 200
    assert denied.json()["denial_reason"] == "Not covered"
    assert denied.json()["notes"] == "Not in policy"

    assert client.put(f"/claims/{claim_id}", json=CLAIM, headers=biller).status_code == 200

    resub = client.patch(url, json={"status": "RESUBMITTED"}, headers=biller)
    assert resub.json()["status"] == "RESUBMITTED"
    assert resub.json()["denial_reason"] == "Not covered"
    edit = client.put(f"/claims/{claim_id}", json=CLAIM, headers=biller)
    assert edit.status_code == 409
    assert edit.json()["error"]["code"] == "CLAIM_NOT_EDITABLE"

    paid = client.patch(url, json={"status": "PAID", "paid_amount": 198.00}, headers=biller)
    assert paid.status_code == 200
    assert paid.json()["paid_amount"] == "198.00"
    assert paid.json()["denial_reason"] is None

    closed = client.patch(
        url, json={"status": "DENIED", "denial_reason": "Not covered"}, headers=biller
    )
    assert closed.status_code == 409
    assert closed.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
    assert client.put(f"/claims/{claim_id}", json=CLAIM, headers=biller).status_code == 409


def test_status_rule_errors(client: TestClient, biller: dict[str, str]) -> None:
    claim_id = _create(client, biller)["id"]
    url = f"/claims/{claim_id}/status"

    def code(body: dict[str, object]) -> tuple[int, str]:
        response = client.patch(url, json=body, headers=biller)
        return response.status_code, response.json()["error"]["code"]

    assert code({"status": "RESUBMITTED"}) == (409, "INVALID_STATUS_TRANSITION")
    assert code({"status": "DENIED"}) == (422, "DENIAL_REASON_REQUIRED")
    assert code({"status": "PAID"}) == (422, "PAID_AMOUNT_REQUIRED")
    assert code({"status": "PAID", "paid_amount": 999}) == (422, "PAID_AMOUNT_EXCEEDS_BILLED")
    assert code({"status": "PAID", "paid_amount": 0}) == (422, "VALIDATION_ERROR")
    assert code({"status": "DENIED", "denial_reason": "Because"}) == (422, "VALIDATION_ERROR")
    missing = client.patch(
        "/claims/999/status", json={"status": "PAID", "paid_amount": 1}, headers=biller
    )
    assert missing.status_code == 404


def test_list_claims_filters_search_sort_pagination(
    client: TestClient, biller: dict[str, str], seed_claims: None
) -> None:
    def ids(query: str) -> list[int]:
        response = client.get(f"/claims?{query}", headers=biller)
        assert response.status_code == 200, response.text
        return [c["id"] for c in response.json()["items"]]

    assert ids("") == [4, 3, 2, 1]
    assert ids("status=DENIED") == [3]
    assert ids("payer_id=2") == [4]
    assert ids("patient_id=1&sort=billed_amount") == [1, 2, 3]
    assert ids("patient_id=1&sort=-billed_amount") == [3, 2, 1]
    assert ids("date_from=2026-08-05") == [4]
    assert ids("date_to=2026-08-05&sort=service_date") == [3, 2, 1]
    assert ids("search=brown") == [4]
    assert ids("search=CLM-0002") == [2]
    assert ids("search=clm-0002") == [2]
    assert ids("search=%25") == []
    page = client.get("/claims?size=2&page=2", headers=biller).json()
    assert page["total"] == 4
    assert [c["id"] for c in page["items"]] == [2, 1]
    assert client.get("/claims?sort=password", headers=biller).status_code == 422
    assert client.get("/claims?status=NOPE", headers=biller).status_code == 422


def test_claims_require_auth(client: TestClient) -> None:
    assert client.get("/claims").status_code == 401
    assert client.post("/claims", json=CLAIM).status_code == 401


def test_dashboard_summary(client: TestClient, biller: dict[str, str], seed_claims: None) -> None:
    body = client.get("/dashboard/summary", headers=biller).json()
    assert body == {
        "total_claims": 4,
        "by_status": {"SUBMITTED": 1, "PAID": 1, "DENIED": 1, "RESUBMITTED": 1},
        "pending_claims": 2,
        "total_billed": "1000.00",
        "total_collected": "150.00",
        "pending_amount": "500.00",
        "denial_rate": 25.0,
        "collection_rate": 15.0,
    }


def test_dashboard_summary_empty(client: TestClient, biller: dict[str, str]) -> None:
    body = client.get("/dashboard/summary", headers=biller).json()
    assert body["total_claims"] == 0
    assert body["denial_rate"] == body["collection_rate"] == 0.0
    assert body["total_billed"] == "0.00"


def test_dashboard_payers_includes_payer_without_claims(
    client: TestClient, biller: dict[str, str], admin: dict[str, str], seed_claims: None
) -> None:
    client.post("/payers", json={"payer_name": "Cigna", "payer_code": "CIG"}, headers=admin)
    rows = client.get("/dashboard/payers", headers=biller).json()
    assert rows[0] == {
        "payer_id": 1,
        "payer_name": "Medicare",
        "claims": 3,
        "denied": 1,
        "billed": "600.00",
        "collected": "150.00",
        "denial_rate": 33.3,
    }
    assert rows[1]["claims"] == 1 and rows[1]["denied"] == 0
    assert rows[2] == {
        "payer_id": 3,
        "payer_name": "Cigna",
        "claims": 0,
        "denied": 0,
        "billed": "0.00",
        "collected": "0.00",
        "denial_rate": 0.0,
    }


def test_dashboard_denial_reasons(
    client: TestClient, biller: dict[str, str], seed_claims: None
) -> None:
    assert client.get("/dashboard/denial-reasons", headers=biller).json() == [
        {"denial_reason": "Coding error", "count": 1}
    ]
    assert client.get("/dashboard/summary").status_code == 401
