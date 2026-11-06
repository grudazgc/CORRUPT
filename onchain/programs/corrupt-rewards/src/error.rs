use anchor_lang::prelude::*;

#[error_code]
pub enum ErrorCode {
    #[msg("Caller is not authorized to perform this action")]
    Unauthorized,

    #[msg("Program is paused")]
    Paused,

    #[msg("Configuration is invalid")]
    InvalidConfig,

    #[msg("Amount must be greater than zero")]
    InvalidAmount,

    #[msg("Reward bounds are invalid: min must be > 0 and <= max")]
    InvalidRewardBounds,

    #[msg("Report category is not recognized")]
    InvalidCategory,

    #[msg("Report status does not allow this operation")]
    InvalidStatus,

    #[msg("Reward amount is below the configured minimum")]
    RewardBelowMinimum,

    #[msg("Reward amount exceeds the configured maximum")]
    RewardAboveMaximum,

    #[msg("Reward exceeds the remaining reward pool budget")]
    InsufficientBudget,

    #[msg("Reporter already has the maximum number of reports in the current window")]
    RateLimitExceeded,

    #[msg("Arithmetic overflow")]
    ArithmeticOverflow,

    #[msg("Content or evidence hash must not be all zeroes")]
    EmptyHash,

    #[msg("Mint does not match the configured reward mint")]
    MintMismatch,

    #[msg("Treasury token account does not match the configured treasury")]
    TreasuryMismatch,
}
