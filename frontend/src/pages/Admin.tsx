import { useCallback, useEffect, useState } from "react";

import { api, formatCorrupt, PlatformConfig } from "../lib/api";

const KEY_STORAGE = "corrupt.adminKey";

interface AuditEntry {
  id: number;
  actor: string;
  action: string;
  report_id: number | null;
  details: string;
  created_at: string;
}

/**
 * Operator console. Pool funding and pausing are signed by the authority
 * keypair held by the backend, so this page only needs the admin API key.
 */
export default function Admin() {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(KEY_STORAGE) ?? "");
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setConfig(await api.publicConfig());
    } catch {
      setConfig(null);
    }
    if (!apiKey) {
      setAudit([]);
      return;
    }
    try {
      setAudit(await api.auditLog(apiKey));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the audit log");
    }
  }, [apiKey]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function rememberKey(value: string) {
    setApiKey(value);
    if (value) localStorage.setItem(KEY_STORAGE, value);
    else localStorage.removeItem(KEY_STORAGE);
  }

  async function togglePause() {
    if (!config) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.setPaused(apiKey, !config.paused);
      setMessage(
        `Program ${result.paused ? "paused" : "resumed"}. Transaction ${result.signature}.`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the pause state");
    } finally {
      setBusy(false);
    }
  }

  async function fund() {
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) {
      setError("Enter an amount in CORRUPT greater than zero.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.fundPool(apiKey, Math.round(value * 1e6));
      setMessage(
        `Pool funded with ${formatCorrupt(result.amount)}. Transaction ${result.signature}.`,
      );
      setAmount("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Funding failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Operator console</h1>
      <p className="lede">
        Fund the reward pool and pause the program in an emergency. Both actions
        are signed on-chain by the authority key, so they are visible to everyone
        in the transparency ledger.
      </p>

      <div className="card">
        <label htmlFor="admin-key">Admin API key</label>
        <input
          id="admin-key"
          type="password"
          value={apiKey}
          onChange={(event) => rememberKey(event.target.value)}
          placeholder="X-Admin-Key"
        />
      </div>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      {config ? (
        <div className="grid">
          <div className="card">
            <h3>Remaining budget</h3>
            <p className="stat" style={{ fontSize: "1.3rem" }}>
              {formatCorrupt(config.remaining_budget)}
            </p>
            <p className="muted">of {formatCorrupt(config.total_budget)}</p>
          </div>
          <div className="card">
            <h3>Distributed</h3>
            <p className="stat" style={{ fontSize: "1.3rem" }}>
              {formatCorrupt(config.total_distributed)}
            </p>
          </div>
          <div className="card">
            <h3>Program state</h3>
            <p className="stat" style={{ fontSize: "1.3rem" }}>
              {config.paused ? "Paused" : "Active"}
            </p>
            <button className="secondary" onClick={togglePause} disabled={!apiKey || busy}>
              {config.paused ? "Resume program" : "Pause program"}
            </button>
          </div>
        </div>
      ) : (
        <p className="muted">The program is not initialized yet.</p>
      )}

      <h2>Fund the reward pool</h2>
      <div className="card">
        <p className="muted">
          Moves CORRUPT from the authority token account into the treasury that
          backs all future rewards.
        </p>
        <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
          <div style={{ flex: "0 0 200px" }}>
            <label htmlFor="fund-amount">Amount (CORRUPT)</label>
            <input
              id="fund-amount"
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder="1000"
            />
          </div>
          <button onClick={fund} disabled={!apiKey || busy}>
            {busy ? "Working…" : "Fund pool"}
          </button>
        </div>
      </div>

      <h2>Audit log</h2>
      {!apiKey ? (
        <p className="muted">Enter the admin API key to read the audit log.</p>
      ) : audit.length === 0 ? (
        <p className="muted">No audited actions yet.</p>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Report</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((entry) => (
                <tr key={entry.id}>
                  <td className="muted">{new Date(entry.created_at).toLocaleString()}</td>
                  <td className="mono">{entry.actor}</td>
                  <td>{entry.action}</td>
                  <td>{entry.report_id === null ? "—" : `#${entry.report_id}`}</td>
                  <td className="mono">{entry.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
