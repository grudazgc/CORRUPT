"""PDA derivation and instruction building for the corrupt_rewards program.

The layout mirrors ``onchain/programs/corrupt-rewards``. Keeping the builder
hand-written (instead of depending on the Anchor Python client) makes the
transaction the API signs explicit and easy to audit.
"""

from __future__ import annotations

from dataclasses import dataclass

from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey

from app.solana import borsh

CONFIG_SEED = b"config"
REPORT_SEED = b"report"
REPORTER_STATS_SEED = b"reporter"

TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")


def config_pda(program_id: Pubkey) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address([CONFIG_SEED], program_id)


def report_pda(program_id: Pubkey, report_id: int) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address([REPORT_SEED, report_id.to_bytes(8, "little")], program_id)


def reporter_stats_pda(program_id: Pubkey, reporter: Pubkey) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address([REPORTER_STATS_SEED, bytes(reporter)], program_id)


def associated_token_address(owner: Pubkey, mint: Pubkey) -> Pubkey:
    return Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN_PROGRAM_ID), bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]


@dataclass(frozen=True)
class ConfigUpdate:
    """Mirrors the on-chain ``ConfigUpdate`` argument."""

    verifier: Pubkey | None = None
    treasury: Pubkey | None = None
    min_reward: int | None = None
    max_reward: int | None = None

    def encode(self) -> bytes:
        return borsh.concat(
            [
                borsh.option(bytes, self.verifier),
                borsh.option(bytes, self.treasury),
                borsh.option(borsh.u64, self.min_reward),
                borsh.option(borsh.u64, self.max_reward),
            ]
        )


def _meta(pubkey: Pubkey, *, signer: bool = False, writable: bool = False) -> AccountMeta:
    return AccountMeta(pubkey=pubkey, is_signer=signer, is_writable=writable)


def build_initialize(
    program_id: Pubkey,
    authority: Pubkey,
    verifier: Pubkey,
    treasury: Pubkey,
    reward_mint: Pubkey,
    min_reward: int,
    max_reward: int,
    initial_supply: int,
) -> Instruction:
    data = borsh.concat(
        [
            borsh.instruction_discriminator("initialize"),
            borsh.u64(min_reward),
            borsh.u64(max_reward),
            borsh.u64(initial_supply),
        ]
    )
    accounts = [
        _meta(authority, signer=True, writable=True),
        _meta(config_pda(program_id)[0], writable=True),
        _meta(verifier),
        _meta(treasury, writable=True),
        _meta(reward_mint, writable=True),
        _meta(associated_token_address(authority, reward_mint), writable=True),
        _meta(TOKEN_PROGRAM_ID),
        _meta(ASSOCIATED_TOKEN_PROGRAM_ID),
        _meta(SYSTEM_PROGRAM_ID),
    ]
    return Instruction(program_id=program_id, data=data, accounts=accounts)


def build_submit_report(
    program_id: Pubkey,
    reporter: Pubkey,
    content_hash: bytes,
    evidence_hash: bytes,
    category: int,
    report_id: int,
) -> Instruction:
    data = borsh.concat(
        [
            borsh.instruction_discriminator("submit_report"),
            borsh.fixed_bytes(content_hash, 32),
            borsh.fixed_bytes(evidence_hash, 32),
            borsh.u8(category),
        ]
    )
    accounts = [
        _meta(reporter, signer=True, writable=True),
        _meta(config_pda(program_id)[0], writable=True),
        _meta(reporter_stats_pda(program_id, reporter)[0], writable=True),
        _meta(report_pda(program_id, report_id)[0], writable=True),
        _meta(SYSTEM_PROGRAM_ID),
    ]
    return Instruction(program_id=program_id, data=data, accounts=accounts)


def build_verify_report(
    program_id: Pubkey,
    verifier: Pubkey,
    reporter: Pubkey,
    report_id: int,
    reward_mint: Pubkey,
    treasury: Pubkey,
    reward_amount: int,
) -> Instruction:
    data = borsh.concat(
        [borsh.instruction_discriminator("verify_report"), borsh.u64(reward_amount)]
    )
    accounts = [
        _meta(verifier, signer=True, writable=True),
        _meta(config_pda(program_id)[0], writable=True),
        _meta(report_pda(program_id, report_id)[0], writable=True),
        _meta(reporter),
        _meta(reward_mint, writable=True),
        _meta(treasury, writable=True),
        _meta(associated_token_address(reporter, reward_mint), writable=True),
        _meta(TOKEN_PROGRAM_ID),
        _meta(ASSOCIATED_TOKEN_PROGRAM_ID),
        _meta(SYSTEM_PROGRAM_ID),
    ]
    return Instruction(program_id=program_id, data=data, accounts=accounts)


def build_reject_report(program_id: Pubkey, verifier: Pubkey, report_id: int) -> Instruction:
    data = borsh.instruction_discriminator("reject_report")
    accounts = [
        _meta(verifier, signer=True),
        _meta(config_pda(program_id)[0]),
        _meta(report_pda(program_id, report_id)[0], writable=True),
    ]
    return Instruction(program_id=program_id, data=data, accounts=accounts)


def build_fund_pool(
    program_id: Pubkey,
    funder: Pubkey,
    reward_mint: Pubkey,
    treasury: Pubkey,
    amount: int,
) -> Instruction:
    data = borsh.concat([borsh.instruction_discriminator("fund_pool"), borsh.u64(amount)])
    accounts = [
        _meta(funder, signer=True, writable=True),
        _meta(config_pda(program_id)[0], writable=True),
        _meta(reward_mint),
        _meta(associated_token_address(funder, reward_mint), writable=True),
        _meta(treasury, writable=True),
        _meta(TOKEN_PROGRAM_ID),
    ]
    return Instruction(program_id=program_id, data=data, accounts=accounts)


def build_update_config(
    program_id: Pubkey,
    authority: Pubkey,
    new_treasury: Pubkey,
    update: ConfigUpdate,
) -> Instruction:
    data = borsh.concat([borsh.instruction_discriminator("update_config"), update.encode()])
    accounts = [
        _meta(authority, signer=True),
        _meta(config_pda(program_id)[0], writable=True),
        _meta(new_treasury),
    ]
    return Instruction(program_id=program_id, data=data, accounts=accounts)


def build_set_paused(program_id: Pubkey, authority: Pubkey, paused: bool) -> Instruction:
    data = borsh.concat([borsh.instruction_discriminator("set_paused"), borsh.boolean(paused)])
    accounts = [
        _meta(authority, signer=True),
        _meta(config_pda(program_id)[0], writable=True),
    ]
    return Instruction(program_id=program_id, data=data, accounts=accounts)
