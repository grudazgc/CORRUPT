pub mod constants;
pub mod error;
pub mod events;
pub mod instructions;
pub mod state;
pub mod utils;

use anchor_lang::prelude::*;

pub use constants::*;
pub use events::*;
pub use instructions::*;
pub use state::*;

declare_id!("FBHxR4B5jMbE5W6vukMJNM1T88gt3VkZh9MbGN4Q464C");

/// Anti-corruption reporting registry with CORRUPT token rewards.
///
/// The program stores only commitments (hashes) to reports. Free-text and
/// evidence files stay off-chain, while verification and reward payouts are
/// fully on-chain and auditable.
#[program]
pub mod corrupt_rewards {
    use super::*;

    /// Creates the singleton configuration. `authority` funds the program,
    /// `verifier` decides on reports, and `reward_mint` must be an SPL mint
    /// whose mint authority is the configuration PDA. `initial_supply` is
    /// minted to the authority so it can seed the reward pool.
    pub fn initialize(
        ctx: Context<Initialize>,
        min_reward: u64,
        max_reward: u64,
        initial_supply: u64,
    ) -> Result<()> {
        crate::instructions::initialize::handle_initialize(
            ctx,
            min_reward,
            max_reward,
            initial_supply,
        )
    }

    /// Anchors a new report commitment. Callers must respect the per-window
    /// submission limit enforced by the reporter stats account.
    pub fn submit_report(
        ctx: Context<SubmitReport>,
        content_hash: [u8; 32],
        evidence_hash: [u8; 32],
        category: u8,
    ) -> Result<()> {
        crate::instructions::submit_report::handle_submit_report(
            ctx,
            content_hash,
            evidence_hash,
            category,
        )
    }

    /// Verifies a pending report and pays the reward to the reporter.
    pub fn verify_report(ctx: Context<VerifyReport>, reward_amount: u64) -> Result<()> {
        crate::instructions::verify_report::handle_verify_report(ctx, reward_amount)
    }

    /// Rejects a pending report without paying a reward.
    pub fn reject_report(ctx: Context<RejectReport>) -> Result<()> {
        crate::instructions::reject_report::handle_reject_report(ctx)
    }

    /// Tops up the reward pool with existing CORRUPT tokens.
    pub fn fund_pool(ctx: Context<FundPool>, amount: u64) -> Result<()> {
        crate::instructions::fund_pool::handle_fund_pool(ctx, amount)
    }

    /// Rotates the verifier, treasury, or reward bounds. Authority only.
    pub fn update_config(ctx: Context<UpdateConfig>, update: ConfigUpdate) -> Result<()> {
        crate::instructions::update_config::handle_update_config(ctx, update)
    }

    /// Freezes or unfreezes submissions and payouts. Authority only.
    pub fn set_paused(ctx: Context<SetPaused>, paused: bool) -> Result<()> {
        crate::instructions::set_paused::handle_set_paused(ctx, paused)
    }
}
