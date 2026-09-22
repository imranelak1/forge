import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OverviewPage } from "@/features/analytics/overview-page";
import {
  CommitDetail,
  HistoryPage,
  PullRequestDetail,
  RepositoryIssues,
} from "@/features/analytics/history-pages";
import { FilterBar } from "@/features/analytics/analytics-ui";
import {
  duration,
  evidenceHref,
  readFilters,
  sourceUrl,
  type Commit,
  type Distribution,
  type Metrics,
  type PullRequest,
} from "@/features/analytics/types";
import { api } from "@/lib/auth-client";

const state = vi.hoisted(() => ({
  organization: "11111111-1111-1111-1111-111111111111",
  query: "",
  replace: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(state.query),
  usePathname: () => "/app",
  useRouter: () => ({ replace: state.replace }),
}));
vi.mock("@/features/auth/auth-provider", () => ({
  useAuth: () => ({
    organization: { id: state.organization, name: "Synthetic team", role: "viewer", is_demo: true },
  }),
}));
vi.mock("@/lib/auth-client", async () => ({
  ...(await vi.importActual<typeof import("@/lib/auth-client")>("@/lib/auth-client")),
  api: vi.fn(),
}));
const org = "11111111-1111-1111-1111-111111111111";
const repo = "22222222-2222-2222-2222-222222222222";
const prId = "33333333-3333-3333-3333-333333333333";
const commitId = "44444444-4444-4444-4444-444444444444";
const complete = {
  status: "complete" as const,
  observed_at: "2026-09-22T00:00:00Z",
  error_code: null,
};
const windowValue = { from: "2026-09-01T13:01:00Z", to: "2026-09-22T12:02:00Z" };
const dist: Distribution = {
  sample_count: 7,
  excluded_count: 2,
  mean_seconds: 14400,
  median_seconds: 7200,
  p75_seconds: 21600,
  p95_seconds: 43200,
  exclusions: { incomplete_reviews: 2 },
};
const missing: Distribution = {
  sample_count: 0,
  excluded_count: 9,
  mean_seconds: null,
  median_seconds: null,
  p75_seconds: null,
  p95_seconds: null,
  exclusions: { missing_approval: 9 },
};
const pr: PullRequest = {
  id: prId,
  repository_id: repo,
  repository_name: "fixture/api",
  number: 18,
  title: "Keep source context",
  state: "closed",
  draft: false,
  author_login: "maya",
  html_url: null,
  opened_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-02T00:00:00Z",
  closed_at: null,
  merged_at: "2026-09-02T00:00:00Z",
  head_sha: "a".repeat(40),
  base_ref: "main",
  merge_commit_sha: "b".repeat(40),
  durations: { cycle_time: 86400, review_wait: null, approval_to_merge: null },
  exclusions: {
    cycle_time: null,
    review_wait: "incomplete_reviews",
    approval_to_merge: "unknown_dismissed_review",
  },
  first_review_at: null,
  first_approved_at: null,
  approval_dismissed: true,
  unknown_dismissed_review_count: 1,
  coverage: {
    reviews: { ...complete, status: "partial" },
    transitions: complete,
    commits: complete,
    issues: { status: "unavailable", observed_at: null, error_code: "issues_permission_missing" },
  },
};
const commit: Commit = {
  id: commitId,
  repository_id: repo,
  repository_name: "fixture/api",
  sha: "a".repeat(40),
  message: "Bound worker retries\n\nKeep checkpoint on transient failure.",
  author_login: "maya",
  authored_at: null,
  committed_at: "2026-09-02T00:00:00Z",
  html_url: null,
  additions: null,
  deletions: null,
  changed_files: null,
  files_coverage: { status: "pending", observed_at: null, error_code: null },
  pull_request_count: 1,
};
const metrics: Metrics = {
  formula_version: "pr-flow-v1",
  as_of: windowValue.to,
  window: windowValue,
  scope: { repository_id: repo, selected_only: false, repository_count: 1 },
  merged_count: 9,
  metrics: { cycle_time: dist, review_wait: dist, approval_to_merge: missing },
  trend: [
    {
      date: "2026-09-01",
      merged_count: 9,
      metrics: { cycle_time: dist, review_wait: dist, approval_to_merge: missing },
    },
  ],
  open_queue: { count: 0, age: { ...missing, excluded_count: 0 }, oldest: [] },
  coverage: {
    status: "partial",
    input_watermark: null,
    repository_count: 1,
    repositories_synced: 1,
    reviews_complete: 7,
    reviews_incomplete: 2,
    dismissed_approval_count: 1,
    unknown_dismissed_review_count: 1,
    unknown_reviewer_count: 0,
    limitations: ["history_window_partial"],
  },
};
const paged = <T,>(items: T[], next_cursor: string | null = null) => ({
  items,
  next_cursor,
  window: windowValue,
});
function provider(children: React.ReactNode) {
  return (
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      {children}
    </QueryClientProvider>
  );
}
function mockApi(handle: (path: string) => unknown) {
  vi.mocked(api).mockImplementation(async (path) => handle(path) as never);
}
beforeEach(() => {
  vi.clearAllMocks();
  state.organization = org;
  state.query = "";
});

