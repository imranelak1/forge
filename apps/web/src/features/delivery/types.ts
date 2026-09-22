import {
  readFilters,
  validId,
  type Distribution,
  type EvidenceCoverage,
  type TimeWindow,
} from "@/features/analytics/types";
export interface DeliveryCoverage {
  status: "complete" | "partial" | "unavailable";
  input_watermark: string | null;
  repository_count: number;
  repositories_complete: number;
  limitations: string[];
  completion_unknown_count?: number;
  completion_proxy_count?: number;
  jobs_incomplete_count?: number;
  statuses_incomplete_count?: number;
}
export interface DeliveryPage<T> {
  items: T[];
  next_cursor: string | null;
  window?: TimeWindow;
  coverage?: DeliveryCoverage;
}
export interface WorkflowRun {
  id: string;
  repository_id: string;
  repository_name: string;
  provider_id: number;
  workflow_id: number;
  workflow_name: string;
  run_number: number;
  attempt: number;
  event: string;
  status: string;
  conclusion: string | null;
  head_sha: string;
  head_branch: string | null;
  actor_login: string | null;
  created_at: string;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  completion_source: string | null;
  html_url: string | null;
  duration_seconds: number | null;
  queue_seconds: number | null;
  duration_exclusion: string | null;
  queue_exclusion: string | null;
  jobs_coverage: EvidenceCoverage;
  links_coverage: EvidenceCoverage;
}
export interface Job {
  id: string;
  provider_id: number;
  name: string;
  status: string;
  conclusion: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  html_url: string | null;
}
export interface CIMetrics {
  formula_version: string;
  as_of: string;
  window: TimeWindow;
  scope: {
    repository_id: string | null;
    selected_only: boolean;
    repository_count: number;
    workflow_id: number | null;
    branch: string | null;
  };
  completed_count: number;
  decisive_count: number;
  success_count: number;
  failure_count: number;
  success_fraction: number | null;
  failure_fraction: number | null;
  conclusions: Record<string, number>;
  duration: Distribution;
  queue: Distribution;
  coverage: DeliveryCoverage;
  trend: {
    date: string;
    completed_count: number;
    decisive_count: number;
    success_count: number;
    failure_count: number;
    success_fraction: number | null;
    duration: Distribution;
    queue: Distribution;
  }[];
  recurring_failures: {
    repository_id: string;
    repository_name: string;
    workflow_id: number;
    workflow_name: string;
    decisive_count: number;
    failure_count: number;
    failure_fraction: number | null;
    category: string;
  }[];
}
export type Classification = "production" | "nonproduction" | "unknown";
export interface Deployment {
  id: string;
  repository_id: string;
  repository_name: string;
  provider_id: number;
  environment: string;
  classification: Classification;
  classification_source: "override" | "provider" | "unknown";
  provider_production_environment: boolean | null;
  sha: string;
  ref: string;
  task: string;
  creator_login: string | null;
  created_at: string;
  updated_at: string;
  first_success_at: string | null;
  latest_state: string | null;
  success_eligible: boolean;
  success_exclusion: string | null;
  html_url: string | null;
  statuses_coverage: EvidenceCoverage;
  links_coverage: EvidenceCoverage;
}
export interface DeploymentStatus {
  id: string;
  provider_id: number;
  state: string;
  created_at: string;
  creator_login: string | null;
  description: string | null;
  html_url: string | null;
}
export interface DeploymentMetrics {
  formula_version: string;
  as_of: string;
  window: TimeWindow;
  scope: {
    repository_id: string | null;
    selected_only: boolean;
    repository_count: number;
    environment: string | null;
    classification: string;
  };
  successful_count: number;
  observed_success_count: number;
  excluded_count: number;
  exclusions: Record<string, number>;
  fully_covered_days: number;
  frequency_per_day: number | null;
  created_count: number;
  states: Record<string, number>;
  coverage: DeliveryCoverage;
  trend: {
    date: string;
    successful_count: number;
    observed_success_count: number;
    fully_covered: boolean;
  }[];
}
export interface EnvironmentPolicy {
  environment: string;
  override: "production" | "nonproduction" | null;
  deployment_count: number;
  production_count: number;
  nonproduction_count: number;
  unknown_count: number;
}
export interface DeliveryFilters {
  repository?: string;
  from?: string;
  to?: string;
  workflow?: string;
  branch?: string;
  cohort?: string;
  outcome?: string;
  metric?: string;
  eligibility?: string;
  environment?: string;
  classification?: string;
}
export function deliveryQuery(filters: DeliveryFilters) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
  return query.toString();
}
export function readDeliveryFilters(
  search: URLSearchParams,
  kind: "ci" | "deployments",
): DeliveryFilters {
  const common = readFilters(search, "metrics");
  const filters: DeliveryFilters = {
    repository: common.repository,
    from: common.from,
    to: common.to,
  };
  if (kind === "ci") {
    const workflow = search.get("workflow");
    if (workflow && /^[1-9]\d{0,18}$/.test(workflow)) filters.workflow = workflow;
    const branch = search.get("branch");
    if (branch && branch.length <= 255 && !/[\u0000-\u001f\u007f]/.test(branch))
      filters.branch = branch;
    const cohort = search.get("cohort");
    if (cohort && ["activity", "completed"].includes(cohort)) filters.cohort = cohort;
    const outcome = search.get("outcome");
    if (outcome && ["all", "success", "failure", "other"].includes(outcome))
      filters.outcome = outcome;
    const metric = search.get("metric");
    if (metric && ["duration", "queue"].includes(metric)) {
      filters.metric = metric;
      filters.cohort = "completed";
    }
  } else {
    const environment = search.get("environment");
    if (environment && environment.length <= 255 && !/[\u0000-\u001f\u007f]/.test(environment))
      filters.environment = environment;
    const classification = search.get("classification");
    if (
      classification &&
      ["production", "nonproduction", "unknown", "all"].includes(classification)
    )
      filters.classification = classification;
    const cohort = search.get("cohort");
    if (cohort && ["created", "success"].includes(cohort)) filters.cohort = cohort;
  }
  const eligibility = search.get("eligibility");
  if (eligibility && ["all", "eligible", "excluded"].includes(eligibility))
    filters.eligibility = eligibility;
  return filters;
}
export function metricFilters(
  filters: DeliveryFilters,
  kind: "ci" | "deployments",
): DeliveryFilters {
  return {
    repository: filters.repository,
    from: filters.from,
    to: filters.to,
    ...(kind === "ci"
      ? { workflow: filters.workflow, branch: filters.branch }
      : { environment: filters.environment, classification: filters.classification }),
  };
}
export function ciEvidence(
  filters: DeliveryFilters,
  window: TimeWindow,
  extra: DeliveryFilters = {},
) {
  return `/app/ci?${deliveryQuery({ ...metricFilters(filters, "ci"), ...window, cohort: "completed", ...extra })}#attempts`;
}
export function deploymentEvidence(
  filters: DeliveryFilters,
  window: TimeWindow,
  eligibility = "eligible",
) {
  return `/app/deployments?${deliveryQuery({ ...metricFilters(filters, "deployments"), ...window, cohort: "success", eligibility })}#deployment-records`;
}
export const fraction = (value: number | null) =>
  value == null
    ? "Not available"
    : new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 }).format(
        value,
      );
