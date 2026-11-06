use anchor_lang::prelude::*;

use crate::error::ErrorCode;

/// Adds two `u64` values, mapping overflow onto a program error.
pub fn checked_add(a: u64, b: u64) -> Result<u64> {
    a.checked_add(b).ok_or_else(|| ErrorCode::ArithmeticOverflow.into())
}

/// Subtracts `b` from `a`, mapping underflow onto a program error.
pub fn checked_sub(a: u64, b: u64) -> Result<u64> {
    a.checked_sub(b).ok_or_else(|| ErrorCode::ArithmeticOverflow.into())
}

/// Returns true when every byte of the digest is zero.
pub fn is_zero_hash(hash: &[u8; 32]) -> bool {
    hash.iter().all(|byte| *byte == 0)
}