describe("analytics presentation contracts", () => {
  it("distinguishes missing durations from a measured zero", () => {
    expect(duration(null)).toBe("Not available");
    expect(duration(-1)).toBe("Not available");
    expect(duration(0)).toBe("0 sec");
    expect(duration(7200)).toBe("2 hr");
    expect(duration(172800)).toBe("2 days");
  });
  it("preserves the exact cohort and eligibility in evidence links", () => {
    const url = new URL(
      evidenceHref({ repository: repo, author: "maya" }, windowValue, "review_wait", "excluded"),
      "https://forge.test",
    );
    expect(Object.fromEntries(url.searchParams)).toEqual({
      repository: repo,
      author: "maya",
      ...windowValue,
      cohort: "merged",
      metric: "review_wait",
      eligibility: "excluded",
    });
  });
  it("only accepts safe source links and bounded known filter values", () => {
    expect(sourceUrl("javascript:alert(1)")).toBeNull();
    expect(sourceUrl("https://github.com.attacker.test/a/b/pull/1")).toBeNull();
    expect(sourceUrl("https://github.com/user:pass@evil.test/a/b/pull/1")).toBeNull();
    expect(sourceUrl(null)).toBeNull();
    expect(sourceUrl("https://github.com/a/b/pull/1#review-4")).toContain("#review-4");
    expect(
      readFilters(
        new URLSearchParams(
          "repository=foreign&cohort=bad&author=dependabot%5Bbot%5D&metric=review_wait&state=open&from=2026-01-01T00:00:00",
        ),
        "pull-requests",
      ),
    ).toEqual({
      author: "dependabot[bot]",
      metric: "review_wait",
      state: "open",
      cohort: "merged",
    });
  });
  it("renders authoritative distributions, exclusions and a separate queue without invented zeros", async () => {
    state.query = `repository=${repo}&author=maya`;
    mockApi((path) => (path.includes("/metrics/") ? metrics : paged([])));
    render(provider(<OverviewPage />));
    const row = await screen.findByRole("row", { name: /Approval to merge First known/ });
    expect(within(row).getAllByText("Not available")).toHaveLength(4);
    expect(within(row).getByRole("link", { name: "9 excluded" })).toHaveAttribute(
      "href",
      evidenceHref(
        { repository: repo, author: "maya" },
        windowValue,
        "approval_to_merge",
        "excluded",
      ),
    );
    const cycle = screen.getByRole("row", { name: /Cycle time Opened to merged/ });
    expect(within(cycle).getByText("4 hr")).toBeVisible();
    expect(within(cycle).getByText("2 hr")).toBeVisible();
    expect(within(cycle).getByText("12 hr")).toBeVisible();
    expect(screen.getByText(/Imported history does not cover the entire/)).toBeVisible();
    expect(screen.getByText(/This current queue is separate/)).toBeVisible();
    expect(within(row).queryByText("0 sec")).not.toBeInTheDocument();
  });
  it("validates the date range before applying filters and supports exact bot author searches", async () => {
    const apply = vi.fn();
    mockApi(() => paged([]));
    render(
      provider(
        <FilterBar
          organization={org}
          filters={{ from: windowValue.to, to: windowValue.from }}
          kind="commits"
          apply={apply}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose an end after the start");
    expect(apply).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Before (UTC)"), {
      target: { value: "2026-09-24T00:00:00" },
    });
    fireEvent.change(screen.getByLabelText("GitHub author"), {
      target: { value: "dependabot[bot]" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(apply).toHaveBeenCalledWith(
      expect.objectContaining({
        author: "dependabot[bot]",
        from: windowValue.to,
        to: "2026-09-24T00:00:00.000Z",
      }),
    );
  });
  it("keeps loaded commits when the next page fails and retries the same cursor", async () => {
    let failed = false;
    mockApi((path) => {
      if (path.includes("/repositories?")) return paged([]);
      if (path.includes("cursor=next-token")) {
        if (!failed) {
          failed = true;
          throw new Error("Next page unavailable");
        }
        return paged([
          { ...commit, id: "55555555-5555-5555-5555-555555555555", message: "Second commit" },
        ]);
      }
      return paged([commit], "next-token");
    });
    render(provider(<HistoryPage kind="commits" />));
    await screen.findByRole("link", { name: "Bound worker retries" });
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Next page unavailable");
    expect(screen.getByRole("link", { name: "Bound worker retries" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading more" }));
    expect(await screen.findByRole("link", { name: "Second commit" })).toBeVisible();
    expect(
      vi.mocked(api).mock.calls.filter(([path]) => path.includes("cursor=next-token")),
    ).toHaveLength(2);
  });
  it("clears old tenant history immediately when the organization changes", async () => {
    mockApi((path) =>
      path.includes("/repositories?") || !path.includes(org) ? paged([]) : paged([commit]),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = () => (
      <QueryClientProvider client={client}>
        <HistoryPage kind="commits" />
      </QueryClientProvider>
    );
    const { rerender } = render(view());
    await screen.findByRole("link", { name: "Bound worker retries" });
    state.organization = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    rerender(view());
    expect(screen.queryByRole("link", { name: "Bound worker retries" })).not.toBeInTheDocument();
    await screen.findByText("0 records loaded");
    expect(vi.mocked(api).mock.calls.some(([path]) => path.includes(state.organization))).toBe(
      true,
    );
  });
  it("shows partial review and historical dismissal evidence without claiming an approval", async () => {
    mockApi((path) =>
      path.endsWith(`/pull-requests/${prId}`)
        ? { pull_request: pr, counts: { reviews: 1, transitions: 1, commits: 0, issues: 0 } }
        : path.includes("/reviews?")
          ? paged([
              {
                id: "review",
                reviewer_login: "maya",
                reviewer_type: "User",
                state: "DISMISSED",
                submitted_at: windowValue.from,
                approved_at: null,
                dismissed_at: windowValue.to,
                html_url: null,
                qualifies: false,
                approval_known: false,
              },
            ])
          : path.includes("/transitions?")
            ? paged([
                {
                  id: "transition",
                  kind: "reopened",
                  occurred_at: windowValue.from,
                  actor_login: "maya",
                  html_url: null,
                },
              ])
            : paged([]),
    );
    render(provider(<PullRequestDetail id={prId} />));
    await screen.findByRole("heading", { name: "Keep source context" });
    expect(await screen.findByText("Original review state not known.")).toBeVisible();
    expect(screen.getByText("Reopened")).toBeVisible();
    expect(screen.getByText(/not current merge authorization/)).toBeVisible();
    expect(screen.queryByRole("link", { name: "View on GitHub" })).not.toBeInTheDocument();
    expect(screen.getByText(/Issues permission not granted/)).toBeVisible();
  });
  it("keeps unimported file totals unavailable and displays explicit PR associations", async () => {
    mockApi((path) =>
      path.endsWith(`/commits/${commitId}`)
        ? { commit }
        : path.includes("/pull-requests?")
          ? paged([{ ...pr, relationship: "merge" }])
          : paged([]),
    );
    render(provider(<CommitDetail id={commitId} />));
    await screen.findByRole("heading", { name: "Bound worker retries" });
    expect(screen.getByText("Files not observed · Line totals unavailable")).toBeVisible();
    expect(screen.getByText("Import pending")).toBeVisible();
    expect(await screen.findByRole("link", { name: pr.title })).toBeVisible();
    expect(screen.getByText(/Merge commit/)).toBeVisible();
  });
  it("discloses missing Issues permission while retaining the rest of the history navigation", async () => {
    mockApi((path) =>
      path.includes("/issues?")
        ? {
            ...paged([]),
            coverage: {
              status: "unavailable",
              observed_at: null,
              error_code: "issues_permission_missing",
            },
          }
        : paged([]),
    );
    render(provider(<RepositoryIssues id={repo} />));
    expect(await screen.findByText("Issues: Unavailable")).toBeVisible();
    expect(
      screen.getByText(/missing permission does not stop PR and commit imports/),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Repositories" })).toHaveAttribute(
      "href",
      "/app/repositories",
    );
  });
  it("retries a failed metric request", async () => {
    let fail = true;
    mockApi((path) => {
      if (!path.includes("/metrics/")) return paged([]);
      if (fail) {
        fail = false;
        throw new Error("Database temporarily unavailable");
      }
      return metrics;
    });
    render(provider(<OverviewPage />));
    expect(await screen.findByRole("alert")).toHaveTextContent("Database temporarily unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Merged pull requests" })).toBeVisible(),
    );
  });
  it("refreshes a detail and its child evidence together after a background import", async () => {
    let observed = false;
    mockApi((path) =>
      path.endsWith(`/commits/${commitId}`)
        ? {
            commit: observed
              ? {
                  ...commit,
                  changed_files: 1,
                  additions: 3,
                  deletions: 1,
                  files_coverage: complete,
                }
              : commit,
          }
        : path.includes("/files?") && observed
          ? paged([
              {
                id: "file",
                filename: "src/retry.ts",
                previous_filename: null,
                status: "modified",
                additions: 3,
                deletions: 1,
                changes: 4,
                blob_url: null,
              },
            ])
          : paged([]),
    );
    render(provider(<CommitDetail id={commitId} />));
    await screen.findByText("Files not observed · Line totals unavailable");
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh data" })).toBeEnabled());
    observed = true;
    fireEvent.click(screen.getByRole("button", { name: "Refresh data" }));
    expect(await screen.findByText("src/retry.ts")).toBeVisible();
    expect(screen.getByText("1 files · +3 / −1 lines")).toBeVisible();
  });
});
