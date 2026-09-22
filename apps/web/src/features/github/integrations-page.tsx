"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-provider";
import { FormMessage } from "@/features/auth/form-parts";
import { api, errorMessage } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import { QueryFailure, SyncDetails, SyncState } from "./github-ui";
import {
  activeSync,
  canManage,
  formatDate,
  githubCallbackError,
  githubDestination,
  type CursorPage,
  type GitHubConnection,
  type GitHubInstallations,
  type GitHubStatus,
  type Repository,
} from "./types";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function IntegrationsPage() {
  const { organization, selectOrganization } = useAuth();
  const params = useSearchParams();
  const requested = params.get("organization");
  const target = requested && uuid.test(requested) ? requested : null;
  const [selectionError, setSelectionError] = useState("");
  useEffect(() => {
    if (!target) return;
    if (organization?.id === target) {
      const url = new URL(window.location.href);
      url.searchParams.delete("organization");
      window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
      return;
    }
    let stopped = false;
    void selectOrganization(target).catch((error) => {
      if (!stopped) setSelectionError(errorMessage(error));
    });
    return () => {
      stopped = true;
    };
  }, [target, organization?.id, selectOrganization]);
  if (target && organization?.id !== target)
    return selectionError ? (
      <div className="github-recovery">
        <FormMessage error={selectionError} />
        <Link href="/app/integrations" className="text-link">
          Return to your selected organization
        </Link>
      </div>
    ) : (
      <p role="status">Opening the organization used for GitHub authorization...</p>
    );
  if (!organization) return null;
  return (
    <IntegrationsContent
      key={organization.id}
      organization={organization}
      callbackError={githubCallbackError(params.get("github_error"))}
      authorized={params.get("github") === "authorized"}
    />
  );
}

