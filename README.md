# CORRUPT — anti-corruption reporting with on-chain rewards

A full-stack Solana application for reporting corruption. Reporters anchor a
SHA-256 commitment of their report on-chain, an independent verifier reviews it,
and verified reporters receive **CORRUPT** SPL tokens from a pre-funded reward
pool. Report bodies and evidence stay off-chain and private; only commitments
and payouts are written to the chain.

```
onchain/   Anchor program (Rust) — the source of truth for rewards
backend/   FastAPI service — auth, evidence custody, transaction building, indexing
frontend/  Vite + React + TypeScript — reporter, verifier, and operator UIs
docs/      Architecture, program reference, API reference, operations
```

## Quickstart (localnet)

Prerequisites: Rust + Anchor, the Solana CLI, Python 3.11+, and Node 20+.

```bash
# 1. Start a local validator and deploy the program
solana-test-validator --reset --ledger /tmp/test-ledger &
cd onchain && anchor build
solana program deploy --url http://127.0.0.1:8899 \
  --program-id keys/corrupt_rewards-keypair.json target/deploy/corrupt_rewards.so

# 2. Create the token, config account, treasury, and seed the reward pool
cd ../backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python scripts/bootstrap.py --rpc http://127.0.0.1:8899

# 3. Run the API
export CORRUPT_VERIFIER_KEYPAIR="$PWD/.keys/verifier.json"
export CORRUPT_AUTHORITY_KEYPAIR="$HOME/.config/solana/id.json"
.venv/bin/uvicorn app.main:app --reload

# 4. Run the web app (proxies /api to the backend)
cd ../frontend && npm install && npm run dev
```

Open <http://localhost:3000>, connect Phantom or Solflare (pointed at localnet),
and submit a report.

## How a report earns a reward

1. **Draft** — the reporter submits the report text to the API. It is stored
   off-chain; the API computes a canonical SHA-256 content hash.
2. **Anchor** — the API builds an unsigned `submit_report` transaction. The
   reporter's wallet signs it, so the API never holds a private key. The
   commitment is now immutable and publicly provable.
3. **Review** — a verifier inspects the report and its evidence.
4. **Payout** — verification and payment happen in one transaction:
   `verify_report` transfers the reward from the treasury to the reporter's
   associated token account. Nothing is minted, so the supply is fixed and every
   reward is backed by tokens that were funded in advance.

Rejections are recorded on-chain too, so the full decision history is auditable.

## Documentation

| Document | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Components, trust boundaries, data flow |
| [docs/onchain.md](docs/onchain.md) | Program accounts, instructions, errors, events |
| [docs/api.md](docs/api.md) | REST endpoints and authentication |
| [docs/operations.md](docs/operations.md) | Bootstrap, key management, running, testing |
| [docs/tokenomics.md](docs/tokenomics.md) | Token model, reward policy, legal guardrails |

## Tests

```bash
cd backend
.venv/bin/python -m pytest                       # unit + API tests (no validator needed)
.venv/bin/python -m pytest --run-validator-tests # adds the live localnet end-to-end tests
cd ../frontend && npm run build                  # type-check and production build
```

## Security model, in one paragraph

The backend is a convenience layer, not a trusted authority. It cannot mint
tokens, cannot move funds without the verifier key, and cannot alter an anchored
report. The reward pool can only be spent by the on-chain `verify_report`
instruction, which requires the configured verifier's signature. Reporters
authenticate with an off-chain wallet signature, so signing in costs nothing and
authorises no transfer.

> This project is a reference implementation. Before handling real reports,
> review the threat model in [docs/architecture.md](docs/architecture.md) and
> replace the shared-secret API keys with your own access control.

## Platforma przeciwdziałania korupcji (PL)

Aplikacja pozwala anonimowo zgłaszać korupcję: treść raportu i dowody pozostają
poza łańcuchem, a na Solanie zapisywany jest wyłącznie skrót SHA-256 raportu.
Po weryfikacji przez niezależnego weryfikatora zgłaszający otrzymuje tokeny
**CORRUPT** z wcześniej zasilonej puli nagród. Wypłata odbywa się w tej samej
transakcji, która oznacza raport jako zweryfikowany, dzięki czemu cała historia
decyzji jest publicznie audytowalna.
