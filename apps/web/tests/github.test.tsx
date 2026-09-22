import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IntegrationsPage } from "@/features/github/integrations-page";
import { RepositoriesPage } from "@/features/github/repositories-page";
import {
  githubDestination,
  validGitHubCallbackRedirect,
  type GitHubConnection,
  type GitHubStatus,
  type Repository,
  type SyncRun,
} from "@/features/github/types";
import { api } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";

const state = vi.hoisted(() => ({
  role: "owner",
  verified: true,
  orgId: "11111111-1111-1111-1111-111111111111",
  select: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(window.location.search),
}));
vi.mock("@/features/auth/auth-provider", () => ({
  useAuth: () => ({
    organization: {
      id: state.orgId,
      name: "Test team",
      slug: "test-team",
      role: state.role,
      is_demo: false,
    } as Organization,
    identity: { user: { email_verified: state.verified } },
    selectOrganization: state.select,
  }),
}));
vi.mock("@/lib/auth-client", async () => ({
  ...(await vi.importActual<typeof import("@/lib/auth-client")>("@/lib/auth-client")),
  api: vi.fn(),
}));

const run: SyncRun = {
  id: "run",
  kind: "history",
  status: "failed",
  stage: "commits",
  since: "2026-06-01T00:00:00Z",
  until: "2026-09-01T00:00:00Z",
  repositories_processed: 0,
  pull_requests_processed: 17,
  commits_processed: 31,
  created_at: "2026-09-01T00:00:00Z",
  started_at: null,
  finished_at: null,
  next_retry_at: null,
  error_code: "access_denied",
};
const repo: Repository = {
  id: "repo",
  integration_id: "connection",
  provider_id: 10,
  full_name: "team/api",
  html_url: "https://github.com/team/api",
  description: null,
  language: "Python",
  default_branch: "main",
  is_private: true,
  is_demo: false,
  archived: false,
  authorized: true,
  selected: false,
  pushed_at: "2026-09-01T00:00:00Z",
  last_synced_at: null,
  pull_request_count: 17,
  open_pull_request_count: 3,
  commit_count: 31,
  latest_sync: run,
};
const connection: GitHubConnection = {
  id: "connection",
  installation_id: 42,
  account_login: "team",
  account_type: "Organization",
  status: "active",
  created_at: "2026-09-01T00:00:00Z",
  last_error: null,
  catalog_sync: null,
};
const integration: GitHubStatus = {
  configured: true,
  install_url: "https://github.com/apps/forge/installations/new",
  authorization: null,
  connections: [connection],
};
function mount(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    ...render(<QueryClientProvider client={client}>{element}</QueryClientProvider>),
    client,
  };
}
beforeEach(() => {
  vi.mocked(api).mockReset();
  state.role = "owner";
  state.verified = true;
  state.orgId = "11111111-1111-1111-1111-111111111111";
  state.select.mockReset();
  window.history.replaceState({}, "", "/app/integrations");
});

