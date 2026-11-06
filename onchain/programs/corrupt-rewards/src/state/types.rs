use anchor_lang::prelude::*;

use crate::constants::MAX_CATEGORY_ID;

/// On-chain category of a corruption report.
///
/// Categories drive the default reward band and let analytics aggregate
/// reports without exposing the underlying evidence, which is kept off-chain.
#[derive(AnchorSerialize, AnchorDeserialize, InitSpace, Clone, Copy, PartialEq, Eq, Debug)]
pub enum Category {
    Bribery,
    Embezzlement,
    ProcurementFraud,
    Nepotism,
    AbuseOfOffice,
    Other,
}

impl Category {
    pub fn from_u8(value: u8) -> Option<Self> {
        match value {
            0 => Some(Category::Bribery),
            1 => Some(Category::Embezzlement),
            2 => Some(Category::ProcurementFraud),
            3 => Some(Category::Nepotism),
            4 => Some(Category::AbuseOfOffice),
            5 => Some(Category::Other),
            _ => None,
        }
    }

    pub fn is_valid(value: u8) -> bool {
        value <= MAX_CATEGORY_ID
    }
}

/// Lifecycle of a report.
///
/// A report is created as [`ReportStatus::Pending`] and is terminal once a
/// verifier rejects it or pays out a reward.
#[derive(AnchorSerialize, AnchorDeserialize, InitSpace, Clone, Copy, PartialEq, Eq, Debug)]
pub enum ReportStatus {
    Pending,
    Verified,
    Rejected,
}

impl ReportStatus {
    pub fn as_u8(&self) -> u8 {
        match self {
            ReportStatus::Pending => 0,
            ReportStatus::Verified => 1,
            ReportStatus::Rejected => 2,
        }
    }

    pub fn from_u8(value: u8) -> Option<Self> {
        match value {
            0 => Some(ReportStatus::Pending),
            1 => Some(ReportStatus::Verified),
            2 => Some(ReportStatus::Rejected),
            _ => None,
        }
    }
}
