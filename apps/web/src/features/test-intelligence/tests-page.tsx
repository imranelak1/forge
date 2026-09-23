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
  PageMore,
  RefreshData,
  WindowLabel,
} from "@/features/analytics/analytics-ui";
import { utcDate } from "@/features/analytics/types";
import { fraction } from "@/features/delivery/types";
import {
  metricScope,
  readTestFilters,
  testQuery,
  type TestEvidence,
  type TestFilters,
  type TestMetrics,
  type TestReport,
} from "./types";
import {
  ReportTable,
  TestCoverageSummary,
  TestEvidenceTable,
  TestFiltersForm,
  UploadHelp,
  testKeys,
  useTestPage,
} from "./tests-ui";

export function TestsPage() {
  const { organization } = useAuth(),
    search = useSearchParams();
  if (!organization) return null;
  return (
    <TestsContent
      key={`${organization.id}:${search}`}
      organization={organization}
      filters={readTestFilters(new URLSearchParams(search))}
    />
  );
}
function TestsContent({
  organization,
  filters,
}: {
  organization: Organization;
  filters: TestFilters;
}) {
  const router = useRouter(),
    pathname = usePathname(),
    scope = metricScope(filters),
    query = testQuery(scope);
  const summary = useQuery({
    queryKey: [...testKeys(organization.id), "metrics", query],
    queryFn: ({ signal }) =>
      api<TestMetrics>(`/organizations/${organization.id}/metrics/tests?${query}`, { signal }),
    retry: false,
  });
  const reports = useTestPage<TestReport>(organization.id, "test-runs", {
    ...scope,
    status: filters.status,
  });
  const candidates = useTestPage<TestEvidence>(organization.id, "tests", {
    repository: filters.repository,
    branch: filters.branch,
    environment: filters.environment,
    to: filters.to,
    potential_only: filters.potential_only ?? "true",
  });
  const reportItems = reports.data?.pages.flatMap((p) => p.items) ?? [],
    testItems = candidates.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <div className="analytics-content">
      <div className="page-heading">
        <div>
          <h1>Test intelligence</h1>
          <p>
            {organization.name} · Uploaded test results and the evidence behind changing outcomes.
          </p>
        </div>
        <div className="delivery-heading-actions">
          <Link
            className="text-link"
            href={`/app/tests/settings${filters.repository ? `?repository=${filters.repository}` : ""}`}
          >
            Report uploads and policy
          </Link>
          <RefreshData organization={organization.id} />
        </div>
      </div>
      <DemoNotice demo={organization.is_demo} />
      <TestFiltersForm
        organization={organization.id}
        filters={filters}
        apply={(next) => router.replace(`${pathname}?${testQuery(next)}`)}
      />
      {summary.isPending ? (
        <AnalyticsLoading label="Loading test metrics" />
      ) : summary.isError ? (
        <AnalyticsError error={summary.error} retry={summary.refetch} />
      ) : (
        summary.data && (
          <>
            <TestCoverageSummary value={summary.data.coverage} />
            <TestSummary data={summary.data} />
          </>
        )
      )}
      <section className="analytics-section" id="test-history">
        <h2>
          {filters.potential_only === "false" ? "Observed test histories" : "Potential flaky tests"}
        </h2>
        <p className="analytics-note">
          One final outcome per workflow attempt, evaluated separately by test, branch and
          environment. The repository policy controls lookback and thresholds; the From filter above
          applies to metrics and reports. A changing outcome is evidence for investigation, not
          proof of a flaky defect.
        </p>
        {candidates.isPending ? (
          <AnalyticsLoading label="Loading test histories" />
        ) : candidates.isError && !testItems.length ? (
          <AnalyticsError error={candidates.error} retry={candidates.refetch} />
        ) : (
          <>
            {testItems.length ? (
              <TestEvidenceTable
                items={testItems}
                window={filters.to ? { to: filters.to } : undefined}
              />
            ) : (
              <p className="analytics-empty">
                {filters.potential_only === "false"
                  ? "No test histories observed in this scope."
                  : "No observed tests meet the current policy thresholds. Missing reports and small samples can prevent a signal; this does not establish that every test is stable."}
              </p>
            )}
            <PageMore result={candidates} count={testItems.length} />
          </>
        )}
      </section>
      <section className="analytics-section" id="reports">
        <h2>Test reports</h2>
        <p className="analytics-note">
          Report status filters this list. Earlier attempts and superseded reports remain
          inspectable; they are not silently added to the overview denominator.
        </p>
        <WindowLabel window={reports.data?.pages[0].window} cohort="Reports" />
        {reports.isPending ? (
          <AnalyticsLoading label="Loading test reports" />
        ) : reports.isError && !reportItems.length ? (
          <AnalyticsError error={reports.error} retry={reports.refetch} />
        ) : (
          <>
            {reportItems.length ? (
              <ReportTable items={reportItems} filters={filters} />
            ) : (
              <UploadHelp repository={filters.repository} />
            )}
            <PageMore result={reports} count={reportItems.length} />
          </>
        )}
      </section>
    </div>
  );
}
function TestSummary({ data }: { data: TestMetrics }) {
  const rows: [[string, number], ...[string, number][]] = [
    ["Passed", data.passed_count],
    ["Failed", data.failed_count],
    ["Errors", data.error_count],
    ["Skipped (outside denominator)", data.skipped_count],
  ];
  return (
    <>
      <section className="analytics-section">
        <div className="analytics-section-heading">
          <h2>Test outcomes</h2>
          <a className="text-link" href="#reports">
            {data.report_count} reports · Inspect reports
          </a>
        </div>
        <WindowLabel window={data.window} cohort="Workflow evidence" />
        <div className="analytics-table-wrap">
          <table className="analytics-table">
            <thead>
              <tr>
                <th scope="col">Measurement</th>
                <th scope="col">Value</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Pass rate</th>
                <td data-label="Value">{fraction(data.pass_fraction)}</td>
                <td data-label="Evidence">
                  {data.eligible_count} eligible executions
                  <span className="analytics-meta">Passed ÷ (passed + failed + error)</span>
                </td>
              </tr>
              {rows.map(([name, count]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td data-label="Value">{count}</td>
                  <td data-label="Evidence">
                    {name.startsWith("Skipped")
                      ? "Reported separately"
                      : "Final explicit retry in the selected report cohort"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="analytics-note">
          Calculated {utcDate(data.as_of)} · {data.formula_version}. An unavailable pass rate means
          no eligible denominator, not a measured zero.
        </p>
      </section>
      <section className="analytics-section">
        <h2>Daily test outcomes</h2>
        <details className="analytics-daily-data">
          <summary>View daily results and denominators</summary>
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th scope="col">Date (UTC)</th>
                  <th scope="col">Pass rate</th>
                  <th scope="col">Eligible</th>
                  <th scope="col">Outcomes</th>
                </tr>
              </thead>
              <tbody>
                {[...data.trend].reverse().map((day) => (
                  <tr key={day.date}>
                    <th scope="row">{day.date}</th>
                    <td data-label="Pass rate">{fraction(day.pass_fraction)}</td>
                    <td data-label="Eligible">{day.eligible_count}</td>
                    <td data-label="Outcomes">
                      {day.passed_count} passed · {day.failed_count} failed · {day.error_count}{" "}
                      errors<span className="analytics-meta">{day.skipped_count} skipped</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!data.trend.length && (
            <p className="analytics-empty">No daily observations in this window.</p>
          )}
        </details>
      </section>
    </>
  );
}
