import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  api,
  formatCorrupt,
  PlatformConfig,
  PlatformStats,
  PublicReport,
  shortAddress,
} from "../lib/api";

export default function Home() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [recent, setRecent] = useState<PublicReport[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [statsResult, recentResult] = await Promise.all([
          api.publicStats(),
          api.publicReports(8),
        ]);
        if (cancelled) return;
        setStats(statsResult);
        setRecent(recentResult);
        try {
          setConfig(await api.publicConfig());
        } catch {
          // The program may not be initialized yet on a fresh localnet.
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load data");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <h1>Report corruption. Stay anonymous. Earn CORRUPT.</h1>
      <p className="lede">
        Submit evidence of corruption, have it verified by an independent
        reviewer, and receive CORRUPT tokens on Solana. Report bodies stay
        off-chain and private; only a content hash is written to the chain so
        anyone can prove a report was not altered after the fact.
      </p>

      {error && <div className="alert error">{error}</div>}

      <div className="grid">
        <div className="card">
          <h3>Reports anchored</h3>
          <p className="stat">{stats ? stats.total_reports : "—"}</p>
          <p className="muted">
            {stats ? `${stats.unique_reporters} unique reporters` : "loading"}
          </p>
        </div>
        <div className="card">
          <h3>Verified</h3>
          <p className="stat">{stats ? stats.verified : "—"}</p>
          <p className="muted">{stats ? `${stats.pending} awaiting review` : "loading"}</p>
        </div>
        <div className="card">
          <h3>Rewards paid</h3>
          <p className="stat" style={{ fontSize: "1.3rem" }}>
            {stats ? formatCorrupt(stats.total_reward_paid) : "—"}
          </p>
          <p className="muted">{stats ? `${stats.rejected} rejected` : "loading"}</p>
        </div>
        <div className="card">
          <h3>Reward pool</h3>
          <p className="stat" style={{ fontSize: "1.3rem" }}>
            {config ? formatCorrupt(config.remaining_budget) : "not initialized"}
          </p>
          <p className="muted">
            {config
              ? `rewards ${formatCorrupt(config.min_reward)} – ${formatCorrupt(config.max_reward)}`
              : "run the bootstrap script to seed the pool"}
          </p>
        </div>
      </div>

      {config?.paused && (
        <div className="alert warning">
          The program is currently paused by the authority. New submissions and
          payouts are frozen until it is resumed.
        </div>
      )}

      <h2>How it works</h2>
      <div className="grid">
        <div className="card">
          <h3>1. Submit</h3>
          <p className="muted">
            Describe the issue, attach evidence, and sign a transaction that
            anchors a SHA-256 commitment of your report on-chain. Your wallet
            stays the only key to the evidence.
          </p>
        </div>
        <div className="card">
          <h3>2. Verify</h3>
          <p className="muted">
            A designated verifier reviews the report. The verifier cannot
            change your report: the on-chain hash proves what you submitted.
          </p>
        </div>
        <div className="card">
          <h3>3. Get paid</h3>
          <p className="muted">
            Verification pays CORRUPT straight into your associated token
            account, in the same transaction that marks the report verified.
          </p>
        </div>
      </div>

      <h2>Recent on-chain activity</h2>
      {recent.length === 0 ? (
        <p className="muted">No reports anchored yet.</p>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>On-chain ID</th>
                <th>Category</th>
                <th>Status</th>
                <th>Reward</th>
                <th>Commitment</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((report) => (
                <tr key={report.id}>
                  <td className="mono">
                    <Link to={`/transparency?id=${report.id}`}>#{report.on_chain_id}</Link>
                  </td>
                  <td>{report.category_label.replace(/_/g, " ")}</td>
                  <td>
                    <span className={`badge ${report.status}`}>{report.status}</span>
                  </td>
                  <td>{formatCorrupt(report.reward_amount)}</td>
                  <td className="mono" title={report.content_hash}>
                    {shortAddress(report.content_hash, 8)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
