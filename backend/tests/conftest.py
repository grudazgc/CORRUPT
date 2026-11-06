"""Shared pytest fixtures.

Environment variables are set before the application is imported so the test
run never touches a developer's real database or evidence directory.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="corrupt-tests-"))
os.environ["CORRUPT_DATABASE_URL"] = f"sqlite+pysqlite:///{_TMP}/test.db"
os.environ["CORRUPT_DATA_DIR"] = str(_TMP / "data")
os.environ["CORRUPT_ADMIN_API_KEY"] = "test-admin-key"
os.environ["CORRUPT_VERIFIER_API_KEY"] = "test-verifier-key"
os.environ["CORRUPT_JWT_SECRET"] = "test-secret"
os.environ["CORRUPT_SOLANA_RPC_URL"] = os.environ.get(
    "CORRUPT_TEST_RPC", "http://127.0.0.1:8899"
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from solders.keypair import Keypair  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def wallet_keypair() -> Keypair:
    return Keypair()


@pytest.fixture
def auth_headers(client: TestClient, wallet_keypair: Keypair) -> dict[str, str]:
    wallet = str(wallet_keypair.pubkey())
    challenge = client.post("/api/auth/challenge", json={"wallet": wallet}).json()
    signature = str(wallet_keypair.sign_message(challenge["message"].encode()))
    token = client.post(
        "/api/auth/verify", json={"wallet": wallet, "signature": signature}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def rpc_url() -> str:
    return os.environ["CORRUPT_SOLANA_RPC_URL"]


@pytest.fixture(scope="session")
def validator_available(rpc_url: str) -> bool:
    try:
        response = httpx.post(
            rpc_url, json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"}, timeout=3.0
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


requires_validator = pytest.mark.skipif(
    "not config.getoption('--run-validator-tests')",
    reason="pass --run-validator-tests to exercise the live local validator",
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-validator-tests",
        action="store_true",
        default=False,
        help="Run tests that need a local solana-test-validator with the program deployed",
    )
