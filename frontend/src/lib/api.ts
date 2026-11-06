/**
 * Typed client for the CORRUPT platform API.
 *
 * The backend never sees a private key: `prepare` returns an unsigned
 * transaction that the wallet signs locally before `confirm`.
 */

const BASE = import.meta.env.VITE_API_URL ?? "";

export type ReportStatus = "draft" | "awaiting_signature" | "pending" | "verified" | "rejected";

export interface Report {
  id: number;
  reporter_wallet: string;
  title: string;
  summary: string;
  category: number;
  category_label: string;
  jurisdiction: string;
  entity_name: string;
  content_hash: string;
  evidence_hash: string | null;
  status: ReportStatus;
  on_chain_id: number | null;
  submit_signature: string | null;
  decision_signature: string | null;
  reward_amount: number | null;
  decision_note: string | null;
  created_at: string;
  anchored_at: string | null;
  decided_at: string | null;
}

export interface ReportDetail extends Report {
  description: string;
  evidence: { filename: string; media_type: string; size: number; sha256: string } | null;
  timeline: { step: string; timestamp: string; detail: string }[];
}

export interface PublicReport {
  id: number;
  category: number;
  category_label: string;
  content_hash: string;
  evidence_hash: string | null;
  status: ReportStatus;
  on_chain_id: number | null;
  reward_amount: number | null;
  created_at: string;
  anchored_at: string | null;
  decided_at: string | null;
}

export interface PlatformStats {
  total_reports: number;
  pending: number;
  verified: number;
  rejected: number;
  total_reward_paid: number;
  unique_reporters: number;
}

export interface PlatformConfig {
  authority: string;
  verifier: string;
  treasury: string;
  reward_mint: string;
  total_budget: number;
  total_distributed: number;
  remaining_budget: number;
  report_count: number;
  min_reward: number;
  max_reward: number;
  paused: boolean;
  created_at: number;
  token_symbol: string;
  token_decimals: number;
}

export interface PreparedSubmission {
  report_id: number;
  on_chain_id: number;
  transaction: string;
  content_hash: string;
  evidence_hash: string;
  program_id: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
  extraHeaders?: Record<string, string>,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (extraHeaders) {
    for (const [name, value] of Object.entries(extraHeaders)) headers.set(name, value);
  }
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface ReportInput {
  title: string;
  summary: string;
  description: string;
  category: number;
  jurisdiction: string;
  entity_name: string;
}

export const api = {
  challenge: (wallet: string) =>
    request<{ wallet: string; nonce: string; message: string; expires_at: string }>(
      "/api/auth/challenge",
      { method: "POST", body: JSON.stringify({ wallet }) },
    ),

  verify: (wallet: string, signature: string) =>
    request<{ access_token: string; expires_in: number; wallet: string; role: string }>(
      "/api/auth/verify",
      { method: "POST", body: JSON.stringify({ wallet, signature }) },
    ),

  createReport: (token: string, input: ReportInput) =>
    request<Report>("/api/reports", { method: "POST", body: JSON.stringify(input) }, token),

  uploadEvidence: (token: string, reportId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ evidence_hash: string; size: number }>(
      `/api/reports/${reportId}/evidence`,
      { method: "POST", body: form },
      token,
    );
  },

  prepare: (token: string, reportId: number) =>
    request<PreparedSubmission>(`/api/reports/${reportId}/prepare`, { method: "POST" }, token),

  confirm: (token: string, reportId: number, signature: string) =>
    request<Report>(
      `/api/reports/${reportId}/confirm`,
      { method: "POST", body: JSON.stringify({ signature }) },
      token,
    ),

  myReports: (token: string) => request<Report[]>("/api/reports/mine", {}, token),

  reportDetail: (token: string, reportId: number) =>
    request<ReportDetail>(`/api/reports/${reportId}`, {}, token),

  publicReports: (limit = 50) => request<PublicReport[]>(`/api/public/reports?limit=${limit}`),

  publicStats: () => request<PlatformStats>("/api/public/stats"),

  publicConfig: () => request<PlatformConfig>("/api/public/config"),

  categories: () => request<{ id: number; label: string }[]>("/api/public/categories"),

  ledger: (limit = 100) =>
    request<{ id: number; signature: string; name: string; payload: string; created_at: string }[]>(
      `/api/public/ledger?limit=${limit}`,
    ),

  // Verifier endpoints authenticate with a shared API key, not a wallet JWT.
  verifierQueue: (apiKey: string) =>
    request<ReportDetail[]>("/api/verifier/queue", {}, undefined, { "X-Verifier-Key": apiKey }),

  verifyReport: (apiKey: string, reportId: number, rewardAmount: number, note: string) =>
    request<Report>(
      `/api/verifier/reports/${reportId}/verify`,
      { method: "POST", body: JSON.stringify({ reward_amount: rewardAmount, note }) },
      undefined,
      { "X-Verifier-Key": apiKey },
    ),

  rejectReport: (apiKey: string, reportId: number, note: string) =>
    request<Report>(
      `/api/verifier/reports/${reportId}/reject`,
      { method: "POST", body: JSON.stringify({ note }) },
      undefined,
      { "X-Verifier-Key": apiKey },
    ),

  // Admin endpoints likewise use a shared API key.
  fundPool: (apiKey: string, amount: number) =>
    request<{ signature: string; amount: number }>(
      "/api/admin/pool/fund",
      { method: "POST", body: JSON.stringify({ amount }) },
      undefined,
      { "X-Admin-Key": apiKey },
    ),

  setPaused: (apiKey: string, paused: boolean) =>
    request<{ signature: string; paused: boolean }>(
      "/api/admin/pause",
      { method: "POST", body: JSON.stringify({ paused }) },
      undefined,
      { "X-Admin-Key": apiKey },
    ),

  auditLog: (apiKey: string, limit = 100) =>
    request<
      { id: number; actor: string; action: string; report_id: number | null; details: string; created_at: string }[]
    >(`/api/admin/audit?limit=${limit}`, {}, undefined, { "X-Admin-Key": apiKey }),
};

/** Formats base units of CORRUPT (6 decimals) for display. */
export function formatCorrupt(baseUnits: number | null | undefined, decimals = 6): string {
  if (baseUnits === null || baseUnits === undefined) return "—";
  const value = baseUnits / 10 ** decimals;
  return `${value.toLocaleString(undefined, { maximumFractionDigits: decimals })} CORRUPT`;
}

export function shortAddress(address: string, size = 4): string {
  if (address.length <= size * 2 + 3) return address;
  return `${address.slice(0, size)}…${address.slice(-size)}`;
}
