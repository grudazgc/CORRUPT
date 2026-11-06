use anchor_lang::prelude::*;

/// Seed for the singleton program configuration account.
#[constant]
pub const CONFIG_SEED: &[u8] = b"config";

/// Seed prefix for per-report accounts (`[REPORT_SEED, id.to_le_bytes()]`).
#[constant]
pub const REPORT_SEED: &[u8] = b"report";

/// Seed prefix for per-reporter anti-spam counters.
#[constant]
pub const REPORTER_STATS_SEED: &[u8] = b"reporter";

/// Denominator used for reward calculations expressed in basis points.
#[constant]
pub const BASIS_POINTS: u64 = 10_000;

/// Highest category id accepted by [`submit_report`](crate::submit_report).
#[constant]
pub const MAX_CATEGORY_ID: u8 = 5;

/// Reports a single wallet may submit inside one rolling window.
#[constant]
pub const MAX_REPORTS_PER_WINDOW: u64 = 5;

/// Length of the rolling submission window, in seconds (24 hours).
#[constant]
pub const SUBMISSION_WINDOW_SECONDS: i64 = 86_400;
