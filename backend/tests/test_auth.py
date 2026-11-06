"""Wallet authentication, JWT handling and API key enforcement."""

from __future__ import annotations

from fastapi.testclient import TestClient
from solders.keypair import Keypair


def test_challenge_then_verify_issues_token(client: TestClient) -> None:
    keypair = Keypair()
    wallet = str(keypair.pubkey())

    challenge = client.post("/api/auth/challenge", json={"wallet": wallet})
    assert challenge.status_code == 200
    body = challenge.json()
    assert wallet in body["message"]
    assert body["nonce"] in body["message"]

    signature = str(keypair.sign_message(body["message"].encode()))
    token_response = client.post(
        "/api/auth/verify", json={"wallet": wallet, "signature": signature}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]
    assert token_response.json()["wallet"] == wallet

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["wallet"] == wallet
    assert me.json()["role"] == "reporter"


def test_signature_from_a_different_wallet_is_rejected(client: TestClient) -> None:
    wallet = str(Keypair().pubkey())
    attacker = Keypair()
    challenge = client.post("/api/auth/challenge", json={"wallet": wallet}).json()
    forged = str(attacker.sign_message(challenge["message"].encode()))

    response = client.post("/api/auth/verify", json={"wallet": wallet, "signature": forged})
    assert response.status_code == 401


def test_replayed_challenge_is_rejected(client: TestClient) -> None:
    keypair = Keypair()
    wallet = str(keypair.pubkey())
    challenge = client.post("/api/auth/challenge", json={"wallet": wallet}).json()
    signature = str(keypair.sign_message(challenge["message"].encode()))

    first = client.post("/api/auth/verify", json={"wallet": wallet, "signature": signature})
    assert first.status_code == 200
    # The nonce was consumed, so a fresh challenge is required for a new token.
    second = client.post("/api/auth/verify", json={"wallet": wallet, "signature": signature})
    assert second.status_code == 401


def test_invalid_wallet_address_is_rejected(client: TestClient) -> None:
    # Long enough to pass the length check, but not valid base58.
    response = client.post("/api/auth/challenge", json={"wallet": "0OIl" + "x" * 40})
    assert response.status_code == 400


def test_protected_endpoint_requires_token(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/reports/mine").status_code == 401


def test_admin_endpoints_require_api_key(client: TestClient) -> None:
    assert client.post("/api/admin/pause", json={"paused": True}).status_code == 403
    assert client.get("/api/admin/audit").status_code == 403
    ok = client.get("/api/admin/audit", headers={"X-Admin-Key": "test-admin-key"})
    assert ok.status_code == 200


def test_verifier_endpoints_require_api_key(client: TestClient) -> None:
    assert client.get("/api/verifier/queue").status_code == 403
    ok = client.get("/api/verifier/queue", headers={"X-Verifier-Key": "test-verifier-key"})
    assert ok.status_code == 200
    assert ok.json() == []


def test_expired_or_tampered_token_is_rejected(client: TestClient) -> None:
    keypair = Keypair()
    wallet = str(keypair.pubkey())
    challenge = client.post("/api/auth/challenge", json={"wallet": wallet}).json()
    signature = str(keypair.sign_message(challenge["message"].encode()))
    token = client.post(
        "/api/auth/verify", json={"wallet": wallet, "signature": signature}
    ).json()["access_token"]

    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401
