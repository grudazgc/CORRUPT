use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, TransferChecked};

use crate::{
    constants::*,
    error::ErrorCode,
    events::RewardPoolFunded,
    state::Config,
    utils::checked_add,
};

#[derive(Accounts)]
pub struct FundPool<'info> {
    /// Anyone may top up the reward pool; the authority is not required.
    #[account(mut)]
    pub funder: Signer<'info>,

    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, Config>,

    #[account(
        constraint = reward_mint.key() == config.reward_mint @ ErrorCode::MintMismatch,
    )]
    pub reward_mint: Account<'info, Mint>,

    #[account(
        mut,
        constraint = funder_token_account.mint == reward_mint.key() @ ErrorCode::MintMismatch,
        constraint = funder_token_account.owner == funder.key() @ ErrorCode::Unauthorized,
    )]
    pub funder_token_account: Account<'info, TokenAccount>,

    #[account(
        mut,
        constraint = treasury.key() == config.treasury @ ErrorCode::TreasuryMismatch,
        constraint = treasury.mint == reward_mint.key() @ ErrorCode::MintMismatch,
    )]
    pub treasury: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
}

pub fn handle_fund_pool(ctx: Context<FundPool>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::InvalidAmount);

    let decimals = ctx.accounts.reward_mint.decimals;
    token::transfer_checked(
        CpiContext::new(
            ctx.accounts.token_program.key(),
            TransferChecked {
                from: ctx.accounts.funder_token_account.to_account_info(),
                mint: ctx.accounts.reward_mint.to_account_info(),
                to: ctx.accounts.treasury.to_account_info(),
                authority: ctx.accounts.funder.to_account_info(),
            },
        ),
        amount,
        decimals,
    )?;

    let clock = Clock::get()?;
    let config = &mut ctx.accounts.config;
    config.total_budget = checked_add(config.total_budget, amount)?;

    emit!(RewardPoolFunded {
        funder: ctx.accounts.funder.key(),
        amount,
        total_budget: config.total_budget,
        timestamp: clock.unix_timestamp,
    });

    Ok(())
}
