use anchor_lang::prelude::*;
use anchor_spl::{
    associated_token::AssociatedToken,
    token::{self, Mint, Token, TokenAccount, TransferChecked},
};

use crate::{
    constants::*,
    error::ErrorCode,
    events::ReportVerified,
    state::{Config, Report, ReportStatus},
    utils::{checked_add, checked_sub},
};

#[derive(Accounts)]
pub struct VerifyReport<'info> {
    /// Verifier or relayer; also pays rent if the reporter has no token account.
    #[account(mut)]
    pub verifier: Signer<'info>,

    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, Config>,

    #[account(
        mut,
        seeds = [REPORT_SEED, report.id.to_le_bytes().as_ref()],
        bump = report.bump,
    )]
    pub report: Account<'info, Report>,

    /// Wallet that receives the reward. Must be the report author; it does not
    /// need to sign because the payout is decided by the verifier.
    ///
    /// CHECK: pubkey equality with `report.reporter` is enforced below.
    #[account(constraint = reporter.key() == report.reporter @ ErrorCode::Unauthorized)]
    pub reporter: UncheckedAccount<'info>,

    #[account(
        mut,
        constraint = reward_mint.key() == config.reward_mint @ ErrorCode::MintMismatch,
    )]
    pub reward_mint: Account<'info, Mint>,

    #[account(
        mut,
        constraint = treasury.key() == config.treasury @ ErrorCode::TreasuryMismatch,
        constraint = treasury.mint == reward_mint.key() @ ErrorCode::MintMismatch,
    )]
    pub treasury: Account<'info, TokenAccount>,

    /// Reporter's CORRUPT account, created on demand so a payout is a single
    /// transaction even for a first-time reporter.
    #[account(
        init_if_needed,
        payer = verifier,
        associated_token::mint = reward_mint,
        associated_token::authority = reporter,
    )]
    pub reporter_token_account: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

pub fn handle_verify_report(ctx: Context<VerifyReport>, reward_amount: u64) -> Result<()> {
    let config = &ctx.accounts.config;
    require!(!config.paused, ErrorCode::Paused);
    require_keys_eq!(
        config.verifier,
        ctx.accounts.verifier.key(),
        ErrorCode::Unauthorized
    );

    let report = &mut ctx.accounts.report;
    require!(report.is_pending(), ErrorCode::InvalidStatus);
    require!(
        reward_amount >= config.min_reward,
        ErrorCode::RewardBelowMinimum
    );
    require!(
        reward_amount <= config.max_reward,
        ErrorCode::RewardAboveMaximum
    );

    let remaining = checked_sub(config.total_budget, config.total_distributed)?;
    require!(
        reward_amount <= remaining,
        ErrorCode::InsufficientBudget
    );

    let decimals = ctx.accounts.reward_mint.decimals;
    let reporter = report.reporter;
    let seeds: &[&[u8]] = &[CONFIG_SEED, &[config.bump]];

    // The configuration PDA owns the treasury, so the transfer is signed with
    // its seeds. Rewards are paid only from the pre-funded pool; nothing is
    // minted, so the total supply stays fixed.
    token::transfer_checked(
        CpiContext::new_with_signer(
            ctx.accounts.token_program.key(),
            TransferChecked {
                from: ctx.accounts.treasury.to_account_info(),
                mint: ctx.accounts.reward_mint.to_account_info(),
                to: ctx.accounts.reporter_token_account.to_account_info(),
                authority: ctx.accounts.config.to_account_info(),
            },
            &[seeds],
        ),
        reward_amount,
        decimals,
    )?;

    let clock = Clock::get()?;
    report.status = ReportStatus::Verified.as_u8();
    report.reward_amount = reward_amount;
    report.reviewed_at = clock.unix_timestamp;

    let config = &mut ctx.accounts.config;
    config.total_distributed = checked_add(config.total_distributed, reward_amount)?;

    emit!(ReportVerified {
        id: report.id,
        reporter,
        verifier: ctx.accounts.verifier.key(),
        reward_amount,
        timestamp: clock.unix_timestamp,
    });

    Ok(())
}
