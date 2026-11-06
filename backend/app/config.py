"""Application settings.

All values can be overridden through environment variables using the
``CORRUPT_`` prefix, for example ``CORRUPT_SOLANA_RPC_URL``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORRUPT_", env_file=".env", extra="ignore")

    app_name: str = "CORRUPT Anti-Corruption Platform"
    environment: str = "development"

    # Persistence
    database_url: str = "sqlite+pysqlite:///./corrupt.db"
    data_dir: Path = Path("./data")

    # Authentication
    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 60 * 60 * 12
    challenge_ttl_seconds: int = 300

    # Roles: comma-separated API keys for privileged endpoints.
    admin_api_key: str = "dev-admin-key"
    verifier_api_key: str = "dev-verifier-key"

    # Solana
    solana_rpc_url: str = "http://127.0.0.1:8899"
    solana_commitment: str = "confirmed"
    program_id: str = "FBHxR4B5jMbE5W6vukMJNM1T88gt3VkZh9MbGN4Q464C"
    idl_path: Path = Path("../onchain/target/idl/corrupt_rewards.json")

    # Operator keypairs. The authority owns the config account and signs
    # administrative actions (pause, pool funding, role rotation); the verifier
    # signs report decisions. They are deliberately separate so a compromised
    # verifier key cannot drain the pool or rotate roles.
    authority_keypair: Path | None = None
    verifier_keypair: Path | None = None

    # Evidence handling
    evidence_encryption_key: str = ""
    max_evidence_bytes: int = 10 * 1024 * 1024

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    return settings
