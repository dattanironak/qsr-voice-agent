const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";
const TOKEN_KEY = "qsr_admin_token";

export interface AdminSession {
  username: string;
  role: string;
}

export class UnauthorizedError extends Error {}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function parseErrorDetail(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = typeof body?.detail === "string" ? body.detail : null;
  return detail ?? fallback;
}

export async function login(username: string, password: string): Promise<AdminSession> {
  const res = await fetch(`${BACKEND_URL}/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res, `Login failed: ${res.status}`));
  }
  const data = await res.json();
  setToken(data.token);
  return { username: data.username, role: data.role };
}

export async function fetchMe(): Promise<AdminSession> {
  const token = getToken();
  if (!token) throw new UnauthorizedError("Not logged in");

  const res = await fetch(`${BACKEND_URL}/admin/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) {
    clearToken();
    throw new UnauthorizedError("Session expired");
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res, `GET /admin/auth/me failed: ${res.status}`));
  }
  return res.json();
}

export function logout(): void {
  clearToken();
}
