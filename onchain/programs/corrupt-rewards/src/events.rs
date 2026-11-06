use anchor_lang::prelude::*;

/// Emitted once when the program configuration is created.
#[event]
pub struct ConfigInitialized {
    pub authority: Pubkey,
    pub verifier: Pubkey,
    pub treasury: Pubkey,
    pub reward_mint: Pubkey,
    pub min_reward: u64,
    pub max_reward: u64,
    pub timestamp: i64,
}

/// Emitted when a new report is anchored on-chain.
#[event]
pub struct ReportSubmitted {
    pub id: u64,
    pub reporter: Pubkey,
    pub category: u8,
    pub content_hash: [u8; 32],
    pub evidence_hash: [u8; 32],
    pub timestamp: i64,
}

/// Emitted when a verifier approves a report and a reward is paid out.
#[event]
pub struct ReportVerified {
    pub id: u64,
    pub reporter: Pubkey,
    pub verifier: Pubkey,
    pub reward_amount: u64,
    pub timestamp: i64,
}

/// Emitted when a verifier rejects a report.
#[event]
pub struct ReportRejected {
    pub id: u64,
    pub reporter: Pubkey,
    pub verifier: Pubkey,
    pub timestamp: i64,
}

/// Emitted when the reward pool receives tokens.
#[event]
pub struct RewardPoolFunded {
    pub funder: Pubkey,
    pub amount: u64,
    pub total_budget: u64,
    pub timestamp: i64,
}

/// Emitted when the authority rotates roles or reward bounds.
#[event]
pub struct ConfigUpdated {
    pub authority: Pubkey,
    pub verifier: Pubkey,
    pub treasury: Pubkey,
    pub min_reward: u64,
    pub max_reward: u64,
    pub timestamp: i64,
}

/// Emitted when the emergency pause flag changes.
#[event]
pub struct PauseToggled {
    pub paused: bool,
    pub timestamp: i64,
}
