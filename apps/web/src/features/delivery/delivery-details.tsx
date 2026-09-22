"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/auth-provider";
import { api } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import {
  AnalyticsError,
  AnalyticsLoading,
  CommitTable,
  DemoNotice,
  EmptyHistory,
  PullRequestTable,
  RefreshData,
} from "@/features/analytics/analytics-ui";
import {
  duration,
  utcDate,
  validId,
  type Commit,
  type PullRequest,
} from "@/features/analytics/types";
import { DeliveryEvidence, DeliverySource, RunOutcome } from "./delivery-ui";
import {
  classificationLabel,
  deliveryReason,
  type Deployment,
  type DeploymentStatus,
  type Job,
  type WorkflowRun,
} from "./types";

export function DeliveryDetail({ kind, id }: { kind: "ci" | "deployments"; id: string }) {
  const { organization } = useAuth();
  if (!organization) return null;
  return validId(id) ? (
    kind === "ci" ? (
      <WorkflowDetail key={`${organization.id}:${id}`} organization={organization} id={id} />
    ) : (
      <DeploymentDetail key={`${organization.id}:${id}`} organization={organization} id={id} />
    )
  ) : (
    <EmptyHistory>This record address is invalid.</EmptyHistory>
  );
}
function WorkflowDetail({ organization, id }: { organization: Organization; id: string }) {
  const query = useQuery({
    queryKey: ["organization", organization.id, "analytics", "delivery", "workflow-run", id],
    queryFn: ({ signal }) =>
      api<{
        workflow_run: WorkflowRun;
        counts: { jobs: number; pull_requests: number; commits: number };
      }>(`/organizations/${organization.id}/workflow-runs/${id}`, { signal }),
    retry: false,
  });
  if (query.isPending) return <AnalyticsLoading label="Loading workflow attempt" />;
  if (query.isError) return <AnalyticsError error={query.error} retry={query.refetch} />;
  const run = query.data.workflow_run;
  const base = `workflow-runs/${id}`;
  return (
    <div className="analytics-content">
      <Link className="analytics-back text-link" href="/app/ci">
        CI workflows
      </Link>
      <div className="page-heading">
        <div>
          <h1>
            {run.workflow_name} · attempt {run.attempt}
          </h1>
          <p>
            {run.repository_name} · Run #{run.run_number} · {run.event}
          </p>
        </div>
        <DeliverySource url={run.html_url} />
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <p>
        <RunOutcome status={run.status} conclusion={run.conclusion} />
      </p>
      <dl className="analytics-facts">
        <div>
          <dt>Branch</dt>
          <dd>{run.head_branch ?? "Not observed"}</dd>
        </div>
        <div>
          <dt>Commit SHA</dt>
          <dd>
            <code>{run.head_sha}</code>
          </dd>
        </div>
        <div>
          <dt>Actor</dt>
          <dd>{run.actor_login ?? "Not observed"}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{utcDate(run.created_at)}</dd>
        </div>
        <div>
          <dt>Attempt queued</dt>
          <dd>{utcDate(run.queued_at)}</dd>
        </div>
        <div>
          <dt>Attempt started</dt>
          <dd>{utcDate(run.started_at)}</dd>
        </div>
        <div>
          <dt>Completed</dt>
          <dd>{utcDate(run.completed_at)}</dd>
        </div>
        <div>
          <dt>Completion evidence</dt>
          <dd>{completionLabel(run.completion_source)}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>
            {duration(run.duration_seconds)}
            {run.duration_exclusion && (
              <span className="analytics-meta">{deliveryReason(run.duration_exclusion)}</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Queue time</dt>
          <dd>
            {duration(run.queue_seconds)}
            {run.queue_exclusion && (
              <span className="analytics-meta">{deliveryReason(run.queue_exclusion)}</span>
            )}
          </dd>
        </div>
      </dl>
      <p className="analytics-note">
        Attempt {run.attempt} is retained separately from other retries of run #{run.run_number}. A
        successful attempt is CI evidence, not a deployment.
      </p>
      <p className="delivery-related">
        <Link
          className="text-link"
          href={`/app/ci?repository=${run.repository_id}&workflow=${run.workflow_id}`}
        >
          All attempts for this workflow
        </Link>
      </p>
      <DeliveryEvidence<Job>
        organization={organization.id}
        path={`${base}/jobs`}
        title={`Jobs (${query.data.counts.jobs})`}
        coverage={run.jobs_coverage}
      >
        {(jobs) => (
          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th scope="col">Job</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Started / completed</th>
                  <th scope="col">Duration</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <th scope="row">
                      {job.name}
                      <span className="analytics-meta">
                        <DeliverySource url={job.html_url}>View job</DeliverySource>
                      </span>
                    </th>
                    <td data-label="Outcome">
                      <RunOutcome status={job.status} conclusion={job.conclusion} />
                    </td>
                    <td data-label="Started / completed">
                      {utcDate(job.started_at)}
                      <span className="analytics-meta">{utcDate(job.completed_at)}</span>
                    </td>
                    <td data-label="Duration">{duration(job.duration_seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DeliveryEvidence>
      <DeliveryEvidence<PullRequest>
        organization={organization.id}
        path={`${base}/pull-requests`}
        title={`Associated pull requests (${query.data.counts.pull_requests})`}
        coverage={run.links_coverage}
      >
        {(items) => <PullRequestTable items={items} />}
      </DeliveryEvidence>
      <DeliveryEvidence<Commit>
        organization={organization.id}
        path={`${base}/commits`}
        title={`Associated commits (${query.data.counts.commits})`}
        coverage={run.links_coverage}
      >
        {(items) => <CommitTable items={items} />}
      </DeliveryEvidence>
    </div>
  );
}
function DeploymentDetail({ organization, id }: { organization: Organization; id: string }) {
  const query = useQuery({
    queryKey: ["organization", organization.id, "analytics", "delivery", "deployment", id],
    queryFn: ({ signal }) =>
      api<{ deployment: Deployment; counts: { statuses: number; commits: number } }>(
        `/organizations/${organization.id}/deployments/${id}`,
        { signal },
      ),
    retry: false,
  });
  if (query.isPending) return <AnalyticsLoading label="Loading deployment" />;
  if (query.isError) return <AnalyticsError error={query.error} retry={query.refetch} />;
  const deployment = query.data.deployment;
  return (
    <div className="analytics-content">
      <Link className="analytics-back text-link" href="/app/deployments">
        Deployments
      </Link>
      <div className="page-heading">
        <div>
          <h1>
            {deployment.environment} deployment #{deployment.provider_id}
          </h1>
          <p>
            {deployment.repository_name} · {deployment.latest_state ?? "No status observed"}
          </p>
        </div>
        <DeliverySource url={deployment.html_url}>View deployments on GitHub</DeliverySource>
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <dl className="analytics-facts">
        <div>
          <dt>Environment</dt>
          <dd>{deployment.environment}</dd>
        </div>
        <div>
          <dt>Classification</dt>
          <dd>
            {classificationLabel(deployment.classification)}
            <span className="analytics-meta">
              {deployment.classification_source === "override"
                ? "Explicit Forge environment override"
                : deployment.classification_source === "provider"
                  ? "Provider production_environment flag"
                  : "Provider flag and Forge override are absent"}
            </span>
          </dd>
        </div>
        <div>
          <dt>Provider production flag</dt>
          <dd>
            {deployment.provider_production_environment === null
              ? "Not supplied"
              : deployment.provider_production_environment
                ? "Production"
                : "Non-production"}
          </dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{utcDate(deployment.created_at)}</dd>
        </div>
        <div>
          <dt>First observed success</dt>
          <dd>{utcDate(deployment.first_success_at)}</dd>
        </div>
        <div>
          <dt>Success-count eligibility</dt>
          <dd>
            {deployment.success_eligible
              ? "Eligible with complete status history"
              : deliveryReason(deployment.success_exclusion)}
          </dd>
        </div>
        <div>
          <dt>Commit SHA</dt>
          <dd>
            <code>{deployment.sha}</code>
          </dd>
        </div>
        <div>
          <dt>Source ref / task</dt>
          <dd>
            {deployment.ref} · {deployment.task}
          </dd>
        </div>
        <div>
          <dt>Creator</dt>
          <dd>{deployment.creator_login ?? "Not observed"}</dd>
        </div>
      </dl>
      <p className="analytics-note">
        Environment names never determine classification. The first successful status counts once;
        later successes do not create extra deployments.
      </p>
      <p className="delivery-related">
        <Link
          className="text-link"
          href={`/app/deployments/environments?repository=${deployment.repository_id}`}
        >
          Inspect environment classification
        </Link>
      </p>
      <DeliveryEvidence<DeploymentStatus>
        organization={organization.id}
        path={`deployments/${id}/statuses`}
        title={`Status history (${query.data.counts.statuses})`}
        coverage={deployment.statuses_coverage}
      >
        {(items) => (
          <ol className="analytics-timeline">
            {items.map((status) => (
              <li key={status.id}>
                <div>
                  <strong>{status.state}</strong>
                  <span>{status.creator_login ?? "Unknown actor"}</span>
                </div>
                <time>{utcDate(status.created_at)}</time>
                {status.description && <p>{status.description}</p>}
                <DeliverySource url={status.html_url}>View deployments on GitHub</DeliverySource>
              </li>
            ))}
          </ol>
        )}
      </DeliveryEvidence>
      <DeliveryEvidence<Commit>
        organization={organization.id}
        path={`deployments/${id}/commits`}
        title={`Associated commits (${query.data.counts.commits})`}
        coverage={deployment.links_coverage}
      >
        {(items) => (
          <>
            <p className="analytics-note">
              Stored commits linked by the deployment’s exact SHA in the same repository.
            </p>
            <CommitTable items={items} />
          </>
        )}
      </DeliveryEvidence>
    </div>
  );
}
function completionLabel(value: string | null) {
  return (
    (
      {
        provider: "Provider completion timestamp",
        jobs: "Last-job completion proxy",
      } as Record<string, string>
    )[value ?? ""] ?? (value ? "Observed provider completion evidence" : "Not observed")
  );
}
