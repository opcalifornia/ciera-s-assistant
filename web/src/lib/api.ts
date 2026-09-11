const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const ACCESS_TOKEN_KEY = "greenroom.access_token";
const REFRESH_TOKEN_KEY = "greenroom.refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  role: "owner" | "manager" | "assistant" | "viewer";
  workspace_id: string;
}

export interface WorkspaceInfo {
  id: string;
  name: string;
  plan: string;
  kill_switch: boolean;
}

export interface Brand {
  id: string;
  persona_name: string;
  assistant_name: string;
  signature: string;
}

export type Channel = "email" | "sms" | "dm" | "intake";

export interface TriageSnapshot {
  classification: string;
  opportunity_type: string | null;
  summary: string;
  urgency: string;
  estimated_deal_value: number | null;
  flags: string[];
  missing_fields: string[];
  recommended_next_action: string;
  confidence: number;
}

export interface ThreadSummary {
  id: string;
  brand_id: string;
  channel: Channel;
  subject: string;
  participants: string[];
  last_message_at: string;
  triage: TriageSnapshot | null;
  needs_a_look: boolean;
  archived: boolean;
}

export interface MessageItem {
  id: string;
  direction: "inbound" | "outbound";
  channel: Channel;
  sender: string;
  recipients: string[];
  subject: string;
  body_text: string;
  sent_or_received_at: string;
  injection_flag: boolean;
}

export interface ThreadDetail extends ThreadSummary {
  messages: MessageItem[];
}

export type PolicyStatus = "allow" | "require_approval" | "deny";

export interface ReplyOption {
  label: string;
  strategy: string;
  tradeoff: string;
  likely_outcome: string;
  draft: string;
  numbers: Record<string, string>;
  is_recommended: boolean;
  recommendation_reason: string;
  action: string;
  policy_status: PolicyStatus;
  policy_reason: string;
}

export interface QuickReply {
  label: string;
  draft: string;
  action: string;
  policy_status: PolicyStatus;
  policy_reason: string;
}

export interface OptionSet {
  id: string;
  thread_id: string;
  playbook_id: string | null;
  options: ReplyOption[];
  quick_replies: QuickReply[];
  status: "pending" | "chosen" | "snoozed" | "dismissed";
  chosen_option_index: number | null;
}

export const api = {
  register: (payload: { workspace_name: string; email: string; password: string; full_name?: string }) =>
    request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request<Me>("/auth/me"),
  myWorkspace: () => request<WorkspaceInfo>("/workspaces/me"),
  setKillSwitch: (enabled: boolean) =>
    request<WorkspaceInfo>("/workspaces/me/kill-switch", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),

  listBrands: () => request<Brand[]>("/brands"),
  createBrand: (payload: { persona_name: string; assistant_name?: string }) =>
    request<Brand>("/brands", { method: "POST", body: JSON.stringify(payload) }),

  listThreads: () => request<ThreadSummary[]>("/threads"),
  getThread: (id: string) => request<ThreadDetail>(`/threads/${id}`),
  ingestMessage: (payload: {
    brand_id: string;
    channel: Channel;
    sender: string;
    subject: string;
    body: string;
  }) => request<ThreadSummary>("/threads/ingest", { method: "POST", body: JSON.stringify(payload) }),

  listOptionSets: (threadId: string) =>
    request<OptionSet[]>(`/threads/${threadId}/option-sets`),
  chooseOption: (
    optionSetId: string,
    payload: {
      kind: "option" | "quick_reply" | "custom";
      index?: number;
      custom_text?: string;
      adjusted_text?: string;
      send: boolean;
    },
  ) =>
    request<{ option_set: OptionSet; sent_message_id: string | null }>(
      `/option-sets/${optionSetId}/choose`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  adjustOption: (optionSetId: string, payload: { index: number; instruction: string }) =>
    request<{ draft: string }>(`/option-sets/${optionSetId}/adjust`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
