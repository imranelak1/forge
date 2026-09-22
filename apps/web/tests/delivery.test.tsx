import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeliveryPage } from "@/features/delivery/delivery-pages";
import { DeliveryDetail } from "@/features/delivery/delivery-details";
import { EnvironmentPage } from "@/features/delivery/environment-page";
import {
  ciEvidence,
  deliverySource,
  deploymentEvidence,
  fraction,
  type CIMetrics,
  type Deployment,
  type DeploymentMetrics,
  type EnvironmentPolicy,
  type WorkflowRun,
} from "@/features/delivery/types";
import { api } from "@/lib/auth-client";
const state = vi.hoisted(() => ({
  organization: "11111111-1111-1111-1111-111111111111",
  role: "owner",
  verified: true,
  query: "",
  replace: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(state.query),
  usePathname: () => "/app/ci",
  useRouter: () => ({ replace: state.replace }),
}));
vi.mock("@/features/auth/auth-provider", () => ({
  useAuth: () => ({
    organization: {
      id: state.organization,
      name: "Synthetic delivery",
      role: state.role,
      is_demo: true,
    },
    identity: { user: { email_verified: state.verified } },
  }),
}));
vi.mock("@/lib/auth-client", async () => ({
  ...(await vi.importActual<typeof import("@/lib/auth-client")>("@/lib/auth-client")),
  api: vi.fn(),
}));
const org = "11111111-1111-1111-1111-111111111111",
  repo = "22222222-2222-2222-2222-222222222222",
  runId = "33333333-3333-3333-3333-333333333333",
  deployId = "44444444-4444-4444-4444-444444444444";
