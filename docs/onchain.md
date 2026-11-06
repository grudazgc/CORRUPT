# On-chain program reference

Program ID (localnet): `FBHxR4B5jMbE5W6vukMJNM1T88gt3VkZh9MbGN4Q464C`

Source: `onchain/programs/corrupt-rewards/`

## Accounts

### `Config` — PDA `["config"]`

The singleton configuration. Created once by `initialize`.

| Field | Type | Meaning |
| --- | --- | --- |
| `authority` | `Pubkey` | Funds the pool, rotates roles, pauses |
| `verifier` | `Pubkey` | The only key allowed to resolve reports |
| `treasury` | `Pubkey` | Token account that pays rewards |
| `reward_mint` | `Pubkey` | CORRUPT mint; authority is the config PDA |
| `total_budget` | `u64` | CORRUPT ever committed to the pool |
| `total_distributed` | `u64` | CORRUPT ever paid out |
| `report_count` | `u64` | Reports submitted; the next report id |
| `min_reward` / `max_reward` | `u64` | Reward bounds enforced on payout |
| `paused` | `bool` | Freezes submissions and payouts |
| `bump` | `u8` | PDA bump |
| `created_at` | `i64` | Unix timestamp |
| `reserved` | `[u8; 32]` | Forward-compatibility padding |

Remaining budget is derived: `total_budget - total_distributed`.

### `Report` — PDA `["report", id.to_le_bytes()]`

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | `u64` | Sequential id, equal to `Config.report_count` at creation |
| `reporter` | `Pubkey` | Author and reward recipient |
| `content_hash` | `[u8; 32]` | SHA-256 of the canonical report body |
| `evidence_hash` | `[u8; 32]` | SHA-256 of the evidence bundle |
| `category` | `u8` | `0`–`5`, see below |
| `status` | `u8` | `0` pending, `1` verified, `2` rejected |
| `reward_amount` | `u64` | Paid amount; zero until verified |
| `submitted_at` / `reviewed_at` | `i64` | Unix timestamps |
| `bump` | `u8` | PDA bump |
| `reserved` | `[u8; 32]` | Forward-compatibility padding |

Categories: `0` bribery, `1` embezzlement, `2` procurement fraud, `3` nepotism,
`4` abuse of office, `5` other.

### `ReporterStats` — PDA `["reporter", reporter]`

Anti-spam counters, created on the reporter's first submission. A wallet may
submit at most `MAX_REPORTS_PER_WINDOW` (5) reports per `SUBMISSION_WINDOW_SECONDS`
(24 h) window.

## Instructions

### `initialize(min_reward, max_reward, initial_supply)`

Creates `Config`. `reward_mint` must already exist with the **config PDA** as its
mint authority. When `initial_supply > 0`, that many base units are minted to the
authority's associated token account so the authority has tokens to seed the
pool. Rejects `min_reward == 0` or `min_reward > max_reward`.

### `submit_report(content_hash, evidence_hash, category)`

Anchors a report. Rejects an all-zero hash (`EmptyHash`), an unknown category
(`InvalidCategory`), or a rate-limited reporter (`RateLimitExceeded`), and fails
when the program is paused. Emits `ReportSubmitted`.

### `verify_report(reward_amount)`

Verifier only. Requires `min_reward <= reward_amount <= max_reward` and
`reward_amount <= remaining budget`. Transfers the reward from the treasury to
the reporter's associated token account (creating it if needed, with the verifier
paying rent) and marks the report `Verified`. **Nothing is minted**, so the total
supply is fixed. Emits `ReportVerified`.

### `reject_report()`

Verifier only. Marks a pending report `Rejected` and pays nothing. Emits
`ReportRejected`.

### `fund_pool(amount)`

Anyone may top up the pool. Transfers `amount` from the funder's token account
into the treasury and adds it to `total_budget`. Emits `RewardPoolFunded`.

### `update_config(update)`

Authority only. Rotates `verifier`, `treasury`, `min_reward`, or `max_reward`.
Emits `ConfigUpdated`.

### `set_paused(paused)`

Authority only. Freezes or unfreezes submissions and payouts. Emits
`PauseToggled`.

## Errors

| Error | Cause |
| --- | --- |
| `Unauthorized` | Wrong signer for a privileged instruction |
| `Paused` | Program is paused |
| `InvalidConfig` | Bad configuration, e.g. mint authority is not the config PDA |
| `InvalidAmount` | A zero amount where a positive one is required |
| `InvalidRewardBounds` | `min_reward == 0` or `min_reward > max_reward` |
| `InvalidCategory` | Category id above `MAX_CATEGORY_ID` |
| `InvalidStatus` | Operation not allowed for the report's current status |
| `RewardBelowMinimum` / `RewardAboveMaximum` | Reward outside the configured band |
| `InsufficientBudget` | Reward exceeds the remaining pool |
| `RateLimitExceeded` | Too many reports in the current window |
| `ArithmeticOverflow` | Checked arithmetic overflow |
| `EmptyHash` | Content or evidence hash is all zeroes |
| `MintMismatch` | Mint does not match `config.reward_mint` |
| `TreasuryMismatch` | Treasury does not match `config.treasury` |

## Events

`ConfigInitialized`, `ReportSubmitted`, `ReportVerified`, `ReportRejected`,
`RewardPoolFunded`, `ConfigUpdated`, `PauseToggled`. The backend decodes these
from transaction logs into the `ChainEvent` table that backs the transparency
ledger.

## Notes for integrators

- The reward path never touches the mint authority after initialization, so an
  auditor can verify the total supply simply by reading the mint.
- The treasury is owned by the config PDA. Only `verify_report` transfers out of
  it, and only within the configured bounds and remaining budget.
- The program stores no personally identifying data; every on-chain field is
  either a hash, an amount, a timestamp, a status, or a public key.
