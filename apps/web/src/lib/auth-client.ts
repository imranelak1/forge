import type { Identity } from "./auth-types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  refresh?: boolean;
};
let refreshInFlight: Promise<boolean> | undefined;

async function errorFrom(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => ({}));
  const detail =
    typeof body.detail === "string"
      ? body.detail
      : response.status === 422
        ? "Check the form fields and try again."
        : "The request could not be completed. Please try again.";
  return new ApiError(
    response.status,
    detail,
    typeof body.code === "string" ? body.code : undefined,
  );
}

async function csrf(): Promise<string> {
  // Fetch fresh binding for each write: another tab may have logged in or rotated a session.
  const response = await fetch("/api/v1/auth/csrf", {
    credentials: "same-origin",
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw await errorFrom(response);
  const body = await response.json();
  if (typeof body.csrf_token !== "string")
    throw new ApiError(503, "Session protection is unavailable. Please retry.");
  return body.csrf_token;
}

async function send(path: string, options: Options = {}) {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = await csrf();
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  return fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
    signal: options.signal
      ? AbortSignal.any([options.signal, AbortSignal.timeout(20_000)])
      : AbortSignal.timeout(20_000),
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
}

async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const rotate = async () => {
    // A different tab may already have refreshed while this tab waited for the browser-wide lock.
    const current = await send("/auth/me");
    if (current.ok) return true;
    if (current.status !== 401) throw await errorFrom(current);
    const response = await send("/auth/refresh", { method: "POST" });
    if (response.status === 401 || response.status === 403) return false;
    if (!response.ok) throw await errorFrom(response);
    return true;
  };
  // Never rotate concurrently across tabs in browsers without the Web Locks API.
  // Those browsers can still use an active session and sign in again when it expires.
  refreshInFlight = (async () => {
    if (typeof navigator !== "undefined" && navigator.locks)
      return await navigator.locks.request("forge-session-refresh", rotate);
    return false;
  })().finally(() => {
    refreshInFlight = undefined;
  });
  return refreshInFlight;
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  let response: Response;
  try {
    response = await send(path, options);
    if (response.status === 401 && options.refresh !== false && (await refreshSession())) {
      response = await send(path, options);
    }
  } catch (error) {
    if (error instanceof ApiError || (error instanceof DOMException && error.name === "AbortError"))
      throw error;
    throw new ApiError(503, "Forge could not be reached. Check your connection and try again.");
  }
  if (!response.ok) {
    if (response.status === 401 && options.refresh !== false)
      window.dispatchEvent(new Event("forge:session-ended"));
    throw await errorFrom(response);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const getIdentity = (signal?: AbortSignal) => api<Identity>("/auth/me", { signal });
export function safeReturn(value: string | null | undefined) {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020]/.test(value))
    return "/app";
  try {
    const target = new URL(value, "https://forge.invalid");
    if (target.origin !== "https://forge.invalid" || !/^\/app(?:\/|$)/.test(target.pathname))
      return "/app";
    return `${target.pathname}${target.search}`;
  } catch {
    return "/app";
  }
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}
