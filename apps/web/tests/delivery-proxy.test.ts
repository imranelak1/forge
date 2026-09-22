// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST, PUT } from "@/app/api/v1/[...path]/route";
const org = "11111111-1111-1111-1111-111111111111",
  id = "22222222-2222-2222-2222-222222222222";
const context = (path: string) => ({ params: Promise.resolve({ path: path.split("/") }) });
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
describe("delivery transport boundary", () => {
  it.each([
    "metrics/ci",
    "metrics/deployments",
    "workflow-runs",
    "deployments",
    `workflow-runs/${id}`,
    `deployments/${id}`,
    `workflow-runs/${id}/jobs`,
    `workflow-runs/${id}/pull-requests`,
    `workflow-runs/${id}/commits`,
    `deployments/${id}/statuses`,
    `deployments/${id}/commits`,
    `repositories/${id}/environments`,
  ])("permits scoped evidence GET %s while denying writes", async (route) => {
    const path = `organizations/${org}/${route}`;
    const fetcher = vi.fn(async () => Response.json({ items: [] }));
    vi.stubGlobal("fetch", fetcher);
    expect(
      (await GET(new Request(`http://localhost:3000/api/v1/${path}`), context(path))).status,
    ).toBe(200);
    expect(
      (
        await POST(
          new Request(`http://localhost:3000/api/v1/${path}`, { method: "POST" }),
          context(path),
        )
      ).status,
    ).toBe(405);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("forwards exact branch, workflow and completed metric-cohort filters", async () => {
    const path = `organizations/${org}/workflow-runs`;
    const params = new URLSearchParams({
      repository: id,
      workflow: "20",
      branch: "feature/ci retry",
      from: "2026-09-01T00:00:00.123456Z",
      to: "2026-09-22T00:00:00Z",
      cohort: "completed",
      metric: "queue",
      eligibility: "excluded",
      cursor: "signed",
      limit: "30",
    });
    const fetcher = vi.fn(async (url: URL) => {
      expect(url.searchParams.toString()).toBe(params.toString());
      return Response.json({ items: [] });
    });
    vi.stubGlobal("fetch", fetcher);
    expect(
      (await GET(new Request(`http://localhost:3000/api/v1/${path}?${params}`), context(path)))
        .status,
    ).toBe(200);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it.each([
    ["metrics/ci", "outcome=failure"],
    ["metrics/deployments", "cohort=success"],
    ["workflow-runs", "classification=all"],
    ["deployments", "workflow=20"],
    ["workflow-runs", "metric=cycle_time"],
    ["workflow-runs", "cohort=merged"],
    ["workflow-runs", "workflow=-1"],
    ["workflow-runs", "workflow=1.5"],
    ["deployments", "classification=guess"],
    ["deployments", "cohort=completed"],
    ["deployments", "environment=a&environment=b"],
    ["workflow-runs", "constructor=bad"],
    [`workflow-runs/${id}/jobs`, "branch=main"],
    ["deployments", `environment=${"a".repeat(256)}`],
  ])("rejects invalid or misplaced %s?%s", async (route, params) => {
    const path = `organizations/${org}/${route}`;
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (await GET(new Request(`http://localhost:3000/api/v1/${path}?${params}`), context(path)))
        .status,
    ).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("forwards policy PUT only with the existing Origin and CSRF boundary", async () => {
    vi.stubEnv("FORGE_PUBLIC_ORIGIN", "http://localhost:3000");
    const path = `organizations/${org}/repositories/${id}/environments/classification`;
    const payload = { environment: "production", classification: null };
    const fetcher = vi.fn(async (_url: URL, options: RequestInit) => {
      expect(options.method).toBe("PUT");
      expect(JSON.parse(options.body as string)).toEqual(payload);
      return Response.json({ environment: "production", override: null });
    });
    vi.stubGlobal("fetch", fetcher);
    const request = (headers: Record<string, string>) =>
      new Request(`http://localhost:3000/api/v1/${path}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(payload),
      });
    expect(
      (
        await PUT(
          request({ Origin: "https://attacker.test", "X-CSRF-Token": "token" }),
          context(path),
        )
      ).status,
    ).toBe(403);
    expect((await PUT(request({ Origin: "http://localhost:3000" }), context(path))).status).toBe(
      403,
    );
    expect(
      (
        await PUT(
          request({ Origin: "http://localhost:3000", "X-CSRF-Token": "token" }),
          context(path),
        )
      ).status,
    ).toBe(200);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("does not expose workflow run actions or logs", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    for (const suffix of ["cancel", "rerun", "logs"]) {
      const path = `organizations/${org}/workflow-runs/${id}/${suffix}`;
      expect(
        (
          await POST(
            new Request(`http://localhost:3000/api/v1/${path}`, { method: "POST" }),
            context(path),
          )
        ).status,
      ).toBe(404);
    }
    expect(fetcher).not.toHaveBeenCalled();
  });
});
