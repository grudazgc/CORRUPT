# Architecture

## Components

```
                     wallet (Phantom / Solflare)
                              │
             signs messages   │   signs transactions
                              ▼
┌──────────────────────────────────────────────────────┐
│  frontend/  (Vite + React + TypeScript)              │
│  reporter UI · verifier console · operator console    │
└──────────────────────────┬───────────────────────────┘
                           │ HTTPS (JSON + multipart)
                           ▼
┌──────────────────────────────────────────────────────┐
│  backend/  (FastAPI)                                 │
│  · wallet auth (challenge → signature → JWT)         │
│  · off-chain report store and evidence custody       │
│  · builds unsigned transactions for the wallet       │
│  · holds the verifier and authority keypairs         │
│  · indexes on-chain events into a read model         │
└──────────────────────────┬───────────────────────────┘
                           │ JSON-RPC
                           ▼
┌──────────────────────────────────────────────────────┐
│  onchain/  (Anchor program on Solana)                │
│  Config · Report · ReporterStats accounts            │
│  submit_report · verify_report · reject_report       │
│  fund_pool · update_config · set_paused              │
└──────────────────────────────────────────────────────┘
```

## Trust boundaries

The design keeps as little trust in the backend as possible.

| Asset | Who can move or change it | Enforced by |
| --- | --- | --- |
| Report commitment | Nobody, once anchored | The on-chain account is immutable apart from status and reward |
| Reward pool | Only `verify_report`, signed by the verifier | `require_keys_eq!(config.verifier, ...)` in the program |
| Reward size | Verifier, within `min_reward`/`max_reward` and remaining budget | Program bounds checks |
| Report text and evidence | The reporter and the API operator | Off-chain custody; only hashes are published |
| Pausing | Authority key | `set_paused` checks `config.authority` |
| Reporter identity | The reporter | Off-chain wallet signature (SIWS-style challenge) |

Consequences worth stating plainly:

- The backend **cannot mint**. `verify_report` only transfers from the treasury,
  so the CORRUPT supply is fixed at bootstrap and every payout is pre-funded.
- The backend **cannot forge a report**. It can only build a transaction that the
  reporter must sign, and the content hash it commits to is what the reporter
  saw.
- A compromised **verifier key** can drain the pool up to `total_budget` by
  approving reports, but cannot mint, change reward bounds, or rotate roles.
- A compromised **authority key** can fund, pause, and rotate the verifier, but
  still cannot mint beyond the initial supply or alter past reports.

## Data flow: submit → verify → pay

```
reporter            backend                        solana
   │  POST /api/reports      │                          │
   │────────────────────────►│ store draft + content hash│
   │  POST …/evidence        │                          │
   │────────────────────────►│ hash evidence, store blob │
   │  POST …/prepare         │                          │
   │────────────────────────►│ build unsigned submit tx  │
   │◄────────────────────────│ base64 VersionedTransaction
   │  sign locally           │                          │
   │  broadcast ─────────────┼─────────────────────────►│ submit_report
   │  POST …/confirm         │                          │
   │────────────────────────►│ verify + index events     │
   │                         │                          │
   │                    verifier                        │
   │                         │ POST /verifier/…/verify   │
   │                         │ sign with verifier key ──►│ verify_report
   │                         │                          │ treasury → reporter
   │◄────────────────────────┼──────────────────────────│ CORRUPT tokens
```

Anchoring is deliberately split into `prepare` and `confirm`: the backend builds
the transaction, the wallet signs it, and the backend only records the result.
The reporter's private key never reaches the server.

## Off-chain data model

SQLAlchemy tables (SQLite by default, any SQLAlchemy URL in production):

- **Wallet** — an address and its role (`reporter`, `verifier`, `admin`).
- **AuthChallenge** — a single-use nonce with an expiry, consumed on verify.
- **Report** — the off-chain body, its `content_hash`, the evidence metadata
  (path, media type, size, hash), the status mirror of the on-chain account, and
  the transaction signatures. Evidence bytes are written to `data/evidence/`
  under a content-addressed name and are encrypted at rest with Fernet when
  `CORRUPT_EVIDENCE_ENCRYPTION_KEY` is set.
- **ChainEvent** — program events decoded from transaction logs, used to render
  the transparency ledger.
- **AuditEvent** — every privileged action, with actor and details.
- **Paused** — a singleton row mirroring the pause flag for cheap API reads; the
  on-chain flag is authoritative.

The database is a **read model plus private content store**, never a source of
truth for money. Balances, budget, and report status on-chain win any conflict;
`/api/public/config` reads the `Config` account straight from the chain for
exactly this reason.

## Privacy

- Report bodies, entity names, and evidence are never written on-chain.
- Evidence is stored under an operator-controlled directory and can be encrypted
  at rest by setting `CORRUPT_EVIDENCE_ENCRYPTION_KEY`.
- The public projection (`/api/public/reports`) exposes only the category,
  commitments, status, reward, and timestamps. Titles, summaries, descriptions,
  and entity names are excluded.
- Wallets are pseudonymous; the platform does not collect names or emails.

## Known limitations

- Roles are enforced with shared-secret API keys (`X-Admin-Key`,
  `X-Verifier-Key`). Put these behind your own SSO or IAM before production.
- The event indexer is pull-based (it indexes events from transactions the
  backend itself submits). A production deployment should run a dedicated
  listener so out-of-band transactions are also captured.
- Evidence is held by the operator; a production deployment should add client-side
  encryption so the operator cannot read evidence at all.
