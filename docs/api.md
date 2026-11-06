# API reference

Base path: `/api`. Interactive schema: `/docs` (Swagger UI) and `/openapi.json`.

All request and response bodies are JSON unless noted. Amounts are CORRUPT
**base units** (6 decimals), so `5_000_000` is 5 CORRUPT.

## Authentication

### Reporter (wallet signature)

1. `POST /api/auth/challenge` with `{ "wallet": "<base58 pubkey>" }` returns a
   human-readable `message` and a single-use `nonce` valid for
   `CORRUPT_CHALLENGE_TTL_SECONDS` (default 300 s).
2. Sign the UTF-8 bytes of `message` with the wallet.
3. `POST /api/auth/verify` with `{ "wallet", "signature" }` (base58) returns
   `{ access_token, expires_in, wallet, role }`.

Send the token as `Authorization: Bearer <token>` on protected routes. The
signature is off-chain, so it costs nothing and authorises no transfer.

### Verifier and admin

Privileged endpoints use shared-secret headers instead of a JWT:

- `X-Verifier-Key: <CORRUPT_VERIFIER_API_KEY>`
- `X-Admin-Key: <CORRUPT_ADMIN_API_KEY>`

## Reporter endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/reports` | Bearer | Create an off-chain draft |
| `POST` | `/reports/{id}/evidence` | Bearer (owner) | Upload evidence (multipart `file`) |
| `POST` | `/reports/{id}/prepare` | Bearer (owner) | Build the unsigned `submit_report` transaction |
| `POST` | `/reports/{id}/confirm` | Bearer (owner) | Record the broadcast signature |
| `GET` | `/reports/mine` | Bearer | List the caller's reports |
| `GET` | `/reports/{id}` | Bearer (owner) | Full report with description, evidence, timeline |

`POST /reports` body:

```json
{
  "title": "Inflated road maintenance contract",
  "summary": "The winning bid was 40% above the engineering estimate",
  "description": "At least 40 characters describing what happened…",
  "category": 2,
  "jurisdiction": "PL-MZ",
  "entity_name": "City Roads Authority"
}
```

`POST /reports/{id}/prepare` returns:

```json
{
  "report_id": 1,
  "on_chain_id": 0,
  "transaction": "<base64 unsigned VersionedTransaction>",
  "content_hash": "…",
  "evidence_hash": "…",
  "program_id": "FBHxR4B5jMbE5W6vukMJNM1T88gt3VkZh9MbGN4Q464C"
}
```

Deserialize `transaction`, sign it with the reporter's wallet, broadcast it, then
call `confirm` with the signature. The backend verifies the transaction was
confirmed and indexed before flipping the report to `pending`.

Common status codes: `409` when a transition is not allowed (wrong status,
program paused), `403` when the caller does not own the report, `422` when the
evidence type or size is rejected.

## Verifier endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/verifier/queue` | Reports in `pending`, with description and evidence metadata |
| `POST` | `/verifier/reports/{id}/verify` | Pay a reward and mark verified |
| `POST` | `/verifier/reports/{id}/reject` | Mark rejected without paying |

Verify body: `{ "reward_amount": 5000000, "note": "verified" }`.
Reject body: `{ "note": "insufficient evidence" }`.

Verification signs and sends the on-chain `verify_report` transaction with the
configured verifier keypair; the response's `decision_signature` is that
transaction. A reward outside the on-chain bounds, or above the remaining budget,
returns `409`.

## Admin endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/admin/pool/fund` | Transfer CORRUPT into the treasury (`{ "amount": 1000000000 }`) |
| `POST` | `/admin/pause` | `{ "paused": true }` |
| `GET` | `/admin/audit` | Audited privileged actions (`?limit=`) |

Funding and pausing are signed with the **authority** keypair
(`CORRUPT_AUTHORITY_KEYPAIR`), which is separate from the verifier key.

## Public endpoints (no auth)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/public/stats` | Totals: reports, pending, verified, rejected, paid, reporters |
| `GET` | `/public/reports` | Privacy-preserving projection (`?limit=&offset=&status=`) |
| `GET` | `/public/reports/{id}` | Single public projection |
| `GET` | `/public/config` | Live `Config` read straight from the chain |
| `GET` | `/public/ledger` | Decoded program events (`?limit=`) |
| `GET` | `/public/categories` | Category ids and labels |

The public report projection deliberately excludes titles, summaries,
descriptions, and entity names. It contains only the category, commitments,
status, reward, and timestamps.

`/public/config` returns the on-chain state, including `token_symbol` (`CORRUPT`)
and `token_decimals` (`6`), so clients can format amounts without hardcoding.

## Error format

Errors are FastAPI's standard shape:

```json
{ "detail": "only pending reports can be verified" }
```

`detail` is a string for domain errors and may be a validation array for `422`.
