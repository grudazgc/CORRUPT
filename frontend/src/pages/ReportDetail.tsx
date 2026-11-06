import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useWallet } from "@solana/wallet-adapter-react";

import { api, formatCorrupt, ReportDetail as ReportDetailType } from "../lib/api";
import { useAuth } from "../hooks/useAuth";

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>();
  const reportId = Number(id);
  const { publicKey } = useWallet();
  const { token, signIn, busy: authBusy } = useAuth();

  const [report, setReport] = useState<ReportDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      setReport(await api.reportDetail(token, reportId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report");
    } finally {
      setBusy(false);
    }
  }, [token, reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <p>
        <Link to="/reports">← Back to my reports</Link>
      </p>
      <h1>Report #{reportId}</h1>

      {!publicKey && (
        <div className="alert info">Connect the wallet that filed this report.</div>
      )}
      {publicKey && !token && (
        <div className="alert info">
          <div className="row">
            <span>Authenticate to view the full report.</span>
            <button onClick={signIn} disabled={authBusy}>
              {authBusy ? "Signing…" : "Sign in"}
            </button>
          </div>
        </div>
      )}
      {error && <div className="alert error">{error}</div>}
      {busy && <p className="muted">Loading…</p>}

      {report && (
        <>
          <div className="card">
            <div className="row">
              <span className={`badge ${report.status}`}>{report.status}</span>
              <span className="muted">{report.category_label.replace(/_/g, " ")}</span>
              <span className="muted">jurisdiction {report.jurisdiction || "n/a"}</span>
            </div>
            <h2 style={{ marginTop: 16 }}>{report.title}</h2>
            <p>{report.summary}</p>
            <p style={{ whiteSpace: "pre-wrap" }}>{report.description}</p>
            {report.entity_name && (
              <p className="muted">Entity named: {report.entity_name}</p>
            )}
          </div>

          <h2>On-chain commitment</h2>
          <div className="card stack">
            <div>
              <span className="muted">Content hash (SHA-256)</span>
              <div className="mono">{report.content_hash}</div>
            </div>
            <div>
              <span className="muted">Evidence hash (SHA-256)</span>
              <div className="mono">{report.evidence_hash ?? "no evidence attached"}</div>
            </div>
            <div>
              <span className="muted">Program account</span>
              <div className="mono">
                {report.on_chain_id === null
                  ? "not anchored yet"
                  : `report PDA #${report.on_chain_id}`}
              </div>
            </div>
            <div>
              <span className="muted">Reward</span>
              <div>{formatCorrupt(report.reward_amount)}</div>
            </div>
          </div>

          <h2>Timeline</h2>
          <ul className="timeline">
            {report.timeline.map((entry) => (
              <li key={`${entry.step}-${entry.timestamp}`}>
                <strong>{entry.step.replace(/_/g, " ")}</strong>
                <div className="muted">
                  {new Date(entry.timestamp).toLocaleString()} — {entry.detail}
                </div>
              </li>
            ))}
          </ul>

          {report.decision_note && (
            <>
              <h2>Reviewer note</h2>
              <div className="card">
                <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{report.decision_note}</p>
              </div>
            </>
          )}

          {report.status === "verified" && report.decision_signature && (
            <div className="alert info">
              Payout settled on-chain in transaction{" "}
              <span className="mono">{report.decision_signature}</span>.
            </div>
          )}
          {report.status === "rejected" && (
            <div className="alert warning">
              This report was reviewed and rejected, so no reward was paid. You
              can file a new report with stronger evidence.
            </div>
          )}
        </>
      )}
    </>
  );
}
