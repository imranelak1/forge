"use client";
import Link from "next/link";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/auth-provider";
import { api } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import {
  AnalyticsError,
  AnalyticsLoading,
  DemoNotice,
  RefreshData,
} from "@/features/analytics/analytics-ui";
import { utcDate, validId } from "@/features/analytics/types";
import {
  readTestFilters,
  testQuery,
  testReason,
  type ReportDetail,
  type TestCase,
  type TestSuite,
} from "./types";
import { CaseTable, EvidenceList, TestOutcome, testKeys } from "./tests-ui";

export function ReportPage({ id }: { id: string }) {
  const { organization } = useAuth(),
    search = useSearchParams();
  if (!organization) return null;
  if (!validId(id)) return <p className="analytics-empty">This report address is invalid.</p>;
  return (
    <ReportContent
      key={`${organization.id}:${id}`}
      organization={organization}
      id={id}
      back={testQuery(readTestFilters(new URLSearchParams(search)))}
    />
  );
}
function ReportContent({
  organization,
  id,
  back,
}: {
  organization: Organization;
  id: string;
  back: string;
}) {
  const [status, setStatus] = useState("");
  const query = useQuery({
    queryKey: [...testKeys(organization.id), "test-run", id],
    queryFn: ({ signal }) =>
      api<ReportDetail>(`/organizations/${organization.id}/test-runs/${id}`, { signal }),
    retry: false,
  });
  if (query.isPending) return <AnalyticsLoading label="Loading test report" />;
  if (query.isError) return <AnalyticsError error={query.error} retry={query.refetch} />;
  const { test_run: report, warnings, counts, error_code } = query.data;
  return (
    <div className="analytics-content">
      <Link className="analytics-back text-link" href={`/app/tests${back ? `?${back}` : ""}`}>
        Test intelligence
      </Link>
      <div className="page-heading">
        <div>
          <h1>{report.report_key}</h1>
          <p>
            {report.repository_name} · {report.shard || "Default shard"} · attempt{" "}
            {report.run_attempt}
          </p>
        </div>
        <RefreshData organization={organization.id} />
      </div>
      <DemoNotice demo={organization.is_demo} />
      <p className="tests-report-status">
        <TestOutcome status={report.status} />
        {report.superseded_by && (
          <>
            {" "}
            · Superseded by{" "}
            <Link className="text-link" href={`/app/tests/reports/${report.superseded_by}`}>
              replacement report
            </Link>
          </>
        )}
      </p>
      {["queued", "processing"].includes(report.status) && (
        <p className="analytics-note">
          This report is waiting for its test evidence to finish processing. Use Refresh data to
          check its result.
        </p>
      )}
      {error_code && (
        <p className="form-error" role="alert">
          Report import: {testReason(error_code)}.{" "}
          <Link className="text-link" href="/guide#test-reports">
            Review upload requirements
          </Link>
          .
        </p>
      )}
      <dl className="analytics-facts">
        <div>
          <dt>Workflow attempt</dt>
          <dd>
            {report.workflow_run_id ? (
              <Link className="text-link" href={`/app/ci/${report.workflow_run_id}`}>
                Run {report.provider_run_id} · attempt {report.run_attempt}
              </Link>
            ) : (
              <>Run {report.provider_run_id} · link unresolved</>
            )}
          </dd>
        </div>
        <div>
          <dt>Commit SHA</dt>
          <dd className="mono">{report.head_sha ?? "Not observed"}</dd>
        </div>
        <div>
          <dt>Branch / environment</dt>
          <dd>
            {report.branch ?? "Branch unknown"} · {report.environment ?? "Environment unknown"}
          </dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>{utcDate(report.received_at)}</dd>
        </div>
        <div>
          <dt>Source timestamp</dt>
          <dd>
            {utcDate(report.source_at)}
            {report.completion_source === "jobs" && (
              <span className="analytics-meta">Last-job completion proxy</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Retained evidence</dt>
          <dd>
            {counts.suites} suites · {counts.cases} case executions
          </dd>
        </div>
      </dl>
      {warnings.length > 0 && (
        <section className="analytics-section">
          <h2>Quality warnings ({warnings.length})</h2>
          <ul className="analytics-limitations">
            {warnings.map((warning, index) => (
              <li key={`${index}:${warning}`}>{testReason(warning)}</li>
            ))}
          </ul>
          <p className="analytics-note">
            Declared suite totals and observed case records can differ. Inspect the report evidence
            before interpreting its rate.
          </p>
        </section>
      )}
      <EvidenceList<TestSuite>
        organization={organization.id}
        path={`test-runs/${id}/suites`}
        title={`Test suites (${counts.suites})`}
        empty="No suites have been imported for this report."
      >
        {(items) => (
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th scope="col">Suite</th>
                  <th scope="col">Observed cases</th>
                  <th scope="col">Declared counts</th>
                </tr>
              </thead>
              <tbody>
                {items.map((suite) => (
                  <tr key={suite.id}>
                    <th scope="row">
                      {suite.name || "Unnamed suite"}
                      <span className="analytics-meta">{suite.path.join(" / ")}</span>
                    </th>
                    <td data-label="Observed cases">{suite.case_count}</td>
                    <td data-label="Declared counts">
                      {Object.entries(suite.declared_counts).length
                        ? Object.entries(suite.declared_counts).map(([name, count]) => (
                            <span className="analytics-meta" key={name}>
                              {name}: {count ?? "Not supplied"}
                            </span>
                          ))
                        : "Not supplied"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </EvidenceList>
      <div className="tests-case-filter">
        <label className="analytics-inline-filter">
          Case outcome
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All outcomes</option>
            {["passed", "failed", "error", "skipped"].map((s) => (
              <option value={s} key={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <p className="analytics-note">
          Final retry marks the last explicit retry in this report. It does not imply that a
          superseded report belongs in the metric cohort.
        </p>
      </div>
      <EvidenceList<TestCase>
        key={status}
        organization={organization.id}
        path={`test-runs/${id}/cases`}
        filters={{ status: status || undefined }}
        title={`Case executions (${counts.cases})`}
        empty="No case executions match this report and outcome."
      >
        {(items) => <CaseTable items={items} />}
      </EvidenceList>
    </div>
  );
}
