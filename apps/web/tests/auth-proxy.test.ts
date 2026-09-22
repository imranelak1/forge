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
