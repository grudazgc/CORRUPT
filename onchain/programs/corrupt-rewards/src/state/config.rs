use anchor_lang::prelude::*;

/// Singleton program configuration.
///
/// Role separation is deliberate: `authority` controls funding and verifier
/// rotation, while `verifier` is the only role allowed to resolve reports. A
/// single key can hold both roles during a pilot, but the contract never
/// requires it.
#[account]
#[derive(InitSpace)]
pub struct Config {
    /// Admin able to fund the reward pool and rotate roles.
    pub authority: Pubkey,
    /// Key allowed to verify or reject reports.
    pub verifier: Pubkey,
    /// Token account funding reward payouts.
    pub treasury: Pubkey,
    /// SPL mint of the CORRUPT reward token.
    pub reward_mint: Pubkey,
    /// Total CORRUPT (base units) the authority has committed to the pool.
    pub total_budget: u64,
    /// Total CORRUPT (base units) already paid out as rewards.
    pub total_distributed: u64,
    /// Number of reports ever submitted; also the next report id.
    pub report_count: u64,
    /// Lower bound for a single reward.
    pub min_reward: u64,
    /// Upper bound for a single reward.
    pub max_reward: u64,
    /// When true, submissions and payouts are frozen.
    pub paused: bool,
    /// PDA bump for this account.
    pub bump: u8,
    /// Unix timestamp of initialization.
    pub created_at: i64,
    /// Reserved for forward-compatible upgrades.
    pub reserved: [u8; 32],
}
