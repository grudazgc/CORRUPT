import { useEffect, useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { LAMPORTS_PER_SOL } from "@solana/web3.js";

import { api, ReportInput } from "../lib/api";
import { useAuth } from "../hooks/useAuth";

const EMPTY: ReportInput = {
  title: "",
  summary: "",
  description: "",
  category: 0,
  jurisdiction: "",
  entity_name: "",
};

export default function SubmitReport() {
  const { connection } = useConnection();
  const { publicKey } = useWallet();
  const { token, signIn, busy: authBusy, error: authError, signAndSendPrepared } = useAuth();

  const [categories, setCategories] = useState<{ id: number; label: string }[]>([]);
  const [form, setForm] = useState<ReportInput>(EMPTY);
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<"form" | "evidence" | "signing" | "done">("form");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    api.categories().then(setCategories).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!publicKey) {
      setBalance(null);
      return;
    }
    connection.getBalance(publicKey).then((lamports) => setBalance(lamports / LAMPORTS_PER_SOL));
  }, [connection, publicKey]);

  const update = (key: keyof ReportInput, value: string | number) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  async function handleSubmit() {
    setError(null);
    setMessage(null);
    if (!publicKey) {
      setError("Connect a wallet to submit a report.");
      return;
    }
    setWorking(true);
    try {
      const jwt = token ?? (await signIn());
      if (!jwt) {
        setError("Sign-in was cancelled.");
        return;
      }

      const report = await api.createReport(jwt, form);
      setMessage(`Draft #${report.id} created. Its content hash is ${report.content_hash}.`);

      if (file) {
        const evidence = await api.uploadEvidence(jwt, report.id, file);
        setMessage(
          `Draft #${report.id} created and evidence hashed (${evidence.evidence_hash}).`,
        );
      }

      const prepared = await api.prepare(jwt, report.id);
      setStep("signing");
      const signature = await signAndSendPrepared(prepared.transaction);
      await api.confirm(jwt, report.id, signature);

      setStep("done");
      setMessage(
        `Report anchored on-chain as #${prepared.on_chain_id}. Transaction ${signature}. ` +
          "It is now queued for verification.",
      );
      setForm(EMPTY);
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setStep("form");
    } finally {
      setWorking(false);
    }
  }

  const insufficientBalance = balance !== null && balance < 0.001;

  return (
    <>
      <h1>Submit a report</h1>
      <p className="lede">
        Your report is stored off-chain. Only a SHA-256 commitment of the
        report and its evidence is written to Solana, so you can later prove the
        report was not modified while keeping its content private.
      </p>

      {!publicKey && (
        <div className="alert info">
          <div className="row">
            <span>Connect a wallet to begin.</span>
            <WalletMultiButton />
          </div>
        </div>
      )}

      {insufficientBalance && (
        <div className="alert warning">
          Your wallet holds {balance?.toFixed(4)} SOL. Anchoring needs a small
          amount of SOL for the transaction fee. Request an airdrop on localnet
          with <span className="mono">solana airdrop 2</span>.
        </div>
      )}

      {authError && <div className="alert error">{authError}</div>}
      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      <div className="card">
        <label htmlFor="title">Short title</label>
        <input
          id="title"
          value={form.title}
          maxLength={160}
          onChange={(event) => update("title", event.target.value)}
          placeholder="Inflated road maintenance contract"
        />

        <label htmlFor="summary">One-line summary</label>
        <input
          id="summary"
          value={form.summary}
          maxLength={280}
          onChange={(event) => update("summary", event.target.value)}
          placeholder="The winning bid was 40% above the engineering estimate"
        />

        <label htmlFor="category">Category</label>
        <select
          id="category"
          value={form.category}
          onChange={(event) => update("category", Number(event.target.value))}
        >
          {categories.length === 0 && <option value={0}>bribery</option>}
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.label.replace(/_/g, " ")}
            </option>
          ))}
        </select>

        <label htmlFor="jurisdiction">Jurisdiction</label>
        <input
          id="jurisdiction"
          value={form.jurisdiction}
          onChange={(event) => update("jurisdiction", event.target.value)}
          placeholder="PL-MZ"
        />

        <label htmlFor="entity">Entity involved</label>
        <input
          id="entity"
          value={form.entity_name}
          onChange={(event) => update("entity_name", event.target.value)}
          placeholder="City Roads Authority"
        />

        <label htmlFor="description">Full description (at least 40 characters)</label>
        <textarea
          id="description"
          rows={8}
          value={form.description}
          onChange={(event) => update("description", event.target.value)}
          placeholder="Describe what happened, who was involved, and what evidence you have."
        />

        <label htmlFor="evidence">Evidence (optional, private)</label>
        <input
          id="evidence"
          type="file"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <p className="muted">
          Accepted: PDF, PNG, JPEG, plain text, CSV. The file stays off-chain;
          only its SHA-256 hash is recorded.
        </p>

        <div className="row" style={{ marginTop: 20 }}>
          <button onClick={handleSubmit} disabled={working || !publicKey || authBusy}>
            {working || authBusy
              ? "Working…"
              : step === "signing"
                ? "Waiting for signature…"
                : "Create and anchor report"}
          </button>
          <span className="muted">
            The wallet will ask you to sign once. No tokens leave your account.
          </span>
        </div>
      </div>
    </>
  );
}
