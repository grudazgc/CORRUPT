import React, { useMemo, useState } from 'react';

function calculateReward(descriptionLength, attachmentCount, multiplier) {
  const blocks = Math.ceil(Math.max(0, descriptionLength) / 100);
  const attachments = Math.min(3, Math.max(0, attachmentCount));
  const safeMultiplier = Math.min(3.0, Math.max(1.5, multiplier));
  const base = 10 + blocks * 2 + attachments * 5;
  return Math.floor(base * safeMultiplier);
}

export default function App() {
  const [descriptionLength, setDescriptionLength] = useState(500);
  const [attachmentCount, setAttachmentCount] = useState(2);
  const [multiplier, setMultiplier] = useState(2.0);

  const preview = useMemo(
    () => calculateReward(descriptionLength, attachmentCount, multiplier),
    [descriptionLength, attachmentCount, multiplier]
  );

  return (
    <main style={{ fontFamily: 'sans-serif', padding: 20 }}>
      <h1>BRIBRRYBUSTER.XYZ — Reward Preview</h1>
      <p>Podgląd naliczania CORRUPT dla zgłoszenia.</p>
      <ul>
        <li>Description length: {descriptionLength}</li>
        <li>Attachments (max 3): {attachmentCount}</li>
        <li>Multiplier: {multiplier}</li>
      </ul>
      <strong>Reward: {preview} CORRUPT</strong>
    </main>
  );
}
