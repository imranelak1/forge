// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { DELETE, GET, POST } from "@/app/api/v1/[...path]/route";

const context = (path: string) => ({ params: Promise.resolve({ path: path.split("/") }) });
const write = (path: string, overrides: RequestInit = {}) =>
  new Request(`http://localhost:3000/api/v1/${path}`, {
    method: "POST",
    headers: {
      Origin: "http://localhost:3000",
      "X-CSRF-Token": "token",
      "Content-Type": "application/json",
    },
    body: "{}",
    ...overrides,
  });
afterEach(() => {
  vi.unstubAllEnvs();
});

describe("authentication transport boundary", () => {
  it.each([
    ["POST", "auth/logout"],
    ["POST", "auth/refresh"],
    ["DELETE", "auth/sessions/11111111-1111-1111-1111-111111111111"],
    [
      "DELETE",
      "organizations/11111111-1111-1111-1111-111111111111/members/22222222-2222-2222-2222-222222222222",
    ],
  ])("forwards a bodyless %s %s when Next exposes an empty body stream", async (method, path) => {
    vi.stubEnv("FORGE_PUBLIC_ORIGIN", "http://localhost:3000");
    const fetcher = vi.fn(async (_url: URL, options: RequestInit) => {
      expect(options.method).toBe(method);
      expect(options.body).toBeUndefined();
      expect(new Headers(options.headers).has("Content-Type")).toBe(false);
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal("fetch", fetcher);
    const request = new Request(`http://localhost:3000/api/v1/${path}`, {
      method,
      headers: { Origin: "http://localhost:3000", "X-CSRF-Token": "token" },
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.close();
        },
      }),
      duplex: "half",
    } as RequestInit & { duplex: "half" });
    expect(request.body).not.toBeNull();
    const response = await (method === "POST" ? POST : DELETE)(request, context(path));
    expect(response.status).toBe(204);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("still requires JSON for a nonempty request payload", async () => {
    vi.stubEnv("FORGE_PUBLIC_ORIGIN", "http://localhost:3000");
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = await POST(
      write("auth/login", {
        headers: {
          Origin: "http://localhost:3000",
          "X-CSRF-Token": "token",
          "Content-Type": "text/plain",
        },
        body: "nonempty",
      }),
      context("auth/login"),
    );
    expect(response.status).toBe(415);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects unknown routes, invalid identifiers and disallowed methods before contacting the API", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (await GET(new Request("http://localhost:3000/api/v1/admin"), context("admin"))).status,
    ).toBe(404);
    expect(
      (
        await GET(
          new Request("http://localhost:3000/api/v1/organizations/../../admin"),
          context("organizations/../../admin"),
        )
      ).status,
    ).toBe(404);
    expect(
      (
        await DELETE(
          new Request("http://localhost:3000/api/v1/auth/me", { method: "DELETE" }),
          context("auth/me"),
        )
      ).status,
    ).toBe(405);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects foreign origins, absent CSRF tokens and oversized request bodies", async () => {
    vi.stubEnv("FORGE_PUBLIC_ORIGIN", "http://localhost:3000");
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (
        await POST(
          write("auth/login", {
            headers: { Origin: "https://attacker.test", "X-CSRF-Token": "token" },
          }),
          context("auth/login"),
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await POST(
          write("auth/login", { headers: { Origin: "http://localhost:3000" } }),
          context("auth/login"),
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await POST(
          write("auth/login", { body: JSON.stringify({ password: "a".repeat(20_000) }) }),
          context("auth/login"),
        )
      ).status,
    ).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("forwards only Forge cookies and real browser origin while preserving multiple Set-Cookie headers", async () => {
    vi.stubEnv("FORGE_PUBLIC_ORIGIN", "http://localhost:3000");
    vi.stubEnv("API_INTERNAL_URL", "http://backend:8000");
    const cookies = new Headers({ "Content-Type": "application/json" });
    cookies.append("Set-Cookie", "forge_access=access; HttpOnly; Path=/");
    cookies.append("Set-Cookie", "forge_refresh=refresh; HttpOnly; Path=/api/v1/auth");
    const fetcher = vi.fn(async (_url: URL, options: RequestInit) => {
      const headers = new Headers(options.headers);
      expect(headers.get("Cookie")).toBe("forge_preauth=anonymous; forge_csrf=csrf");
      expect(headers.get("Origin")).toBe("http://localhost:3000");
      expect(headers.has("Authorization")).toBe(false);
      expect(options.redirect).toBe("error");
      return new Response(JSON.stringify({ user: { id: "user" } }), { headers: cookies });
    });
    vi.stubGlobal("fetch", fetcher);
    const request = write("auth/login", {
      headers: {
        Origin: "http://localhost:3000",
        "X-CSRF-Token": "token",
        "Content-Type": "application/json",
        Cookie: "unrelated=secret; forge_preauth=anonymous; forge_csrf=csrf",
        Authorization: "Bearer ignored",
      },
    });
    const response = await POST(request, context("auth/login"));
    expect(response.status).toBe(200);
    expect(response.headers.getSetCookie()).toHaveLength(2);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(String(fetcher.mock.calls[0][0])).toBe("http://backend:8000/api/v1/auth/login");
  });

  it("allows only bounded pagination query parameters", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = await GET(
      new Request("http://localhost:3000/api/v1/organizations?upstream=https://attacker.test"),
      context("organizations"),
    );
    expect(response.status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("returns a recoverable error if the upstream is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));
    const response = await GET(
      new Request("http://localhost:3000/api/v1/auth/me"),
      context("auth/me"),
    );
    expect(response.status).toBe(503);
    expect((await response.json()).detail).toContain("could not be reached");
  });
});

describe("OAuth transport boundary", () => {
  it.each(["github", "google"])(
    "forwards %s callback without following redirects and preserves session cookies",
    async (provider) => {
      const route = `auth/oauth/${provider}/callback`;
      const fetcher = vi.fn(async (url: URL, options: RequestInit) => {
        expect(url.searchParams.get("code")).toBe("single-use-code");
        expect(url.searchParams.get("state")).toBe("browser-bound-state");
        expect(url.searchParams.get("iss")).toBe(
          provider === "google" ? "https://accounts.google.com" : "https://github.com/login/oauth",
        );
        expect(options.redirect).toBe("manual");
        expect(new Headers(options.headers).get("Cookie")).toBe("forge_oauth=binding");
        const headers = new Headers({ Location: "/app?oauth=signed-in" });
        headers.append("Set-Cookie", "forge_access=session; HttpOnly; Path=/api/v1");
        headers.append("Set-Cookie", "forge_oauth=; Max-Age=0; HttpOnly; Path=/api/v1/auth/oauth");
        return new Response(null, { status: 303, headers });
      });
      vi.stubGlobal("fetch", fetcher);
      const result = await GET(
        new Request(
          `http://localhost:3000/api/v1/${route}?code=single-use-code&state=browser-bound-state&iss=${encodeURIComponent(provider === "google" ? "https://accounts.google.com" : "https://github.com/login/oauth")}&scope=openid&authuser=0&prompt=consent&hd=example.com`,
          { headers: { Cookie: "forge_oauth=binding; unrelated=private" } },
        ),
        context(route),
      );
      expect(result.status).toBe(303);
      expect(result.headers.get("Location")).toBe("/app?oauth=signed-in");
      expect(result.headers.getSetCookie()).toHaveLength(2);
      expect(result.headers.get("Referrer-Policy")).toBe("no-referrer");
      expect(result.headers.get("Cache-Control")).toBe("no-store");
      expect(fetcher).toHaveBeenCalledTimes(1);
    },
  );

  it.each([
    "code=one&code=two",
    "state=one&state=two",
    "error=one&error=two",
    "iss=https://accounts.google.com&iss=https://attacker.example",
  ])("rejects ambiguous callback parameters: %s", async (query) => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (
        await GET(
          new Request(`http://localhost:3000/api/v1/auth/oauth/github/callback?${query}`),
          context("auth/oauth/github/callback"),
        )
      ).status,
    ).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("discards unrecognized callback extensions instead of rejecting the provider response", async () => {
    const fetcher = vi.fn(async (url: URL) => {
      expect([...url.searchParams]).toEqual([
        ["code", "one"],
        ["state", "bound"],
      ]);
      return new Response(null, { status: 303, headers: { Location: "/app?oauth=signed-in" } });
    });
    vi.stubGlobal("fetch", fetcher);
    const result = await GET(
      new Request(
        "http://localhost:3000/api/v1/auth/oauth/google/callback?code=one&state=bound&provider_extension=value&returnTo=https://attacker.example&toString=prototype",
      ),
      context("auth/oauth/google/callback"),
    );
    expect(result.status).toBe(303);
    expect(result.headers.get("Location")).toBe("/app?oauth=signed-in");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([`iss=${"x".repeat(2049)}`, `provider_extension=${"x".repeat(16_384)}`])(
    "retains callback size limits",
    async (query) => {
      const fetcher = vi.fn();
      vi.stubGlobal("fetch", fetcher);
      const result = await GET(
        new Request(`http://localhost:3000/api/v1/auth/oauth/google/callback?${query}`),
        context("auth/oauth/google/callback"),
      );
      expect(result.status).toBe(400);
      expect(fetcher).not.toHaveBeenCalled();
    },
  );

  it.each([
    "https://attacker.example/",
    "//attacker.example/",
    "/login?oauth_error=unknown",
    "/app/../../login?arbitrary=true",
  ])("blocks unsafe upstream redirect %s before exposing cookies", async (destination) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(null, {
          status: 303,
          headers: { Location: destination, "Set-Cookie": "forge_access=untrusted" },
        }),
      ),
    );
    const result = await GET(
      new Request("http://localhost:3000/api/v1/auth/oauth/google/callback?state=opaque"),
      context("auth/oauth/google/callback"),
    );
    expect(result.status).toBe(502);
    expect(result.headers.has("Location")).toBe(false);
    expect(result.headers.getSetCookie()).toHaveLength(0);
  });

  it("requires origin and CSRF protection before starting either provider", async () => {
    vi.stubEnv("FORGE_PUBLIC_ORIGIN", "http://localhost:3000");
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (
        await POST(
          write("auth/oauth/github/start", {
            headers: { Origin: "https://attacker.example", "X-CSRF-Token": "token" },
          }),
          context("auth/oauth/github/start"),
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await POST(
          write("auth/oauth/google/start", { headers: { Origin: "http://localhost:3000" } }),
          context("auth/oauth/google/start"),
        )
      ).status,
    ).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("accepts a fixed provider cancellation redirect without revealing the provider description", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(null, { status: 303, headers: { Location: "/login?oauth_error=denied" } }),
        ),
    );
    const result = await GET(
      new Request(
        "http://localhost:3000/api/v1/auth/oauth/google/callback?error=access_denied&error_description=private&error_uri=https%3A%2F%2Fprovider.example%2Fhelp&state=opaque",
      ),
      context("auth/oauth/google/callback"),
    );
    expect(result.status).toBe(303);
    expect(result.headers.get("Location")).toBe("/login?oauth_error=denied");
    expect(await result.text()).toBe("");
  });
});
