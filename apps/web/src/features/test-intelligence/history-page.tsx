"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
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
import { duration, utcDate, validId } from "@/features/analytics/types";
import { readTestFilters, testQuery, type TestFilters, type TestHistory } from "./types";
import { TestEvidenceTable, TestFiltersForm, TestOutcome, testKeys } from "./tests-ui";

export function TestHistoryPage({ id }: { id: string }) {
  const { organization } = useAuth(),
    search = useSearchParams();
  if (!organization) return null;
  if (!validId(id)) return <p className="analytics-empty">This test address is invalid.</p>;
  const { branch, environment, from, to } = readTestFilters(new URLSearchParams(search));
  return (
    <HistoryContent
      key={`${organization.id}:${id}:${search}`}
      organization={organization}
      id={id}
      filters={{ branch, environment, from, to }}
    />
  );
}
function HistoryContent({
  organization,
  id,
  filters,
}: {
  organization: Organization;
  id: string;
  filters: TestFilters;
}) {
  const router = useRouter(),
    pathname = usePathname(),
    query = testQuery(filters);
  const history = useInfiniteQuery({
    queryKey: [...testKeys(organization.id), "history", id, query],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<TestHistory>(
        `/organizations/${organization.id}/tests/${id}/history?limit=30${query ? `&${query}` : ""}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });
  const data = history.data?.pages[0],
    items = history.data?.pages.flatMap((p) => p.items) ?? [];
  if (history.isPending) return <AnalyticsLoading label="Loading test history" />;
  if (history.isError && !data)
    return <AnalyticsError error={history.error} retry={history.refetch} />;
  if (!data) return null;
  return (
    <div className="analytics-content">
      <Link
        className="analytics-back text-link"
        href={`/app/tests?repository=${data.test.repository_id}`}
      >
        Test intelligence
      </Link>
      <div className="page-heading">
        <div>
          <h1>{data.test.name}</h1>
          <p>{data.test.class_name || data.test.file || "No class or file supplied"}</p>
        </div>
        <RefreshData organization={organization.id} />
      </div>
      <DemoNotice demo={organization.is_demo} />
      <TestFiltersForm
        organization={organization.id}
        kind="history"
        filters={filters}
        apply={(next) => router.replace(`${pathname}?${testQuery(next)}`)}
      />
      <section className="analytics-section">
        <h2>Potential-flakiness evidence</h2>
        <p className="analytics-note">
          Evaluation uses the current policy lookback ending at the selected Before time. The From
          filter controls the execution list below, so evaluation samples can extend beyond that
          list&apos;s window.
        </p>
        <p className="analytics-note">
          Each row evaluates a distinct branch/environment and report context under the current
          repository policy. Counts use eligible final outcomes; failed and error outcomes form the
          failing side of a transition. Same-SHA reversals provide supporting evidence and do not
          prove a defect.
        </p>
        <p className="analytics-note">
          Identity quality: {data.test.identity_quality.replaceAll("_", " ")}. Missing identity or
          context can reduce confidence.
        </p>
        {data.evidence.length ? (
          <TestEvidenceTable items={data.evidence} window={data.window} />
        ) : (
          <p className="analytics-empty">
            No eligible policy samples for this context. Recorded executions below remain available
            for inspection.
          </p>
        )}
        {data.evidence_truncated && (
          <p className="analytics-note">
            Only the first 100 evidence contexts are shown. Filter by branch and environment to
            narrow the evaluation.
          </p>
        )}
      </section>
      <section className="analytics-section">
        <h2>Execution history</h2>
        <WindowLabel window={data.window} cohort="Test evidence" />
        <p className="analytics-note">
          Earlier retries and superseded reports stay visible here. Source time is shown only when
          observed; receipt ordering does not invent a source timestamp.
        </p>
        {items.length ? (
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th scope="col">Report and attempt</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Context</th>
                  <th scope="col">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <th scope="row">
                      <Link href={`/app/tests/reports/${item.test_run_id}`}>
                        {item.report_key} · {item.shard || "Default shard"}
                      </Link>
                      <span className="analytics-meta">
                        Run {item.provider_run_id} · attempt {item.run_attempt}
                      </span>
                      {item.workflow_run_id && (
                        <Link
                          className="analytics-meta text-link"
                          href={`/app/ci/${item.workflow_run_id}`}
                        >
                          View workflow attempt
                        </Link>
                      )}
                    </th>
                    <td data-label="Outcome">
                      <TestOutcome status={item.status} />
                      <span className="analytics-meta">
                        {duration(item.duration_seconds)} · retry ordinal {item.retry_ordinal}
                      </span>
                      <span className="analytics-meta">
                        {item.is_final ? "Final explicit retry" : "Earlier retry"}
                        {item.superseded ? " · Superseded report" : ""}
                      </span>
                    </td>
                    <td data-label="Context">
                      {item.branch ?? "Branch unknown"}
                      <span className="analytics-meta">
                        {item.environment ?? "Environment unknown"}
                      </span>
                      <span className="analytics-meta mono">
                        {item.head_sha ?? "Commit unknown"}
                      </span>
                    </td>
                    <td data-label="Evidence">
                      {utcDate(item.source_at)}
                      {item.failure_message && (
                        <details className="tests-failure">
                          <summary>Read failure message</summary>
                          <pre>{item.failure_message}</pre>
                        </details>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="analytics-empty">No executions in this observation window.</p>
        )}
        <PageMore result={history} count={items.length} />
      </section>
    </div>
  );
}
