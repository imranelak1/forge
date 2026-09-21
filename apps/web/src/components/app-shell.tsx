"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Anvil,
  ArrowUpRight,
  BookOpen,
  Boxes,
  ChevronRight,
  CircleHelp,
  GitBranch,
  GitPullRequest,
  LayoutDashboard,
  Monitor,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/system", label: "System status", icon: Activity },
  { href: "/guide", label: "Setup guide", icon: BookOpen },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const current = navigation.find((item) => item.href === pathname)?.label ?? "Forge";
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
        <div className="installation-name">
          <Monitor size={16} aria-hidden="true" />
          <span>Local installation</span>
        </div>
        <nav aria-label="Main navigation" className="navigation">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className={cn("nav-link", pathname === href && "nav-link-active")}
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
            { icon: GitBranch, label: "Repositories" },
            { icon: GitPullRequest, label: "Pull requests" },
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
          <span className="build-label">Foundation build</span>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
