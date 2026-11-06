use anchor_lang::prelude::*;

/// Rolling anti-spam window for a single reporter.
///
/// The account is created on the reporter's first submission and recycled
/// afterwards, so a reporter only ever pays rent for one extra account.
#[account]
#[derive(InitSpace)]
pub struct ReporterStats {
    /// Wallet these counters belong to.
    pub reporter: Pubkey,
    /// Total number of reports ever submitted by this wallet.
    pub total_reports: u64,
    /// Reports submitted inside the current window.
    pub window_count: u64,
    /// Unix timestamp at which the current window started.
    pub window_start: i64,
    /// PDA bump for this account.
    pub bump: u8,
}
