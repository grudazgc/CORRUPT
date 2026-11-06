import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";

import { api, formatCorrupt, Report } from "../lib/api";
import { useAuth } from "../hooks/useAuth";

export default function MyReports() {
  const { publicKey } = useWallet();
  const { token, signIn, busy, error: authError } = useAuth();
  const [reports, setReports] = useState<Report[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    api
      .myReports(token)
      .then((result) => {
        if (!cancelled) setReports(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load reports");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const totalEarned = reports
    .filter((report) => report.status === "verified")
    .reduce((sum, report) => sum + (report.reward_amount ?? 0), 0);

  return (
    <>
      <h1>My reports</h1>
      <p className="lede">
        Only you can see the full content of these reports. Every entry links to
        the on-chain record that proves its hash and payout.
      </p>

      {!publicKey && (
        <div className="alert info">
          <div className="row">
            <span>Connect a wallet to see your reports.</span>
            <WalletMultiButton />
          </div>
        </div>
      )}

      {publicKey && !token && (
        <div className="alert info">
          <div className="row">
            <span>Sign a message to authenticate. This is free and off-chain.</span>
            <button onClick={signIn} disabled={busy}>
              {busy ? "Signing…" : "Sign in"}
            </button>
          </div>
        </div>
      )}

      {authError && <div className="alert error">{authError}</div>}
      {error && <div className="alert error">{error}</div>}

      {token && (
        <>
          <div className="grid">
            <div className="card">
              <h3>Total reports</h3>
              <p className="stat">{reports.length}</p>
            </div>
            <div className="card">
              <h3>Verified</h3>
              <p className="stat">
                {reports.filter((report) => report.status === "verified").length}
              </p>
            </div>
            <div className="card">
              <h3>CORRUPT earned</h3>
              <p className="stat" style={{ fontSize: "1.3rem" }}>
                {formatCorrupt(totalEarned)}
              </p>
            </div>
          </div>

          {loading ? (
            <p className="muted">Loading…</p>
          ) : reports.length === 0 ? (
            <p className="muted">
              You have no reports yet. <Link to="/submit">Submit your first one</Link>.
            </p>
          ) : (
            <div className="card">
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Reward</th>
                    <th>On-chain</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((report) => (
                    <tr key={report.id}>
                      <td>
                        <Link to={`/reports/${report.id}`}>{report.title}</Link>
                      </td>
                      <td>{report.category_label.replace(/_/g, " ")}</td>
                      <td>
                        <span className={`badge ${report.status}`}>{report.status}</span>
                      </td>
                      <td>{formatCorrupt(report.reward_amount)}</td>
                      <td className="mono">
                        {report.on_chain_id === null ? "—" : `#${report.on_chain_id}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}
