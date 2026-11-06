"""Report creation, privacy of public endpoints, and hashing determinism."""

from __future__ import annotations

from fastapi.testclient import TestClient
from solders.keypair import Keypair

from app.services.hashing import canonical_json, report_content_hash, sha256_hex

VALID_REPORT = {
    "title": "Inflated road maintenance contract",
    "summary": "The winning bid was 40% above the engineering estimate.",
    "description": (
        "The municipal tender for road resurfacing was awarded to a company "
        "owned by the deputy mayor's brother-in-law at a price far above the "
        "independent estimate."
    ),
    "category": 2,
    "jurisdiction": "PL-MZ",
    "entity_name": "City Roads Authority",
}


def _headers(client: TestClient) -> dict[str, str]:
    keypair = Keypair()
    wallet = str(keypair.pubkey())
    challenge = client.post("/api/auth/challenge", json={"wallet": wallet}).json()
    signature = str(keypair.sign_message(challenge["message"].encode()))
    token = client.post(
        "/api/auth/verify", json={"wallet": wallet, "signature": signature}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_hashing_is_deterministic_and_order_independent() -> None:
    first = report_content_hash(**VALID_REPORT, reporter_wallet="ABC")
    second = report_content_hash(**VALID_REPORT, reporter_wallet="ABC")
    assert first == second
    assert len(first) == 64

    reordered = {
        "entity_name": VALID_REPORT["entity_name"],
        "jurisdiction": VALID_REPORT["jurisdiction"],
        "category": VALID_REPORT["category"],
        "description": VALID_REPORT["description"],
        "summary": VALID_REPORT["summary"],
        "title": VALID_REPORT["title"],
    }
    assert canonical_json(reordered) == canonical_json(VALID_REPORT)


def test_hash_changes_when_reporter_changes() -> None:
    a = report_content_hash(**VALID_REPORT, reporter_wallet="AAA")
    b = report_content_hash(**VALID_REPORT, reporter_wallet="BBB")
    assert a != b


def test_sha256_hex_matches_reference_vector() -> None:
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_create_report_returns_hash_and_draft_status(client: TestClient) -> None:
    headers = _headers(client)
    response = client.post("/api/reports", json=VALID_REPORT, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert len(body["content_hash"]) == 64
    assert body["category_label"] == "procurement_fraud"
    assert body["on_chain_id"] is None


def test_duplicate_report_is_rejected(client: TestClient) -> None:
    headers = _headers(client)
    first = client.post("/api/reports", json=VALID_REPORT, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/reports", json=VALID_REPORT, headers=headers)
    assert second.status_code == 409


def test_reporter_cannot_read_another_reporters_report(client: TestClient) -> None:
    owner = _headers(client)
    report_id = client.post("/api/reports", json=VALID_REPORT, headers=owner).json()["id"]
    intruder = _headers(client)
    assert client.get(f"/api/reports/{report_id}", headers=intruder).status_code == 403


def test_public_endpoints_hide_report_content(client: TestClient) -> None:
    headers = _headers(client)
    report = client.post("/api/reports", json=VALID_REPORT, headers=headers).json()

    listing = client.get("/api/public/reports")
    assert listing.status_code == 200
    entry = next(item for item in listing.json() if item["id"] == report["id"])
    # Identifying fields must never appear in the public projection.
    for leaked in ("title", "summary", "description", "jurisdiction", "entity_name"):
        assert leaked not in entry
    assert entry["content_hash"] == report["content_hash"]

    detail = client.get(f"/api/public/reports/{report['id']}").json()
    assert "title" not in detail
    assert "description" not in detail


def test_public_stats_shape(client: TestClient) -> None:
    stats = client.get("/api/public/stats")
    assert stats.status_code == 200
    for key in (
        "total_reports",
        "pending",
        "verified",
        "rejected",
        "total_reward_paid",
        "unique_reporters",
    ):
        assert key in stats.json()


def test_cannot_anchor_without_evidence(client: TestClient) -> None:
    headers = _headers(client)
    report = client.post("/api/reports", json=VALID_REPORT, headers=headers).json()
    # Without a validator this fails on the evidence check, which is what we
    # assert here; the check happens before any RPC call.
    response = client.post(f"/api/reports/{report['id']}/prepare", headers=headers)
    assert response.status_code == 409
    assert "evidence" in response.json()["detail"]


def test_evidence_upload_hashes_content(client: TestClient) -> None:
    headers = _headers(client)
    report = client.post("/api/reports", json=VALID_REPORT, headers=headers).json()
    payload = b"invoice scan bytes"
    response = client.post(
        f"/api/reports/{report['id']}/evidence",
        headers=headers,
        files={"file": ("invoice.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["evidence_hash"] == sha256_hex(payload)
    assert response.json()["size"] == len(payload)


def test_evidence_rejects_unsupported_media_type(client: TestClient) -> None:
    headers = _headers(client)
    report = client.post("/api/reports", json=VALID_REPORT, headers=headers).json()
    response = client.post(
        f"/api/reports/{report['id']}/evidence",
        headers=headers,
        files={"file": ("payload.exe", b"MZ", "application/x-msdownload")},
    )
    assert response.status_code == 422


def test_validation_rejects_short_description(client: TestClient) -> None:
    headers = _headers(client)
    bad = dict(VALID_REPORT, description="too short")
    assert client.post("/api/reports", json=bad, headers=headers).status_code == 422
