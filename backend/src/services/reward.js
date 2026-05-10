function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function calculateReward(descriptionLength, attachmentCount, multiplier) {
  const safeDescription = Math.max(0, Number(descriptionLength) || 0);
  const safeAttachments = Math.min(3, Math.max(0, Number(attachmentCount) || 0));
  const safeMultiplier = clamp(Number(multiplier) || 1.5, 1.5, 3.0);

  const blocks = Math.ceil(safeDescription / 100);
  const base = 10 + blocks * 2 + safeAttachments * 5;
  return Math.floor(base * safeMultiplier);
}

module.exports = { calculateReward };
