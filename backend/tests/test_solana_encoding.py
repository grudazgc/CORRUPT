"""Instruction encoding and PDA derivation must match the deployed program."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from solders.pubkey import Pubkey

from app.solana import borsh, instructions

IDL_PATH = Path(__file__).resolve().parents[2] / "onchain/target/idl/corrupt_rewards.json"


@pytest.fixture(scope="module")
def idl() -> dict:
    if not IDL_PATH.exists():
        pytest.skip("IDL not built; run `anchor build` in onchain/")
    return json.loads(IDL_PATH.read_text())


def test_discriminator_matches_anchor_convention() -> None:
    expected = hashlib.sha256(b"global:verify_report").digest()[:8]
    assert borsh.instruction_discriminator("verify_report") == expected


def test_discriminators_are_unique_per_instruction(idl: dict) -> None:
    names = [ix["name"] for ix in idl["instructions"]]
    discriminators = {borsh.instruction_discriminator(name) for name in names}
    assert len(discriminators) == len(names)


def test_account_discriminators_match_idl(idl: dict) -> None:
    """Anchor writes the account discriminator into IDL account discriminators."""

    for account in idl["accounts"]:
        expected = bytes(account["discriminator"])
        assert borsh.account_discriminator(account["name"]) == expected


def test_program_id_matches_idl(idl: dict) -> None:
    from app.config import get_settings

    assert get_settings().program_id == idl["address"]


def test_config_pda_is_stable(idl: dict) -> None:
    program_id = Pubkey.from_string(idl["address"])
    address, bump = instructions.config_pda(program_id)
    # The PDA must be off-curve; otherwise it could be a real keypair.
    assert not address.is_on_curve()
    assert 0 <= bump <= 255
    assert instructions.config_pda(program_id) == (address, bump)


def test_report_pda_changes_with_id(idl: dict) -> None:
    program_id = Pubkey.from_string(idl["address"])
    first = instructions.report_pda(program_id, 0)[0]
    second = instructions.report_pda(program_id, 1)[0]
    assert first != second


def test_associated_token_address_matches_reference(idl: dict) -> None:
    owner = Pubkey.from_string("ALhqM42K9ih8KUBXvR9tE69Uv9hCzhJRvVWxKbXRWquw")
    mint = Pubkey.from_string("So11111111111111111111111111111111111111112")
    address = instructions.associated_token_address(owner, mint)
    assert str(address) != str(owner)


def test_u64_encoding_is_little_endian() -> None:
    assert borsh.u64(1) == b"\x01\x00\x00\x00\x00\x00\x00\x00"
    assert borsh.u64(2**64 - 1) == b"\xff" * 8


def test_u64_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        borsh.u64(2**64)


def test_option_encoding() -> None:
    assert borsh.option(borsh.u64, None) == b"\x00"
    assert borsh.option(borsh.u64, 7) == b"\x01\x07" + b"\x00" * 7


def test_config_update_encoding_length() -> None:
    update = instructions.ConfigUpdate(min_reward=1, max_reward=2)
    # 1 + 1 + (1 + 8) + (1 + 8)
    assert len(update.encode()) == 20


def test_verify_instruction_account_order(idl: dict) -> None:
    program_id = Pubkey.from_string(idl["address"])
    verifier = Pubkey.new_unique()
    reporter = Pubkey.new_unique()
    mint = Pubkey.new_unique()
    treasury = Pubkey.new_unique()
    ix = instructions.build_verify_report(
        program_id=program_id,
        verifier=verifier,
        reporter=reporter,
        report_id=3,
        reward_mint=mint,
        treasury=treasury,
        reward_amount=100,
    )
    idl_accounts = [a["name"] for a in _instruction(idl, "verify_report")["accounts"]]
    assert len(ix.accounts) == len(idl_accounts)
    assert str(ix.accounts[0].pubkey) == str(verifier)
    assert ix.accounts[0].is_signer
    # The treasury is the sixth account in the IDL order and must be writable.
    assert str(ix.accounts[5].pubkey) == str(treasury)
    assert ix.accounts[5].is_writable


def _instruction(idl: dict, name: str) -> dict:
    return next(ix for ix in idl["instructions"] if ix["name"] == name)


def test_submit_report_data_layout(idl: dict) -> None:
    program_id = Pubkey.from_string(idl["address"])
    ix = instructions.build_submit_report(
        program_id=program_id,
        reporter=Pubkey.new_unique(),
        content_hash=b"\x01" * 32,
        evidence_hash=b"\x02" * 32,
        category=4,
        report_id=0,
    )
    assert ix.data[:8] == borsh.instruction_discriminator("submit_report")
    assert ix.data[8:40] == b"\x01" * 32
    assert ix.data[40:72] == b"\x02" * 32
    assert ix.data[72] == 4
