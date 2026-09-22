"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Anvil,
  ArrowUpRight,
  BookOpen,
  Boxes,
  ChevronRight,
  CircleHelp,
  GitBranch,
  GitCommitHorizontal,
  GitPullRequest,
  LayoutDashboard,
  Monitor,
  Plug,
  ShieldCheck,
  Settings,
  UserRound,
  Workflow,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/features/auth/auth-provider";
import { errorMessage } from "@/lib/auth-client";

const navigation = [
  { href: "/app", label: "Overview", icon: LayoutDashboard },
  { href: "/system", label: "System status", icon: Activity },
  { href: "/guide", label: "Setup guide", icon: BookOpen },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { identity, organization, selectOrganization, loadMoreOrganizations } = useAuth();
  const [loadingOrganizations, setLoadingOrganizations] = useState(false);
  const [organizationError, setOrganizationError] = useState("");
  const links = identity
    ? [
        navigation[0],
        { href: "/app/repositories", label: "Repositories", icon: GitBranch },
        { href: "/app/pull-requests", label: "Pull requests", icon: GitPullRequest },
        { href: "/app/commits", label: "Commits", icon: GitCommitHorizontal },
        { href: "/app/integrations", label: "Integrations", icon: Plug },
        ...navigation.slice(1),
        { href: "/app/settings", label: "Organization settings", icon: Settings },
        { href: "/app/account", label: "Account", icon: UserRound },
      ]
    : navigation;
  const active = (href: string) =>
    pathname === href || (href !== "/app" && pathname.startsWith(`${href}/`));
  const current = links.find((item) => active(item.href))?.label ?? "Forge";
  if (
    pathname === "/" ||
    [
      "/login",
      "/register",
      "/forgot-password",
      "/reset-password",
      "/verify-email",
      "/invite",
    ].includes(pathname)
  )
    return <>{children}</>;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Application sidebar">
        <Link href="/" className="brand" aria-label="Forge home">
          <Anvil size={23} strokeWidth={1.7} aria-hidden="true" />
          <span>Forge</span>
        </Link>
        {identity ? (
          <div className="organization-switcher">
            <label htmlFor="active-organization">Organization</label>
            <select
              id="active-organization"
              value={organization?.id ?? ""}
              onChange={(event) => {
                if (event.target.value === "new") router.push("/app/organizations/new");
                else void selectOrganization(event.target.value);
              }}
            >
              {!organization && <option value="">No organization yet</option>}
              {identity.organizations.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
              <option value="new">Create organization...</option>
            </select>
            {identity.organizations_page?.has_more && (
              <button
                type="button"
                className="organization-load text-link"
                disabled={loadingOrganizations}
                onClick={async () => {
                  setLoadingOrganizations(true);
                  setOrganizationError("");
                  try {
                    await loadMoreOrganizations();
                  } catch (error) {
                    setOrganizationError(errorMessage(error));
                  } finally {
                    setLoadingOrganizations(false);
                  }
                }}
              >
                {loadingOrganizations ? "Loading organizations..." : "Load more organizations"}
              </button>
            )}
            {organizationError && (
              <p className="form-error" role="alert">
                {organizationError}
              </p>
            )}
          </div>
        ) : (
          <div className="installation-name">
            <Monitor size={16} aria-hidden="true" />
            <span>Local installation</span>
          </div>
        )}
        <nav aria-label="Main navigation" className="navigation">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={active(href) ? "page" : undefined}
              className={cn("nav-link", active(href) && "nav-link-active")}
            >
              <Icon size={17} aria-hidden="true" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="planned-navigation">
          <p>
            Engineering tools <span>Planned</span>
          </p>
          {[
            { icon: Workflow, label: "CI & deployments" },
            { icon: ShieldCheck, label: "Test intelligence" },
            { icon: Boxes, label: "Errors & automation" },
          ].map(({ icon: Icon, label }) => (
            <div className="planned-link" key={label}>
              <Icon size={17} aria-hidden="true" />
              {label}
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <Link href="/guide#next-phase">
            <CircleHelp size={16} aria-hidden="true" />
            About this build
            <ArrowUpRight size={14} aria-hidden="true" />
          </Link>
          <span>
            Forge <span className="mono">v0.1.0</span>
          </span>
        </div>
      </aside>
      <div className="app-body">
        <header className="context-bar">
          <div>
            <span className="context-root">Forge</span>
            <ChevronRight size={14} aria-hidden="true" />
            <span>{current}</span>
          </div>
          <span className="build-label">Phase 4 · Pull request analytics</span>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
