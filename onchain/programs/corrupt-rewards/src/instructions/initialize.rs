use anchor_lang::prelude::*;
use anchor_spl::{
    associated_token::AssociatedToken,
    token::{self, Mint, Token, TokenAccount},
};

use crate::{constants::*, error::ErrorCode, events::ConfigInitialized, state::Config};

#[derive(Accounts)]
pub struct Initialize<'info> {
    /// Pays for the configuration account and becomes the program authority.
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        init,
        payer = authority,
        space = 8 + Config::INIT_SPACE,
        seeds = [CONFIG_SEED],
        bump,
    )]
    pub config: Account<'info, Config>,

    /// CHECK: role assignment only, the pubkey is stored and never invoked.
    pub verifier: UncheckedAccount<'info>,

    /// Treasury token account that backs the advertised reward budget.
    #[account(
        constraint = treasury.mint == reward_mint.key() @ ErrorCode::MintMismatch,
    )]
    pub treasury: Account<'info, TokenAccount>,

    /// CORRUPT mint. Its mint authority must be the configuration PDA, because
    /// the program signs reward minting with that PDA. Writable because the
    /// initial supply is minted through it.
    #[account(
        mut,
        constraint = reward_mint.mint_authority.contains(&config.key()) @ ErrorCode::InvalidConfig,
    )]
    pub reward_mint: Account<'info, Mint>,

    /// Receives the optional initial supply so the authority has CORRUPT to
    /// seed the reward pool with. Created on demand.
    #[account(
        init_if_needed,
        payer = authority,
        associated_token::mint = reward_mint,
        associated_token::authority = authority,
    )]
    pub authority_token_account: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

pub fn handle_initialize(
    ctx: Context<Initialize>,
    min_reward: u64,
    max_reward: u64,
    initial_supply: u64,
) -> Result<()> {
    require!(
        min_reward > 0 && min_reward <= max_reward,
        ErrorCode::InvalidRewardBounds
    );

    let bump = ctx.bumps.config;

    if initial_supply > 0 {
        let seeds: &[&[u8]] = &[CONFIG_SEED, &[bump]];
        token::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.key(),
                token::MintTo {
                    mint: ctx.accounts.reward_mint.to_account_info(),
                    to: ctx.accounts.authority_token_account.to_account_info(),
                    authority: ctx.accounts.config.to_account_info(),
                },
                &[seeds],
            ),
            initial_supply,
        )?;
    }

    let clock = Clock::get()?;
    let config = &mut ctx.accounts.config;
    config.authority = ctx.accounts.authority.key();
    config.verifier = ctx.accounts.verifier.key();
    config.treasury = ctx.accounts.treasury.key();
    config.reward_mint = ctx.accounts.reward_mint.key();
    config.total_budget = 0;
    config.total_distributed = 0;
    config.report_count = 0;
    config.min_reward = min_reward;
    config.max_reward = max_reward;
    config.paused = false;
    config.bump = bump;
    config.created_at = clock.unix_timestamp;
    config.reserved = [0u8; 32];

    emit!(ConfigInitialized {
        authority: config.authority,
        verifier: config.verifier,
        treasury: config.treasury,
        reward_mint: config.reward_mint,
        min_reward,
        max_reward,
        timestamp: clock.unix_timestamp,
    });

    Ok(())
}