function IntegrationsContent({
  organization,
  callbackError,
  authorized,
}: {
  organization: Organization;
  callbackError: string;
  authorized: boolean;
}) {
  const { identity } = useAuth();
  const manager = canManage(organization.role);
  const editable = manager && !!identity?.user.email_verified;
  const client = useQueryClient();
  const base = `/organizations/${organization.id}/integrations/github`;
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState("");
  const status = useQuery({
    queryKey: ["organization", organization.id, "github"],
    queryFn: ({ signal }) => api<GitHubStatus>(base, { signal }),
    refetchInterval: (query) =>
      query.state.data?.connections.some((connection) => activeSync(connection.catalog_sync))
        ? 4000
        : false,
    retry: false,
  });
  async function authorize() {
    setBusy(true);
    setStartError("");
    try {
      const result = await api<{ authorization_url: string }>(`${base}/authorize`, {
        method: "POST",
        body: {},
      });
      const destination = githubDestination(result.authorization_url, "authorize");
      if (!destination)
        throw new Error("The GitHub authorization address could not be verified. Please retry.");
      window.location.assign(destination);
    } catch (error) {
      setStartError(errorMessage(error));
      setBusy(false);
    }
  }
  const installUrl = status.data?.install_url
    ? githubDestination(status.data.install_url, "install")
    : null;
  return (
    <div className="github-content settings-content">
      <div className="page-heading">
        <div>
          <h1>Integrations</h1>
          <p>{organization.name} · Connect the sources your team works with.</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/app/repositories">View repositories</Link>
        </Button>
      </div>
      {organization.is_demo && (
        <p className="phase-notice github-notice">This organization contains demonstration data.</p>
      )}
      <section className="settings-section" aria-labelledby="github-integration-title">
        <div className="settings-section-heading">
          <h2 id="github-integration-title" className="github-provider-title">
            <Image
              src="/integrations/github.svg"
              width={20}
              height={20}
              alt=""
              className="provider-github-logo"
            />
            GitHub
          </h2>
          <p>
            Import repositories, pull requests and commits. GitHub sign-in alone does not grant
            repository access.
          </p>
        </div>
        <div className="github-setup">
          <FormMessage error={startError || callbackError} />
          {status.isPending ? (
            <p role="status">Checking GitHub integration...</p>
          ) : status.isError ? (
            <QueryFailure
              error={status.error}
              retry={() => void status.refetch()}
              label="Retry GitHub integration"
            />
          ) : !status.data.configured ? (
            <>
              <h3>GitHub App setup is required</h3>
              <p>
                The installation administrator needs to configure the Forge GitHub App before
                repositories can be connected.
              </p>
              <Link href="/guide#github-app" className="text-link">
                GitHub App setup guide
              </Link>
            </>
          ) : (
            <>
              {!manager ? (
                <p>An organization owner or admin can connect GitHub and select repositories.</p>
              ) : !identity?.user.email_verified ? (
                <p>
                  Verify your Forge email before connecting GitHub.{" "}
                  <Link href="/app/account" className="text-link">
                    Open account settings
                  </Link>
                </p>
              ) : (
                <>
                  <p>
                    Install the app on GitHub, then authorize your GitHub account to choose the
                    installation for this organization.
                  </p>
                  <div className="github-toolbar">
                    {installUrl && (
                      <Button asChild variant="outline">
                        <a href={installUrl} target="_blank" rel="noreferrer">
                          Install GitHub App
                          <ExternalLink size={14} aria-hidden="true" />
                        </a>
                      </Button>
                    )}
                    <Button disabled={busy} onClick={() => void authorize()}>
                      {busy
                        ? "Opening GitHub..."
                        : status.data.authorization
                          ? "Authorize again"
                          : "Authorize GitHub"}
                    </Button>
                  </div>
                </>
              )}
              {editable && status.data.authorization && (
                <InstallationPicker
                  key={status.data.authorization.id}
                  organizationId={organization.id}
                  authorization={status.data.authorization}
                  onConnected={() =>
                    void client.invalidateQueries({ queryKey: ["organization", organization.id] })
                  }
                />
              )}
              {authorized &&
                !status.data.authorization &&
                !callbackError &&
                !status.data.connections.some((item) => item.status !== "disconnected") && (
                  <p className="field-hint">
                    Your authorization is no longer available. Authorize GitHub again to choose an
                    installation.
                  </p>
                )}
            </>
          )}
        </div>
      </section>
      {status.data &&
        status.data.connections
          .filter((connection) => connection.status !== "disconnected")
          .map((connection) => (
            <ConnectionSection
              key={connection.id}
              connection={connection}
              organization={organization}
              editable={editable}
            />
          ))}
      <p className="github-scope-note">
        Forge reads repository metadata, contents and pull requests. Organization membership is used
        to verify who can connect an installation. Your GitHub installation controls which
        repositories are available.
      </p>
    </div>
  );
}

function InstallationPicker({
  organizationId,
  authorization,
  onConnected,
}: {
  organizationId: string;
  authorization: { id: string; expires_at: string };
  onConnected: () => void;
}) {
  const base = `/organizations/${organizationId}/integrations/github`;
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const installations = useQuery({
    queryKey: ["organization", organizationId, "github-installations", authorization.id],
    queryFn: ({ signal }) =>
      api<GitHubInstallations>(`${base}/authorizations/${authorization.id}/installations`, {
        signal,
      }),
    retry: false,
  });
  async function connect(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await api(`${base}/connections`, {
        method: "POST",
        body: { authorization_id: authorization.id, installation_id: Number(selected) },
      });
      onConnected();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="installation-picker">
      <h3>Choose a GitHub installation</h3>
      <p className="field-hint">
        Authorization expires{" "}
        <time dateTime={authorization.expires_at}>{formatDate(authorization.expires_at)}</time>.
      </p>
      {installations.isPending ? (
        <p role="status">Loading GitHub installations...</p>
      ) : installations.isError ? (
        <QueryFailure
          error={installations.error}
          retry={() => void installations.refetch()}
          label="Retry installations"
        />
      ) : (
        <>
          {!installations.data.installations.length ? (
            <p>
              No installations are available to this GitHub account. Install the app, then refresh
              this list.
            </p>
          ) : (
            <form
              className="account-form"
              onSubmit={(event) => void connect(event)}
              aria-busy={busy}
            >
              <div className="form-field">
                <label htmlFor="github-installation">GitHub account</label>
                <select
                  id="github-installation"
                  value={selected}
                  required
                  disabled={busy}
                  onChange={(event) => setSelected(event.target.value)}
                >
                  <option value="">Choose an installation</option>
                  {installations.data.installations.map((installation) => (
                    <option key={installation.id} value={installation.id}>
                      {installation.account_login} · {installation.account_type}
                    </option>
                  ))}
                </select>
              </div>
              <FormMessage error={error} />
              <Button type="submit" disabled={busy || !selected}>
                {busy ? "Connecting..." : "Connect installation"}
              </Button>
            </form>
          )}
          <Button
            variant="outline"
            disabled={busy || installations.isFetching}
            onClick={() => void installations.refetch()}
          >
            {installations.isFetching ? "Refreshing..." : "Refresh installations"}
          </Button>
        </>
      )}
    </div>
  );
}

