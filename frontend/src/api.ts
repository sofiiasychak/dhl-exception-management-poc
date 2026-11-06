import { mockApiRequest, publicDemoMode } from "./mockApi";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";
const TOKEN_KEY = "exception-management-id-token";

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  if (publicDemoMode) return mockApiRequest<T>(path, init);
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(payload.detail ?? `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function postJson<T>(path: string, value: unknown): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body: JSON.stringify(value) });
}

export function postForm<T>(path: string, value: FormData): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body: value });
}
