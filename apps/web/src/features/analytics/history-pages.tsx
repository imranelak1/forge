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
  CommitTable,
  Coverage,
  DemoNotice,
  EmptyHistory,
  EvidenceSection,
  FilterBar,
  PageMore,
  PullRequestTable,
  RefreshData,
  SourceLink,
  WindowLabel,
  relationshipLabel,
  useEvidencePage,
} from "./analytics-ui";
import {
  duration,
  exclusionLabel,
  filterQuery,
  metricDefinitions,
  metricKeys,
  metricLabels,
  readFilters,
  utcDate,
  validId,
  type Commit,
  type CommitFile,
  type Filters,
  type Issue,
  type PullRequest,
  type Review,
  type Transition,
} from "./types";

export function HistoryPage({ kind }: { kind: "pull-requests" | "commits" }) {
  const { organization } = useAuth();
  const search = useSearchParams();
  if (!organization) return null;
  return (
    <HistoryContent
      key={`${organization.id}:${kind}:${search.toString()}`}
      organization={organization}
      kind={kind}
      filters={readFilters(new URLSearchParams(search), kind)}
    />
  );
}
function HistoryContent({
  organization,
  kind,
  filters,
}: {
  organization: Organization;
  kind: "pull-requests" | "commits";
  filters: Filters;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const result = useEvidencePage<PullRequest | Commit>(organization.id, kind, filters);
  const items = result.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <div className="analytics-content">
      <div className="page-heading">
        <div>
          <h1>
            {kind === "commits"
              ? "Commits"
              : filters.metric
                ? `${metricLabels[filters.metric]} evidence`
                : "Pull requests"}
          </h1>
          <p>
            {organization.name} ·{" "}
            {kind === "commits"
              ? "Imported commits and their explicit pull request associations."
              : filters.metric
                ? metricDefinitions[filters.metric]
                : "Imported pull requests, review evidence and lifecycle history."}
          </p>
        </div>
        <Link className="text-link" href="/app">
          Engineering overview
        </Link>
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <FilterBar
        organization={organization.id}
        filters={filters}
        kind={kind}
        apply={(next) => router.replace(`${pathname}?${filterQuery(next)}`)}
      />
      {filters.metric && (
        <p className="analytics-note">
          Showing{" "}
          {filters.eligibility === "excluded"
            ? "excluded"
            : filters.eligibility === "all"
              ? "all"
              : "included"}{" "}
          samples from the same merged cohort as the overview.
        </p>
      )}
      {result.isPending ? (
        <AnalyticsLoading />
      ) : result.isError && !items.length ? (
        <AnalyticsError error={result.error} retry={result.refetch} />
      ) : (
        <>
          <WindowLabel
            window={result.data?.pages[0].window}
            cohort={
              kind === "commits"
                ? "Committed"
                : filters.cohort === "merged" || filters.metric
                  ? "Merged"
                  : "Last active"
            }
          />
          {items.length ? (
            kind === "commits" ? (
              <CommitTable items={items as Commit[]} />
            ) : (
              <PullRequestTable items={items as PullRequest[]} metric={filters.metric} />
            )
          ) : (
            <EmptyHistory />
          )}
          <PageMore result={result} count={items.length} />
        </>
      )}
    </div>
  );
}

