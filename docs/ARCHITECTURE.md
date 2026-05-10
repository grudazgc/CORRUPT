# BRIBRRYBUSTER.XYZ — Technical Architecture (MVP)

## 1. Scope (MVP)
- Submit corruption reports with attachments.
- Store files off-chain (IPFS/Arweave), anchor integrity on-chain (hash + CID).
- Admin review with quality score.
- Reward distribution in CORRUPT SPL token.

## 2. Domain Model

### Report status lifecycle
`pending -> approved|rejected -> rewarded`

Rules:
- only `approved` can transition to `rewarded`;
- `rejected` is terminal;
- reward is idempotent (cannot reward twice).

### Reward formula
`reward = base_points * multiplier`

- base points:
  - report submit: 10
  - +2 per started 100 description chars
  - +5 per attachment (max 3)
- multiplier: [1.5, 3.0]

## 3. Smart Contract (Solana)

### Accounts
- `ConfigAccount`
  - admin pubkey
  - CORRUPT mint pubkey
  - treasury ATA pubkey
  - bump/version
- `ReportAccount`
  - report id
  - author pubkey
  - data hash
  - CID
  - attachment_count
  - description_length
  - status
  - quality_multiplier_bps
  - reward_amount
  - rewarded_at

### Instructions
1. `initialize_config(admin, mint, treasury_ata)`
2. `submit_report(report_id, hash, cid, attachment_count, description_length)`
3. `review_report(report_id, status, multiplier_bps)` (admin only)
4. `distribute_reward(report_id)` (admin/operator)

## 4. Backend/API

### REST contracts
- `POST /reports`
- `GET /reports/:id`
- `GET /users/:wallet/rewards`
- `POST /admin/reports/:id/review`
- `POST /admin/reports/:id/reward`

### Idempotency
- `POST /admin/reports/:id/reward` requires idempotency key.

## 5. Storage
- Store evidence files in IPFS/Arweave.
- Store only hash + CID on-chain.
- Keep moderation notes off-chain.

## 6. Security controls
- RBAC (`reviewer`, `reward_operator`, `superadmin`)
- Rate limiting per wallet/IP
- Duplicate detection by `(description_hash, evidence_hashes)`
- Audit logs for each admin action