const windowValue = { from: "2026-09-01T12:00:00.123456Z", to: "2026-09-22T12:00:00Z" };
const evidence = { status: "complete" as const, observed_at: windowValue.to, error_code: null };
const coverage = {
  status: "partial" as const,
  input_watermark: windowValue.to,
  repository_count: 1,
  repositories_complete: 1,
  limitations: ["history_window_partial"],
  completion_unknown_count: 2,
  completion_proxy_count: 3,
  jobs_incomplete_count: 1,
};
const distribution = {
  sample_count: 2,
  excluded_count: 0,
  mean_seconds: 120,
  median_seconds: 120,
  p75_seconds: 180,
  p95_seconds: 220,
  exclusions: {},
};
const missing = {
  sample_count: 0,
  excluded_count: 2,
  mean_seconds: null,
  median_seconds: null,
  p75_seconds: null,
  p95_seconds: null,
  exclusions: { queue_unknown: 2 },
};
const run: WorkflowRun = {
  id: runId,
  repository_id: repo,
  repository_name: "fixture/api",
  provider_id: 101,
  workflow_id: 20,
  workflow_name: "Build and test",
  run_number: 7,
  attempt: 1,
  event: "push",
  status: "completed",
  conclusion: "failure",
  head_sha: "a".repeat(40),
  head_branch: "main",
  actor_login: "maya",
  created_at: windowValue.from,
  queued_at: null,
  started_at: windowValue.from,
  completed_at: windowValue.to,
  completion_source: "jobs",
  html_url: null,
  duration_seconds: 120,
  queue_seconds: null,
  duration_exclusion: null,
  queue_exclusion: "queue_unknown",
  jobs_coverage: evidence,
  links_coverage: evidence,
};
const ci: CIMetrics = {
  formula_version: "ci-attempts-v1",
  as_of: windowValue.to,
  window: windowValue,
  scope: {
    repository_id: repo,
    selected_only: false,
    repository_count: 1,
    workflow_id: 20,
    branch: "main",
  },
  completed_count: 3,
  decisive_count: 2,
  success_count: 1,
  failure_count: 1,
  success_fraction: 0.5,
  failure_fraction: 0.5,
  conclusions: { success: 1, failure: 1, canceled: 1 },
  duration: distribution,
  queue: missing,
  trend: [
    {
      date: "2026-09-20",
      completed_count: 3,
      decisive_count: 2,
      success_count: 1,
      failure_count: 1,
      success_fraction: 0.5,
      duration: distribution,
      queue: missing,
    },
  ],
  recurring_failures: [
    {
      repository_id: repo,
      repository_name: "fixture/api",
      workflow_id: 20,
      workflow_name: "Build and test",
      decisive_count: 2,
      failure_count: 1,
      failure_fraction: 0.5,
      category: "unknown",
    },
  ],
  coverage,
};
const deployment: Deployment = {
  id: deployId,
  repository_id: repo,
  repository_name: "fixture/api",
  provider_id: 99,
  environment: "production",
  classification: "unknown",
  classification_source: "unknown",
  provider_production_environment: null,
  sha: "a".repeat(40),
  ref: "main",
  task: "deploy",
  creator_login: "maya",
  created_at: windowValue.from,
  updated_at: windowValue.to,
  first_success_at: windowValue.to,
  latest_state: "success",
  success_eligible: false,
  success_exclusion: "incomplete_statuses",
  html_url: null,
  statuses_coverage: { ...evidence, status: "partial" },
  links_coverage: evidence,
};
const deployments: DeploymentMetrics = {
  formula_version: "deployments-v1",
  as_of: windowValue.to,
  window: windowValue,
  scope: {
    repository_id: repo,
    selected_only: false,
    repository_count: 1,
    environment: null,
    classification: "all",
  },
  successful_count: 2,
  observed_success_count: 3,
  excluded_count: 1,
  exclusions: { incomplete_statuses: 1 },
  fully_covered_days: 0,
  frequency_per_day: null,
  created_count: 4,
  states: { success: 3, failure: 1 },
  trend: [
    { date: "2026-09-20", successful_count: 2, observed_success_count: 3, fully_covered: false },
  ],
  coverage: { ...coverage, statuses_incomplete_count: 1 },
};
const paged = <T,>(items: T[], next_cursor: string | null = null) => ({
  items,
  next_cursor,
  window: windowValue,
  coverage,
});
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
function mount(node: React.ReactNode) {
  return render(<QueryClientProvider client={client()}>{node}</QueryClientProvider>);
}
function mock(handle: (path: string, options?: Parameters<typeof api>[1]) => unknown) {
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.includes("/repositories?"))
      return paged([{ id: repo, full_name: "fixture/api" }]) as never;
    return handle(path, options) as never;
  });
}
beforeEach(() => {
  vi.clearAllMocks();
  state.organization = org;
  state.role = "owner";
  state.verified = true;
  state.query = "";
});
describe("delivery evidence", () => {
  it("keeps null rates distinct from measured zero and pins provider links", () => {
    expect(fraction(null)).toBe("Not available");
    expect(fraction(0)).toBe("0%");
    expect(fraction(0.5)).toBe("50%");
    expect(deliverySource("https://github.com/team/api/actions/runs/123/job/456")).not.toBeNull();
    expect(deliverySource("https://github.com/team/api/deployments")).not.toBeNull();
    expect(deliverySource("https://preview.example.com/production")).toBeNull();
    expect(deliverySource("https://github.com.attacker.test/team/api/deployments")).toBeNull();
    expect(deliverySource(null)).toBeNull();
  });
  it("preserves exact filters and server windows in attempt and deployment evidence links", () => {
    expect(
      Object.fromEntries(
        new URL(
          ciEvidence({ repository: repo, workflow: "20", branch: "feature/a" }, windowValue, {
            metric: "queue",
            eligibility: "excluded",
          }),
          "https://forge.test",
        ).searchParams,
      ),
    ).toEqual({
      repository: repo,
      workflow: "20",
      branch: "feature/a",
      ...windowValue,
      cohort: "completed",
      metric: "queue",
      eligibility: "excluded",
    });
    expect(
      Object.fromEntries(
        new URL(
          deploymentEvidence(
            { repository: repo, classification: "unknown", environment: "production" },
            windowValue,
            "excluded",
          ),
          "https://forge.test",
        ).searchParams,
      ),
    ).toEqual({
      repository: repo,
      classification: "unknown",
      environment: "production",
      ...windowValue,
      cohort: "success",
      eligibility: "excluded",
    });
  });
  it("shows retries separately, null queue distributions and timing provenance coverage", async () => {
    state.query = `repository=${repo}&workflow=20&branch=main`;
    mock((path) =>
      path.includes("/metrics/ci")
        ? ci
        : paged([run, { ...run, id: deployId, attempt: 2, conclusion: "success" }]),
    );
    mount(<DeliveryPage kind="ci" />);
    await screen.findByRole("link", { name: "Build and test #7 · attempt 1" });
    expect(screen.getByRole("link", { name: "Build and test #7 · attempt 2" })).toBeVisible();
    const queue = screen.getByRole("row", { name: /Queue time Not available/ });
    expect(within(queue).getAllByText("Not available")).toHaveLength(4);
    expect(within(queue).getByRole("link", { name: "2 excluded" })).toHaveAttribute(
      "href",
      ciEvidence({ repository: repo, workflow: "20", branch: "main" }, windowValue, {
        metric: "queue",
        eligibility: "excluded",
      }),
    );
    expect(screen.getByText(/Missing completion times: 2/)).toBeVisible();
    expect(screen.getByText(/Last-job completion proxies: 3/)).toBeVisible();
    expect(screen.getByText(/Incomplete job histories: 1/)).toBeVisible();
    const disclosure = screen.getByText("Coverage details and setup");
    expect(disclosure.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(disclosure);
    expect(
      screen.getByText(/Terminal attempts without a usable completion timestamp/),
    ).toBeVisible();
    expect(screen.getByText(/It is not an exact run completion timestamp/)).toBeVisible();
  });
  it("does not turn a zero-observation unavailable source into a healthy zero rate", async () => {
    mock((path) =>
      path.includes("/metrics/ci")
        ? {
            ...ci,
            success_count: 0,
            failure_count: 0,
            decisive_count: 0,
            completed_count: 0,
            success_fraction: null,
            failure_fraction: null,
            duration: missing,
            queue: missing,
            coverage: {
              ...coverage,
              status: "unavailable",
              limitations: ["actions_permission_missing"],
            },
          }
        : paged([]),
    );
    mount(<DeliveryPage kind="ci" />);
    expect(await screen.findByText("Observations unavailable")).toBeVisible();
    fireEvent.click(screen.getByText("Coverage details and setup"));
    expect(screen.getByText("Actions read permission is missing")).toBeVisible();
    expect(screen.getByText(/administrator must enable Actions read permission/)).toBeVisible();
    const row = screen.getByRole("row", { name: /Successful attempts/ });
    expect(within(row).getByText("Not available")).toBeVisible();
  });
  it("renders job evidence and the last-job completion proxy without inventing retry queue timing", async () => {
    mock((path) =>
      path.endsWith(`/workflow-runs/${runId}`)
        ? {
            workflow_run: { ...run, attempt: 2 },
            counts: { jobs: 1, pull_requests: 0, commits: 0 },
          }
        : path.includes("/jobs?")
          ? paged([
              {
                id: "job",
                provider_id: 123,
                name: "Unit tests",
                status: "completed",
                conclusion: "failure",
                started_at: windowValue.from,
                completed_at: windowValue.to,
                duration_seconds: 120,
                html_url: null,
              },
            ])
          : paged([]),
    );
    mount(<DeliveryDetail kind="ci" id={runId} />);
    await screen.findByRole("heading", { name: "Build and test · attempt 2" });
    expect(screen.getByText("Last-job completion proxy")).toBeVisible();
    expect(await screen.findByText("Unit tests")).toBeVisible();
    expect(screen.getByText(/Attempt queue time not observed/)).toBeVisible();
    expect(screen.queryByRole("link", { name: "View on GitHub" })).not.toBeInTheDocument();
  });
  it("retains attempt rows when pagination fails and retries the original cursor", async () => {
    let failed = false;
    mock((path) => {
      if (path.includes("/metrics/ci")) return ci;
      if (path.includes("cursor=page-two")) {
        if (!failed) {
          failed = true;
          throw new Error("Next page unavailable");
        }
        return paged([{ ...run, id: deployId, attempt: 2 }]);
      }
      return paged([run], "page-two");
    });
    mount(<DeliveryPage kind="ci" />);
    await screen.findByRole("link", { name: "Build and test #7 · attempt 1" });
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Next page unavailable");
    expect(screen.getByRole("link", { name: "Build and test #7 · attempt 1" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading more" }));
    expect(
      await screen.findByRole("link", { name: "Build and test #7 · attempt 2" }),
    ).toBeVisible();
  });
  it("uses authoritative first-success counts while keeping incomplete-window frequency unavailable", async () => {
    state.query = "classification=all";
    mock((path) => (path.includes("/metrics/deployments") ? deployments : paged([deployment])));
    mount(<DeliveryPage kind="deployments" />);
    const row = await screen.findByRole("row", { name: /Eligible first successes/ });
    expect(within(row).getByText("2")).toBeVisible();
    expect(
      within(screen.getByRole("row", { name: /Deployment frequency Not available/ })).getByText(
        "Not available",
      ),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "View excluded deployments" })).toHaveAttribute(
      "href",
      deploymentEvidence({ classification: "all" }, windowValue, "excluded"),
    );
    expect(screen.getByText("No classification evidence")).toBeVisible();
  });
  it("shows repeated successful statuses as source events rather than new deployments", async () => {
    mock((path) =>
      path.endsWith(`/deployments/${deployId}`)
        ? { deployment, counts: { statuses: 2, commits: 0 } }
        : path.includes("/statuses?")
          ? paged([
              {
                id: "status1",
                provider_id: 11,
                state: "success",
                created_at: windowValue.from,
                creator_login: "maya",
                description: "Initial rollout",
                html_url: null,
              },
              {
                id: "status2",
                provider_id: 12,
                state: "success",
                created_at: windowValue.to,
                creator_login: "maya",
                description: "Repeated success event",
                html_url: null,
              },
            ])
          : paged([]),
    );
    mount(<DeliveryDetail kind="deployments" id={deployId} />);
    await screen.findByRole("heading", { name: "production deployment #99" });
    expect(await screen.findByText("Repeated success event")).toBeVisible();
    expect(screen.getByText(/later successes do not create extra deployments/)).toBeVisible();
    expect(screen.getByText("Provider flag and Forge override are absent")).toBeVisible();
  });
  it("saves an explicit environment override then removes it with null", async () => {
    state.query = `repository=${repo}`;
    let policy: EnvironmentPolicy = {
      environment: "production",
      override: null,
      deployment_count: 3,
      production_count: 0,
      nonproduction_count: 0,
      unknown_count: 3,
    };
    mock((_path, options) => {
      if (options?.method === "PUT") {
        const body = options.body as {
          environment: string;
          classification: EnvironmentPolicy["override"];
        };
        policy = { ...policy, override: body.classification };
        return { environment: body.environment, override: body.classification };
      }
      return { items: [policy] };
    });
    mount(<EnvironmentPage />);
    const field = await screen.findByRole("combobox", { name: "Classification for production" });
    fireEvent.change(field, { target: { value: "production" } });
    fireEvent.click(screen.getByRole("button", { name: "Save classification" }));
    await screen.findByText(/Classification saved for production/);
    expect(
      vi.mocked(api).mock.calls.find(([, options]) => options?.method === "PUT")?.[1]?.body,
    ).toEqual({ environment: "production", classification: "production" });
    fireEvent.change(screen.getByRole("combobox", { name: "Classification for production" }), {
      target: { value: "provider" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save classification" }));
    await waitFor(() =>
      expect(
        vi
          .mocked(api)
          .mock.calls.filter(([, options]) => options?.method === "PUT")
          .at(-1)?.[1]?.body,
      ).toEqual({ environment: "production", classification: null }),
    );
  });
  it.each([
    ["viewer", true],
    ["member", true],
    ["admin", false],
  ])("keeps environment policy read-only for %s verified=%s", async (role, verified) => {
    state.role = String(role);
    state.verified = Boolean(verified);
    state.query = `repository=${repo}`;
    mock(() => ({
      items: [
        {
          environment: "staging",
          override: null,
          deployment_count: 1,
          production_count: 0,
          nonproduction_count: 1,
          unknown_count: 0,
        },
      ],
    }));
    mount(<EnvironmentPage />);
    expect(
      await screen.findByRole("combobox", { name: "Classification for staging" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save classification" })).toBeDisabled();
    expect(screen.getByText(/A verified organization owner or admin/)).toBeVisible();
  });
  it("clears prior organization attempt data when switching tenant", async () => {
    mock((path) => (path.includes("/metrics/ci") ? ci : paged(path.includes(org) ? [run] : [])));
    const store = client();
    const node = () => (
      <QueryClientProvider client={store}>
        <DeliveryPage kind="ci" />
      </QueryClientProvider>
    );
    const view = render(node());
    await screen.findByRole("link", { name: "Build and test #7 · attempt 1" });
    state.organization = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    view.rerender(node());
    expect(
      screen.queryByRole("link", { name: "Build and test #7 · attempt 1" }),
    ).not.toBeInTheDocument();
    await screen.findByText("0 records loaded");
  });
});
