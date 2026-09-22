"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/auth-provider";
import { api } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import {
  AnalyticsError,
  AnalyticsLoading,
  DemoNotice,
  EmptyHistory,
  RefreshData,
  WindowLabel,
} from "@/features/analytics/analytics-ui";
import { duration, utcDate, type TimeWindow } from "@/features/analytics/types";
import {
  DeliveryFiltersForm,
  DeploymentTable,
  DistributionRow,
  PageMore,
  SourceCoverage,
  WorkflowTable,
  useDeliveryPage,
} from "./delivery-ui";
import {
  ciEvidence,
  classificationLabel,
  deliveryQuery,
  deliveryReason,
  deploymentEvidence,
  fraction,
  metricFilters,
  readDeliveryFilters,
  type CIMetrics,
  type DeliveryFilters,
  type Deployment,
  type DeploymentMetrics,
  type WorkflowRun,
} from "./types";

export function DeliveryPage({ kind }: { kind: "ci" | "deployments" }) {
  const { organization } = useAuth();
  const search = useSearchParams();
  if (!organization) return null;
  return (
    <DeliveryContent
      key={`${organization.id}:${kind}:${search}`}
      organization={organization}
      kind={kind}
      filters={readDeliveryFilters(new URLSearchParams(search), kind)}
    />
  );
}
function DeliveryContent({
  organization,
  kind,
  filters,
}: {
  organization: Organization;
  kind: "ci" | "deployments";
  filters: DeliveryFilters;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const metricsQuery = deliveryQuery(metricFilters(filters, kind));
  const summary = useQuery({
    queryKey: [
      "organization",
      organization.id,
      "analytics",
      "delivery",
      "metrics",
      kind,
      metricsQuery,
    ],
    queryFn: ({ signal }) =>
      api<CIMetrics | DeploymentMetrics>(
        `/organizations/${organization.id}/metrics/${kind}?${metricsQuery}`,
        { signal },
      ),
    retry: false,
  });
  const records = useDeliveryPage<WorkflowRun | Deployment>(
    organization.id,
    kind === "ci" ? "workflow-runs" : "deployments",
    filters,
  );
  const items = records.data?.pages.flatMap((page) => page.items) ?? [];
  const coverage = summary.data?.coverage ?? records.data?.pages[0].coverage;
  return (
    <div className="analytics-content">
      <div className="page-heading">
        <div>
          <h1>{kind === "ci" ? "CI workflows" : "Deployments"}</h1>
          <p>
            {organization.name} ·{" "}
            {kind === "ci"
              ? "Attempt outcomes, timings and job evidence. Retries stay distinct."
              : "Provider-reported deployments and their first successful status."}
          </p>
        </div>
        <div className="delivery-heading-actions">
          <Link
            className="text-link"
            href={kind === "ci" ? "/app/deployments" : "/app/deployments/environments"}
          >
            {kind === "ci" ? "Deployments" : "Environment classification"}
          </Link>
          <RefreshData organization={organization.id} />
        </div>
      </div>
      <DemoNotice demo={organization.is_demo} />
      <DeliveryFiltersForm
        organization={organization.id}
        kind={kind}
        filters={filters}
        apply={(next) => router.replace(`${pathname}?${deliveryQuery(next)}`)}
      />
      {coverage && (
        <SourceCoverage coverage={coverage} source={kind === "ci" ? "Actions" : "Deployments"} />
      )}
      {summary.isPending ? (
        <AnalyticsLoading label="Loading metrics" />
      ) : summary.isError ? (
        <AnalyticsError error={summary.error} retry={summary.refetch} />
      ) : (
        summary.data &&
        (kind === "ci" ? (
          <CISummary data={summary.data as CIMetrics} filters={filters} />
        ) : (
          <DeploymentSummary data={summary.data as DeploymentMetrics} filters={filters} />
        ))
      )}
      <section className="analytics-section" id={kind === "ci" ? "attempts" : "deployment-records"}>
        <h2>{kind === "ci" ? "Workflow attempts" : "Deployment records"}</h2>
        <p className="analytics-note">
          {kind === "ci"
            ? filters.metric
              ? `${filters.metric === "queue" ? "Queue time" : "Duration"} evidence: ${filters.eligibility ?? "eligible"} samples from decisive completed attempts.`
              : "Every attempt is a separate record. Changing the attempt window or outcome filters this list; summary metrics always use the completed cohort."
            : "Successful workflow runs do not create deployment records. Classification comes from the provider or a repository environment override."}
        </p>
        {records.isPending ? (
          <AnalyticsLoading label={kind === "ci" ? "Loading attempts" : "Loading deployments"} />
        ) : records.isError && !items.length ? (
          <AnalyticsError error={records.error} retry={records.refetch} />
        ) : (
          <>
            <WindowLabel
              window={records.data?.pages[0].window}
              cohort={
                kind === "ci"
                  ? filters.cohort === "completed" || filters.metric
                    ? "Completed"
                    : "Created"
                  : filters.cohort === "success"
                    ? "First observed success"
                    : "Created"
              }
            />
            {items.length ? (
              kind === "ci" ? (
                <WorkflowTable items={items as WorkflowRun[]} />
              ) : (
                <DeploymentTable items={items as Deployment[]} />
              )
            ) : (
              <EmptyHistory>
                {kind === "ci"
                  ? "No workflow attempts imported for these filters. Check source coverage before interpreting this as no CI activity."
                  : "No deployment records imported for these filters. Unknown classifications and missing access are shown separately from confirmed production deployments."}
              </EmptyHistory>
            )}
            <PageMore result={records} count={items.length} />
          </>
        )}
      </section>
    </div>
  );
}
function CISummary({ data, filters }: { data: CIMetrics; filters: DeliveryFilters }) {
  return (
    <>
      <section className="analytics-section">
        <div className="analytics-section-heading">
          <h2>Completed attempt metrics</h2>
          <Link className="text-link" href={ciEvidence(filters, data.window)}>
            {data.completed_count} observed completions · View cohort
          </Link>
        </div>
        <WindowLabel window={data.window} cohort="Completed" />
        <p className="analytics-note">
          Success and failure rates use {data.decisive_count} decisive attempts. Canceled, skipped,
          neutral, stale and unknown conclusions remain separate. Each retry counts as its own
          attempt.
        </p>
        <div className="analytics-table-wrap">
          <table className="analytics-table">
            <thead>
              <tr>
                <th scope="col">Outcome</th>
                <th scope="col">Observed count</th>
                <th scope="col">Rate</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Successful attempts</th>
                <td data-label="Observed count">{data.success_count}</td>
                <td data-label="Rate">{fraction(data.success_fraction)}</td>
                <td data-label="Evidence">
                  <Link
                    className="text-link"
                    href={ciEvidence(filters, data.window, { outcome: "success" })}
                  >
                    View successful attempts
                  </Link>
                </td>
              </tr>
              <tr>
                <th scope="row">Failed attempts</th>
                <td data-label="Observed count">{data.failure_count}</td>
                <td data-label="Rate">{fraction(data.failure_fraction)}</td>
                <td data-label="Evidence">
                  <Link
                    className="text-link"
                    href={ciEvidence(filters, data.window, { outcome: "failure" })}
                  >
                    View failed attempts
                  </Link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <details className="analytics-daily-data">
          <summary>All observed conclusions</summary>
          <dl className="analytics-facts">
            {Object.entries(data.conclusions).map(([conclusion, count]) => (
              <div key={conclusion}>
                <dt>{conclusion}</dt>
                <dd>{count}</dd>
              </div>
            ))}
          </dl>
          <Link className="text-link" href={ciEvidence(filters, data.window, { outcome: "other" })}>
            View other conclusions
          </Link>
        </details>
        <div className="analytics-table-wrap">
          <table className="analytics-table analytics-distributions">
            <thead>
              <tr>
                <th scope="col">Timing</th>
                <th scope="col">Mean</th>
                <th scope="col">Median</th>
                <th scope="col">P75</th>
                <th scope="col">P95</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {(["duration", "queue"] as const).map((metric) => (
                <DistributionRow
                  key={metric}
                  name={metric === "duration" ? "Attempt duration" : "Queue time"}
                  value={data[metric]}
                  included={ciEvidence(filters, data.window, { metric, eligibility: "eligible" })}
                  excluded={ciEvidence(filters, data.window, { metric, eligibility: "excluded" })}
                />
              ))}
            </tbody>
          </table>
        </div>
        <p className="analytics-note">
          Duration and queue time use the same decisive completed cohort, with separate timestamp
          exclusions. Queue timing requires an observed queue timestamp for that attempt. Calculated{" "}
          {utcDate(data.as_of)} · {data.formula_version}.
        </p>
      </section>
      <section className="analytics-section">
        <h2>Daily CI trend</h2>
        <p className="analytics-note">
          UTC completion dates. Daily rates use that day’s decisive attempts.
        </p>
        <details className="analytics-daily-data">
          <summary>View daily outcomes and durations</summary>
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th scope="col">Completed (UTC)</th>
                  <th scope="col">Decisive attempts</th>
                  <th scope="col">Success rate</th>
                  <th scope="col">Duration median / P95</th>
                </tr>
              </thead>
              <tbody>
                {[...data.trend].reverse().map((day) => (
                  <tr key={day.date}>
                    <th scope="row">
                      <Link
                        className="text-link"
                        href={ciEvidence(filters, dayWindow(day.date, data.window))}
                      >
                        {day.date}
                      </Link>
                      <span className="analytics-meta">{day.completed_count} completions</span>
                    </th>
                    <td data-label="Decisive attempts">
                      {day.decisive_count}
                      <span className="analytics-meta">
                        {day.success_count} successful · {day.failure_count} failed
                      </span>
                    </td>
                    <td data-label="Success rate">{fraction(day.success_fraction)}</td>
                    <td data-label="Duration median / P95">
                      {duration(day.duration.median_seconds)} / {duration(day.duration.p95_seconds)}
                      <span className="analytics-meta">
                        {day.duration.sample_count} timing samples · {day.duration.excluded_count}{" "}
                        excluded
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
      <section className="analytics-section">
        <h2>Recurring workflow failures</h2>
        <p className="analytics-note">
          Observed failures grouped by workflow in the same completed window. Category is unknown;
          Forge does not infer a root cause from job names or logs.
        </p>
        {data.recurring_failures.length ? (
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th scope="col">Workflow</th>
                  <th scope="col">Failures / decisive</th>
                  <th scope="col">Failure rate</th>
                  <th scope="col">Category</th>
                </tr>
              </thead>
              <tbody>
                {data.recurring_failures.map((item) => (
                  <tr key={`${item.repository_id}:${item.workflow_id}`}>
                    <th scope="row">
                      <Link
                        href={ciEvidence(
                          {
                            ...filters,
                            repository: item.repository_id,
                            workflow: String(item.workflow_id),
                          },
                          data.window,
                          { outcome: "failure" },
                        )}
                      >
                        {item.workflow_name}
                      </Link>
                      <span className="analytics-meta">{item.repository_name}</span>
                    </th>
                    <td data-label="Failures / decisive">
                      {item.failure_count} / {item.decisive_count}
                    </td>
                    <td data-label="Failure rate">{fraction(item.failure_fraction)}</td>
                    <td data-label="Category">Unknown</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="analytics-empty">No recurring workflow failures observed in this cohort.</p>
        )}
      </section>
    </>
  );
}
function DeploymentSummary({
  data,
  filters,
}: {
  data: DeploymentMetrics;
  filters: DeliveryFilters;
}) {
  return (
    <>
      <section className="analytics-section">
        <h2>First successful deployments</h2>
        <WindowLabel window={data.window} cohort="First success" />
        <p className="analytics-note">
          {classificationLabel(data.scope.classification)} · Each deployment counts once, at its
          first successful status. Complete status history is required to establish that first
          success.
        </p>
        <div className="analytics-table-wrap">
          <table className="analytics-table">
            <thead>
              <tr>
                <th scope="col">Observation</th>
                <th scope="col">Value</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Eligible first successes</th>
                <td data-label="Value">{data.successful_count}</td>
                <td data-label="Evidence">
                  <Link className="text-link" href={deploymentEvidence(filters, data.window)}>
                    View included deployments
                  </Link>
                </td>
              </tr>
              <tr>
                <th scope="row">Excluded first-success observations</th>
                <td data-label="Value">{data.excluded_count}</td>
                <td data-label="Evidence">
                  <Link
                    className="text-link"
                    href={deploymentEvidence(filters, data.window, "excluded")}
                  >
                    View excluded deployments
                  </Link>
                  {Object.entries(data.exclusions)
                    .filter(([, count]) => count > 0)
                    .map(([reason, count]) => (
                      <span className="analytics-meta" key={reason}>
                        {count} · {deliveryReason(reason)}
                      </span>
                    ))}
                </td>
              </tr>
              <tr>
                <th scope="row">Deployment frequency</th>
                <td data-label="Value">
                  {data.frequency_per_day == null
                    ? "Not available"
                    : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(data.frequency_per_day)} / day`}
                </td>
                <td data-label="Evidence">{data.fully_covered_days} fully covered UTC days</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="analytics-note">
          {data.observed_success_count} first-success observations before exclusions. Frequency uses
          full UTC days only and remains unavailable when window coverage is incomplete. Partial-day
          successes may appear in the raw count. Calculated {utcDate(data.as_of)} ·{" "}
          {data.formula_version}.
        </p>
        <details className="analytics-daily-data">
          <summary>Created deployments and observed states</summary>
          <p>
            {data.created_count} deployments created in the window. These counts describe creation,
            separately from first-success timing.
          </p>
          <dl className="analytics-facts">
            {Object.entries(data.states).map(([state, count]) => (
              <div key={state}>
                <dt>{state}</dt>
                <dd>{count}</dd>
              </div>
            ))}
          </dl>
        </details>
      </section>
      <section className="analytics-section">
        <h2>Daily deployment trend</h2>
        <details className="analytics-daily-data">
          <summary>View daily first successes and coverage</summary>
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th scope="col">Date (UTC)</th>
                  <th scope="col">Eligible successes</th>
                  <th scope="col">Observed successes</th>
                  <th scope="col">Day coverage</th>
                </tr>
              </thead>
              <tbody>
                {[...data.trend].reverse().map((day) => (
                  <tr key={day.date}>
                    <th scope="row">
                      <Link
                        className="text-link"
                        href={deploymentEvidence(filters, dayWindow(day.date, data.window))}
                      >
                        {day.date}
                      </Link>
                    </th>
                    <td data-label="Eligible successes">{day.successful_count}</td>
                    <td data-label="Observed successes">{day.observed_success_count}</td>
                    <td data-label="Day coverage">
                      {day.fully_covered ? "Complete UTC day" : "Partial or unavailable"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
    </>
  );
}
function dayWindow(day: string, window: TimeWindow): TimeWindow {
  const start = Date.parse(day + "T00:00:00Z");
  return {
    from: new Date(Math.max(start, Date.parse(window.from))).toISOString(),
    to: new Date(Math.min(start + 86400000, Date.parse(window.to))).toISOString(),
  };
}
