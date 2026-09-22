export type MetricKey = "cycle_time" | "review_wait" | "approval_to_merge";
export const metricKeys: MetricKey[] = ["cycle_time", "review_wait", "approval_to_merge"];
export const metricLabels: Record<MetricKey, string> = {
  cycle_time: "Cycle time",
  review_wait: "Review wait",
  approval_to_merge: "Approval to merge",
};
export const metricDefinitions: Record<MetricKey, string> = {
  cycle_time: "Opened to merged, including draft and reopened time.",
  review_wait: "Opened to first submitted review by someone other than the author; bots excluded.",
  approval_to_merge:
    "First known qualifying approval to merge, including approvals later dismissed.",
};
export interface Distribution {
  sample_count: number;
  excluded_count: number;
  mean_seconds: number | null;
  median_seconds: number | null;
  p75_seconds: number | null;
  p95_seconds: number | null;
  exclusions: Record<string, number>;
}
export interface EvidenceCoverage {
  status: "pending" | "complete" | "partial" | "failed" | "unavailable";
  observed_at: string | null;
  error_code: string | null;
}
export interface TimeWindow {
  from: string;
  to: string;
}
export interface Page<T> {
  items: T[];
  next_cursor: string | null;
  window?: TimeWindow;
}
export interface PullRequest {
  id: string;
  repository_id: string;
  repository_name: string;
  number: number;
  title: string;
  state: "open" | "closed";
  draft: boolean;
  author_login: string | null;
  html_url: string | null;
  opened_at: string;
  updated_at: string;
  closed_at: string | null;
  merged_at: string | null;
  head_sha: string;
  base_ref: string;
  merge_commit_sha: string | null;
  durations: Record<MetricKey, number | null>;
  exclusions: Record<MetricKey, string | null>;
  first_review_at: string | null;
  first_approved_at: string | null;
  approval_dismissed: boolean;
  unknown_dismissed_review_count: number;
  coverage: Record<"reviews" | "transitions" | "commits" | "issues", EvidenceCoverage>;
  relationship?: string;
}
export interface Commit {
  id: string;
  repository_id: string;
  repository_name: string;
  sha: string;
  message: string;
  author_login: string | null;
  authored_at: string | null;
  committed_at: string;
  html_url: string | null;
  additions: number | null;
  deletions: number | null;
  changed_files: number | null;
  files_coverage: EvidenceCoverage;
  pull_request_count: number;
  relationship?: string;
}
export interface Review {
  id: string;
  provider_id: number;
  reviewer_login: string | null;
  reviewer_type: string;
  state: string;
  submitted_at: string | null;
  approved_at: string | null;
  dismissed_at: string | null;
  html_url: string | null;
  qualifies: boolean;
  approval_known: boolean;
}
export interface Transition {
  id: string;
  provider_id: number;
  kind: string;
  occurred_at: string;
  actor_login: string | null;
  html_url: string | null;
}
export interface CommitFile {
  id: string;
  filename: string;
  previous_filename: string | null;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  blob_url: string | null;
}
export interface Issue {
  id: string;
  repository_id: string;
  repository_name: string;
  number: number;
  title: string;
  state: string;
  author_login: string | null;
  opened_at: string;
  updated_at: string;
  closed_at: string | null;
  html_url: string | null;
  relationship?: string;
  links_coverage: EvidenceCoverage;
}
export interface Metrics {
  formula_version: string;
  as_of: string;
  window: TimeWindow;
  scope: { repository_id: string | null; selected_only: boolean; repository_count: number };
  merged_count: number;
  metrics: Record<MetricKey, Distribution>;
  trend: { date: string; merged_count: number; metrics: Record<MetricKey, Distribution> }[];
  open_queue: { count: number; age: Distribution; oldest: PullRequest[] };
  coverage: {
    status: "complete" | "partial" | "unavailable";
    input_watermark: string | null;
    repository_count: number;
    repositories_synced: number;
    reviews_complete: number;
    reviews_incomplete: number;
    dismissed_approval_count: number;
    unknown_dismissed_review_count: number;
    unknown_reviewer_count: number;
    limitations: string[];
  };
}
export interface Filters {
  repository?: string;
  author?: string;
  from?: string;
  to?: string;
  state?: string;
  cohort?: string;
  metric?: MetricKey;
  eligibility?: string;
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const validId = (value: string) => uuid.test(value);
export function readFilters(
  search: URLSearchParams,
  kind: "metrics" | "pull-requests" | "commits" | "issues",
): Filters {
  const filters: Filters = {};
  const repository = search.get("repository");
  if (repository && validId(repository)) filters.repository = repository;
  const author = search.get("author");
  if (author && validAuthor(author)) filters.author = author;
  for (const key of ["from", "to"] as const) {
    const value = search.get(key);
    if (
      value &&
      value.length <= 40 &&
      /^\d{4}-\d{2}-\d{2}T/.test(value) &&
      /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
      Number.isFinite(Date.parse(value))
    )
      filters[key] = value;
  }
  if (kind === "issues") {
    const state = search.get("state");
    if (state && ["all", "open", "closed"].includes(state)) filters.state = state;
  }
  if (kind === "pull-requests") {
    const state = search.get("state");
    if (state && ["all", "open", "closed", "merged"].includes(state)) filters.state = state;
    const cohort = search.get("cohort");
    if (cohort && ["activity", "merged"].includes(cohort)) filters.cohort = cohort;
    const metric = search.get("metric") as MetricKey;
    if (metricKeys.includes(metric)) {
      filters.metric = metric;
      filters.cohort = "merged";
    }
    const eligibility = search.get("eligibility");
    if (eligibility && ["eligible", "excluded", "all"].includes(eligibility))
      filters.eligibility = eligibility;
  }
  return filters;
}
export function filterQuery(filters: Filters) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
  return query.toString();
}
export function evidenceHref(
  filters: Filters,
  window: TimeWindow,
  metric?: MetricKey,
  eligibility = "eligible",
) {
  return `/app/pull-requests?${filterQuery({ repository: filters.repository, author: filters.author, ...window, cohort: "merged", ...(metric ? { metric, eligibility } : {}) })}`;
}
export function duration(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "Not available";
  if (seconds === 0) return "0 sec";
  const [value, unit] =
    seconds >= 86400
      ? [seconds / 86400, "days"]
      : seconds >= 3600
        ? [seconds / 3600, "hr"]
        : seconds >= 60
          ? [seconds / 60, "min"]
          : [seconds, "sec"];
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)} ${unit}`;
}
export function utcDate(value: string | null | undefined) {
  if (!value || !Number.isFinite(Date.parse(value))) return "Not observed";
  return (
    new Date(value).toLocaleString(undefined, {
      timeZone: "UTC",
      dateStyle: "medium",
      timeStyle: "short",
    }) + " UTC"
  );
}
const reasons: Record<string, string> = {
  invalid_timestamps: "Invalid or missing timestamps",
  incomplete_reviews: "Review history incomplete",
  missing_review: "No qualifying review observed",
  missing_approval: "No qualifying approval observed",
  unknown_dismissed_review: "Original dismissed review state unknown",
  unknown_reviewer: "Reviewer identity unknown; earliest qualifying review is uncertain",
  not_merged: "Not merged",
  unmerged: "Not merged",
  missing_author: "PR author identity unknown",
  not_configured: "Source not configured",
  permissions_required: "GitHub permission required",
  access_denied: "GitHub access unavailable",
  issues_permission_missing: "Issues permission not granted",
  pending_enrichment: "Evidence import pending",
  history_window: "Limited imported history",
  incomplete_history: "Imported history is incomplete",
  reviews_incomplete: "Review history incomplete",
  no_selected_repositories: "No repositories selected for this scope",
  repositories_not_synced: "Some repositories have not completed an import",
  history_window_partial: "Imported history does not cover the entire requested window",
  source_access_unavailable: "Some source repositories are no longer accessible",
};
export const validAuthor = (value: string) => /^[a-z\d][a-z\d-]{0,38}(?:\[bot\])?$/i.test(value);
export const exclusionLabel = (code: string | null | undefined) =>
  code ? (reasons[code] ?? "Source evidence is incomplete") : "No exclusion";
export function sourceUrl(value: string | null | undefined) {
  if (!value || value.length > 4096 || /[\\\u0000-\u0020]/.test(value)) return null;
  try {
    const url = new URL(value);
    return url.origin === "https://github.com" &&
      !url.username &&
      !url.password &&
      /^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/(pull|issues|commit|blob)\//.test(url.pathname)
      ? url.href
      : null;
  } catch {
    return null;
  }
}
