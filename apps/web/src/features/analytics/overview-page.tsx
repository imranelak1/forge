"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/features/auth/auth-provider";
import { api } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import {
  AnalyticsError,
  AnalyticsLoading,
  DemoNotice,
  EmptyHistory,
  FilterBar,
  PullRequestTable,
  RefreshData,
  WindowLabel,
} from "./analytics-ui";
import {
  duration,
  evidenceHref,
  exclusionLabel,
  filterQuery,
  metricDefinitions,
  metricKeys,
  metricLabels,
  readFilters,
  utcDate,
  type Filters,
  type MetricKey,
  type Metrics,
} from "./types";

export function OverviewPage() {
  const { organization } = useAuth();
  const search = useSearchParams();
  if (!organization) return null;
  return (
    <OverviewContent
      key={`${organization.id}:${search.toString()}`}
      organization={organization}
      filters={readFilters(new URLSearchParams(search), "metrics")}
    />
  );
}
function OverviewContent({
  organization,
  filters,
}: {
  organization: Organization;
  filters: Filters;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const query = useQuery({
    queryKey: ["organization", organization.id, "analytics", "metrics", filterQuery(filters)],
    queryFn: ({ signal }) =>
      api<Metrics>(
        `/organizations/${organization.id}/metrics/pull-requests?${filterQuery(filters)}`,
        { signal },
      ),
    retry: false,
  });
  const data = query.data;
  return (
    <div className="analytics-content">
      <div className="page-heading">
        <div>
          <h1>Engineering overview</h1>
          <p>{organization.name} · Pull request flow and the evidence behind it.</p>
        </div>
        <Link className="text-link" href="/app/repositories">
          Repository imports
        </Link>
      </div>
      <DemoNotice demo={organization.is_demo} />
      <nav className="delivery-overview-links" aria-label="Delivery analytics">
        <Link className="text-link" href="/app/ci">
          CI outcomes and attempts
        </Link>
        <Link className="text-link" href="/app/deployments">
          Deployment frequency and evidence
        </Link>
      </nav>
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <FilterBar
        organization={organization.id}
        filters={filters}
        kind="metrics"
        apply={(next) => router.replace(`${pathname}?${filterQuery(next)}`)}
      />
      {query.isPending ? (
        <AnalyticsLoading label="Loading pull request metrics" />
      ) : query.isError ? (
        <AnalyticsError error={query.error} retry={query.refetch} />
      ) : (
        data && (
          <>
            <section className="analytics-section" aria-labelledby="merged-heading">
              <div className="analytics-section-heading">
                <h2 id="merged-heading">Merged pull requests</h2>
                <Link className="text-link" href={evidenceHref(filters, data.window)}>
                  {data.merged_count} merged · View cohort
                </Link>
              </div>
              <WindowLabel window={data.window} />
              <div className="analytics-table-wrap">
                <table className="analytics-table analytics-distributions">
                  <thead>
                    <tr>
                      <th scope="col">Metric</th>
                      <th scope="col">Mean</th>
                      <th scope="col">Median</th>
                      <th scope="col">P75</th>
                      <th scope="col">P95</th>
                      <th scope="col">Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metricKeys.map((key) => {
                      const metric = data.metrics[key];
                      return (
                        <tr key={key}>
                          <th scope="row">
                            {metricLabels[key]}
                            <span className="analytics-meta">{metricDefinitions[key]}</span>
                          </th>
                          {(
                            [
                              "mean_seconds",
                              "median_seconds",
                              "p75_seconds",
                              "p95_seconds",
                            ] as const
                          ).map((stat, index) => (
                            <td key={stat} data-label={["Mean", "Median", "P75", "P95"][index]}>
                              {duration(metric[stat])}
                            </td>
                          ))}
                          <td data-label="Evidence">
                            <Link
                              className="text-link"
                              href={evidenceHref(filters, data.window, key)}
                            >
                              {metric.sample_count} included
                            </Link>
                            <Link
                              className="analytics-meta text-link"
                              href={evidenceHref(filters, data.window, key, "excluded")}
                            >
                              {metric.excluded_count} excluded
                            </Link>
                            {Object.entries(metric.exclusions)
                              .filter(([, count]) => count > 0)
                              .map(([reason, count]) => (
                                <span className="analytics-meta" key={reason}>
                                  {count} · {exclusionLabel(reason)}
                                </span>
                              ))}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="analytics-note">
                All three metrics use the same merge window. P75 and P95 are the durations at the
                75th and 95th percentiles. Missing or invalid evidence is excluded separately for
                each metric.
              </p>
            </section>
            <section className="analytics-section" aria-labelledby="coverage-heading">
              <div className="analytics-section-heading">
                <h2 id="coverage-heading">Source coverage</h2>
                <span
                  className={
                    data.coverage.status === "complete" ? "analytics-observed" : "analytics-missing"
                  }
                >
                  {data.coverage.status === "complete"
                    ? "Complete observations"
                    : data.coverage.status === "partial"
                      ? "Partial observations"
                      : "Observations unavailable"}
                </span>
              </div>
              <p>
                {data.scope.repository_count} {data.scope.selected_only ? "selected" : "filtered"}{" "}
                repositories · {data.coverage.repositories_synced} with a completed import. Review
                history: {data.coverage.reviews_complete} complete,{" "}
                {data.coverage.reviews_incomplete} incomplete.
              </p>
              <p className="analytics-note">
                Oldest repository sync: {utcDate(data.coverage.input_watermark)}. Calculated{" "}
                {utcDate(data.as_of)} · {data.formula_version}.
              </p>
              {!!data.coverage.dismissed_approval_count && (
                <p className="analytics-note">
                  {data.coverage.dismissed_approval_count} historical approvals were later
                  dismissed; they remain observed timing evidence.
                </p>
              )}
              {!!data.coverage.unknown_dismissed_review_count && (
                <p className="analytics-note">
                  {data.coverage.unknown_dismissed_review_count} dismissed reviews have unknown
                  original states.
                </p>
              )}
              {!!data.coverage.unknown_reviewer_count && (
                <p className="analytics-note">
                  {data.coverage.unknown_reviewer_count} reviews have unknown reviewer identities;
                  affected timing samples remain excluded.
                </p>
              )}
              {data.coverage.limitations.length > 0 && (
                <ul className="analytics-limitations">
                  {data.coverage.limitations.map((code) => (
                    <li key={code}>{exclusionLabel(code)}</li>
                  ))}
                </ul>
              )}
              {data.coverage.status !== "complete" && (
                <p className="analytics-note">
                  These figures describe imported history.{" "}
                  <Link className="text-link" href="/app/repositories">
                    Check sync progress
                  </Link>{" "}
                  for missing source evidence.
                </p>
              )}
            </section>
            <Trend data={data} filters={filters} />
            <section className="analytics-section">
              <h2>Open pull request queue</h2>
              <p>
                {data.open_queue.count} open as of {utcDate(data.as_of)}. This current queue is
                separate from the merge window.
              </p>
              <dl className="analytics-facts">
                <div>
                  <dt>Mean age</dt>
                  <dd>{duration(data.open_queue.age.mean_seconds)}</dd>
                </div>
                <div>
                  <dt>Median age</dt>
                  <dd>{duration(data.open_queue.age.median_seconds)}</dd>
                </div>
                <div>
                  <dt>P95 age</dt>
                  <dd>{duration(data.open_queue.age.p95_seconds)}</dd>
                </div>
                <div>
                  <dt>Age evidence</dt>
                  <dd>
                    {data.open_queue.age.sample_count} included ·{" "}
                    {data.open_queue.age.excluded_count} excluded
                  </dd>
                </div>
              </dl>
              {data.open_queue.oldest.length ? (
                <>
                  <h3>Oldest observed requests</h3>
                  <PullRequestTable items={data.open_queue.oldest} />
                </>
              ) : (
                <EmptyHistory>
                  No open pull requests observed in this repository and author scope.
                </EmptyHistory>
              )}
            </section>
          </>
        )
      )}
    </div>
  );
}
function Trend({ data, filters }: { data: Metrics; filters: Filters }) {
  const [metric, setMetric] = useState<MetricKey>("cycle_time");
  const points = data.trend.map((day, index) => ({
    day,
    value: day.metrics[metric].median_seconds,
    x: data.trend.length > 1 ? (index / (data.trend.length - 1)) * 980 + 10 : 500,
  }));
  const maximum = Math.max(...points.map((point) => point.value ?? 0), 1);
  const y = (value: number) => 170 - (value / maximum) * 150;
  const segments: string[] = [];
  let current = "";
  for (const point of points) {
    if (point.value === null) {
      if (current) segments.push(current);
      current = "";
    } else current += `${point.x},${y(point.value)} `;
  }
  if (current) segments.push(current);
  const observed = points.some((point) => point.value !== null);
  return (
    <section className="analytics-section">
      <div className="analytics-section-heading">
        <h2>Daily merge trend</h2>
        <label className="analytics-inline-filter">
          Median duration
          <select
            aria-label="Trend metric"
            value={metric}
            onChange={(event) => setMetric(event.target.value as MetricKey)}
          >
            {metricKeys.map((key) => (
              <option value={key} key={key}>
                {metricLabels[key]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="analytics-note">
        UTC merge dates. Each point opens that day’s included PRs; gaps mean no eligible samples.
      </p>
      {observed ? (
        <div className="analytics-chart">
          <div className="analytics-chart-range">
            <span>{duration(maximum)}</span>
            <span>0 sec</span>
          </div>
          <div className="analytics-chart-plot">
            <svg
              viewBox="0 0 1000 190"
              preserveAspectRatio="none"
              role="img"
              aria-label={`Daily median ${metricLabels[metric].toLowerCase()}, with links to sample evidence`}
            >
              <line x1="0" x2="1000" y1="170" y2="170" className="analytics-chart-axis" />
              {segments.map((segment, index) => (
                <polyline
                  key={index}
                  points={segment}
                  fill="none"
                  className="analytics-chart-line"
                />
              ))}
              {points
                .filter((point) => point.value !== null)
                .map((point) => (
                  <a
                    key={point.day.date}
                    href={dayEvidence(filters, data, point.day.date, metric)}
                    aria-label={`${point.day.date}: ${duration(point.value)}, ${point.day.metrics[metric].sample_count} samples`}
                  >
                    <circle
                      cx={point.x}
                      cy={y(point.value!)}
                      r="5"
                      className="analytics-chart-point"
                    >
                      <title>
                        {point.day.date}: {duration(point.value)} ·{" "}
                        {point.day.metrics[metric].sample_count} included
                      </title>
                    </circle>
                  </a>
                ))}
            </svg>
            <div className="analytics-chart-dates">
              <span>{points[0]?.day.date}</span>
              <span>{points.at(-1)?.day.date}</span>
            </div>
          </div>
        </div>
      ) : (
        <p className="analytics-empty">
          No eligible {metricLabels[metric].toLowerCase()} samples in this window.
        </p>
      )}
      <details className="analytics-daily-data">
        <summary>View daily values and sample counts</summary>
        <div className="analytics-table-wrap">
          <table className="analytics-table">
            <thead>
              <tr>
                <th scope="col">Merge date (UTC)</th>
                <th scope="col">Merged</th>
                <th scope="col">Median</th>
                <th scope="col">P95</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {[...data.trend].reverse().map((day) => (
                <tr key={day.date}>
                  <th scope="row">{day.date}</th>
                  <td data-label="Merged">{day.merged_count}</td>
                  <td data-label="Median">{duration(day.metrics[metric].median_seconds)}</td>
                  <td data-label="P95">{duration(day.metrics[metric].p95_seconds)}</td>
                  <td data-label="Evidence">
                    <Link className="text-link" href={dayEvidence(filters, data, day.date, metric)}>
                      {day.metrics[metric].sample_count} included
                    </Link>
                    <span className="analytics-meta">
                      {day.metrics[metric].excluded_count} excluded
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
function dayEvidence(filters: Filters, data: Metrics, day: string, metric: MetricKey) {
  const start = new Date(day + "T00:00:00Z");
  const end = new Date(start.getTime() + 86400000);
  return evidenceHref(
    filters,
    {
      from: new Date(Math.max(start.getTime(), Date.parse(data.window.from))).toISOString(),
      to: new Date(Math.min(end.getTime(), Date.parse(data.window.to))).toISOString(),
    },
    metric,
  );
}
