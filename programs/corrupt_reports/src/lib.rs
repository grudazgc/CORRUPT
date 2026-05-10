//! Minimal scaffold for BRIBRRYBUSTER Solana program.

#[repr(u8)]
pub enum ReportStatus {
    Pending = 0,
    Approved = 1,
    Rejected = 2,
    Rewarded = 3,
}

pub struct ReportAccount {
    pub author: [u8; 32],
    pub data_hash: [u8; 32],
    pub cid: [u8; 64],
    pub attachment_count: u8,
    pub description_length: u32,
    pub status: u8,
    pub multiplier_bps: u16,
    pub reward_amount: u64,
}

pub fn calculate_reward(description_length: u32, attachment_count: u8, multiplier_bps: u16) -> u64 {
    let blocks = description_length.div_ceil(100) as u64;
    let attachments = attachment_count.min(3) as u64;
    let base = 10 + blocks * 2 + attachments * 5;

    let clamped = multiplier_bps.clamp(150, 300) as u64;
    (base * clamped) / 100
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reward_example() {
      assert_eq!(calculate_reward(500, 2, 200), 60);
    }
}
