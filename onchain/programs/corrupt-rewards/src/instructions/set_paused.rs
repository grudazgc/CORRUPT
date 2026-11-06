use anchor_lang::prelude::*;

use crate::{constants::*, error::ErrorCode, events::PauseToggled, state::Config};

#[derive(Accounts)]
pub struct SetPaused<'info> {
    pub authority: Signer<'info>,

    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, Config>,
}

pub fn handle_set_paused(ctx: Context<SetPaused>, paused: bool) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.config.authority,
        ctx.accounts.authority.key(),
        ErrorCode::Unauthorized
    );

    ctx.accounts.config.paused = paused;
    emit!(PauseToggled {
        paused,
        timestamp: Clock::get()?.unix_timestamp,
    });

    Ok(())
}
