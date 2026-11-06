import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, formatCorrupt, PlatformConfig, PublicReport, shortAddress } from "../lib/api";

interface LedgerEntry {
  id: number;
  signature: string;
  name: string;
  payload: string;
  created_at: string;
}

export default function Transparency() {
  const [params, setParams] = useSearchParams();
  const [reports, setReports] = useState<PublicReport[]>([]);
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const selected = params.get("id") ? Number(params.get("id")) : null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [reportList, ledgerEntries] = await Promise.all([
          api.publicReports(100),
          api.ledger(100),
        ]);
        if (cancelled) return;
        setReports(reportList);
        setLedger(ledgerEntries);
        try {
          setConfig(await api.publicConfig());
        } catch {
          /* program not initialized */
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
      <h1>Transparency ledger</h1>
      <p className="lede">
        Everything here is public and verifiable. Report content stays private;
        the commitments and payouts below can be checked against the Solana
        ledger at any time.
      </p>

      {error && <div className="alert error">{error}</div>}

      {config && (
        <div className="grid">
          <div className="card">
            <h3>Reward pool remaining</h3>
            <p className="stat" style={{ fontSize: "1.3rem" }}>
              {formatCorrupt(config.remaining_budget)}
            </p>
          </div>
          <div className="card">
            <h3>Total distributed</h3>
            <p className="stat" style={{ fontSize: "1.3rem" }}>
              {formatCorrupt(config.total_distributed)}
            </p>
          </div>
          <div className="card">
            <h3>Status</h3>
            <p className="stat" style={{ fontSize: "1.3rem" }}>
              {config.paused ? "Paused" : "Active"}
            </p>
            <p className="muted">
              rewards {formatCorrupt(config.min_reward)} – {formatCorrupt(config.max_reward)}
            </p>
          </div>
        </div>
      )}

      {config && (
        <div className="card" style={{ marginTop: 16 }}>
          <span className="muted">CORRUPT mint</span>
          <div className="mono">{config.reward_mint}</div>
          <span className="muted">Treasury</span>
          <div className="mono">{config.treasury}</div>
          <span className="muted">Verifier</span>
          <div className="mono">{config.verifier}</div>
        </div>
      )}

      <h2>Anchored reports</h2>
      {reports.length === 0 ? (
        <p className="muted">No reports yet.</p>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>On-chain ID</th>
                <th>Category</th>
                <th>Status</th>
                <th>Reward</th>
                <th>Content hash</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id}>
                  <td className="mono">#{report.on_chain_id}</td>
                  <td>{report.category_label.replace(/_/g, " ")}</td>
                  <td>
                    <span className={`badge ${report.status}`}>{report.status}</span>
                  </td>
                  <td>{formatCorrupt(report.reward_amount)}</td>
                  <td className="mono" title={report.content_hash}>
                    {shortAddress(report.content_hash, 8)}
                  </td>
                  <td>
                    <button
                      className="secondary"
                      onClick={() => setParams({ id: String(report.id) })}
                    >
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected !== null && (
        <>
          <h2>Report #{selected} (public view)</h2>
          {(() => {
            const report = reports.find((item) => item.id === selected);
            if (!report) return <p className="muted">Not found in the public projection.</p>;
            return (
              <div className="card stack">
                <div>
                  <span className="muted">Content hash</span>
                  <div className="mono">{report.content_hash}</div>
                </div>
                <div>
                  <span className="muted">Evidence hash</span>
                  <div className="mono">{report.evidence_hash ?? "no evidence"}</div>
                </div>
                <div className="muted">
                  Status {report.status} · reward {formatCorrupt(report.reward_amount)} ·
                  anchored {report.anchored_at ? new Date(report.anchored_at).toLocaleString() : "—"}
                </div>
              </div>
            );
          })()}
        </>
      )}

      <h2>Program event log</h2>
      {ledger.length === 0 ? (
        <p className="muted">
          No events indexed yet. Events appear here as the indexer observes them
          on-chain.
        </p>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Signature</th>
                <th>Payload</th>
                <th>Observed</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.name}</td>
                  <td className="mono" title={entry.signature}>
                    {shortAddress(entry.signature, 6)}
                  </td>
                  <td className="mono">{shortAddress(entry.payload, 24)}</td>
                  <td className="muted">{new Date(entry.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
