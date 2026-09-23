import { validId, type TimeWindow } from "@/features/analytics/types";

export type CaseStatus = "passed" | "failed" | "error" | "skipped";
export interface TestPolicy {
  version: number;
  lookback_days: number;
  min_executions: number;
  failure_rate_min: number;
  failure_rate_max: number;
  min_flips: number;
  excluded_branches: string[];
}
export interface TestCoverage {
  status: "partial" | "unavailable";
  limitations: string[];
  input_watermark: string | null;
  known_workflow_count: number;
  with_reports_count: number;
  missing_report_count: number;
  queued_report_count: number;
  failed_report_count: number;
  warning_report_count: number;
  unknown_link_count: number;
  completion_proxy_count: number;
}
export interface TestMetrics {
  formula_version: string;
  as_of: string;
  window: TimeWindow;
  scope: {
    repository_id: string | null;
    selected_only: boolean;
    branch: string | null;
    environment: string | null;
  };
  passed_count: number;
  failed_count: number;
  error_count: number;
  skipped_count: number;
  eligible_count: number;
  pass_fraction: number | null;
  report_count: number;
  trend: {
    date: string;
    passed_count: number;
    failed_count: number;
    error_count: number;
    skipped_count: number;
    eligible_count: number;
    pass_fraction: number | null;
  }[];
  coverage: TestCoverage;
}
export interface TestReport {
  id: string;
  repository_id: string;
  repository_name: string;
  workflow_run_id: string | null;
  provider_run_id: number;
  run_attempt: number;
  head_sha: string | null;
  branch: string | null;
  environment: string | null;
  report_key: string;
  shard: string;
  status: string;
  received_at: string;
  source_at: string | null;
  completion_source: string | null;
  superseded_by: string | null;
  case_count: number;
  warning_count: number;
}
export interface TestSuite {
  id: string;
  name: string;
  path: string[];
  ordinal: number;
  case_count: number;
  declared_counts: Record<string, number | null>;
}
export interface TestCase {
  id: string;
  test_id: string;
  name: string;
  class_name: string;
  file: string;
  status: CaseStatus;
  duration_seconds: number | null;
  failure_message: string | null;
  ordinal: number;
  retry_ordinal: number;
  is_final: boolean;
  identity_quality: string;
}
export interface TestEvidence {
  id: string;
  repository_id: string;
  repository_name: string;
  name: string;
  class_name: string;
  file: string;
  branch: string | null;
  environment: string | null;
  report_key: string;
  shard: string;
  sample_count: number;
  passed_count: number;
  failed_count: number;
  flip_count: number;
  same_sha_reversal_count: number;
  failure_fraction: number | null;
  first_at: string | null;
  last_at: string | null;
  potential_flaky: boolean;
  confidence: "standard" | "reduced";
  policy: TestPolicy;
}
export interface TestExecution extends TestCase {
  test_run_id: string;
  workflow_run_id: string | null;
  provider_run_id: number;
  run_attempt: number;
  head_sha: string | null;
  branch: string | null;
  environment: string | null;
  source_at: string | null;
  report_key: string;
  shard: string;
  superseded: boolean;
}
export interface TestHistory {
  test: {
    id: string;
    repository_id: string;
    name: string;
    class_name: string;
    file: string;
    identity_quality: string;
  };
  items: TestExecution[];
  next_cursor: string | null;
  window: TimeWindow;
  evidence: TestEvidence[];
  evidence_truncated: boolean;
}
export interface ReportDetail {
  test_run: TestReport;
  warnings: string[];
  counts: { suites: number; cases: number };
  error_code: string | null;
}
export interface TestPage<T> {
  items: T[];
  next_cursor: string | null;
  window?: TimeWindow;
  as_of?: string;
}
export interface TestFilters {
  repository?: string;
  branch?: string;
  environment?: string;
  from?: string;
  to?: string;
  status?: string;
  potential_only?: string;
}
export interface RepositoryTestPolicy {
  repository_id: string;
  version?: number;
  window_days: number;
  min_executions: number;
  failure_rate_low: number;
  failure_rate_high: number;
  min_transitions: number;
  excluded_branches: string[];
  updated_at: string | null;
}
export interface CIToken {
  id: string;
  repository_id: string;
  name: string;
  token_prefix: string;
  scope: "test_reports:write";
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
}
export function readTestFilters(search: URLSearchParams): TestFilters {
  const out: TestFilters = {};
  const repository = search.get("repository");
  if (repository && validId(repository)) out.repository = repository;
  for (const key of ["branch", "environment"] as const) {
    const value = search.get(key);
    if (value && value.length <= 255 && !/[\u0000-\u001f\u007f]/.test(value)) out[key] = value;
  }
  for (const key of ["from", "to"] as const) {
    const value = search.get(key);
    if (
      value &&
      value.length <= 40 &&
      /^\d{4}-\d{2}-\d{2}T/.test(value) &&
      /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
      Number.isFinite(Date.parse(value))
    )
      out[key] = value;
  }
  const status = search.get("status");
  if (status && ["queued", "processing", "completed", "failed"].includes(status))
    out.status = status;
  if (["true", "false"].includes(search.get("potential_only") ?? ""))
    out.potential_only = search.get("potential_only")!;
  return out;
}
export function testQuery(filters: TestFilters) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters))
    if (value !== undefined && value !== "") query.set(key, value);
  return query.toString();
}
export function metricScope(filters: TestFilters): TestFilters {
  const { repository, branch, environment, from, to } = filters;
  return { repository, branch, environment, from, to };
}
export function historyHref(
  id: string,
  context: Pick<TestEvidence, "branch" | "environment">,
  window?: Partial<TimeWindow>,
) {
  const query = testQuery({
    branch: context.branch ?? undefined,
    environment: context.environment ?? undefined,
    ...window,
  });
  return `/app/tests/cases/${id}${query ? `?${query}` : ""}`;
}
const reasons: Record<string, string> = {
  no_reports: "No test reports received for this scope",
  no_selected_repositories: "No repositories selected",
  uploaded_reports_only:
    "Coverage describes uploaded reports; it does not establish complete CI coverage",
  missing_reports: "Known workflow attempts have no uploaded report",
  pending_reports: "Some reports are waiting to be processed",
  failed_reports: "Some reports could not be processed",
  report_warnings: "Some reports have quality warnings",
  unknown_link:
    "Some reports have no usable workflow completion time or belong to an attempt still running",
  invalid_xml: "The XML report could not be parsed",
  invalid_report: "The report could not be accepted",
};
export const testReason = (code: string) => reasons[code] ?? code.replaceAll("_", " ");
