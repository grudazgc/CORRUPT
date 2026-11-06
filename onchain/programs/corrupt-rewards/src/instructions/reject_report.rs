use anchor_lang::prelude::*;

use crate::{
    constants::*,
    error::ErrorCode,
    events::ReportRejected,
    state::{Config, Report, ReportStatus},
};

#[derive(Accounts)]
pub struct RejectReport<'info> {
    pub verifier: Signer<'info>,

    #[account(seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, Config>,

    #[account(
        mut,
        seeds = [REPORT_SEED, report.id.to_le_bytes().as_ref()],
        bump = report.bump,
    )]
    pub report: Account<'info, Report>,
}

pub fn handle_reject_report(ctx: Context<RejectReport>) -> Result<()> {
    require!(!ctx.accounts.config.paused, ErrorCode::Paused);
    require_keys_eq!(
        ctx.accounts.config.verifier,
        ctx.accounts.verifier.key(),
        ErrorCode::Unauthorized
    );

    let report = &mut ctx.accounts.report;
    require!(report.is_pending(), ErrorCode::InvalidStatus);

    let clock = Clock::get()?;
    report.status = ReportStatus::Rejected.as_u8();
    report.reviewed_at = clock.unix_timestamp;

    emit!(ReportRejected {
        id: report.id,
        reporter: report.reporter,
        verifier: ctx.accounts.verifier.key(),
        timestamp: clock.unix_timestamp,
    });

    Ok(())
}
