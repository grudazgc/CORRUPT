# Operations

## Prerequisites

- Rust and Anchor (`avm` recommended), Solana CLI 2.x
- Python 3.11+ (the reference environment uses 3.13)
- Node 20+

## 1. Build and deploy the program

```bash
cd onchain
anchor build
anchor keys list                      # confirm the program id matches Anchor.toml
solana-test-validator --reset --ledger /tmp/test-ledger &
solana program deploy --url http://127.0.0.1:8899 \
  --program-id keys/corrupt_rewards-keypair.json target/deploy/corrupt_rewards.so
```

For a hosted cluster, point `--url` at it and fund the deployer first. Update
`[programs.<cluster>]` in `Anchor.toml` and `CORRUPT_PROGRAM_ID` in the backend.

## 2. Bootstrap the platform

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python scripts/bootstrap.py --rpc http://127.0.0.1:8899
```

The script:

1. airdrops to the authority, verifier, and a throwaway reporter (localnet only);
2. creates the CORRUPT mint with the **config PDA** as mint authority;
3. creates the treasury token account, owned by the config PDA;
4. calls `initialize` with `min_reward = 1 CORRUPT`, `max_reward = 1000 CORRUPT`,
   and a 1,000,000 CORRUPT initial supply to the authority;
5. funds the pool with 100,000 CORRUPT;
6. drives one report through `submit → verify → reward` as a smoke test.

Useful flags: `--keypair` (authority), `--verifier-keypair`, `--reward`.

The verifier keypair is written to `backend/.keys/verifier.json` on first run and
**reused** on later runs, so re-running bootstrap does not invalidate a running
backend. Keep this file secret; it is the key that can pay out rewards.

## 3. Configure the backend

Settings use the `CORRUPT_` prefix and can live in `backend/.env`:

| Variable | Default | Notes |
| --- | --- | --- |
| `CORRUPT_DATABASE_URL` | `sqlite+pysqlite:///./corrupt.db` | Any SQLAlchemy URL |
| `CORRUPT_DATA_DIR` | `./data` | Evidence storage root |
| `CORRUPT_JWT_SECRET` | `change-me-in-production` | **Change this** |
| `CORRUPT_ADMIN_API_KEY` | `dev-admin-key` | **Change this** |
| `CORRUPT_VERIFIER_API_KEY` | `dev-verifier-key` | **Change this** |
| `CORRUPT_SOLANA_RPC_URL` | `http://127.0.0.1:8899` | Cluster endpoint |
| `CORRUPT_PROGRAM_ID` | `FBHxR4B5jMbE5W6vukMJNM1T88gt3VkZh9MbGN4Q464C` | Deployed program |
| `CORRUPT_VERIFIER_KEYPAIR` | unset | Path to the verifier keypair (required to pay out) |
| `CORRUPT_AUTHORITY_KEYPAIR` | unset | Path to the authority keypair (funding, pause) |
| `CORRUPT_EVIDENCE_ENCRYPTION_KEY` | unset | Optional evidence encryption at rest |
| `CORRUPT_MAX_EVIDENCE_BYTES` | `10485760` | 10 MiB upload cap |

```bash
export CORRUPT_VERIFIER_KEYPAIR="$PWD/.keys/verifier.json"
export CORRUPT_AUTHORITY_KEYPAIR="$HOME/.config/solana/id.json"
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 4. Run the frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000, proxies /api to :8000
npm run build          # production bundle in dist/
```

Environment:

| Variable | Default | Notes |
| --- | --- | --- |
| `VITE_RPC_URL` | dev: `http://127.0.0.1:8899`, prod: devnet | Wallet connection endpoint |
| `VITE_API_URL` | empty (same origin) | Absolute API base for split deployments |
| `VITE_API_PROXY` | `http://127.0.0.1:8000` | Dev proxy target |
| `VITE_ALLOWED_HOSTS` | empty | Comma-separated hostnames allowed to reach the dev server (needed behind a tunnel) |

## Key management

Two keypairs, deliberately separate:

- **Verifier** — signs `verify_report`. Can drain the pool up to the remaining
  budget but cannot mint, change bounds, or rotate roles.
- **Authority** — owns the config. Can fund, pause, and rotate the verifier, but
  cannot mint beyond the initial supply or alter past reports.

Store both outside the repository. `backend/.keys/` is for local development
only; in production use a KMS or a signer service, and mount the keys read-only.

The CORRUPT mint authority is the config PDA, so no private key can mint. Total
supply is fixed at bootstrap; verify it by reading the mint account.

## Testing

```bash
cd backend
.venv/bin/python -m pytest                       # unit + API tests, no validator
.venv/bin/python -m pytest --run-validator-tests # + live localnet end-to-end
cd ../frontend && npm run build
```

The end-to-end tests need a running validator with the program deployed, a
completed bootstrap, and `CORRUPT_VERIFIER_KEYPAIR` / `CORRUPT_AUTHORITY_KEYPAIR`
set. They cover: reading live config, the full submit → anchor → verify → payout
lifecycle with a real token-balance delta, rejection paying nothing, and pause
freezing submissions. They are skipped by default so `pytest` stays fast and
hermetic.

## Routine operations

**Fund the pool**

```bash
curl -X POST localhost:8000/api/admin/pool/fund \
  -H "X-Admin-Key: $CORRUPT_ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"amount": 1000000000}'    # 1000 CORRUPT
```

**Emergency pause** (freezes submissions and payouts)

```bash
curl -X POST localhost:8000/api/admin/pause \
  -H "X-Admin-Key: $CORRUPT_ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"paused": true}'
```

**Rotate the verifier** — call `update_config` on-chain with the new verifier,
then point `CORRUPT_VERIFIER_KEYPAIR` at the new key.

**Inspect state**

```bash
curl localhost:8000/api/public/config
curl localhost:8000/api/public/stats
curl localhost:8000/api/admin/audit -H "X-Admin-Key: $CORRUPT_ADMIN_API_KEY"
```

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `verifier keypair is not configured` | `CORRUPT_VERIFIER_KEYPAIR` unset or file missing |
| `Caller is not authorized` on pause/fund | `CORRUPT_AUTHORITY_KEYPAIR` is not the config authority |
| `program is not initialized` | Bootstrap has not run against this cluster |
| `program is paused` (409) | Resume with `/api/admin/pause` |
| `Reward exceeds the remaining pool budget` | Fund the pool before verifying |
| Anchor build complains about the program id | `anchor keys sync`, then rebuild |