describe("GitHub organization workflows", () => {
  it("shows a setup path and no fake connect action when app credentials are absent", async () => {
    vi.mocked(api).mockResolvedValue({
      ...integration,
      configured: false,
      install_url: null,
      connections: [],
    });
    mount(<IntegrationsPage />);
    await screen.findByText("GitHub App setup is required");
    expect(screen.getByRole("link", { name: "GitHub App setup guide" })).toHaveAttribute(
      "href",
      "/guide#github-app",
    );
    expect(screen.queryByRole("button", { name: "Authorize GitHub" })).not.toBeInTheDocument();
  });

  it("allows viewers to inspect catalog but prevents mutation actions", async () => {
    state.role = "viewer";
    vi.mocked(api).mockImplementation(async (path) =>
      path.endsWith("/github") ? integration : { items: [repo], next_cursor: null },
    );
    mount(<IntegrationsPage />);
    expect(await screen.findByRole("checkbox")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save repositories" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Authorize GitHub" })).not.toBeInTheDocument();
  });

  it("sends only changed repository selections and confirms queued imports", async () => {
    vi.mocked(api).mockImplementation(async (path) =>
      path.endsWith("/github")
        ? integration
        : path.endsWith("/selection")
          ? { updated: 1 }
          : {
              items: [
                repo,
                { ...repo, id: "already-selected", full_name: "team/web", selected: true },
              ],
              next_cursor: null,
            },
    );
    mount(<IntegrationsPage />);
    const checkbox = await screen.findByRole("checkbox", { name: /team\/api/ });
    expect(screen.getByRole("button", { name: "Save repositories" })).toBeDisabled();
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Save repositories" }));
    await screen.findByText(
      "Repository selection saved. New selections are queued for history import.",
    );
    expect(api).toHaveBeenCalledWith(
      `/organizations/${state.orgId}/integrations/github/connections/connection/selection`,
      { method: "POST", body: { changes: [{ id: "repo", selected: true }] } },
    );
  });

  it("requires confirmation before disconnecting an installation", async () => {
    vi.mocked(api).mockImplementation(async (path) =>
      path.endsWith("/github") ? integration : { items: [], next_cursor: null },
    );
    mount(<IntegrationsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));
    expect(api).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ method: "DELETE" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm disconnect" }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        `/organizations/${state.orgId}/integrations/github/connections/connection`,
        { method: "DELETE" },
      ),
    );
  });

  it("renders real import counts and queues an authorized retry", async () => {
    vi.mocked(api).mockImplementation(async (path) =>
      path.endsWith("/sync")
        ? { sync: { ...run, status: "queued" } }
        : { items: [{ ...repo, selected: true }], next_cursor: null },
    );
    mount(<RepositoriesPage />);
    await screen.findByText("3 open PRs");
    expect(screen.getByText("17 total PRs")).toBeVisible();
    expect(screen.getByText("31 commits")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry sync" }));
    await screen.findByText("Sync queued for team/api. Progress updates automatically.");
    expect(api).toHaveBeenCalledWith(`/organizations/${state.orgId}/repositories/repo/sync`, {
      method: "POST",
      body: {},
    });
  });

  it("does not offer sync when GitHub access is removed", async () => {
    vi.mocked(api).mockResolvedValue({
      items: [{ ...repo, authorized: false }],
      next_cursor: null,
    });
    mount(<RepositoriesPage />);
    await screen.findByText("GitHub access removed");
    expect(screen.getByRole("button", { name: "Retry sync" })).toBeDisabled();
  });

  it("hides the previous organization's selection when switching organizations", async () => {
    vi.mocked(api).mockImplementation(async (path) =>
      path.endsWith("/github") ? integration : { items: [repo], next_cursor: null },
    );
    const { rerender, client } = mount(<IntegrationsPage />);
    fireEvent.click(await screen.findByRole("checkbox"));
    await screen.findByText("1 unsaved change.");
    state.orgId = "22222222-2222-2222-2222-222222222222";
    rerender(
      <QueryClientProvider client={client}>
        <IntegrationsPage />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
    expect(screen.queryByText("1 unsaved change.")).not.toBeInTheDocument();
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining(`/organizations/${state.orgId}/`),
      expect.anything(),
    );
  });
});

describe("GitHub link boundaries", () => {
  it("pins authorization and app install links to the expected GitHub routes", () => {
    expect(
      githubDestination("https://github.com/login/oauth/authorize?state=safe", "authorize"),
    ).toContain("github.com");
    expect(
      githubDestination("https://github.com/apps/forge/installations/new", "install"),
    ).toContain("github.com");
    expect(
      githubDestination(
        "https://github.com.attacker.example/apps/forge/installations/new",
        "install",
      ),
    ).toBeNull();
    expect(githubDestination("javascript:alert(1)", "repository")).toBeNull();
    expect(
      githubDestination("https://github.com/login/oauth/authorize?state=safe", "repository"),
    ).toBeNull();
  });
  it("restricts app callback redirects to a validated organization and fixed result", () => {
    expect(
      validGitHubCallbackRedirect(
        `/app/integrations?organization=${state.orgId}&github=authorized`,
      ),
    ).toBe(true);
    expect(
      validGitHubCallbackRedirect(
        `/app/integrations?organization=${state.orgId}&github_error=denied`,
      ),
    ).toBe(true);
    for (const destination of [
      "//attacker.example",
      "/app/integrations?organization=evil&github=authorized",
      "/app/integrations?github_error=untrusted",
      "/app/integrations?github=authorized&next=https://attacker.example",
      "/app/integrations?github=authorized&github_error=denied",
    ])
      expect(validGitHubCallbackRedirect(destination)).toBe(false);
  });
});
