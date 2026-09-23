"use client";
import Link from "next/link";
import { useId, useState, type ReactNode } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/auth-client";
import {
  AnalyticsError,
  AnalyticsLoading,
  PageMore,
  useEvidencePage,
} from "@/features/analytics/analytics-ui";
import { duration, utcDate, type TimeWindow } from "@/features/analytics/types";
import { fraction } from "@/features/delivery/types";
import type { Repository } from "@/features/github/types";
import {
  historyHref,
  testQuery,
  testReason,
  type TestCase,
  type TestCoverage,
  type TestEvidence,
  type TestFilters,
  type TestPage,
  type TestPolicy,
  type TestReport,
} from "./types";

export const testKeys = (organization: string) => [
  "organization",
  organization,
  "analytics",
  "tests",
];
export function useTestPage<T>(organization: string, path: string, filters: TestFilters = {}) {
  const query = testQuery(filters);
  return useInfiniteQuery({
    queryKey: [...testKeys(organization), path, query],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<TestPage<T>>(
        `/organizations/${organization}/${path}?limit=30${query ? `&${query}` : ""}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });
}
export function TestOutcome({ status }: { status: string }) {
  return (
    <span
      className={
        status === "passed"
          ? "analytics-observed"
          : ["failed", "error"].includes(status)
            ? "analytics-missing"
            : ""
      }
    >
      {status}
    </span>
  );
}
export function UploadHelp({ repository }: { repository?: string }) {
  return (
    <div className="analytics-empty">
      <p>
        No test reports match this scope. A successful workflow alone does not establish test
        results. Upload a JUnit XML report from CI to begin collecting evidence.
      </p>
      <Link
        className="text-link"
        href={`/app/tests/settings${repository ? `?repository=${repository}` : ""}`}
      >
        Set up report uploads
      </Link>
      <span className="tests-inline-separator"> · </span>
      <Link className="text-link" href="/guide#test-reports">
        Read the upload guide
      </Link>
    </div>
  );
}
export function TestCoverageSummary({ value }: { value: TestCoverage }) {
  return (
    <section className="analytics-section delivery-coverage">
      <div className="analytics-section-heading">
        <h2>Report coverage</h2>
        <span className="analytics-missing">
          {value.status === "unavailable" ? "Reports unavailable" : "Uploaded reports only"}
        </span>
      </div>
      <div className="delivery-coverage-summary analytics-note">
        <span>
          {value.with_reports_count} of {value.known_workflow_count} known workflow attempts have
          reports.
        </span>
        <span>Input watermark: {utcDate(value.input_watermark)}.</span>
      </div>
      <p className="analytics-note">
        Missing reports: {value.missing_report_count} · Pending: {value.queued_report_count} ·
        Failed imports: {value.failed_report_count} · With warnings: {value.warning_report_count} ·
        Without workflow completion: {value.unknown_link_count} · Last-job completion proxies:{" "}
        {value.completion_proxy_count}
      </p>
      <details className="analytics-daily-data delivery-coverage-details">
        <summary>Coverage and measurement method</summary>
        <p className="analytics-note">
          Metrics use the latest completed attempt for each workflow run, non-superseded reports and
          final explicit retries. Skipped tests are reported separately from the pass-rate
          denominator. Reports with unresolved workflow evidence cannot establish the measured
          cohort.
        </p>
        <p className="analytics-note">
          Coverage describes reports that reached Forge. It cannot prove that all suites or all CI
          runs uploaded a report.
        </p>
        {value.limitations.length > 0 && (
          <ul className="analytics-limitations">
            {value.limitations.map((code) => (
              <li key={code}>{testReason(code)}</li>
            ))}
          </ul>
        )}
        <Link className="text-link" href="/guide#test-reports">
          Report upload guide
        </Link>
      </details>
    </section>
  );
}
export function TestFiltersForm({
  organization,
  filters,
  kind = "overview",
  apply,
}: {
  organization: string;
  filters: TestFilters;
  kind?: "overview" | "history" | "settings";
  apply: (filters: TestFilters) => void;
}) {
  const [draft, setDraft] = useState(filters),
    [expanded, setExpanded] = useState(kind === "settings"),
    [error, setError] = useState("");
  const id = useId();
  const repositories = useEvidencePage<Repository>(organization, "repositories");
  const items = repositories.data?.pages.flatMap((p) => p.items) ?? [];
  const count = Object.values(filters).filter(Boolean).length;
  const change = (key: keyof TestFilters, value: string) =>
    setDraft({ ...draft, [key]: value || undefined });
  const field = (key: keyof TestFilters, name: string, children: ReactNode) => (
    <div className="delivery-field" key={key}>
      <label htmlFor={`${id}-${key}`}>{name}</label>
      {children}
    </div>
  );
  return (
    <form
      className={`analytics-filters${expanded ? " is-open" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        if (
          draft.from &&
          draft.to &&
          (Date.parse(draft.to) <= Date.parse(draft.from) ||
            Date.parse(draft.to) - Date.parse(draft.from) > 366 * 86400000)
        ) {
          setError("Choose an end after the start, within 366 days.");
          return;
        }
        setError("");
        apply(draft);
      }}
    >
      <button
        className="analytics-filter-toggle"
        type="button"
        aria-expanded={expanded}
        aria-controls={id}
        onClick={() => setExpanded(!expanded)}
      >
        <span>
          Filters{" "}
          <span className="analytics-filter-summary">
            {count
              ? `${count} applied`
              : kind === "history"
                ? "Policy lookback"
                : "Default observation window"}
          </span>
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      <div className="analytics-filter-body" id={id}>
        <div className="analytics-filter-fields">
          {kind !== "history" &&
            field(
              "repository",
              "Repository",
              <select
                id={`${id}-repository`}
                value={draft.repository ?? ""}
                onChange={(e) => change("repository", e.target.value)}
              >
                <option value="">
                  {kind === "settings" ? "Choose a repository" : "All selected repositories"}
                </option>
                {draft.repository && !items.some((r) => r.id === draft.repository) && (
                  <option value={draft.repository}>Filtered repository (retained history)</option>
                )}
                {items.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.full_name}
                  </option>
                ))}
              </select>,
            )}
          {kind !== "settings" && (
            <>
              {(["branch", "environment"] as const).map((key) =>
                field(
                  key,
                  key === "branch" ? "Branch (exact)" : "Environment (exact)",
                  <input
                    id={`${id}-${key}`}
                    maxLength={255}
                    placeholder={key === "branch" ? "All branches" : "All environments"}
                    value={draft[key] ?? ""}
                    onChange={(e) => change(key, e.target.value)}
                  />,
                ),
              )}
              {(["from", "to"] as const).map((key) =>
                field(
                  key,
                  key === "from" ? "From (UTC)" : "Before (UTC)",
                  <input
                    id={`${id}-${key}`}
                    type="datetime-local"
                    step="1"
                    value={draft[key] ? new Date(draft[key]).toISOString().slice(0, 19) : ""}
                    onChange={(e) =>
                      change(
                        key,
                        e.target.value ? new Date(`${e.target.value}Z`).toISOString() : "",
                      )
                    }
                  />,
                ),
              )}
              {kind === "overview" && (
                <>
                  {field(
                    "status",
                    "Report status",
                    <select
                      id={`${id}-status`}
                      value={draft.status ?? ""}
                      onChange={(e) => change("status", e.target.value)}
                    >
                      <option value="">All report states</option>
                      {["queued", "processing", "completed", "failed"].map((s) => (
                        <option value={s} key={s}>
                          {s}
                        </option>
                      ))}
                    </select>,
                  )}
                  {field(
                    "potential_only",
                    "Test history",
                    <select
                      id={`${id}-potential_only`}
                      value={draft.potential_only ?? "true"}
                      onChange={(e) => change("potential_only", e.target.value)}
                    >
                      <option value="true">Potential flaky tests</option>
                      <option value="false">All observed tests</option>
                    </select>,
                  )}
                </>
              )}
            </>
          )}
        </div>
        <div className="analytics-filter-actions">
          <Button type="submit" variant="outline">
            {kind === "settings" ? "Show repository settings" : "Apply filters"}
          </Button>
          <button
            type="button"
            className="text-link"
            onClick={() => {
              setDraft({});
              setError("");
              apply({});
            }}
          >
            Reset filters
          </button>
          {kind !== "settings" && (
            <span>
              All times UTC. Potential-flakiness evaluation uses the repository policy lookback.
            </span>
          )}
        </div>
        {repositories.isError && kind !== "history" && (
          <p className="form-error" role="alert">
            Repository choices could not load.{" "}
            <button type="button" className="text-link" onClick={() => void repositories.refetch()}>
              Retry choices
            </button>
          </p>
        )}
        {repositories.hasNextPage && kind !== "history" && (
          <button
            className="text-link"
            type="button"
            disabled={repositories.isFetchingNextPage}
            onClick={() => void repositories.fetchNextPage()}
          >
            Load more repositories
          </button>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </form>
  );
}
export function ReportTable({
  items,
  filters = {},
}: {
  items: TestReport[];
  filters?: TestFilters;
}) {
  const query = testQuery(filters);
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Report</th>
            <th scope="col">Workflow</th>
            <th scope="col">Import</th>
            <th scope="col">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <th scope="row">
                <Link href={`/app/tests/reports/${r.id}${query ? `?${query}` : ""}`}>
                  {r.report_key} · {r.shard || "Default shard"}
                </Link>
                <span className="analytics-meta">{r.repository_name}</span>
                <span className="analytics-meta">Received {utcDate(r.received_at)}</span>
              </th>
              <td data-label="Workflow">
                {r.workflow_run_id ? (
                  <Link className="text-link" href={`/app/ci/${r.workflow_run_id}`}>
                    Run {r.provider_run_id} · attempt {r.run_attempt}
                  </Link>
                ) : (
                  <>
                    Run {r.provider_run_id} · attempt {r.run_attempt}
                    <span className="analytics-meta">Workflow link unresolved</span>
                  </>
                )}
                <span className="analytics-meta">
                  {r.branch ?? "Branch unknown"} · {r.environment ?? "Environment unknown"}
                </span>
              </td>
              <td data-label="Import">
                <TestOutcome status={r.status} />
                {r.superseded_by && (
                  <Link
                    className="analytics-meta text-link"
                    href={`/app/tests/reports/${r.superseded_by}`}
                  >
                    Superseded · View replacement
                  </Link>
                )}
              </td>
              <td data-label="Evidence">
                {r.case_count} cases
                <span className="analytics-meta">{r.warning_count} quality warnings</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function PolicyEvidence({ policy }: { policy: TestPolicy }) {
  return (
    <p className="analytics-note">
      Policy {policy.version}: {policy.lookback_days} days · at least {policy.min_executions}{" "}
      executions · failure fraction {fraction(policy.failure_rate_min)}–
      {fraction(policy.failure_rate_max)} · at least {policy.min_flips} flips.
      {policy.excluded_branches.length > 0 && (
        <> Excluded branches: {policy.excluded_branches.join(", ")}.</>
      )}
    </p>
  );
}
export function TestEvidenceTable({
  items,
  window,
}: {
  items: TestEvidence[];
  window?: Partial<TimeWindow>;
}) {
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Test</th>
            <th scope="col">Outcomes</th>
            <th scope="col">Transitions</th>
            <th scope="col">Evaluation</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr
              key={`${item.id}:${item.branch}:${item.environment}:${item.report_key}:${item.shard}:${index}`}
            >
              <th scope="row">
                <Link href={historyHref(item.id, item, window)}>{item.name}</Link>
                <span className="analytics-meta">
                  {item.class_name || item.file || "Identity has no class or file"}
                </span>
                <span className="analytics-meta">
                  {item.repository_name} · {item.branch ?? "Branch unknown"} ·{" "}
                  {item.environment ?? "Environment unknown"}
                </span>
                <span className="analytics-meta">
                  {item.report_key} · {item.shard || "Default shard"}
                </span>
              </th>
              <td data-label="Outcomes">
                {item.sample_count} eligible samples
                <span className="analytics-meta">
                  {item.passed_count} passed · {item.failed_count} failed/error
                </span>
                <span className="analytics-meta">
                  Failure fraction {fraction(item.failure_fraction)}
                </span>
              </td>
              <td data-label="Transitions">
                {item.flip_count} flips
                <span className="analytics-meta">
                  {item.same_sha_reversal_count} same-SHA reversals
                </span>
              </td>
              <td data-label="Evaluation">
                <span className={item.potential_flaky ? "analytics-missing" : ""}>
                  {item.potential_flaky ? "Potential flaky test" : "No policy signal"}
                </span>
                <span className="analytics-meta">
                  {item.confidence === "reduced" ? "Reduced confidence" : "Standard confidence"}
                </span>
                <PolicyEvidence policy={item.policy} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function CaseTable({ items, window }: { items: TestCase[]; window?: TimeWindow }) {
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Test case</th>
            <th scope="col">Outcome</th>
            <th scope="col">Execution</th>
            <th scope="col">Failure evidence</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <th scope="row">
                <Link href={historyHref(item.test_id, { branch: null, environment: null }, window)}>
                  {item.name}
                </Link>
                <span className="analytics-meta">
                  {item.class_name || item.file || "Class and file not provided"}
                </span>
                <span className="analytics-meta">
                  Identity: {item.identity_quality.replaceAll("_", " ")}
                </span>
              </th>
              <td data-label="Outcome">
                <TestOutcome status={item.status} />
                <span className="analytics-meta">{duration(item.duration_seconds)}</span>
              </td>
              <td data-label="Execution">
                Retry ordinal {item.retry_ordinal}
                <span className="analytics-meta">
                  {item.is_final ? "Final explicit retry" : "Earlier retry"}
                </span>
              </td>
              <td data-label="Failure evidence">
                {item.failure_message ? (
                  <details className="tests-failure">
                    <summary>Read failure message</summary>
                    <pre>{item.failure_message}</pre>
                  </details>
                ) : (
                  "No message retained"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function EvidenceList<T>({
  organization,
  path,
  title,
  filters = {},
  empty = "No records observed.",
  children,
}: {
  organization: string;
  path: string;
  title: string;
  filters?: TestFilters;
  empty?: string;
  children: (items: T[]) => ReactNode;
}) {
  const result = useTestPage<T>(organization, path, filters),
    items = result.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <section className="analytics-section">
      <h2>{title}</h2>
      {result.isPending ? (
        <AnalyticsLoading label={`Loading ${title.toLowerCase()}`} />
      ) : result.isError && !items.length ? (
        <AnalyticsError error={result.error} retry={result.refetch} />
      ) : (
        <>
          {items.length ? children(items) : <p className="analytics-empty">{empty}</p>}
          <PageMore result={result} count={items.length} />
        </>
      )}
    </section>
  );
}
