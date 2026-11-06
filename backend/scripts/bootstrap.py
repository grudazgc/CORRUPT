#!/usr/bin/env python3
"""End-to-end deployment and smoke test against a Solana cluster.

Bootstraps the CORRUPT mint (mint authority = config PDA), initializes the
program, seeds the reward pool, and drives one report through
submit -> verify -> reward. Prints a summary and exits non-zero on failure.

Usage:
    python scripts/bootstrap.py --rpc http://127.0.0.1:8899
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solders.instruction import AccountMeta, Instruction  # noqa: E402
from solders.keypair import Keypair  # noqa: E402
from solders.message import Message  # noqa: E402
from solders.pubkey import Pubkey  # noqa: E402
from solders.system_program import CreateAccountParams, create_account  # noqa: E402
from solders.transaction import VersionedTransaction  # noqa: E402

from app.solana import SolanaClient, instructions  # noqa: E402
from app.solana.client import deserialize_config, deserialize_report  # noqa: E402
from app.solana.instructions import (  # noqa: E402
    TOKEN_PROGRAM_ID,
    associated_token_address,
    build_initialize,
)

DECIMALS = 6
ONE_TOKEN = 10**DECIMALS
MINT_SPACE = 82
TOKEN_ACCOUNT_SPACE = 165
MINT_RENT = 1_461_600
TOKEN_ACCOUNT_RENT = 2_039_280
RENT_SYSVAR = Pubkey.from_string("SysvarRent111111111111111111111111111111111")


def send(client: SolanaClient, ixs: list[Instruction], payer: Keypair, signers: list[Keypair]):
    message = Message.new_with_blockhash(ixs, payer.pubkey(), client.latest_blockhash())
    transaction = VersionedTransaction(message, signers)
    signature = client.send_transaction(transaction)
    if not client.confirm_signature(signature):
        raise SystemExit(f"transaction {signature} was not confirmed")
    tx = client.get_transaction(signature) or {}
    err = (tx.get("meta") or {}).get("err")
    if err is not None:
        raise SystemExit(f"transaction {signature} failed: {err}")
    return signature


def spl_create_mint(payer: Keypair, mint: Keypair, authority: Pubkey, decimals: int):
    create = create_account(
        CreateAccountParams(
            from_pubkey=payer.pubkey(),
            to_pubkey=mint.pubkey(),
            lamports=MINT_RENT,
            space=MINT_SPACE,
            owner=TOKEN_PROGRAM_ID,
        )
    )
    # SPL Token InitializeMint2 (20): decimals || mint_authority || freeze(None)
    data = bytes([20, decimals]) + bytes(authority) + bytes([0])
    initialize = Instruction(
        program_id=TOKEN_PROGRAM_ID,
        data=data,
        accounts=[AccountMeta(pubkey=mint.pubkey(), is_signer=False, is_writable=True)],
    )
    return [create, initialize]


def spl_create_token_account(payer: Keypair, account: Keypair, mint: Pubkey, owner: Pubkey):
    create = create_account(
        CreateAccountParams(
            from_pubkey=payer.pubkey(),
            to_pubkey=account.pubkey(),
            lamports=TOKEN_ACCOUNT_RENT,
            space=TOKEN_ACCOUNT_SPACE,
            owner=TOKEN_PROGRAM_ID,
        )
    )
    # SPL Token InitializeAccount3 (18): owner pubkey, no rent sysvar needed.
    data = bytes([18]) + bytes(owner)
    initialize = Instruction(
        program_id=TOKEN_PROGRAM_ID,
        data=data,
        accounts=[
            AccountMeta(pubkey=account.pubkey(), is_signer=False, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
        ],
    )
    return [create, initialize]


def spl_transfer_checked(
    source: Pubkey, mint: Pubkey, destination: Pubkey, owner: Pubkey, amount: int, decimals: int
) -> Instruction:
    # SPL Token TransferChecked (12): amount || decimals
    data = bytes([12]) + amount.to_bytes(8, "little") + bytes([decimals])
    return Instruction(
        program_id=TOKEN_PROGRAM_ID,
        data=data,
        accounts=[
            AccountMeta(pubkey=source, is_signer=False, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=destination, is_signer=False, is_writable=True),
            AccountMeta(pubkey=owner, is_signer=True, is_writable=False),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default="http://127.0.0.1:8899")
    parser.add_argument("--program-id", default=None)
    parser.add_argument("--keypair", default=str(Path.home() / ".config/solana/id.json"))
    parser.add_argument(
        "--verifier-keypair",
        default=str(Path(__file__).resolve().parents[1] / ".keys/verifier.json"),
    )
    parser.add_argument("--reward", type=int, default=25 * ONE_TOKEN)
    args = parser.parse_args()

    idl = json.loads((Path(__file__).resolve().parents[2] / "onchain/target/idl/corrupt_rewards.json").read_text())
    program_id = Pubkey.from_string(args.program_id or idl["address"])
    authority = Keypair.from_json(Path(args.keypair).read_text())

    # The verifier keypair is reused across runs so the backend can be pointed
    # at the same key with CORRUPT_VERIFIER_KEYPAIR.
    verifier_path = Path(args.verifier_keypair)
    if verifier_path.exists():
        verifier = Keypair.from_json(verifier_path.read_text())
    else:
        verifier = Keypair()
        verifier_path.parent.mkdir(parents=True, exist_ok=True)
        verifier_path.write_text(verifier.to_json())
        verifier_path.chmod(0o600)
    reporter = Keypair()

    with SolanaClient(args.rpc) as client:
        print(f"rpc          : {args.rpc}")
        print(f"program      : {program_id}")
        print(f"authority    : {authority.pubkey()}")

        for who in (authority, verifier, reporter):
            client.request_airdrop(who.pubkey(), 5 * 10**9)
        time.sleep(2)

        config_key = instructions.config_pda(program_id)[0]
        mint = Keypair()
        send(client, spl_create_mint(authority, mint, config_key, DECIMALS), authority, [authority, mint])
        print(f"mint         : {mint.pubkey()} (authority={config_key})")

        treasury = Keypair()
        send(
            client,
            spl_create_token_account(authority, treasury, mint.pubkey(), config_key),
            authority,
            [authority, treasury],
        )
        print(f"verifier     : {verifier.pubkey()} ({verifier_path})")
        print(f"treasury     : {treasury.pubkey()}")

        send(
            client,
            [
                build_initialize(
                    program_id=program_id,
                    authority=authority.pubkey(),
                    verifier=verifier.pubkey(),
                    treasury=treasury.pubkey(),
                    reward_mint=mint.pubkey(),
                    min_reward=ONE_TOKEN,
                    max_reward=1000 * ONE_TOKEN,
                    initial_supply=1_000_000 * ONE_TOKEN,
                )
            ],
            authority,
            [authority],
        )
        print(f"initialized  : authority ATA {associated_token_address(authority.pubkey(), mint.pubkey())}")

        pool_amount = 100_000 * ONE_TOKEN
        send(
            client,
            [
                spl_transfer_checked(
                    associated_token_address(authority.pubkey(), mint.pubkey()),
                    mint.pubkey(),
                    treasury.pubkey(),
                    authority.pubkey(),
                    pool_amount,
                    DECIMALS,
                ),
                instructions.build_fund_pool(
                    program_id=program_id,
                    funder=authority.pubkey(),
                    reward_mint=mint.pubkey(),
                    treasury=treasury.pubkey(),
                    amount=pool_amount,
                ),
            ],
            authority,
            [authority],
        )
        config = deserialize_config(client.get_account(config_key).data)
        print(f"pool funded  : budget={config.total_budget / 10**DECIMALS:.2f} CORRUPT")

        send(
            client,
            [
                instructions.build_submit_report(
                    program_id=program_id,
                    reporter=reporter.pubkey(),
                    content_hash=bytes(range(32)),
                    evidence_hash=bytes(range(32, 64)),
                    category=0,
                    report_id=0,
                )
            ],
            reporter,
            [reporter],
        )
        report_pda = instructions.report_pda(program_id, 0)[0]
        report = deserialize_report(client.get_account(report_pda).data)
        print(f"report 0     : status={report.status} hash={report.content_hash[:16]}…")

        send(
            client,
            [
                instructions.build_verify_report(
                    program_id=program_id,
                    verifier=verifier.pubkey(),
                    reporter=reporter.pubkey(),
                    report_id=0,
                    reward_mint=mint.pubkey(),
                    treasury=treasury.pubkey(),
                    reward_amount=args.reward,
                )
            ],
            verifier,
            [verifier],
        )
        report = deserialize_report(client.get_account(report_pda).data)
        config = deserialize_config(client.get_account(config_key).data)
        reporter_ata = associated_token_address(reporter.pubkey(), mint.pubkey())
        print(f"report 0     : status={report.status} reward={report.reward_amount / 10**DECIMALS} CORRUPT")
        print(f"distributed  : {config.total_distributed / 10**DECIMALS:.2f} CORRUPT")
        print(f"reporter ATA : {reporter_ata} exists={client.get_account(reporter_ata) is not None}")

        ok = (
            report.status == 1
            and report.reward_amount == args.reward
            and config.total_distributed == args.reward
        )
        print("SMOKE TEST   :", "PASS" if ok else "FAIL")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
