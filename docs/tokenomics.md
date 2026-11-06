# Tokenomics and legal guardrails

## The CORRUPT token

CORRUPT is a standard SPL token, created at bootstrap with 6 decimals. Its
**mint authority is the program's config PDA**, so the only key that could ever
mint is the program itself, and the program only mints once — during
`initialize`, to give the authority tokens to seed the pool.

After that, the supply is fixed. `verify_report` pays rewards by **transferring**
from the treasury; it never mints. Two consequences follow:

1. **The supply is auditable.** Read the mint account and you have the entire
   supply; no instruction can increase it.
2. **Every reward is pre-funded.** A payout can never exceed what the authority
   actually deposited, so the pool cannot promise tokens it does not hold.

## Where tokens live

| Account | Owner | Role |
| --- | --- | --- |
| Mint | Config PDA (authority) | Fixed supply |
| Authority token account | Authority key | Holding account for seeding and top-ups |
| Treasury | Config PDA | The reward pool; only `verify_report` can move tokens out |
| Reporter token account | Reporter | Receives rewards; created on first payout |

`total_budget` is how much the authority has committed to the pool;
`total_distributed` is how much has been paid. Remaining budget is the
difference, and no single payout may exceed it.

## Reward policy

The verifier chooses each reward within on-chain bounds:

- `min_reward` and `max_reward` are set at initialization and changeable only by
  the authority via `update_config`.
- The reference bootstrap uses 1 CORRUPT minimum and 1,000 CORRUPT maximum, with
  a 100,000 CORRUPT pool and a 1,000,000 CORRUPT initial supply.
- The verifier must also justify the amount in a note, which is stored off-chain
  and shown to the reporter.

The token has **no monetary promise**. It is a recognition and incentive
mechanism for verified reports, not an investment, security, or claim on any
entity. Deployments that intend to give it market value must handle the
regulatory questions that follow on their own; the code makes no attempt to.

## Anti-abuse

- **Rate limiting** — a wallet may anchor at most 5 reports per 24-hour window,
  enforced on-chain by `ReporterStats`.
- **Human review** — every payout requires a verifier decision; there is no
  automatic payout path.
- **Bounded payouts** — the per-report maximum plus the remaining-budget check
  cap the damage a compromised verifier key can do.
- **Emergency pause** — the authority can freeze submissions and payouts while
  investigating abuse.
- **Immutable commitments** — a report's content hash cannot be changed after
  anchoring, so a reporter cannot swap evidence under a reviewer.

## Legal and ethical guardrails

Corruption reporting is sensitive, and a system that pays for accusations can be
misused. These are the guardrails this reference implementation builds in, and
the ones an operator must add.

**Built in**

- Report content and evidence are **never written on-chain**. Only SHA-256
  commitments are published, so the ledger proves integrity without exposing
  allegations.
- The **public API excludes** titles, summaries, descriptions, and entity names.
  Named parties are not exposed by default.
- Evidence is **encrypted at rest** when `CORRUPT_EVIDENCE_ENCRYPTION_KEY` is
  set, and stored under an operator-controlled directory.
- Every privileged action is written to an **append-only audit log**.
- Rewards are **paid only after human review**, never automatically.

**Operator responsibilities**

- **Data protection.** Reports contain personal data about third parties. Put in
  place a lawful basis, retention limits, and a deletion path before going live,
  and prefer client-side encryption so the operator cannot read evidence either.
- **Presumption of innocence.** A verified report means "the reviewer judged the
  submission credible", not "the accused is guilty". Wording, UI copy, and any
  downstream use must not overstate that.
- **Protect reporters.** Consider anonymity-preserving intake (for example
  Tor or a mixnet) for high-risk jurisdictions, and never publish timing metadata
  that could deanonymise a reporter.
- **Manage the verifier role.** The verifier decides who gets paid. Vet that role
  carefully, rotate keys, and monitor the audit log for unusual approval
  patterns.
- **Do not create a market you cannot govern.** If CORRUPT becomes tradeable,
  expect securities, AML, and tax obligations, and expect the incentive to
  submit false reports to grow.

**Explicitly out of scope**

- No legal advice is provided; nothing here is a compliance opinion.
- No identity verification, sanctions screening, or KYC.
- No claim that a rewarded report is true, only that it was reviewed.
