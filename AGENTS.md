# AGENTS.md — corrupt-rewards

Repository-specific notes for agents and contributors.

## Layout

- `onchain/` — Anchor program `corrupt-rewards` (Rust). The source of truth for
  rewards, report status, and budget.
- `backend/` — FastAPI service: wallet auth, off-chain report/evidence store,
  transaction building, event indexing.
- `frontend/` — Vite + React + TypeScript SPA (reporter, verifier, admin views).
- `docs/` — architecture, on-chain reference, API reference, operations.

## Commands

```bash
# On-chain
cd onchain && anchor build
solana program deploy --url http://127.0.0.1:8899 \
  --program-id keys/corrupt_rewards-keypair.json target/deploy/corrupt_rewards.so

# Backend
cd backend
.venv/bin/python -m pytest                       # hermetic; no validator needed
.venv/bin/python -m pytest --run-validator-tests # requires localnet + bootstrap
.venv/bin/python scripts/bootstrap.py --rpc http://127.0.0.1:8899

# Frontend
cd frontend && npm run build     # tsc -b && vite build (this is the type-check)
```

## Conventions

- Report **content and evidence stay off-chain**; only SHA-256 commitments go
  on-chain. Never add a code path that writes report text on-chain.
- Rewards are **transferred from the treasury, never minted**. The mint authority
  is the config PDA and is only used once, at `initialize`. Do not reintroduce
  `mint_to` in `verify_report`.
- **Authority** (fund, pause, rotate) and **verifier** (resolve reports) are
  separate roles and separate keypairs. Admin endpoints sign with the authority
  key; verifier endpoints sign with the verifier key.
- Amounts in the API are CORRUPT base units (6 decimals).
- Rust on-chain code: keep the `require!`/`require_keys_eq!` guard order — paused
  check first, then role check, then status, then bounds.
- The backend never holds a reporter's private key: anchoring is
  `prepare` (build unsigned tx) → wallet signs → `confirm`.

## Gotchas

- `solders` 0.29: use `signature.verify(pubkey, message)` (there is no
  `Pubkey.verify_signature`), `VersionedTransaction.from_bytes` (no
  `deserialize`), `VersionedTransaction(message, [keypair])` (no `.sign`), and
  `Message.recent_blockhash` is read-only.
- The frontend must not depend on `@solana/wallet-adapter-wallets`; it pulls in
  React Native and React 19 types that break `tsc`. Use the individual
  `-phantom` / `-solflare` adapters, and keep the `overrides` pinning
  `@types/react` to 18 in `frontend/package.json`.
- `bootstrap.py` reuses `backend/.keys/verifier.json` across runs so a running
  backend stays valid. Delete it only if you intend to re-initialize.
- Port 8000 may be occupied in some sandboxes; pass `--port` and set
  `VITE_API_PROXY` accordingly.
- The sandbox environment can reset between sessions: the Solana toolchain,
  `/tmp/test-ledger`, and `~/.config/solana/id.json` are wiped, while the repo
  (including `onchain/target/deploy/corrupt_rewards.so`) survives. Reinstall with
  `sh /tmp/install-toolchain.sh` (Agave stable + rustup + anchor 0.31.1), recreate
  the authority with `solana-keygen new`, then restart the validator, redeploy,
  and re-run `bootstrap.py`. The verifier keypair in `backend/.keys/` survives, so
  the backend keeps working.
