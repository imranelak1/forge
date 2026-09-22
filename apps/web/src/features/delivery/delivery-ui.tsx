"use client";
import Link from "next/link";
import { useId, useState, type ReactNode } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/auth-client";
import {
  AnalyticsError,
  AnalyticsLoading,
  PageMore,
  useEvidencePage,
} from "@/features/analytics/analytics-ui";
import {
  duration,
  utcDate,
  type Distribution,
  type EvidenceCoverage,
} from "@/features/analytics/types";
import type { Repository } from "@/features/github/types";
import {
  classificationLabel,
  deliveryQuery,
  deliveryReason,
  deliverySource,
  type DeliveryCoverage,
  type DeliveryFilters,
  type DeliveryPage,
  type Deployment,
  type WorkflowRun,
} from "./types";

export function useDeliveryPage<T>(
  organization: string,
  path: string,
  filters: DeliveryFilters = {},
) {
  const query = deliveryQuery(filters);
  return useInfiniteQuery({
    queryKey: ["organization", organization, "analytics", "delivery", path, query],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<DeliveryPage<T>>(
        `/organizations/${organization}/${path}?limit=30${query ? `&${query}` : ""}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });
}
export function DeliverySource({
  url,
  children = "View on GitHub",
}: {
  url: string | null;
  children?: ReactNode;
}) {
  const href = deliverySource(url);
  return href ? (
    <a className="analytics-source text-link" href={href} rel="noopener noreferrer" target="_blank">
      {children}
      <ExternalLink size={13} aria-hidden="true" />
    </a>
  ) : null;
}
export function EvidenceStatus({ value, label }: { value: EvidenceCoverage; label: string }) {
  return (
    <div className="analytics-coverage-item">
      <span className={value.status === "complete" ? "analytics-observed" : "analytics-missing"}>
        {label}:{" "}
        {value.status === "complete"
          ? "Complete"
          : value.status === "pending"
            ? "Import pending"
            : value.status === "partial"
              ? "Partial history"
              : value.status === "failed"
                ? "Import failed"
                : "Unavailable"}
      </span>
      {value.observed_at && <span>Observed {utcDate(value.observed_at)}</span>}
      {value.error_code && <span>{deliveryReason(value.error_code)}</span>}
    </div>
  );
}
export function DeliveryEvidence<T>({
  organization,
  path,
  title,
  coverage,
  children,
}: {
  organization: string;
  path: string;
  title: string;
  coverage: EvidenceCoverage;
  children: (items: T[]) => ReactNode;
}) {
  const result = useEvidencePage<T>(organization, path);
  const items = result.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section className="analytics-section">
      <h2>{title}</h2>
      <EvidenceStatus value={coverage} label="Coverage" />
      {result.isPending ? (
        <AnalyticsLoading label={`Loading ${title.toLowerCase()}`} />
      ) : result.isError && !items.length ? (
        <AnalyticsError error={result.error} retry={result.refetch} />
      ) : (
        <>
          {items.length ? (
            children(items)
          ) : (
            <p className="analytics-empty">
              {coverage.status === "complete"
                ? "No records observed."
                : "No records imported yet. Coverage above describes what is missing."}
            </p>
          )}
          <PageMore result={result} count={items.length} />
        </>
      )}
    </section>
  );
}
export function SourceCoverage({
  coverage,
  source,
}: {
  coverage: DeliveryCoverage;
  source: "Actions" | "Deployments";
}) {
  const counts = [
    coverage.completion_unknown_count &&
      `Missing completion times: ${coverage.completion_unknown_count}`,
    coverage.completion_proxy_count &&
      `Last-job completion proxies: ${coverage.completion_proxy_count}`,
    coverage.jobs_incomplete_count && `Incomplete job histories: ${coverage.jobs_incomplete_count}`,
    coverage.statuses_incomplete_count &&
      `Incomplete status histories: ${coverage.statuses_incomplete_count}`,
  ].filter(Boolean);
  const explained = new Set([
    ...(coverage.completion_unknown_count ? ["completion_unknown"] : []),
    ...(coverage.completion_proxy_count ? ["job_completion_proxy"] : []),
    ...(coverage.jobs_incomplete_count ? ["jobs_incomplete"] : []),
    ...(coverage.statuses_incomplete_count ? ["statuses_incomplete", "incomplete_statuses"] : []),
  ]);
  const limitations = coverage.limitations.filter((reason) => !explained.has(reason));
  return (
    <section className="analytics-section delivery-coverage">
      <div className="analytics-section-heading">
        <h2>Source coverage</h2>
        <span
          className={coverage.status === "complete" ? "analytics-observed" : "analytics-missing"}
        >
          {coverage.status === "complete"
            ? "Complete observations"
            : coverage.status === "partial"
              ? "Partial observations"
              : "Observations unavailable"}
        </span>
      </div>
      <div className="delivery-coverage-summary analytics-note">
        <span>
          {source}: {coverage.repositories_complete} of {coverage.repository_count} repositories
          complete.
        </span>
        <span>Input watermark: {utcDate(coverage.input_watermark)}.</span>
      </div>
      {counts.length > 0 && <p className="analytics-note">{counts.join(" · ")}</p>}
      {(coverage.status !== "complete" || counts.length > 0 || limitations.length > 0) && (
        <details className="analytics-daily-data delivery-coverage-details">
          <summary>Coverage details and setup</summary>
          {!!coverage.completion_unknown_count && (
            <p className="analytics-note">
              Terminal attempts without a usable completion timestamp are outside the completed
              cohort.
            </p>
          )}
          {!!coverage.completion_proxy_count && (
            <p className="analytics-note">
              The last-job completion proxy uses the final job&apos;s timestamp. It is not an exact
              run completion timestamp.
            </p>
          )}
          {!!coverage.jobs_incomplete_count && (
            <p className="analytics-note">
              Incomplete job histories may omit individual jobs from an attempt.
            </p>
          )}
          {!!coverage.statuses_incomplete_count && (
            <p className="analytics-note">
              Deployments with incomplete status histories are excluded from the eligible
              first-success count.
            </p>
          )}
          {limitations.length > 0 && (
            <ul className="analytics-limitations">
              {limitations.map((reason) => (
                <li key={reason}>{deliveryReason(reason)}</li>
              ))}
            </ul>
          )}
          {coverage.status !== "complete" && (
            <p className="analytics-note">
              Check{" "}
              <Link className="text-link" href="/app/repositories">
                repository sync progress
              </Link>
              . If access is missing, the GitHub App administrator must enable {source} read
              permission in GitHub App settings, then the installation owner must approve it.{" "}
              <Link className="text-link" href="/guide#github-app">
                Setup instructions
              </Link>
              .
            </p>
          )}
        </details>
      )}
    </section>
  );
}
export function DistributionRow({
  name,
  value,
  included,
  excluded,
}: {
  name: string;
  value: Distribution;
  included: string;
  excluded: string;
}) {
  return (
    <tr>
      <th scope="row">{name}</th>
      <td data-label="Mean">{duration(value.mean_seconds)}</td>
      <td data-label="Median">{duration(value.median_seconds)}</td>
      <td data-label="P75">{duration(value.p75_seconds)}</td>
      <td data-label="P95">{duration(value.p95_seconds)}</td>
      <td data-label="Evidence">
        <Link className="text-link" href={included}>
          {value.sample_count} included
        </Link>
        <Link className="text-link analytics-meta" href={excluded}>
          {value.excluded_count} excluded
        </Link>
        {Object.entries(value.exclusions)
          .filter(([, count]) => count > 0)
          .map(([code, count]) => (
            <span key={code} className="analytics-meta">
              {count} · {deliveryReason(code)}
            </span>
          ))}
      </td>
    </tr>
  );
}
export function DeliveryFiltersForm({
  organization,
  filters,
  kind,
  apply,
}: {
  organization: string;
  filters: DeliveryFilters;
  kind: "ci" | "deployments" | "environments";
  apply: (filters: DeliveryFilters) => void;
}) {
  const [draft, setDraft] = useState(filters);
  const [expanded, setExpanded] = useState(kind === "environments");
  const [error, setError] = useState("");
  const id = useId();
  const repositories = useEvidencePage<Repository>(organization, "repositories");
  const items = repositories.data?.pages.flatMap((page) => page.items) ?? [];
  const count = Object.values(filters).filter(Boolean).length;
  const change = (key: keyof DeliveryFilters, value: string) =>
    setDraft({ ...draft, [key]: value || undefined });
  const field = (key: keyof DeliveryFilters, name: string, children: ReactNode) => (
    <div className="delivery-field" key={key}>
      <label htmlFor={`${id}-${key}`}>{name}</label>
      {children}
    </div>
  );
  const select = (
    key: keyof DeliveryFilters,
    name: string,
    values: [string, string][],
    fallback = "",
    disabled = false,
  ) =>
    field(
      key,
      name,
      <select
        id={`${id}-${key}`}
        value={draft[key] ?? fallback}
        disabled={disabled}
        onChange={(event) => change(key, event.target.value)}
      >
        {values.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>,
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
        if (draft.workflow && !/^[1-9]\d{0,18}$/.test(draft.workflow)) {
          setError("Workflow ID must be a positive whole number.");
          return;
        }
        setError("");
        apply(draft.metric ? { ...draft, cohort: "completed", outcome: "all" } : draft);
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
              : kind === "deployments"
                ? "Production · last 90 days"
                : "Last 90 days"}
          </span>
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      <div className="analytics-filter-body" id={id}>
        <div className="analytics-filter-fields">
          {field(
            "repository",
            "Repository",
            <select
              id={`${id}-repository`}
              value={draft.repository ?? ""}
              onChange={(event) => change("repository", event.target.value)}
            >
              <option value="">
                {kind === "environments" ? "Choose a repository" : "All selected repositories"}
              </option>
              {draft.repository && !items.some((repo) => repo.id === draft.repository) && (
                <option value={draft.repository}>Filtered repository (retained history)</option>
              )}
              {items.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.full_name}
                </option>
              ))}
            </select>,
          )}
          {kind !== "environments" && (
            <>
              {kind === "ci" ? (
                <>
                  {field(
                    "workflow",
                    "Workflow ID",
                    <input
                      id={`${id}-workflow`}
                      inputMode="numeric"
                      maxLength={19}
                      placeholder="All workflows"
                      value={draft.workflow ?? ""}
                      onChange={(event) => change("workflow", event.target.value)}
                    />,
                  )}
                  {field(
                    "branch",
                    "Branch (exact)",
                    <input
                      id={`${id}-branch`}
                      maxLength={255}
                      placeholder="All branches"
                      value={draft.branch ?? ""}
                      onChange={(event) => change("branch", event.target.value)}
                    />,
                  )}
                </>
              ) : (
                <>
                  {field(
                    "environment",
                    "Environment (exact)",
                    <input
                      id={`${id}-environment`}
                      maxLength={255}
                      placeholder="All environments"
                      value={draft.environment ?? ""}
                      onChange={(event) => change("environment", event.target.value)}
                    />,
                  )}
                  {select(
                    "classification",
                    "Classification",
                    [
                      ["production", "Production"],
                      ["nonproduction", "Non-production"],
                      ["unknown", "Unknown"],
                      ["all", "All classifications"],
                    ],
                    "production",
                  )}
                </>
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
                    onChange={(event) =>
                      change(
                        key,
                        event.target.value ? new Date(`${event.target.value}Z`).toISOString() : "",
                      )
                    }
                  />,
                ),
              )}
              {kind === "ci" ? (
                <>
                  {select(
                    "cohort",
                    "Attempt window",
                    [
                      ["activity", "Created"],
                      ["completed", "Completed"],
                    ],
                    draft.metric ? "completed" : "activity",
                    !!draft.metric,
                  )}
                  {select(
                    "outcome",
                    "Attempt outcome",
                    [
                      ["all", "All outcomes"],
                      ["success", "Success"],
                      ["failure", "Failure"],
                      ["other", "Other conclusions"],
                    ],
                    "all",
                    !!draft.metric,
                  )}
                  {select("metric", "Timing evidence", [
                    ["", "All attempts"],
                    ["duration", "Duration"],
                    ["queue", "Queue time"],
                  ])}
                  {draft.metric &&
                    select(
                      "eligibility",
                      "Samples",
                      [
                        ["eligible", "Included"],
                        ["excluded", "Excluded"],
                        ["all", "All decisive attempts"],
                      ],
                      "eligible",
                    )}
                </>
              ) : (
                <>
                  {select(
                    "cohort",
                    "Deployment window",
                    [
                      ["created", "Created"],
                      ["success", "First observed success"],
                    ],
                    "created",
                  )}
                  {draft.cohort === "success" &&
                    select(
                      "eligibility",
                      "Samples",
                      [
                        ["all", "All observed"],
                        ["eligible", "Included"],
                        ["excluded", "Excluded"],
                      ],
                      "all",
                    )}
                </>
              )}
            </>
          )}
        </div>
        <div className="analytics-filter-actions">
          <Button type="submit" variant="outline">
            {kind === "environments" ? "Show environments" : "Apply filters"}
          </Button>
          <button
            className="text-link"
            type="button"
            onClick={() => {
              setDraft({});
              setError("");
              apply({});
            }}
          >
            Reset filters
          </button>
          {kind !== "environments" && (
            <span>Last 90 days by default. All times UTC; at most 366 days.</span>
          )}
        </div>
        {repositories.isError && (
          <p className="form-error" role="alert">
            Repository choices could not load.{" "}
            <button type="button" className="text-link" onClick={() => void repositories.refetch()}>
              Retry choices
            </button>
          </p>
        )}
        {repositories.hasNextPage && (
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
export function WorkflowTable({ items }: { items: WorkflowRun[] }) {
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Workflow attempt</th>
            <th scope="col">Outcome</th>
            <th scope="col">Timing</th>
            <th scope="col">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {items.map((run) => (
            <tr key={run.id}>
              <th scope="row">
                <Link href={`/app/ci/${run.id}`}>
                  {run.workflow_name} #{run.run_number} · attempt {run.attempt}
                </Link>
                <span className="analytics-meta">
                  {run.repository_name} · {run.head_branch ?? "Branch unknown"} · {run.event}
                </span>
                <span className="analytics-meta">Created {utcDate(run.created_at)}</span>
              </th>
              <td data-label="Outcome">
                <RunOutcome status={run.status} conclusion={run.conclusion} />
                <span className="analytics-meta">Completed {utcDate(run.completed_at)}</span>
              </td>
              <td data-label="Timing">
                {duration(run.duration_seconds)}
                <span className="analytics-meta">Queue: {duration(run.queue_seconds)}</span>
                {run.duration_exclusion && (
                  <span className="analytics-meta">{deliveryReason(run.duration_exclusion)}</span>
                )}
              </td>
              <td data-label="Evidence">
                <EvidenceStatus value={run.jobs_coverage} label="Jobs" />
                <EvidenceStatus value={run.links_coverage} label="Links" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function RunOutcome({ status, conclusion }: { status: string; conclusion: string | null }) {
  return (
    <span
      className={
        conclusion === "success"
          ? "analytics-observed"
          : conclusion &&
              ["failure", "timed_out", "startup_failure", "action_required"].includes(conclusion)
            ? "analytics-missing"
            : ""
      }
    >
      {status}
      {conclusion ? ` · ${conclusion}` : " · No conclusion"}
    </span>
  );
}
export function DeploymentTable({ items }: { items: Deployment[] }) {
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Deployment</th>
            <th scope="col">Classification</th>
            <th scope="col">First success</th>
            <th scope="col">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {items.map((deployment) => (
            <tr key={deployment.id}>
              <th scope="row">
                <Link href={`/app/deployments/${deployment.id}`}>
                  {deployment.environment} deployment #{deployment.provider_id}
                </Link>
                <span className="analytics-meta">
                  {deployment.repository_name} · {deployment.latest_state ?? "No status observed"}
                </span>
                <span className="analytics-meta">Created {utcDate(deployment.created_at)}</span>
              </th>
              <td data-label="Classification">
                {classificationLabel(deployment.classification)}
                <span className="analytics-meta">
                  {deployment.classification_source === "override"
                    ? "Forge override"
                    : deployment.classification_source === "provider"
                      ? "Provider flag"
                      : "No classification evidence"}
                </span>
              </td>
              <td data-label="First success">
                {utcDate(deployment.first_success_at)}
                {deployment.success_exclusion && (
                  <span className="analytics-meta">
                    {deliveryReason(deployment.success_exclusion)}
                  </span>
                )}
              </td>
              <td data-label="Evidence">
                <EvidenceStatus value={deployment.statuses_coverage} label="Statuses" />
                <EvidenceStatus value={deployment.links_coverage} label="Links" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export { PageMore };
