// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST, PATCH, DELETE } from "@/app/api/v1/[...path]/route";
const org = "11111111-1111-1111-1111-111111111111",
  id = "22222222-2222-2222-2222-222222222222";
const context = (path: string) => ({ params: Promise.resolve({ path: path.split("/") }) });
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
describe("test intelligence proxy boundary", () => {
  it.each([
    "metrics/tests",
    "test-runs",
    `test-runs/${id}`,
    `test-runs/${id}/suites`,
    `test-runs/${id}/cases`,
    "tests",
    `tests/${id}/history`,
    `repositories/${id}/test-policy`,
    `repositories/${id}/service-tokens`,
  ])("allows member GET %s", async (route) => {
    const path = `organizations/${org}/${route}`,
      fetcher = vi.fn(async () => Response.json({ items: [] }));
    vi.stubGlobal("fetch", fetcher);
    const result = await GET(new Request(`http://localhost:3000/api/v1/${path}`), context(path));
    expect(result.status).toBe(200);
    expect(result.headers.get("cache-control")).toBe("no-store");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it.each([
    ["metrics/tests", "status=completed"],
    ["test-runs", "status=passed"],
    [`test-runs/${id}/cases`, "status=completed"],
    [`test-runs/${id}/suites`, "status=passed"],
    ["tests", "from=2026-09-01T00%3A00%3A00Z"],
    ["tests", "potential_only=yes"],
    [`tests/${id}/history`, `repository=${id}`],
    ["test-runs", "branch=main&branch=other"],
    ["metrics/tests", "constructor=unsafe"],
    ["tests", "environment=%00bad"],
  ])("rejects out-of-contract filters %s?%s", async (route, query) => {
    const path = `organizations/${org}/${route}`,
      fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (await GET(new Request(`http://localhost:3000/api/v1/${path}?${query}`), context(path)))
        .status,
    ).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("preserves report status and exact context while allowing false potential-only", async () => {
    const fetcher = vi.fn(async (url: URL) => {
      expect(url.searchParams.get("potential_only")).toBe("false");
      expect(url.searchParams.get("branch")).toBe("feature/retry");
      return Response.json({ items: [] });
    });
    vi.stubGlobal("fetch", fetcher);
    const path = `organizations/${org}/tests`;
    expect(
      (
        await GET(
          new Request(
            `http://localhost:3000/api/v1/${path}?repository=${id}&branch=feature%2Fretry&potential_only=false`,
          ),
          context(path),
        )
      ).status,
    ).toBe(200);
  });
  it.each([
    ["PATCH", `repositories/${id}/test-policy`, { window_days: 14 }],
    ["POST", `repositories/${id}/service-tokens`, { name: "CI", expires_in_days: 30 }],
    ["DELETE", `service-tokens/${id}`, undefined],
  ])("requires origin and CSRF for %s %s", async (method, route, body) => {
    vi.stubEnv("FORGE_PUBLIC_ORIGIN", "http://localhost:3000");
    const path = `organizations/${org}/${route}`,
      fetcher = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetcher);
    const handler = method === "PATCH" ? PATCH : method === "POST" ? POST : DELETE;
    const request = (headers: Record<string, string>) =>
      new Request(`http://localhost:3000/api/v1/${path}`, {
        method,
        headers: { "Content-Type": "application/json", ...headers },
        body: body ? JSON.stringify(body) : undefined,
      });
    expect(
      (
        await handler(
          request({ origin: "https://foreign.example", "x-csrf-token": "test" }),
          context(path),
        )
      ).status,
    ).toBe(403);
    expect(
      (await handler(request({ origin: "http://localhost:3000" }), context(path))).status,
    ).toBe(403);
    expect(
      (
        await handler(
          request({ origin: "http://localhost:3000", "x-csrf-token": "test" }),
          context(path),
        )
      ).status,
    ).toBe(200);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("does not expose machine XML upload or bearer forwarding through the browser", async () => {
    const path = `organizations/${org}/repositories/${id}/test-reports`,
      fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (
        await POST(
          new Request(`http://localhost:3000/api/v1/${path}`, {
            method: "POST",
            headers: { "Content-Type": "application/xml", Authorization: "Bearer fixture_only" },
            body: "<testsuite/>",
          }),
          context(path),
        )
      ).status,
    ).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
