"use client";

import Link from "next/link";
import { useId, useState, type ReactNode } from "react";
import { useInfiniteQuery, useIsFetching, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/auth-client";
import type { Repository } from "@/features/github/types";
import type { Commit, EvidenceCoverage, Filters, Page, PullRequest, TimeWindow } from "./types";
import {
  duration,
  exclusionLabel,
  filterQuery,
  metricKeys,
  metricLabels,
  sourceUrl,
  utcDate,
  validAuthor,
} from "./types";

export function AnalyticsLoading({ label = "Loading imported history" }: { label?: string }) {
  return (
    <div className="analytics-loading" role="status">
      <p>{label}…</p>
      <span />
      <span />
      <span />
    </div>
  );
}
export function AnalyticsError({ error, retry }: { error: unknown; retry: () => unknown }) {
  return (
    <div className="analytics-error">
      <p className="form-error" role="alert">
        {errorMessage(error)}
      </p>
      <Button variant="outline" onClick={() => void retry()}>
        Try again
      </Button>
    </div>
  );
}
export function EmptyHistory({ children }: { children?: ReactNode }) {
  return (
    <div className="analytics-empty">
      <p>{children ?? "No imported records match these filters."}</p>
      <Link className="text-link" href="/app/repositories">
        Review repository imports
      </Link>
    </div>
  );
}
export function SourceLink({
  url,
  children = "View on GitHub",
}: {
  url: string | null;
  children?: ReactNode;
}) {
  const href = sourceUrl(url);
  return href ? (
    <a className="analytics-source text-link" href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <ExternalLink size={13} aria-hidden="true" />
    </a>
  ) : null;
}
export function Coverage({ value, label }: { value: EvidenceCoverage; label?: string }) {
  const labels = {
    pending: "Import pending",
    complete: "Complete",
    partial: "Partial history",
    failed: "Import failed",
    unavailable: "Unavailable",
  };
  return (
    <div className="analytics-coverage-item">
      <span className={value.status === "complete" ? "analytics-observed" : "analytics-missing"}>
        {label ? `${label}: ` : ""}
        {labels[value.status] ?? "Unknown coverage"}
      </span>
      {value.observed_at && <span>Observed {utcDate(value.observed_at)}</span>}
      {value.error_code && (
        <span>{exclusionLabel(value.error_code)}. Check repository sync details.</span>
      )}
    </div>
  );
}
export function WindowLabel({
  window,
  cohort = "Merged",
}: {
  window?: TimeWindow;
  cohort?: string;
}) {
  return window ? (
    <p className="analytics-window">
      {cohort} from {utcDate(window.from)} to {utcDate(window.to)} (end excluded).
    </p>
  ) : null;
}
export function DemoNotice({ demo }: { demo: boolean }) {
  return demo ? (
    <p className="phase-notice github-notice">
      This organization contains generated demonstration history. Metrics use those stored records.
    </p>
  ) : null;
}
export function RefreshData({ organization }: { organization: string }) {
  const client = useQueryClient();
  const queryKey = ["organization", organization, "analytics"];
  const busy = useIsFetching({ queryKey }) > 0;
  return (
    <Button
      variant="outline"
      disabled={busy}
      onClick={() => void client.invalidateQueries({ queryKey })}
    >
      {busy ? "Refreshing data…" : "Refresh data"}
    </Button>
  );
}
export function FilterBar({
  organization,
  filters,
  kind,
  apply,
}: {
  organization: string;
  filters: Filters;
  kind: "metrics" | "pull-requests" | "commits" | "issues";
  apply: (filters: Filters) => void;
}) {
  const [draft, setDraft] = useState(filters);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const filterId = useId();
  const activeCount = Object.values(filters).filter((value) => value && value !== "all").length;
  const repositories = useInfiniteQuery({
    queryKey: ["organization", organization, "analytics-repositories"],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<Page<Repository>>(
        `/organizations/${organization}/repositories?limit=100${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });
  const items = repositories.data?.pages.flatMap((page) => page.items) ?? [];
  function change(key: keyof Filters, value: string) {
    setDraft({ ...draft, [key]: value || undefined });
  }
  return (
    <form
      className={`analytics-filters${expanded ? " is-open" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        const next = { ...draft, author: draft.author?.trim() || undefined };
        if (next.author && !validAuthor(next.author)) {
          setError(
            "Enter an exact GitHub login (letters, numbers or hyphens; bot logins may end with [bot]).",
          );
          return;
        }
        if (
          next.from &&
          next.to &&
          (Date.parse(next.to) <= Date.parse(next.from) ||
            Date.parse(next.to) - Date.parse(next.from) > 366 * 86400000)
        ) {
          setError("Choose an end after the start, within 366 days.");
          return;
        }
        if (next.metric) next.cohort = "merged";
        setError("");
        apply(next);
      }}
    >
      <button
        className="analytics-filter-toggle"
        type="button"
        aria-expanded={expanded}
        aria-controls={filterId}
        onClick={() => setExpanded(!expanded)}
      >
        <span>
          Filters{" "}
          <span className="analytics-filter-summary">
            {activeCount ? `${activeCount} applied` : "Last 90 days"}
          </span>
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      <div className="analytics-filter-body" id={filterId}>
        <div className="analytics-filter-fields">
          <label>
            Repository
            <select
              value={draft.repository ?? ""}
              onChange={(event) => change("repository", event.target.value)}
            >
              <option value="">All selected repositories</option>
              {draft.repository && !items.some((repo) => repo.id === draft.repository) && (
                <option value={draft.repository}>Filtered repository (retained history)</option>
              )}
              {items.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            GitHub author
            <input
              value={draft.author ?? ""}
              maxLength={44}
              placeholder="Any author"
              onChange={(event) => change("author", event.target.value)}
            />
          </label>
          <label>
            From (UTC)
            <input
              type="datetime-local"
              step="1"
              value={draft.from ? new Date(draft.from).toISOString().slice(0, 19) : ""}
              onChange={(event) =>
                change(
                  "from",
                  event.target.value ? new Date(`${event.target.value}Z`).toISOString() : "",
                )
              }
            />
          </label>
          <label>
            Before (UTC)
            <input
              type="datetime-local"
              step="1"
              value={draft.to ? new Date(draft.to).toISOString().slice(0, 19) : ""}
              onChange={(event) =>
                change(
                  "to",
                  event.target.value ? new Date(`${event.target.value}Z`).toISOString() : "",
                )
              }
            />
          </label>
          {kind === "issues" && (
            <label>
              State
              <select
                value={draft.state ?? "all"}
                onChange={(event) => change("state", event.target.value)}
              >
                <option value="all">All states</option>
                <option value="open">Open</option>
                <option value="closed">Closed</option>
              </select>
            </label>
          )}
          {kind === "pull-requests" && (
            <>
              <label>
                State
                <select
                  value={draft.state ?? "all"}
                  onChange={(event) => change("state", event.target.value)}
                >
                  {["all", "open", "closed", "merged"].map((value) => (
                    <option key={value} value={value}>
                      {value === "all" ? "All states" : value[0].toUpperCase() + value.slice(1)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Window applies to
                <select
                  value={draft.metric ? "merged" : (draft.cohort ?? "activity")}
                  disabled={!!draft.metric}
                  onChange={(event) => change("cohort", event.target.value)}
                >
                  <option value="activity">Last activity</option>
                  <option value="merged">Merge time</option>
                </select>
              </label>
              <label>
                Metric evidence
                <select
                  value={draft.metric ?? ""}
                  onChange={(event) => change("metric", event.target.value)}
                >
                  <option value="">All pull requests</option>
                  {metricKeys.map((key) => (
                    <option key={key} value={key}>
                      {metricLabels[key]}
                    </option>
                  ))}
                </select>
              </label>
              {draft.metric && (
                <label>
                  Samples
                  <select
                    value={draft.eligibility ?? "eligible"}
                    onChange={(event) => change("eligibility", event.target.value)}
                  >
                    <option value="eligible">Included</option>
                    <option value="excluded">Excluded</option>
                    <option value="all">All in cohort</option>
                  </select>
                </label>
              )}
            </>
          )}
        </div>
        <div className="analytics-filter-actions">
          <Button type="submit" variant="outline">
            Apply filters
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
          <span>Defaults to the last 90 days. All times are UTC.</span>
        </div>
        {repositories.isError && (
          <div className="analytics-filter-actions">
            <p className="form-error">Repository choices could not load.</p>
            <button type="button" className="text-link" onClick={() => void repositories.refetch()}>
              Retry repository choices
            </button>
          </div>
        )}
        {repositories.hasNextPage && (
          <button
            type="button"
            className="text-link"
            disabled={repositories.isFetchingNextPage}
            onClick={() => void repositories.fetchNextPage()}
          >
            {repositories.isFetchingNextPage
              ? "Loading repositories…"
              : "Load more repository choices"}
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

export function useEvidencePage<T>(organization: string, path: string, filters: Filters = {}) {
  const query = filterQuery(filters);
  return useInfiniteQuery({
    queryKey: ["organization", organization, "analytics", path, query],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<Page<T>>(
        `/organizations/${organization}/${path}?limit=30${query ? `&${query}` : ""}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });
}
export function EvidenceSection<T>({
  organization,
  path,
  title,
  coverage,
  children,
}: {
  organization: string;
  path: string;
  title: string;
  coverage?: EvidenceCoverage;
  children: (items: T[]) => ReactNode;
}) {
  const result = useEvidencePage<T>(organization, path);
  const items = result.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section className="analytics-section">
      <h2>{title}</h2>
      {coverage && <Coverage value={coverage} />}
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
              {coverage && coverage.status !== "complete"
                ? "No records imported yet. Coverage above describes what is missing."
                : "No records observed."}
            </p>
          )}
          <PageMore result={result} count={items.length} />
        </>
      )}
    </section>
  );
}
export function PageMore({
  result,
  count,
}: {
  result: {
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    isFetchNextPageError: boolean;
    error: unknown;
    fetchNextPage: () => unknown;
  };
  count: number;
}) {
  return (
    <div className="analytics-pagination">
      <span>{count} records loaded</span>
      {result.isFetchNextPageError && (
        <p className="form-error" role="alert">
          {errorMessage(result.error)}
        </p>
      )}
      {result.hasNextPage && (
        <Button
          variant="outline"
          disabled={result.isFetchingNextPage}
          onClick={() => void result.fetchNextPage()}
        >
          {result.isFetchingNextPage
            ? "Loading more…"
            : result.isFetchNextPageError
              ? "Retry loading more"
              : "Load more"}
        </Button>
      )}
    </div>
  );
}
export function PullRequestTable({
  items,
  metric,
}: {
  items: PullRequest[];
  metric?: import("./types").MetricKey;
}) {
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Pull request</th>
            <th scope="col">State</th>
            <th scope="col">{metric ? metricLabels[metric] : "Last activity"}</th>
            <th scope="col">Review evidence</th>
          </tr>
        </thead>
        <tbody>
          {items.map((pr) => (
            <tr key={pr.id}>
              <th scope="row">
                <Link href={`/app/pull-requests/${pr.id}`}>{pr.title}</Link>
                <span className="analytics-meta">
                  {pr.repository_name} #{pr.number} · {pr.author_login ?? "Unknown author"}
                  {pr.relationship ? ` · ${relationshipLabel(pr.relationship)}` : ""}
                </span>
              </th>
              <td data-label="State">
                {pr.merged_at
                  ? "Merged"
                  : pr.draft
                    ? "Draft"
                    : pr.state === "open"
                      ? "Open"
                      : "Closed"}
              </td>
              <td data-label={metric ? metricLabels[metric] : "Last activity"}>
                {metric ? (
                  <>
                    {duration(pr.durations[metric])}
                    {pr.exclusions[metric] && (
                      <span className="analytics-meta">
                        {exclusionLabel(pr.exclusions[metric])}
                      </span>
                    )}
                  </>
                ) : (
                  utcDate(pr.updated_at)
                )}
              </td>
              <td data-label="Review evidence">
                <Coverage value={pr.coverage.reviews} />
                {pr.approval_dismissed && (
                  <span className="analytics-meta">Historical approval later dismissed</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function CommitTable({ items }: { items: Commit[] }) {
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Commit</th>
            <th scope="col">Committed</th>
            <th scope="col">Changes</th>
            <th scope="col">Observed PR links</th>
          </tr>
        </thead>
        <tbody>
          {items.map((commit) => (
            <tr key={commit.id}>
              <th scope="row">
                <Link href={`/app/commits/${commit.id}`}>
                  {commit.message.split("\n")[0] || "Untitled commit"}
                </Link>
                <span className="analytics-meta">
                  {commit.repository_name} · <code>{commit.sha.slice(0, 8)}</code> ·{" "}
                  {commit.author_login ?? "Unknown author"}
                  {commit.relationship ? ` · ${relationshipLabel(commit.relationship)}` : ""}
                </span>
              </th>
              <td data-label="Committed">{utcDate(commit.committed_at)}</td>
              <td data-label="Changes">
                {commit.changed_files === null ? "Not available" : `${commit.changed_files} files`}
                <span className="analytics-meta">
                  {commit.additions == null || commit.deletions == null
                    ? "Change totals not observed"
                    : `+${commit.additions} / −${commit.deletions} lines`}
                </span>
                <Coverage value={commit.files_coverage} />
              </td>
              <td data-label="Observed PR links">{commit.pull_request_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function relationshipLabel(value: string) {
  return (
    (
      {
        member: "PR member",
        merge: "Merge commit",
        member_and_merge: "PR member and merge commit",
        closes: "Closing reference",
        references: "Explicit reference",
        cross_reference: "Explicit reference",
      } as Record<string, string>
    )[value] ?? "Explicit association"
  );
}
