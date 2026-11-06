use anchor_lang::prelude::*;

use crate::{
    constants::*,
    error::ErrorCode,
    events::ReportSubmitted,
    state::{Category, Config, Report, ReportStatus, ReporterStats},
    utils::{checked_add, is_zero_hash},
};

#[derive(Accounts)]
pub struct SubmitReport<'info> {
    #[account(mut)]
    pub reporter: Signer<'info>,

    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, Config>,

    #[account(
        init_if_needed,
        payer = reporter,
        space = 8 + ReporterStats::INIT_SPACE,
        seeds = [REPORTER_STATS_SEED, reporter.key().as_ref()],
        bump,
    )]
    pub reporter_stats: Account<'info, ReporterStats>,

    #[account(
        init,
        payer = reporter,
        space = 8 + Report::INIT_SPACE,
        seeds = [REPORT_SEED, config.report_count.to_le_bytes().as_ref()],
        bump,
    )]
    pub report: Account<'info, Report>,

    pub system_program: Program<'info, System>,
}

pub fn handle_submit_report(
    ctx: Context<SubmitReport>,
    content_hash: [u8; 32],
    evidence_hash: [u8; 32],
    category: u8,
) -> Result<()> {
    require!(!ctx.accounts.config.paused, ErrorCode::Paused);
    require!(Category::is_valid(category), ErrorCode::InvalidCategory);
    require!(!is_zero_hash(&content_hash), ErrorCode::EmptyHash);
    require!(!is_zero_hash(&evidence_hash), ErrorCode::EmptyHash);

    let clock = Clock::get()?;
    let now = clock.unix_timestamp;

    let stats = &mut ctx.accounts.reporter_stats;
    if stats.reporter == Pubkey::default() {
        stats.reporter = ctx.accounts.reporter.key();
        stats.bump = ctx.bumps.reporter_stats;
        stats.window_start = now;
    }
    if now.saturating_sub(stats.window_start) >= SUBMISSION_WINDOW_SECONDS {
        stats.window_start = now;
        stats.window_count = 0;
    }
    require!(
        stats.window_count < MAX_REPORTS_PER_WINDOW,
        ErrorCode::RateLimitExceeded
    );
    stats.window_count = checked_add(stats.window_count, 1)?;
    stats.total_reports = checked_add(stats.total_reports, 1)?;

    let id = ctx.accounts.config.report_count;
    let report = &mut ctx.accounts.report;
    report.id = id;
    report.reporter = ctx.accounts.reporter.key();
    report.content_hash = content_hash;
    report.evidence_hash = evidence_hash;
    report.category = category;
    report.status = ReportStatus::Pending.as_u8();
    report.reward_amount = 0;
    report.submitted_at = now;
    report.reviewed_at = 0;
    report.bump = ctx.bumps.report;
    report.reserved = [0u8; 32];

    ctx.accounts.config.report_count = checked_add(id, 1)?;

    emit!(ReportSubmitted {
        id,
        reporter: report.reporter,
        category,
        content_hash,
        evidence_hash,
        timestamp: now,
    });

    Ok(())
}