export const classificationLabel = (value: string) =>
  ({
    production: "Production",
    nonproduction: "Non-production",
    unknown: "Unknown",
    all: "All classifications",
  })[value] ?? "Unknown";
const reasons: Record<string, string> = {
  no_selected_repositories: "No repositories selected",
  repositories_not_synced: "Some repositories have not completed an import",
  source_access_unavailable: "GitHub access is unavailable for part of this scope",
  history_window_partial: "Imported history does not cover the requested window",
  permissions_required: "GitHub App permission required",
  access_denied: "GitHub access unavailable",
  actions_permission_missing: "Actions read permission is missing",
  deployments_permission_missing: "Deployments read permission is missing",
  invalid_timestamps: "Missing or invalid timing evidence",
  missing_completion: "Completion time not observed",
  missing_queue_time: "Attempt queue time not observed",
  incomplete_jobs: "Job history incomplete",
  incomplete_statuses: "Deployment status history incomplete",
  unknown_classification: "Environment classification unknown",
  no_success: "No successful status observed",
  not_decisive: "Outcome is outside the decisive cohort",
  non_decisive: "Outcome is outside the decisive cohort",
  start_unknown: "Attempt start time not observed",
  queue_unknown: "Attempt queue time not observed",
  commit_not_imported: "The source commit has not been imported",
  incomplete_history: "Source history incomplete",
  incomplete_links: "Commit or PR evidence incomplete",
  source_incomplete: "Source enumeration is incomplete",
  completion_unknown: "Completed attempts are missing a usable completion timestamp",
  jobs_incomplete: "Some attempts have incomplete job history",
  statuses_incomplete: "Some deployments have incomplete status history",
  job_completion_proxy: "Some completion timestamps use the last job as a proxy",
};
export const deliveryReason = (value: string | null) =>
  value ? (reasons[value] ?? "Source evidence is incomplete") : "No exclusion";
export function deliverySource(value: string | null) {
  if (!value || value.length > 4096 || /[\\\u0000-\u0020]/.test(value)) return null;
  try {
    const url = new URL(value);
    return url.origin === "https://github.com" &&
      !url.username &&
      !url.password &&
      /^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/(actions\/(runs|jobs)\/|deployments(\/|$)|commit\/)/.test(
        url.pathname,
      )
      ? url.href
      : null;
  } catch {
    return null;
  }
}
export const validRepository = validId;