export function PullRequestDetail({ id }: { id: string }) {
  const { organization } = useAuth();
  if (!organization) return null;
  return validId(id) ? (
    <PullRequestContent key={`${organization.id}:${id}`} organization={organization} id={id} />
  ) : (
    <EmptyHistory>This pull request address is invalid.</EmptyHistory>
  );
}
function PullRequestContent({ organization, id }: { organization: Organization; id: string }) {
  const query = useQuery({
    queryKey: ["organization", organization.id, "analytics", "pull-request", id],
    queryFn: ({ signal }) =>
      api<{
        pull_request: PullRequest;
        counts: Record<"reviews" | "transitions" | "commits" | "issues", number>;
      }>(`/organizations/${organization.id}/pull-requests/${id}`, { signal }),
    retry: false,
  });
  if (query.isPending) return <AnalyticsLoading label="Loading pull request" />;
  if (query.isError) return <AnalyticsError error={query.error} retry={query.refetch} />;
  const pr = query.data.pull_request;
  const base = `pull-requests/${id}`;
  return (
    <div className="analytics-content">
      <Link className="analytics-back text-link" href="/app/pull-requests">
        All pull requests
      </Link>
      <div className="page-heading">
        <div>
          <h1>{pr.title}</h1>
          <p>
            {pr.repository_name} #{pr.number} ·{" "}
            {pr.merged_at ? "Merged" : pr.draft ? "Draft" : pr.state === "open" ? "Open" : "Closed"}{" "}
            · {pr.author_login ?? "Unknown author"}
          </p>
        </div>
        <SourceLink url={pr.html_url} />
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <dl className="analytics-facts">
        <div>
          <dt>Opened</dt>
          <dd>{utcDate(pr.opened_at)}</dd>
        </div>
        <div>
          <dt>Merged</dt>
          <dd>{utcDate(pr.merged_at)}</dd>
        </div>
        <div>
          <dt>Last activity</dt>
          <dd>{utcDate(pr.updated_at)}</dd>
        </div>
        <div>
          <dt>Base branch</dt>
          <dd>
            <code>{pr.base_ref}</code>
          </dd>
        </div>
      </dl>
      <section className="analytics-section">
        <h2>Timing evidence</h2>
        <p className="analytics-note">
          Wall-clock duration includes draft and reopened time. Missing evidence does not count as
          zero.
        </p>
        <div className="analytics-table-wrap">
          <table className="analytics-table">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Duration</th>
                <th scope="col">Observation</th>
              </tr>
            </thead>
            <tbody>
              {metricKeys.map((key) => (
                <tr key={key}>
                  <th scope="row">
                    {metricLabels[key]}
                    <span className="analytics-meta">{metricDefinitions[key]}</span>
                  </th>
                  <td data-label="Duration">{duration(pr.durations[key])}</td>
                  <td data-label="Observation">
                    {pr.exclusions[key]
                      ? exclusionLabel(pr.exclusions[key])
                      : "Qualifying timestamps observed"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <dl className="analytics-facts">
          <div>
            <dt>First qualifying review</dt>
            <dd>{utcDate(pr.first_review_at)}</dd>
          </div>
          <div>
            <dt>First known qualifying approval</dt>
            <dd>{utcDate(pr.first_approved_at)}</dd>
          </div>
        </dl>
        {pr.approval_dismissed && (
          <p className="analytics-note">
            The first historical approval was later dismissed. It describes timing, not current
            merge authorization.
          </p>
        )}
        {pr.unknown_dismissed_review_count > 0 && (
          <p className="analytics-note">
            {pr.unknown_dismissed_review_count} dismissed reviews have an unknown original state.
            Forge does not infer their former approval status.
          </p>
        )}
      </section>
      <EvidenceSection<Review>
        organization={organization.id}
        path={`${base}/reviews`}
        title={`Reviews (${query.data.counts.reviews})`}
        coverage={pr.coverage.reviews}
      >
        {(items) => (
          <ol className="analytics-timeline">
            {items.map((review) => (
              <li key={review.id}>
                <div>
                  <strong>{review.reviewer_login ?? "Unknown reviewer"}</strong>
                  <span>
                    {reviewState(review.state)} ·{" "}
                    {review.reviewer_type === "Bot"
                      ? "Bot"
                      : review.qualifies
                        ? "Qualifying review"
                        : "Not a qualifying timing sample"}
                  </span>
                </div>
                <time>{utcDate(review.submitted_at)}</time>
                {review.approval_known && (
                  <p>Known historical approval: {utcDate(review.approved_at)}</p>
                )}
                {review.dismissed_at && <p>Dismissed {utcDate(review.dismissed_at)}</p>}
                {review.state === "DISMISSED" && !review.approval_known && (
                  <p>Original review state not known.</p>
                )}
                <SourceLink url={review.html_url}>View review</SourceLink>
              </li>
            ))}
          </ol>
        )}
      </EvidenceSection>
      <EvidenceSection<Transition>
        organization={organization.id}
        path={`${base}/transitions`}
        title={`Lifecycle (${query.data.counts.transitions})`}
        coverage={pr.coverage.transitions}
      >
        {(items) => (
          <ol className="analytics-timeline">
            {items.map((event) => (
              <li key={event.id}>
                <div>
                  <strong>{transitionLabel(event.kind)}</strong>
                  <span>{event.actor_login ?? "Unknown actor"}</span>
                </div>
                <time>{utcDate(event.occurred_at)}</time>
                <SourceLink url={event.html_url}>View event</SourceLink>
              </li>
            ))}
          </ol>
        )}
      </EvidenceSection>
      <EvidenceSection<Commit>
        organization={organization.id}
        path={`${base}/commits`}
        title={`Associated commits (${query.data.counts.commits})`}
        coverage={pr.coverage.commits}
      >
        {(items) => (
          <>
            <p className="analytics-note">
              Provider-reported PR membership and merge SHA only. A squash commit can be the merge
              commit without being a member commit.
            </p>
            <CommitTable items={items} />
          </>
        )}
      </EvidenceSection>
      <EvidenceSection<Issue>
        organization={organization.id}
        path={`${base}/issues`}
        title={`Linked issues (${query.data.counts.issues})`}
        coverage={pr.coverage.issues}
      >
        {(items) => <IssueTable items={items} />}
      </EvidenceSection>
      <p className="analytics-note">
        Issue evidence requires GitHub Issues read permission.{" "}
        <Link className="text-link" href={`/app/repositories/${pr.repository_id}/issues`}>
          Browse imported repository issues
        </Link>
        .
      </p>
    </div>
  );
}
export function CommitDetail({ id }: { id: string }) {
  const { organization } = useAuth();
  if (!organization) return null;
  return validId(id) ? (
    <CommitContent key={`${organization.id}:${id}`} organization={organization} id={id} />
  ) : (
    <EmptyHistory>This commit address is invalid.</EmptyHistory>
  );
}
function CommitContent({ organization, id }: { organization: Organization; id: string }) {
  const query = useQuery({
    queryKey: ["organization", organization.id, "analytics", "commit", id],
    queryFn: ({ signal }) =>
      api<{ commit: Commit }>(`/organizations/${organization.id}/commits/${id}`, { signal }),
    retry: false,
  });
  if (query.isPending) return <AnalyticsLoading label="Loading commit" />;
  if (query.isError) return <AnalyticsError error={query.error} retry={query.refetch} />;
  const commit = query.data.commit;
  return (
    <div className="analytics-content">
      <Link className="analytics-back text-link" href="/app/commits">
        All commits
      </Link>
      <div className="page-heading">
        <div>
          <h1>{commit.message.split("\n")[0] || "Untitled commit"}</h1>
          <p>
            {commit.repository_name} · {commit.author_login ?? "Unknown author"}
          </p>
        </div>
        <SourceLink url={commit.html_url} />
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <dl className="analytics-facts">
        <div>
          <dt>Commit SHA</dt>
          <dd>
            <code>{commit.sha}</code>
          </dd>
        </div>
        <div>
          <dt>Committed</dt>
          <dd>{utcDate(commit.committed_at)}</dd>
        </div>
        <div>
          <dt>Authored</dt>
          <dd>{utcDate(commit.authored_at)}</dd>
        </div>
        <div>
          <dt>Observed changes</dt>
          <dd>
            {commit.changed_files == null ? "Files not observed" : `${commit.changed_files} files`}
            {commit.additions != null && commit.deletions != null
              ? ` · +${commit.additions} / −${commit.deletions} lines`
              : " · Line totals unavailable"}
          </dd>
        </div>
      </dl>
      {commit.message.includes("\n") && (
        <details className="analytics-message">
          <summary>Full commit message</summary>
          <pre>{commit.message}</pre>
        </details>
      )}
      <EvidenceSection<CommitFile>
        organization={organization.id}
        path={`commits/${id}/files`}
        title="Changed files"
        coverage={commit.files_coverage}
      >
        {(files) => (
          <>
            <p className="analytics-note">
              File paths and change counts only. Source patches are not imported.
            </p>
            <div className="analytics-table-wrap">
              <table className="analytics-table">
                <thead>
                  <tr>
                    <th scope="col">File</th>
                    <th scope="col">Status</th>
                    <th scope="col">Added lines</th>
                    <th scope="col">Deleted lines</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr key={file.id}>
                      <th scope="row">
                        <code>{file.filename}</code>
                        {file.previous_filename && (
                          <span className="analytics-meta">
                            Previously <code>{file.previous_filename}</code>
                          </span>
                        )}
                        <SourceLink url={file.blob_url}>View file on GitHub</SourceLink>
                      </th>
                      <td data-label="Status">{file.status}</td>
                      <td data-label="Added lines">{file.additions}</td>
                      <td data-label="Deleted lines">{file.deletions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </EvidenceSection>
      <EvidenceSection<PullRequest>
        organization={organization.id}
        path={`commits/${id}/pull-requests`}
        title={`Associated pull requests (${commit.pull_request_count})`}
      >
        {(items) => (
          <>
            <p className="analytics-note">
              Explicit member and merge-commit relationships. No association is inferred from a
              shared branch or author. Only imported associations are shown; missing links can
              reflect incomplete PR history.
            </p>
            <PullRequestTable items={items} />
          </>
        )}
      </EvidenceSection>
    </div>
  );
}
export function IssueDetail({ id }: { id: string }) {
  const { organization } = useAuth();
  if (!organization) return null;
  return validId(id) ? (
    <IssueContent key={`${organization.id}:${id}`} organization={organization} id={id} />
  ) : (
    <EmptyHistory>This issue address is invalid.</EmptyHistory>
  );
}
function IssueContent({ organization, id }: { organization: Organization; id: string }) {
  const query = useQuery({
    queryKey: ["organization", organization.id, "analytics", "issue", id],
    queryFn: ({ signal }) =>
      api<{ issue: Issue }>(`/organizations/${organization.id}/issues/${id}`, { signal }),
    retry: false,
  });
  if (query.isPending) return <AnalyticsLoading label="Loading issue" />;
  if (query.isError) return <AnalyticsError error={query.error} retry={query.refetch} />;
  const issue = query.data.issue;
  return (
    <div className="analytics-content">
      <Link
        className="analytics-back text-link"
        href={`/app/repositories/${issue.repository_id}/issues`}
      >
        Repository issues
      </Link>
      <div className="page-heading">
        <div>
          <h1>{issue.title}</h1>
          <p>
            {issue.repository_name} #{issue.number} · {issue.state} ·{" "}
            {issue.author_login ?? "Unknown author"}
          </p>
        </div>
        <SourceLink url={issue.html_url} />
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <dl className="analytics-facts">
        <div>
          <dt>Opened</dt>
          <dd>{utcDate(issue.opened_at)}</dd>
        </div>
        <div>
          <dt>Last activity</dt>
          <dd>{utcDate(issue.updated_at)}</dd>
        </div>
        <div>
          <dt>Closed</dt>
          <dd>{utcDate(issue.closed_at)}</dd>
        </div>
      </dl>
      <EvidenceSection<PullRequest>
        organization={organization.id}
        path={`issues/${id}/pull-requests`}
        title="Linked pull requests"
        coverage={issue.links_coverage}
      >
        {(items) => <PullRequestTable items={items} />}
      </EvidenceSection>
    </div>
  );
}
export function RepositoryIssues({ id }: { id: string }) {
  const { organization } = useAuth();
  const search = useSearchParams();
  if (!organization) return null;
  return validId(id) ? (
    <RepositoryIssuesContent
      key={`${organization.id}:${id}:${search.toString()}`}
      organization={organization}
      id={id}
      filters={readFilters(new URLSearchParams(search), "issues")}
    />
  ) : (
    <EmptyHistory>This repository address is invalid.</EmptyHistory>
  );
}
function RepositoryIssuesContent({
  organization,
  id,
  filters,
}: {
  organization: Organization;
  id: string;
  filters: Filters;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const result = useEvidencePage<Issue>(organization.id, `repositories/${id}/issues`, {
    author: filters.author,
    from: filters.from,
    to: filters.to,
    state: filters.state,
  });
  const items = result.data?.pages.flatMap((page) => page.items) ?? [];
  const coverage = (
    result.data?.pages[0] as
      | (import("./types").Page<Issue> & { coverage?: import("./types").EvidenceCoverage })
      | undefined
  )?.coverage;
  return (
    <div className="analytics-content">
      <Link className="analytics-back text-link" href="/app/repositories">
        Repositories
      </Link>
      <div className="page-heading">
        <div>
          <h1>Repository issues</h1>
          <p>
            {organization.name} · {items[0]?.repository_name ?? "Imported issue history"}
          </p>
        </div>
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <FilterBar
        organization={organization.id}
        filters={{ ...filters, repository: id }}
        kind="issues"
        apply={(next) =>
          router.replace(
            `/app/repositories/${next.repository || id}/issues?${filterQuery({ author: next.author, from: next.from, to: next.to, state: next.state })}`,
          )
        }
      />
      {result.isPending ? (
        <AnalyticsLoading label="Loading issues" />
      ) : result.isError && !items.length ? (
        <AnalyticsError error={result.error} retry={result.refetch} />
      ) : (
        <>
          {coverage && <Coverage label="Issues" value={coverage} />}
          <WindowLabel window={result.data?.pages[0].window} cohort="Last active" />
          {items.length ? (
            <IssueTable items={items} />
          ) : (
            <EmptyHistory>
              No issues imported for this window. Issues read permission is required; missing
              permission does not stop PR and commit imports.
            </EmptyHistory>
          )}
          <PageMore result={result} count={items.length} />
        </>
      )}
      <Link className="text-link" href={`${pathname}?`}>
        Reset issue window
      </Link>
    </div>
  );
}
function IssueTable({ items }: { items: Issue[] }) {
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead>
          <tr>
            <th scope="col">Issue</th>
            <th scope="col">State</th>
            <th scope="col">Last activity</th>
            <th scope="col">Relationship</th>
          </tr>
        </thead>
        <tbody>
          {items.map((issue) => (
            <tr key={issue.id}>
              <th scope="row">
                <Link href={`/app/issues/${issue.id}`}>{issue.title}</Link>
                <span className="analytics-meta">
                  {issue.repository_name} #{issue.number} · {issue.author_login ?? "Unknown author"}
                </span>
              </th>
              <td data-label="State">{issue.state}</td>
              <td data-label="Last activity">{utcDate(issue.updated_at)}</td>
              <td data-label="Relationship">
                {issue.relationship ? relationshipLabel(issue.relationship) : "Repository issue"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function reviewState(state: string) {
  return (
    (
      {
        APPROVED: "Approved",
        CHANGES_REQUESTED: "Changes requested",
        COMMENTED: "Commented",
        DISMISSED: "Dismissed",
        PENDING: "Pending",
      } as Record<string, string>
    )[state] ?? "Review submitted"
  );
}
function transitionLabel(kind: string) {
  return (
    (
      {
        opened: "Opened",
        closed: "Closed",
        reopened: "Reopened",
        merged: "Merged",
        ready_for_review: "Ready for review",
        converted_to_draft: "Converted to draft",
        review_dismissed: "Review dismissed",
      } as Record<string, string>
    )[kind] ?? "Lifecycle event"
  );
}
