// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/v1/[...path]/route";
const org = "11111111-1111-1111-1111-111111111111";
const resource = "22222222-2222-2222-2222-222222222222";
const context = (path: string) => ({ params: Promise.resolve({ path: path.split("/") }) });
afterEach(() => vi.unstubAllGlobals());
describe("analytics transport boundary", () => {
  it.each([
    "metrics/pull-requests",
    "pull-requests",
    "commits",
    `pull-requests/${resource}`,
    `commits/${resource}`,
    `issues/${resource}`,
    ...["reviews", "transitions", "commits", "issues"].map(
      (kind) => `pull-requests/${resource}/${kind}`,
    ),
    `commits/${resource}/files`,
    `commits/${resource}/pull-requests`,
    `issues/${resource}/pull-requests`,
    `repositories/${resource}/issues`,
  ])("allows the scoped GET %s without permitting mutations", async (route) => {
    const path = `organizations/${org}/${route}`;
    const fetcher = vi.fn(async () => Response.json({ items: [] }));
    vi.stubGlobal("fetch", fetcher);
    const response = await GET(new Request(`http://localhost:3000/api/v1/${path}`), context(path));
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
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
  it("forwards the exact UTC cohort, author, repository and pagination token", async () => {
    const path = `organizations/${org}/pull-requests`;
    const params = new URLSearchParams({
      repository: resource,
      author: "dependabot[bot]",
      from: "2026-06-01T12:01:02.123456Z",
      to: "2026-09-01T12:01:02+00:00",
      metric: "review_wait",
      cohort: "merged",
      eligibility: "excluded",
      state: "merged",
      cursor: "signed-cursor",
      limit: "30",
    });
    const fetcher = vi.fn(async (url: URL) => {
      expect(url.searchParams.toString()).toBe(params.toString());
      return Response.json({ items: [], next_cursor: null });
    });
    vi.stubGlobal("fetch", fetcher);
    expect(
      (await GET(new Request(`http://localhost:3000/api/v1/${path}?${params}`), context(path)))
        .status,
    ).toBe(200);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it.each([
    ["commits", "metric=cycle_time"],
    ["metrics/pull-requests", "cohort=activity"],
    ["pull-requests", "repository=foreign"],
    ["pull-requests", "metric=unknown"],
    ["pull-requests", "eligibility=maybe"],
    ["pull-requests", "cohort=updated"],
    ["pull-requests", "state=unknown"],
    ["pull-requests", "from=2026-09-01T00:00:00"],
    ["pull-requests", "author=maya&author=evan"],
    ["pull-requests", "constructor=abc"],
    ["repositories", "from=2026-09-01T00:00:00Z"],
    [`commits/${resource}/files`, "repository=" + resource],
    [`repositories/${resource}/issues`, "state=merged"],
    ["pull-requests", `author=${"a".repeat(101)}`],
  ])("rejects unsupported or malformed query for %s: %s", async (route, query) => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const path = `organizations/${org}/${route}`;
    expect(
      (await GET(new Request(`http://localhost:3000/api/v1/${path}?${query}`), context(path)))
        .status,
    ).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("does not expose unrecognized evidence routes", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const path = `organizations/${org}/commits/${resource}/patches`;
    expect(
      (await GET(new Request(`http://localhost:3000/api/v1/${path}`), context(path))).status,
    ).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