function ConnectionSection({
  connection,
  organization,
  editable,
}: {
  connection: GitHubConnection;
  organization: Organization;
  editable: boolean;
}) {
  const client = useQueryClient();
  const base = `/organizations/${organization.id}/integrations/github/connections/${connection.id}`;
  const [busy, setBusy] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [message, setMessage] = useState({ error: "", success: "" });
  async function change(operation: "refresh" | "disconnect") {
    setBusy(true);
    setMessage({ error: "", success: "" });
    try {
      await api(
        operation === "refresh" ? `${base}/refresh` : base,
        operation === "refresh" ? { method: "POST", body: {} } : { method: "DELETE" },
      );
      await client.invalidateQueries({ queryKey: ["organization", organization.id] });
      setMessage({
        error: "",
        success:
          operation === "refresh"
            ? "Repository catalog refresh queued."
            : "Installation disconnected. Imported history is retained.",
      });
      setDisconnecting(false);
    } catch (error) {
      setMessage({ error: errorMessage(error), success: "" });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="settings-section" aria-labelledby={`installation-${connection.id}`}>
      <div className="settings-section-heading">
        <h2 id={`installation-${connection.id}`}>{connection.account_login}</h2>
        <p>{connection.account_type} installation</p>
        <p className={connection.status === "active" ? "state-success" : "state-warning"}>
          {connection.status === "needs_attention"
            ? "Needs attention"
            : connection.status === "suspended"
              ? "Suspended on GitHub"
              : "Connected"}
        </p>
      </div>
      <div className="github-connection">
        <FormMessage error={message.error} success={message.success} />
        {connection.last_error && (
          <p className="form-error">
            GitHub access needs attention. Check the app installation and permissions on GitHub,
            then refresh the catalog or reconnect.
          </p>
        )}
        {connection.catalog_sync && (
          <div className="catalog-progress" aria-live="polite">
            <SyncState run={connection.catalog_sync} />
            <SyncDetails run={connection.catalog_sync} />
          </div>
        )}
        {editable && (
          <div className="github-toolbar">
            <Button
              variant="outline"
              disabled={
                busy || activeSync(connection.catalog_sync) || connection.status === "suspended"
              }
              onClick={() => void change("refresh")}
            >
              {busy ? "Updating..." : "Refresh repository catalog"}
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => setDisconnecting(!disconnecting)}
            >
              Disconnect
            </Button>
          </div>
        )}
        {disconnecting && (
          <div className="disconnect-confirm">
            <p>
              Disconnect {connection.account_login}? Syncs will stop and its repositories will be
              deselected. Imported history stays in Forge.
            </p>
            <div className="github-toolbar">
              <Button variant="outline" disabled={busy} onClick={() => void change("disconnect")}>
                Confirm disconnect
              </Button>
              <Button variant="ghost" disabled={busy} onClick={() => setDisconnecting(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
        <RepositoryPicker
          organizationId={organization.id}
          connection={connection}
          editable={editable && !busy && !disconnecting}
        />
      </div>
    </section>
  );
}

function RepositoryPicker({
  organizationId,
  connection,
  editable,
}: {
  organizationId: string;
  connection: GitHubConnection;
  editable: boolean;
}) {
  const client = useQueryClient();
  const base = `/organizations/${organizationId}/integrations/github/connections/${connection.id}`;
  const [changes, setChanges] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ error: "", success: "" });
  const catalog = useInfiniteQuery({
    queryKey: ["organization", organizationId, "github-catalog", connection.id],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<CursorPage<Repository>>(
        `${base}/repositories?limit=25${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    refetchInterval: activeSync(connection.catalog_sync) ? 4000 : false,
    retry: false,
  });
  const items = catalog.data?.pages.flatMap((page) => page.items) ?? [];
  const pending = Object.keys(changes).length;
  const available = editable && connection.status === "active";
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage({ error: "", success: "" });
    try {
      await api(`${base}/selection`, {
        method: "POST",
        body: { changes: Object.entries(changes).map(([id, selected]) => ({ id, selected })) },
      });
      setChanges({});
      await client.invalidateQueries({ queryKey: ["organization", organizationId] });
      setMessage({
        error: "",
        success: "Repository selection saved. New selections are queued for history import.",
      });
    } catch (error) {
      setMessage({ error: errorMessage(error), success: "" });
    } finally {
      setSaving(false);
    }
  }
  function toggle(repo: Repository, selected: boolean) {
    setChanges((previous) => {
      const next = { ...previous };
      if (selected === repo.selected) delete next[repo.id];
      else next[repo.id] = selected;
      return next;
    });
  }
  return (
    <div className="repository-picker">
      <h3>Select repositories</h3>
      <p className="field-hint">
        Selection starts a history import. Deselecting stops future syncs and retains imported
        history.
      </p>
      {catalog.isPending ? (
        <p role="status">Loading available repositories...</p>
      ) : catalog.isError ? (
        <QueryFailure
          error={catalog.error}
          retry={() => void catalog.refetch()}
          label="Retry repository catalog"
        />
      ) : !items.length ? (
        <p>
          {activeSync(connection.catalog_sync)
            ? "The repository catalog is syncing. Available repositories will appear here."
            : "No repositories are available. Check repository access on GitHub, then refresh the catalog."}
        </p>
      ) : (
        <form onSubmit={(event) => void save(event)} aria-busy={saving}>
          <fieldset disabled={!available || saving} className="repository-selection">
            <legend className="sr-only">
              Repositories available from {connection.account_login}
            </legend>
            {items.map((repo) => (
              <label className="repository-choice" key={repo.id}>
                <input
                  type="checkbox"
                  checked={changes[repo.id] ?? repo.selected}
                  disabled={
                    !repo.authorized || (pending >= 100 && !Object.hasOwn(changes, repo.id))
                  }
                  onChange={(event) => toggle(repo, event.target.checked)}
                />
                <span>
                  <strong>{repo.full_name}</strong>
                  <span>
                    {repo.is_private ? "Private" : "Public"} · {repo.default_branch}
                    {repo.archived ? " · Archived" : ""}
                    {!repo.authorized ? " · Access removed" : ""}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
          {catalog.hasNextPage && (
            <Button
              type="button"
              variant="outline"
              disabled={catalog.isFetchingNextPage || saving}
              onClick={() => void catalog.fetchNextPage()}
            >
              {catalog.isFetchingNextPage ? "Loading..." : "Load more available repositories"}
            </Button>
          )}
          <FormMessage error={message.error} success={message.success} />
          {editable && (
            <div className="repository-save">
              <p className="field-hint">
                {pending
                  ? `${pending} unsaved ${pending === 1 ? "change" : "changes"}${pending >= 100 ? ". Save before selecting more repositories." : "."}`
                  : "Your selection is saved."}
              </p>
              <div className="github-toolbar">
                <Button type="submit" disabled={!available || saving || !pending}>
                  {saving ? "Saving selection..." : "Save repositories"}
                </Button>
                {pending > 0 && (
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={saving}
                    onClick={() => setChanges({})}
                  >
                    Discard changes
                  </Button>
                )}
              </div>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
