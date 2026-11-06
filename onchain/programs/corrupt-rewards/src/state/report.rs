use anchor_lang::prelude::*;

use super::types::ReportStatus;

/// A single corruption report.
///
/// Only cryptographic commitments are stored on-chain. The free-text
/// description and evidence files live off-chain; their SHA-256 digests are
/// anchored here so anyone can later prove the evidence was not altered.
#[account]
#[derive(InitSpace)]
pub struct Report {
    /// Sequential identifier, equal to `Config.report_count` at creation.
    pub id: u64,
    /// Wallet that submitted the report and receives the reward.
    pub reporter: Pubkey,
    /// SHA-256 of the canonical off-chain report body.
    pub content_hash: [u8; 32],
    /// SHA-256 of the bundled evidence archive.
    pub evidence_hash: [u8; 32],
    /// Category id, see [`Category`](super::types::Category).
    pub category: u8,
    /// Current status id, see [`ReportStatus`].
    pub status: u8,
    /// CORRUPT (base units) paid to the reporter; zero until verified.
    pub reward_amount: u64,
    /// Unix timestamp of submission.
    pub submitted_at: i64,
    /// Unix timestamp of the verifying decision; zero while pending.
    pub reviewed_at: i64,
    /// PDA bump for this account.
    pub bump: u8,
    /// Reserved for forward-compatible upgrades.
    pub reserved: [u8; 32],
}

impl Report {
    pub fn status(&self) -> ReportStatus {
        ReportStatus::from_u8(self.status).unwrap_or(ReportStatus::Pending)
    }

    pub fn is_pending(&self) -> bool {
        self.status == ReportStatus::Pending.as_u8()
    }
}
