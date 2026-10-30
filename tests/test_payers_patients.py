from fastapi.testclient import TestClient

PAYER = {"payer_name": "ICICI Lombard", "payer_code": "icici", "contact_phone": "+91-22-61961100"}
PATIENT = {
    "full_name": "Leela Deepak",
    "date_of_birth": "1999-05-12",
    "gender": "MALE",
    "phone": "+1-555-0211",
    "insurance_member_id": "ICL100567",
}


def test_payers_read_for_biller_write_for_admin_only(
    client: TestClient, biller: dict[str, str], admin: dict[str, str]
) -> None:
    assert len(client.get("/payers", headers=biller).json()) == 2
    assert client.post("/payers", json=PAYER, headers=biller).status_code == 403
    created = client.post("/payers", json=PAYER, headers=admin)
    assert created.status_code == 201
    assert created.json()["payer_code"] == "ICICI"


def test_payer_duplicate_and_validation(client: TestClient, admin: dict[str, str]) -> None:
    dup = client.post("/payers", json={**PAYER, "payer_code": "MCR"}, headers=admin)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "PAYER_ALREADY_EXISTS"
    bad = client.post("/payers", json={**PAYER, "payer_code": "bad code!"}, headers=admin)
    assert bad.status_code == 422


def test_payer_update_and_delete(
    client: TestClient, admin: dict[str, str], seed_claims: None
) -> None:
    updated = client.put(
        "/payers/2", json={"payer_name": "Aetna Inc", "payer_code": "AET"}, headers=admin
    )
    assert updated.status_code == 200
    assert updated.json()["payer_name"] == "Aetna Inc"
    clash = client.put(
        "/payers/2", json={"payer_name": "Medicare", "payer_code": "AET"}, headers=admin
    )
    assert clash.status_code == 409
    assert (
        client.put("/payers/99", json=PAYER, headers=admin).json()["error"]["code"]
        == "PAYER_NOT_FOUND"
    )

    blocked = client.delete("/payers/1", headers=admin)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "PAYER_HAS_CLAIMS"

    new_id = client.post("/payers", json=PAYER, headers=admin).json()["id"]
    assert client.delete(f"/payers/{new_id}", headers=admin).status_code == 204
    assert client.delete(f"/payers/{new_id}", headers=admin).status_code == 404


def test_patient_create_validation_and_get(client: TestClient, biller: dict[str, str]) -> None:
    created = client.post("/patients", json=PATIENT, headers=biller)
    assert created.status_code == 201
    patient_id = created.json()["id"]
    assert created.json()["claim_count"] == 0

    future = client.post(
        "/patients", json={**PATIENT, "date_of_birth": "2999-01-01"}, headers=biller
    )
    assert future.status_code == 422
    short = client.post("/patients", json={**PATIENT, "full_name": "A"}, headers=biller)
    assert short.status_code == 422
    gender = client.post("/patients", json={**PATIENT, "gender": "X"}, headers=biller)
    assert gender.status_code == 422

    assert client.get(f"/patients/{patient_id}", headers=biller).status_code == 200
    missing = client.get("/patients/999", headers=biller)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PATIENT_NOT_FOUND"


def test_patient_list_search_and_claim_count(
    client: TestClient, biller: dict[str, str], seed_claims: None
) -> None:
    everyone = client.get("/patients", headers=biller).json()
    counts = {p["full_name"]: p["claim_count"] for p in everyone["items"]}
    assert counts == {"Emily Johnson": 3, "Michael Brown": 1}
    by_name = client.get("/patients?search=emily", headers=biller).json()
    assert by_name["total"] == 1
    by_member = client.get("/patients?search=AET55", headers=biller).json()
    assert by_member["items"][0]["full_name"] == "Emily Johnson"
    assert client.get("/patients?search=%25", headers=biller).json()["total"] == 0
    assert client.get("/patients?size=101", headers=biller).status_code == 422


def test_patient_detail_summary_update_delete(
    client: TestClient, biller: dict[str, str], admin: dict[str, str], seed_claims: None
) -> None:
    detail = client.get("/patients/1", headers=biller).json()
    assert detail["claims_summary"] == {"total": 3, "paid": 1, "denied": 1, "pending": 1}

    updated = client.put("/patients/1", json={**PATIENT, "gender": None}, headers=biller)
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Leela Deepak"
    assert updated.json()["claim_count"] == 3
    assert client.put("/patients/99", json=PATIENT, headers=biller).status_code == 404

    assert client.delete("/patients/1", headers=biller).status_code == 403
    assert client.delete("/patients/1", headers=admin).status_code == 204
    assert client.get("/patients/1", headers=biller).status_code == 404
    assert client.get("/claims", headers=biller).json()["total"] == 1
    assert client.delete("/patients/1", headers=admin).status_code == 404
