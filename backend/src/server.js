const express = require('express');
const { calculateReward } = require('./services/reward');

const app = express();
app.use(express.json());

app.get('/health', (_req, res) => {
  res.json({ ok: true, service: 'bribrrybuster-backend' });
});

app.post('/reports/reward-preview', (req, res) => {
  const { descriptionLength = 0, attachmentCount = 0, multiplier = 1.5 } = req.body || {};
  const reward = calculateReward(descriptionLength, attachmentCount, multiplier);
  res.json({ reward });
});

if (require.main === module) {
  const port = Number(process.env.PORT) || 3000;
  app.listen(port, () => {
    console.log(`bribrrybuster-backend listening on port ${port}`);
  });
}

module.exports = app;
