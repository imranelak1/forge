import { describe, expect, it, vi } from "vitest";
import { api, ApiError, safeReturn } from "@/lib/auth-client";

describe("authentication navigation", () => {
  it("only returns local workspace paths", () => {
    expect(safeReturn("/app/settings?tab=members")).toBe("/app/settings?tab=members");
    for (const value of [
      "https://other.test/app",
      "//other.test/app",
      "/\\other.test",
      "javascript:alert(1)",
      "/login",
      "/app\n/evil",
      "https://forge.invalid/app",
    ]) {
      expect(safeReturn(value)).toBe("/app");
    }
  });
});

describe("cookie session client", () => {
  it("uses a fresh CSRF binding on writes and never sends credentials as an authorization header", async () => {
    const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
      if (url.endsWith("/csrf")) return Response.json({ csrf_token: "bound-token" });
      expect(options?.headers).toMatchObject({
        "X-CSRF-Token": "bound-token",
        "Content-Type": "application/json",
      });
      expect(new Headers(options?.headers).has("Authorization")).toBe(false);
      expect(options?.credentials).toBe("same-origin");
      return Response.json({ id: "organization" });
    });
    vi.stubGlobal("fetch", fetcher);
    await api("/organizations", { method: "POST", body: { name: "Team", slug: "team" } });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("coalesces expired requests, checks the session inside a browser-wide lock, then retries", async () => {
    let refreshed = false;
    const calls: string[] = [];
    const lock = vi.fn(async (_name: string, callback: () => Promise<boolean>) => callback());
    vi.stubGlobal("navigator", { locks: { request: lock } });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        if (url.endsWith("/csrf")) return Response.json({ csrf_token: "bound-token" });
        if (url.endsWith("/refresh")) {
          await new Promise((resolve) => setTimeout(resolve, 5));
          refreshed = true;
          return Response.json({ user: {} });
        }
        return refreshed
          ? Response.json({ ok: true })
          : Response.json({ detail: "Expired" }, { status: 401 });
      }),
    );
    await expect(Promise.all([api("/organizations"), api("/auth/sessions")])).resolves.toEqual([
      { ok: true },
      { ok: true },
    ]);
    expect(lock).toHaveBeenCalledTimes(1);
    expect(lock.mock.calls[0][0]).toBe("forge-session-refresh");
    expect(calls.filter((url) => url.endsWith("/refresh"))).toHaveLength(1);
    expect(calls.indexOf("/api/v1/auth/me")).toBeLessThan(calls.indexOf("/api/v1/auth/refresh"));
  });

  it("does not rotate again when another tab refreshed before the lock was acquired", async () => {
    let first = true;
    const calls: string[] = [];
    vi.stubGlobal("navigator", {
      locks: { request: async (_name: string, callback: () => Promise<boolean>) => callback() },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        if (first) {
          first = false;
          return Response.json({ detail: "Expired" }, { status: 401 });
        }
        return Response.json({ ok: true });
      }),
    );
    await expect(api("/organizations")).resolves.toEqual({ ok: true });
    expect(calls).toEqual(["/api/v1/organizations", "/api/v1/auth/me", "/api/v1/organizations"]);
  });

  it("does not retry a rejected login or silently retry a permission error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.endsWith("/csrf")
          ? Response.json({ csrf_token: "token" })
          : Response.json({ detail: "Not permitted" }, { status: 403 }),
      ),
    );
    await expect(
      api("/auth/login", { method: "POST", refresh: false, body: {} }),
    ).rejects.toMatchObject({ status: 403 });
    await expect(api("/organizations")).rejects.toBeInstanceOf(ApiError);
  });
});
