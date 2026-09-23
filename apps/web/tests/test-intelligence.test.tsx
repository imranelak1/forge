import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TestsPage } from "@/features/test-intelligence/tests-page";
import { ReportPage } from "@/features/test-intelligence/report-page";
import { TestHistoryPage } from "@/features/test-intelligence/history-page";
import { TestSettingsPage } from "@/features/test-intelligence/settings-page";
import { historyHref, readTestFilters, testQuery } from "@/features/test-intelligence/types";
import { api, ApiError } from "@/lib/auth-client";
import * as f from "./fixtures/test-intelligence";

const state = vi.hoisted(() => ({
  organization: "11111111-1111-1111-1111-111111111111",
  role: "owner",
  verified: true,
  query: "",
  replace: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(state.query),
  usePathname: () => "/app/tests",
  useRouter: () => ({ replace: state.replace }),
}));
vi.mock("@/features/auth/auth-provider", () => ({
  useAuth: () => ({
    organization: {
      id: state.organization,
      name: "Synthetic test history",
      role: state.role,
      is_demo: false,
    },
    identity: { user: { email_verified: state.verified } },
  }),
}));
vi.mock("@/lib/auth-client", async () => ({
  ...(await vi.importActual<typeof import("@/lib/auth-client")>("@/lib/auth-client")),
  api: vi.fn(),
}));
function mount(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) };
}
function defaults(path: string): unknown {
  const url = new URL(path, "https://fixture.invalid"),
    p = url.pathname;
  if (p.endsWith("/repositories")) return f.testPage([f.testRepository]);
  if (p.endsWith("/metrics/tests")) return f.testMetrics;
  if (p.endsWith("/test-runs")) return f.testPage([f.testReport]);
  if (p.endsWith(`/test-runs/${f.testReportId}`)) return f.reportDetail;
  if (p.endsWith("/suites")) return f.testPage([f.testSuite]);
  if (p.endsWith("/cases")) return f.testPage([f.testCase]);
  if (p.endsWith("/tests")) return f.testPage([f.testEvidence]);
  if (p.endsWith("/history")) return f.testHistory;
  if (p.endsWith("/test-policy")) return f.testPolicy;
  if (p.endsWith("/service-tokens")) return f.testPage([f.testToken]);
  throw new Error(`Unexpected fixture path ${path}`);
}
function mock(custom?: (path: string, options: Parameters<typeof api>[1]) => unknown) {
  vi.mocked(api).mockImplementation(async (path, options) => {
    const result = custom?.(path, options);
    return (result === undefined ? defaults(path) : result) as never;
  });
}
beforeEach(() => {
  vi.clearAllMocks();
  state.organization = f.testOrg;
  state.role = "owner";
  state.verified = true;
  state.query = "";
  mock();
});

