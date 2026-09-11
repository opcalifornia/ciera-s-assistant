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
};
