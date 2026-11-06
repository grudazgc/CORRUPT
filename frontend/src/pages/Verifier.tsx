import { useCallback, useEffect, useState } from "react";

import { api, formatCorrupt, ReportDetail } from "../lib/api";

const KEY_STORAGE = "corrupt.verifierKey";

/**
 * Review queue for designated verifiers. The verifier key is a shared secret
 * held by the operator; it is kept in local storage only for convenience and is
 * never sent anywhere except the verifier endpoints.
 */
export default function Verifier() {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(KEY_STORAGE) ?? "");
  const [queue, setQueue] = useState<ReportDetail[]>([]);
  const [rewards, setRewards] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!apiKey) return;
    setBusy(true);
    setError(null);
    try {
      setQueue(await api.verifierQueue(apiKey));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the queue");
    } finally {
      setBusy(false);
    }
  }, [apiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  function rememberKey(value: string) {
    setApiKey(value);
    if (value) localStorage.setItem(KEY_STORAGE, value);
    else localStorage.removeItem(KEY_STORAGE);
  }

  async function decide(report: ReportDetail, action: "verify" | "reject") {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      const note = notes[report.id] ?? "";
      if (action === "verify") {
        const amount = Number(rewards[report.id] ?? "");
        if (!Number.isFinite(amount) || amount <= 0) {
          throw new Error("Enter a reward amount in CORRUPT before verifying.");
        }
        const result = await api.verifyReport(apiKey, report.id, Math.round(amount * 1e6), note);
        setMessage(
          `Report #${result.id} verified. Payout transaction ${result.decision_signature}.`,
        );
      } else {
        const result = await api.rejectReport(apiKey, report.id, note);
        setMessage(`Report #${result.id} rejected. No reward was paid.`);
      }
      setQueue((prev) => prev.filter((item) => item.id !== report.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Verifier console</h1>
      <p className="lede">
        Review pending reports and release rewards from the on-chain pool. The
        verifier key signs the payout; the reporter's evidence never leaves this
        server.
      </p>

      <div className="card">
        <label htmlFor="verifier-key">Verifier API key</label>
        <input
          id="verifier-key"
          type="password"
          value={apiKey}
          onChange={(event) => rememberKey(event.target.value)}
          placeholder="X-Verifier-Key"
        />
        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={load} disabled={!apiKey || busy}>
            {busy ? "Loading…" : "Load queue"}
          </button>
          <span className="muted">{queue.length} report(s) awaiting review</span>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      {queue.length === 0 && apiKey && !busy && (
        <p className="muted">Nothing to review right now.</p>
      )}

      {queue.map((report) => (
        <div className="card" key={report.id}>
          <div className="row">
            <span className="badge pending">{report.status}</span>
            <span className="muted">
              #{report.id} · on-chain #{report.on_chain_id} ·{" "}
              {report.category_label.replace(/_/g, " ")}
            </span>
          </div>
          <h2 style={{ marginTop: 12 }}>{report.title}</h2>
          <p>{report.summary}</p>

          <button
            className="secondary"
            onClick={() => setExpanded(expanded === report.id ? null : report.id)}
          >
            {expanded === report.id ? "Hide details" : "Show details"}
          </button>

          {expanded === report.id && (
            <div className="stack" style={{ marginTop: 12 }}>
              <p style={{ whiteSpace: "pre-wrap" }}>{report.description}</p>
              <div>
                <span className="muted">Entity</span>
                <div>{report.entity_name || "n/a"}</div>
              </div>
              <div>
                <span className="muted">Jurisdiction</span>
                <div>{report.jurisdiction || "n/a"}</div>
              </div>
              <div>
                <span className="muted">Evidence</span>
                <div className="mono">
                  {report.evidence
                    ? `${report.evidence.filename} (${report.evidence.media_type}, ${report.evidence.size} bytes) sha256=${report.evidence.sha256}`
                    : "no evidence attached"}
                </div>
              </div>
              <div>
                <span className="muted">Content hash</span>
                <div className="mono">{report.content_hash}</div>
              </div>
            </div>
          )}

          <div className="row" style={{ marginTop: 16, alignItems: "flex-end", gap: 12 }}>
            <div style={{ flex: "0 0 180px" }}>
              <label htmlFor={`reward-${report.id}`}>Reward (CORRUPT)</label>
              <input
                id={`reward-${report.id}`}
                inputMode="decimal"
                value={rewards[report.id] ?? ""}
                onChange={(event) =>
                  setRewards((prev) => ({ ...prev, [report.id]: event.target.value }))
                }
                placeholder="5"
              />
            </div>
            <div style={{ flex: 1 }}>
              <label htmlFor={`note-${report.id}`}>Reviewer note</label>
              <input
                id={`note-${report.id}`}
                value={notes[report.id] ?? ""}
                onChange={(event) =>
                  setNotes((prev) => ({ ...prev, [report.id]: event.target.value }))
                }
                placeholder="Why this decision?"
              />
            </div>
          </div>

          <div className="row" style={{ marginTop: 12 }}>
            <button onClick={() => decide(report, "verify")} disabled={busy}>
              Verify and pay
            </button>
            <button className="secondary" onClick={() => decide(report, "reject")} disabled={busy}>
              Reject
            </button>
            <span className="muted">
              Verifying transfers {formatCorrupt(Number(rewards[report.id] ?? 0) * 1e6)} from the
              pool to the reporter.
            </span>
          </div>
        </div>
      ))}
    </>
  );
}