describe("test intelligence evidence", () => {
  it("whitelists filters and preserves exact context in history links", () => {
    expect(
      readTestFilters(
        new URLSearchParams(
          `repository=${f.testRepo}&branch=feature%2Fretry&environment=ci&status=completed&potential_only=false&from=${f.testWindow.from}&to=${f.testWindow.to}&junk=value`,
        ),
      ),
    ).toEqual({
      repository: f.testRepo,
      branch: "feature/retry",
      environment: "ci",
      status: "completed",
      potential_only: "false",
      ...f.testWindow,
    });
    expect(
      readTestFilters(
        new URLSearchParams(
          "repository=foreign&branch=%00bad&status=passed&potential_only=maybe&from=not-a-date",
        ),
      ),
    ).toEqual({});
    expect(historyHref(f.testCaseId, f.testEvidence, { to: f.testWindow.to })).toBe(
      `/app/tests/cases/${f.testCaseId}?branch=main&environment=ci&to=2026-09-23T00%3A00%3A00Z`,
    );
    expect(testQuery({ potential_only: "false" })).toBe("potential_only=false");
  });
  it("shows the server denominator and skips while keeping policy lookback separate from report dates", async () => {
    state.query = `repository=${f.testRepo}&from=${f.testWindow.from}&to=${f.testWindow.to}&branch=main`;
    mount(<TestsPage />);
    const rate = await screen.findByRole("row", { name: /Pass rate 80%/ });
    expect(within(rate).getByText("10 eligible executions")).toBeVisible();
    expect(screen.getByRole("row", { name: /Skipped \(outside denominator\) 3/ })).toBeVisible();
    expect(screen.getByText(/Missing reports: 2/)).toBeVisible();
    expect(screen.getByText("Potential flaky test")).toBeVisible();
    const paths = vi.mocked(api).mock.calls.map(([p]) => new URL(p, "https://fixture.invalid"));
    const candidate = paths.find(
      (p) => p.pathname.endsWith("/tests") && !p.pathname.endsWith("/metrics/tests"),
    )!;
    expect(candidate.searchParams.has("from")).toBe(false);
    expect(candidate.searchParams.get("to")).toBe(f.testWindow.to);
    const reports = paths.find((p) => p.pathname.endsWith("/test-runs"))!;
    expect(reports.searchParams.get("from")).toBe(f.testWindow.from);
  });
  it("shows unavailable pass rate and upload guidance when reports are absent", async () => {
    mock((path) =>
      path.includes("/metrics/tests")
        ? {
            ...f.testMetrics,
            pass_fraction: null,
            report_count: 0,
            passed_count: 0,
            failed_count: 0,
            error_count: 0,
            skipped_count: 0,
            eligible_count: 0,
            coverage: { ...f.testMetrics.coverage, status: "unavailable", with_reports_count: 0 },
          }
        : path.includes("/test-runs?") || /\/tests\?/.test(path)
          ? f.testPage([])
          : undefined,
    );
    mount(<TestsPage />);
    expect(await screen.findByRole("row", { name: /Pass rate Not available/ })).toBeVisible();
    expect(screen.getByText("Reports unavailable")).toBeVisible();
    expect(screen.getByRole("link", { name: "Set up report uploads" })).toHaveAttribute(
      "href",
      "/app/tests/settings",
    );
    expect(screen.getByText(/No observed tests meet/)).toBeVisible();
  });
  it("keeps report records while a next-page request fails and retries that cursor", async () => {
    let fail = true;
    mock((path) => {
      if (path.includes("/test-runs?")) {
        if (path.includes("cursor=next")) {
          if (fail) throw new ApiError(503, "Report page unavailable");
          return f.testPage([
            { ...f.testReport, id: f.testWorkflow, report_key: "integration-tests" },
          ]);
        }
        return f.testPage([f.testReport], "next");
      }
    });
    mount(<TestsPage />);
    await screen.findByRole("link", { name: "unit-tests · linux" });
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    await screen.findByText("Report page unavailable");
    expect(screen.getByRole("link", { name: "unit-tests · linux" })).toBeVisible();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry loading more" }));
    expect(await screen.findByRole("link", { name: "integration-tests · linux" })).toBeVisible();
  });
  it("renders suites, proxy timestamps and escaped failure evidence without losing retry identity", async () => {
    mount(<ReportPage id={f.testReportId} />);
    expect(await screen.findByText("Last-job completion proxy")).toBeVisible();
    expect(await screen.findByText("API / Checkout")).toBeVisible();
    await screen.findByRole("link", { name: f.testCase.name });
    fireEvent.click(screen.getByText("Read failure message"));
    expect(screen.getByText(f.testCase.failure_message!)).toBeVisible();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText("Retry ordinal 1")).toBeVisible();
    expect(screen.getByRole("link", { name: "Run 200 · attempt 2" })).toHaveAttribute(
      "href",
      `/app/ci/${f.testWorkflow}`,
    );
    fireEvent.change(screen.getByRole("combobox", { name: "Case outcome" }), {
      target: { value: "error" },
    });
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        expect.stringContaining("/cases?limit=30&status=error"),
        expect.anything(),
      ),
    );
  });
  it("keeps superseded reports explicit and preserves the return filters", async () => {
    state.query = `repository=${f.testRepo}&status=completed`;
    mock((path) =>
      path.endsWith(`/test-runs/${f.testReportId}`)
        ? { ...f.reportDetail, test_run: { ...f.testReport, superseded_by: f.testWorkflow } }
        : undefined,
    );
    mount(<ReportPage id={f.testReportId} />);
    expect(await screen.findByRole("link", { name: "replacement report" })).toHaveAttribute(
      "href",
      `/app/tests/reports/${f.testWorkflow}`,
    );
    expect(screen.getByRole("link", { name: "Test intelligence" })).toHaveAttribute(
      "href",
      `/app/tests?repository=${f.testRepo}&status=completed`,
    );
  });
  it("shows policy/sample/flip evidence with earlier retry and superseded history", async () => {
    mock((path) =>
      path.includes("/history?")
        ? {
            ...f.testHistory,
            items: [{ ...f.testHistory.items[0], is_final: false, superseded: true }],
            evidence: [{ ...f.testEvidence, confidence: "reduced" }],
          }
        : undefined,
    );
    mount(<TestHistoryPage id={f.testCaseId} />);
    expect(await screen.findByText("12 eligible samples")).toBeVisible();
    expect(screen.getByText("4 flips")).toBeVisible();
    expect(screen.getByText("1 same-SHA reversals")).toBeVisible();
    expect(screen.getByText("Reduced confidence")).toBeVisible();
    expect(screen.getByText("Earlier retry · Superseded report")).toBeVisible();
    expect(screen.getByText(/Policy 1: 14 days/)).toBeVisible();
  });
  it("clears old organization results during a scope switch", async () => {
    let release: (v: unknown) => void = () => {};
    mock((path) =>
      path.includes(testOtherMarker())
        ? new Promise((resolve) => {
            release = resolve;
          })
        : undefined,
    );
    const view = mount(<TestsPage />);
    await screen.findByRole("link", { name: "unit-tests · linux" });
    state.organization = f.testOther;
    view.rerender(
      <QueryClientProvider client={view.client}>
        <TestsPage />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("link", { name: "unit-tests · linux" })).toBeNull();
    release(f.testPage([]));
  });
});
function testOtherMarker() {
  return `/organizations/${f.testOther}/`;
}

