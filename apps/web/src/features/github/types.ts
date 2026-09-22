export type SyncStatus =
  "queued" | "running" | "retrying" | "succeeded" | "partial" | "failed" | "canceled";
export interface SyncRun {
  id: string;
  kind: "catalog" | "history" | "incremental";
  status: SyncStatus;
  stage: "repositories" | "pull_requests" | "commits";
  since: string;
  until: string;
  repositories_processed: number;
  pull_requests_processed: number;
  commits_processed: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  next_retry_at: string | null;
  error_code: string | null;
}
export interface GitHubConnection {
  id: string;
  installation_id: number;
  account_login: string;
  account_type: string;
  status: "active" | "suspended" | "disconnected" | "needs_attention";
  created_at: string;
  last_error: string | null;
  catalog_sync: SyncRun | null;
}
export interface Repository {
  id: string;
  integration_id: string;
  provider_id: number;
  full_name: string;
  html_url: string;
  description: string | null;
  language: string | null;
  default_branch: string;
  is_private: boolean;
  archived: boolean;
  authorized: boolean;
  selected: boolean;
  pushed_at: string | null;
  last_synced_at: string | null;
  pull_request_count: number;
  open_pull_request_count: number;
  commit_count: number;
  latest_sync: SyncRun | null;
}
export interface GitHubStatus {
  configured: boolean;
  install_url: string | null;
  authorization: { id: string; expires_at: string } | null;
  connections: GitHubConnection[];
}
export interface GitHubInstallation {
  id: number;
  account_login: string;
  account_type: string;
  repository_selection: string;
}
export interface GitHubInstallations {
  installations: GitHubInstallation[];
  install_url: string | null;
}
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

export const activeSync = (run: SyncRun | null | undefined) =>
  !!run && ["queued", "running", "retrying"].includes(run.status);
export const canManage = (role: string) => role === "owner" || role === "admin";
export const formatDate = (value: string) =>
  new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export function githubDestination(value: string, kind: "authorize" | "install" | "repository") {
  try {
    const url = new URL(value);
    if (url.origin !== "https://github.com" || url.username || url.password || url.hash)
      return null;
    const allowed =
      kind === "authorize"
        ? url.pathname === "/login/oauth/authorize"
        : kind === "install"
          ? /^\/apps\/[a-z0-9-]+\/installations\/new$/.test(url.pathname)
          : /^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(url.pathname) && !url.search;
    return allowed ? url.href : null;
  } catch {
    return null;
  }
}

const callbackErrors: Record<string, string> = {
  denied: "GitHub authorization was cancelled. Authorize again when you are ready.",
  invalid_state:
    "This authorization expired or could not be verified. Start again in this browser.",
  provider_unavailable: "GitHub could not be reached. Please try authorizing again shortly.",
  invalid_identity:
    "GitHub could not verify this authorization. Start again with the GitHub account that manages your installation.",
  link_unavailable:
    "Sign in with a verified Forge account and ask an organization owner or admin to connect GitHub.",
  authorization_expired:
    "This GitHub authorization has expired. Authorize again to choose an installation.",
  invalid_callback: "GitHub returned an invalid authorization response. Please start again.",
  forbidden: "An organization owner or admin must authorize this GitHub connection.",
  email_unverified: "Verify your Forge email in Account settings, then authorize GitHub again.",
  not_configured: "The installation administrator must configure the Forge GitHub App first.",
  authorization_failed: "GitHub authorization could not be completed. Please start again.",
  credentials_rejected:
    "GitHub rejected the app credentials. Ask the installation administrator to check the GitHub App configuration.",
  access_denied: "GitHub did not grant access. Check app access on GitHub, then authorize again.",
  rate_limited: "GitHub is limiting requests. Wait a few minutes, then authorize again.",
  invalid_response: "GitHub returned an unexpected response. Please try again shortly.",
  installation_admin_required:
    "Sign in to GitHub as the installation's account owner or an organization owner.",
};
export function githubCallbackError(code: string | null) {
  if (!code) return "";
  return Object.hasOwn(callbackErrors, code)
    ? callbackErrors[code]
    : "GitHub authorization could not be completed. Please start again.";
}

export function validGitHubCallbackRedirect(value: string | null): value is string {
  if (
    !value ||
    value.length > 4096 ||
    /[\\\u0000-\u0020]/.test(value) ||
    !value.startsWith("/") ||
    value.startsWith("//")
  )
    return false;
  const url = new URL(value, "https://forge.invalid");
  if (
    url.origin !== "https://forge.invalid" ||
    url.hash ||
    !value.startsWith("/") ||
    value.startsWith("//")
  )
    return false;
  if (value === "/login?oauth_error=link_unavailable") return true;
  if (url.pathname !== "/app/integrations" || value.split("?", 1)[0] !== "/app/integrations")
    return false;
  const seen = new Set<string>();
  for (const [key, item] of url.searchParams) {
    if (seen.has(key)) return false;
    seen.add(key);
    if (key === "organization") {
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(item))
        return false;
    } else if (key === "github") {
      if (item !== "authorized") return false;
    } else if (key === "github_error") {
      if (!Object.hasOwn(callbackErrors, item)) return false;
    } else return false;
  }
  return seen.has("github") !== seen.has("github_error");
}
