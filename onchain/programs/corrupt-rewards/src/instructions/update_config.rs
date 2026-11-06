use anchor_lang::prelude::*;
use anchor_spl::token::TokenAccount;

use crate::{constants::*, error::ErrorCode, events::ConfigUpdated, state::Config};

/// Partial update payload; `None` fields are left untouched.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Default)]
pub struct ConfigUpdate {
    pub verifier: Option<Pubkey>,
    pub treasury: Option<Pubkey>,
    pub min_reward: Option<u64>,
    pub max_reward: Option<u64>,
}

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    pub authority: Signer<'info>,

    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, Config>,

    /// Checked and persisted only when `update.treasury` is set; otherwise it
    /// is ignored, so callers may pass the current treasury unchanged.
    pub new_treasury: Account<'info, TokenAccount>,
}

pub fn handle_update_config(ctx: Context<UpdateConfig>, update: ConfigUpdate) -> Result<()> {
    let config = &mut ctx.accounts.config;
    require_keys_eq!(
        config.authority,
        ctx.accounts.authority.key(),
        ErrorCode::Unauthorized
    );

    if let Some(verifier) = update.verifier {
        require_keys_neq!(verifier, Pubkey::default(), ErrorCode::InvalidConfig);
        config.verifier = verifier;
    }

    if let Some(treasury) = update.treasury {
        let account = &ctx.accounts.new_treasury;
        require_keys_eq!(account.key(), treasury, ErrorCode::TreasuryMismatch);
        require_keys_eq!(account.mint, config.reward_mint, ErrorCode::MintMismatch);
        config.treasury = treasury;
    }

    if let Some(min_reward) = update.min_reward {
        config.min_reward = min_reward;
    }
    if let Some(max_reward) = update.max_reward {
        config.max_reward = max_reward;
    }
    require!(
        config.min_reward > 0 && config.min_reward <= config.max_reward,
        ErrorCode::InvalidRewardBounds
    );

    emit!(ConfigUpdated {
        authority: config.authority,
        verifier: config.verifier,
        treasury: config.treasury,
        min_reward: config.min_reward,
        max_reward: config.max_reward,
        timestamp: Clock::get()?.unix_timestamp,
    });

    Ok(())
}
