"use client";

import Link from "next/link";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ExternalLink, GitBranch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-provider";
import { FormMessage } from "@/features/auth/form-parts";
import { api, errorMessage } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import { SystemStatus } from "@/features/system/system-status";
import { QueryFailure, SyncDetails, SyncState } from "./github-ui";
import {
  activeSync,
  canManage,
  formatDate,
  githubDestination,
  type CursorPage,
  type Repository,
  type SyncRun,
} from "./types";

export function RepositoriesPage({ overview = false }: { overview?: boolean }) {
  const { organization } = useAuth();
  if (!organization) return null;
  return (
    <RepositoriesContent key={organization.id} organization={organization} overview={overview} />
  );
}

function RepositoriesContent({
  organization,
  overview,
}: {
  organization: Organization;
  overview: boolean;
}) {
  const { identity } = useAuth();
  const client = useQueryClient();
  const manager = canManage(organization.role) && !!identity?.user.email_verified;
  const base = `/organizations/${organization.id}/repositories`;
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState({ error: "", success: "" });
  const [expanded, setExpanded] = useState<string | null>(null);
  const repos = useInfiniteQuery({
    queryKey: ["organization", organization.id, "repositories"],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<CursorPage<Repository>>(
        `${base}?limit=25${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) =>
        page.items.some((repo) => activeSync(repo.latest_sync)),
      )
        ? 4000
        : false,
    retry: false,
  });
  const items = repos.data?.pages.flatMap((page) => page.items) ?? [];
  async function sync(repo: Repository) {
    setBusy(repo.id);
    setNotice({ error: "", success: "" });
    try {
      await api(`${base}/${repo.id}/sync`, { method: "POST", body: {} });
      await client.invalidateQueries({
        queryKey: ["organization", organization.id, "repositories"],
      });
      await client.invalidateQueries({
        queryKey: ["organization", organization.id, "sync-runs", repo.id],
      });
      setNotice({
        error: "",
        success: `Sync queued for ${repo.full_name}. Progress updates automatically.`,
      });
    } catch (error) {
      setNotice({ error: errorMessage(error), success: "" });
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="github-content">
      <div className="page-heading">
        <div>
          <h1>{overview ? "Engineering overview" : "Repositories"}</h1>
          <p>
            {organization.name} ·{" "}
            {overview
              ? "Repository activity and import progress."
              : "Selected GitHub repositories and their imported history."}
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="/app/integrations">Manage integrations</Link>
        </Button>
      </div>
      {organization.is_demo && (
        <p className="phase-notice github-notice">This organization contains demonstration data.</p>
      )}
      <FormMessage error={notice.error} success={notice.success} />
      {repos.isPending ? (
        <p role="status">Loading repositories...</p>
      ) : repos.isError ? (
        <QueryFailure
          error={repos.error}
          retry={() => void repos.refetch()}
          label="Retry repositories"
        />
      ) : !items.length ? (
        <section className="github-empty">
          <GitBranch size={28} aria-hidden="true" />
          <h2>No repositories selected</h2>
          <p>
            Connect a GitHub installation and choose repositories to import pull requests and commit
            history.
          </p>
          <Button asChild variant="outline">
            <Link href="/app/integrations">Open integrations</Link>
          </Button>
        </section>
      ) : (
        <>
          <p className="repository-scroll-hint">
            Scroll the table to see sync details and actions.
          </p>
          <div
            className="github-table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Repositories and synchronization"
          >
            <table className="github-repositories">
              <caption className="sr-only">Selected repositories for {organization.name}</caption>
              <thead>
                <tr>
                  <th scope="col">Repository</th>
                  <th scope="col">Last push</th>
                  <th scope="col">Imported history</th>
                  <th scope="col">Synchronization</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((repo) => (
                  <RepositoryRow
                    key={repo.id}
                    repo={repo}
                    manager={manager}
                    busy={busy !== null}
                    onSync={() => void sync(repo)}
                    expanded={expanded === repo.id}
                    onDetails={() => setExpanded(expanded === repo.id ? null : repo.id)}
                    orgId={organization.id}
                  />
                ))}
              </tbody>
            </table>
          </div>
          {repos.hasNextPage && (
            <Button
              variant="outline"
              disabled={repos.isFetchingNextPage}
              onClick={() => void repos.fetchNextPage()}
            >
              {repos.isFetchingNextPage ? "Loading..." : "Load more repositories"}
            </Button>
          )}
        </>
      )}
      {!manager && (
        <p className="field-hint github-permission">
          A verified organization owner or admin can select repositories and start a sync.
        </p>
      )}
      <p className="github-scope-note">
        History imports start with the last 90 days. Counts reflect data stored in Forge;
        synchronization may still be in progress. CI, test and production analytics arrive in later
        phases.
      </p>
      {overview && <SystemStatus compact />}
    </div>
  );
}

function RepositoryRow({
  repo,
  manager,
  busy,
  onSync,
  expanded,
  onDetails,
  orgId,
}: {
  repo: Repository;
  manager: boolean;
  busy: boolean;
  onSync: () => void;
  expanded: boolean;
  onDetails: () => void;
  orgId: string;
}) {
  const link = githubDestination(repo.html_url, "repository");
  return (
    <>
      <tr>
        <th scope="row">
          <div className="repository-name">
            {link ? (
              <a href={link} target="_blank" rel="noreferrer">
                {repo.full_name}
                <ExternalLink size={12} aria-hidden="true" />
              </a>
            ) : (
              repo.full_name
            )}
          </div>
          <p className="repository-meta">
            {repo.is_private ? "Private" : "Public"}
            {repo.archived ? " · Archived" : ""} · {repo.language ?? "Language not reported"}
          </p>
          <p className="repository-meta repository-branch">
            <GitBranch size={12} aria-hidden="true" />
            {repo.default_branch}
          </p>
        </th>
        <td data-label="Last push">
          {repo.pushed_at ? (
            <time dateTime={repo.pushed_at}>{formatDate(repo.pushed_at)}</time>
          ) : (
            "Not reported"
          )}
        </td>
        <td data-label="Imported history">
          <p className="repository-count">
            {repo.open_pull_request_count.toLocaleString()} open PRs
          </p>
          <p>{repo.pull_request_count.toLocaleString()} total PRs</p>
          <p>{repo.commit_count.toLocaleString()} commits</p>
        </td>
        <td data-label="Synchronization">
          {!repo.authorized ? (
            <span className="state-warning">GitHub access removed</span>
          ) : (
            <SyncState run={repo.latest_sync} />
          )}
          <p className="repository-meta">
            {repo.last_synced_at ? (
              <>
                Last synced{" "}
                <time dateTime={repo.last_synced_at}>{formatDate(repo.last_synced_at)}</time>
              </>
            ) : (
              "No completed sync yet"
            )}
          </p>
        </td>
        <td>
          <div className="repository-actions">
            {manager && (
              <Button
                variant="outline"
                size="sm"
                disabled={busy || !repo.authorized || activeSync(repo.latest_sync)}
                onClick={onSync}
              >
                {activeSync(repo.latest_sync)
                  ? "Sync in progress"
                  : repo.latest_sync?.status === "failed" || repo.latest_sync?.status === "partial"
                    ? "Retry sync"
                    : "Sync now"}
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              aria-expanded={expanded}
              aria-controls={`history-${repo.id}`}
              onClick={onDetails}
            >
              {expanded ? "Hide details" : "Sync details"}
            </Button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} className="sync-expanded">
            <SyncHistory orgId={orgId} repo={repo} />
          </td>
        </tr>
      )}
    </>
  );
}

function SyncHistory({ orgId, repo }: { orgId: string; repo: Repository }) {
  const history = useInfiniteQuery({
    queryKey: ["organization", orgId, "sync-runs", repo.id],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<CursorPage<SyncRun>>(
        `/organizations/${orgId}/repositories/${repo.id}/sync-runs?limit=5${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) => page.items.some(activeSync)) ? 4000 : false,
    retry: false,
  });
  return (
    <div id={`history-${repo.id}`} className="sync-history">
      <h3>Sync history · {repo.full_name}</h3>
      {history.isPending ? (
        <p role="status">Loading sync history...</p>
      ) : history.isError ? (
        <QueryFailure
          error={history.error}
          retry={() => void history.refetch()}
          label="Retry sync history"
        />
      ) : !history.data.pages[0].items.length ? (
        <p>This repository has no sync runs yet.</p>
      ) : (
        <>
          <ol>
            {history.data.pages
              .flatMap((page) => page.items)
              .map((run) => (
                <li key={run.id}>
                  <div className="sync-history-heading">
                    <SyncState run={run} />
                    <time dateTime={run.created_at}>{formatDate(run.created_at)}</time>
                  </div>
                  <SyncDetails run={run} />
                </li>
              ))}
          </ol>
          {history.hasNextPage && (
            <Button
              variant="outline"
              size="sm"
              disabled={history.isFetchingNextPage}
              onClick={() => void history.fetchNextPage()}
            >
              {history.isFetchingNextPage ? "Loading..." : "Load more sync runs"}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