describe("repository test policy and credentials", () => {
  beforeEach(() => {
    state.query = `repository=${f.testRepo}`;
  });
  it("validates policy bounds and writes the exact repository-scoped policy", async () => {
    let stored = { ...f.testPolicy };
    mock((path, options) => {
      if (path.endsWith("/test-policy")) {
        if (options?.method === "PATCH")
          stored = {
            ...stored,
            ...(options.body as Partial<typeof stored>),
            updated_at: f.testWindow.to,
          };
        return stored;
      }
    });
    mount(<TestSettingsPage />);
    const low = await screen.findByRole("spinbutton", { name: "Minimum failure fraction" });
    fireEvent.change(low, { target: { value: "0.96" } });
    fireEvent.submit(low.closest("form")!);
    expect(
      await screen.findByText("Maximum failure fraction must be greater than the minimum."),
    ).toBeVisible();
    expect(vi.mocked(api).mock.calls.some(([, o]) => o?.method === "PATCH")).toBe(false);
    fireEvent.change(low, { target: { value: "0.1" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Excluded branches" }), {
      target: { value: "release/old\nmaintenance" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save test policy" }));
    expect(await screen.findByText("Test policy saved.")).toBeVisible();
    expect(api).toHaveBeenCalledWith(
      `/organizations/${f.testOrg}/repositories/${f.testRepo}/test-policy`,
      expect.objectContaining({
        method: "PATCH",
        body: expect.objectContaining({
          failure_rate_low: 0.1,
          excluded_branches: ["release/old", "maintenance"],
        }),
      }),
    );
  });
  it("reveals an issued credential once without adding it to query caches or storage", async () => {
    const credential = "fixture_only_new_ci_credential",
      setItem = vi.spyOn(Storage.prototype, "setItem"),
      tokens = [f.testToken];
    mock((path, options) => {
      if (path.endsWith("/service-tokens") && options?.method === "POST")
        return { token: f.testToken, credential };
      if (path.includes("/service-tokens?")) return f.testPage(tokens);
    });
    const view = mount(<TestSettingsPage />);
    await screen.findByRole("textbox", { name: "Token name" });
    fireEvent.change(screen.getByRole("textbox", { name: "Token name" }), {
      target: { value: "CI uploader" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Issue upload token" }));
    expect(await screen.findByRole("textbox", { name: "CI upload credential" })).toHaveValue(
      credential,
    );
    expect(
      JSON.stringify(
        view.client
          .getQueryCache()
          .getAll()
          .map((q) => q.state.data),
      ),
    ).not.toContain(credential);
    expect(setItem).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss credential" }));
    expect(screen.queryByRole("textbox", { name: "CI upload credential" })).toBeNull();
    expect(api).toHaveBeenCalledWith(
      `/organizations/${f.testOrg}/repositories/${f.testRepo}/service-tokens`,
      expect.objectContaining({
        method: "POST",
        body: { name: "CI uploader", expires_in_days: 30 },
      }),
    );
    setItem.mockRestore();
  });
  it("requires inline confirmation to revoke and updates retained metadata", async () => {
    let token = { ...f.testToken };
    mock((path, options) => {
      if (path.endsWith(`/service-tokens/${f.testTokenId}`) && options?.method === "DELETE") {
        token = { ...token, revoked_at: f.testWindow.to };
        return {};
      }
      if (path.includes("/service-tokens?")) return f.testPage([token]);
    });
    mount(<TestSettingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Revoke Build uploader" }));
    expect(vi.mocked(api).mock.calls.some(([, o]) => o?.method === "DELETE")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Confirm revoke" }));
    expect(await screen.findByText(/Revoked Build uploader/)).toBeVisible();
    expect(api).toHaveBeenCalledWith(
      `/organizations/${f.testOrg}/service-tokens/${f.testTokenId}`,
      { method: "DELETE" },
    );
    expect(screen.queryByRole("button", { name: "Revoke Build uploader" })).toBeNull();
  });
  it.each([
    ["viewer", true],
    ["member", true],
    ["admin", false],
  ])("keeps policy and tokens read-only for %s verified=%s", async (role, verified) => {
    state.role = role;
    state.verified = verified;
    mount(<TestSettingsPage />);
    expect(await screen.findByRole("spinbutton", { name: "Lookback days" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Issue upload token" })).toBeDisabled();
    expect(await screen.findByRole("button", { name: "Revoke Build uploader" })).toBeDisabled();
  });
  it("allows demo policy inspection but disables live token issue", async () => {
    mock((path) =>
      path.includes("/repositories?")
        ? f.testPage([{ ...f.testRepository, is_demo: true }])
        : undefined,
    );
    mount(<TestSettingsPage />);
    expect(
      await screen.findByText(/Generated demo repositories cannot receive live uploads/),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Issue upload token" })).toBeDisabled();
    expect(await screen.findByRole("button", { name: "Save test policy" })).toBeEnabled();
  });
  it("does not fetch policy or tokens before choosing a repository", async () => {
    state.query = "";
    mount(<TestSettingsPage />);
    await screen.findByText("Choose a repository to inspect its policy and CI upload tokens.");
    expect(
      vi
        .mocked(api)
        .mock.calls.some(([p]) => p.includes("test-policy") || p.includes("service-tokens")),
    ).toBe(false);
  });
});
