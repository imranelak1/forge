import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CircleDot,
  GitBranch,
  GitCommitHorizontal,
  GitPullRequest,
  PackageCheck,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { SystemStatus } from "@/features/system/system-status";

const stages = [
  { name: "Issue", icon: CircleDot },
  { name: "Pull request", icon: GitPullRequest },
  { name: "Commit", icon: GitCommitHorizontal },
  { name: "CI pipeline", icon: Workflow },
  { name: "Tests", icon: ShieldCheck },
  { name: "Deployment", icon: PackageCheck },
  { name: "Production", icon: CircleDot },
];

export default function OverviewPage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Engineering overview</h1>
          <p>Your delivery lifecycle, from the first change to production.</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/guide">
            <BookOpen size={16} aria-hidden="true" />
            Setup guide
          </Link>
        </Button>
      </div>
      <div className="phase-notice">
        <span className="notice-mark" aria-hidden="true">
          2
        </span>
        <p>
          <strong>Your workspace is ready.</strong> Accounts, organizations and team permissions are
          available. Engineering sources are not connected yet.
        </p>
      </div>
      <section className="lifecycle-section" aria-labelledby="lifecycle-title">
        <div className="section-label">
          <h2 id="lifecycle-title">Lifecycle coverage</h2>
          <span>Planned · no sources connected</span>
        </div>
        <ol className="lifecycle" tabIndex={0} aria-label="Planned lifecycle stages">
          {stages.map(({ name, icon: Icon }) => (
            <li key={name}>
              <Icon size={18} aria-hidden="true" />
              <span>{name}</span>
            </li>
          ))}
        </ol>
        <p className="lifecycle-hint">
          Scroll to see all seven stages <ArrowRight size={12} aria-hidden="true" />
        </p>
      </section>
      <section className="repository-section" aria-labelledby="repositories-title">
        <div className="section-label">
          <h2 id="repositories-title">Repositories</h2>
          <span>Integration available in Phase 3</span>
        </div>
        <div className="repository-table">
          <div className="repository-columns" aria-hidden="true">
            <span>Repository</span>
            <span>Last activity</span>
            <span>CI status</span>
            <span>Production</span>
          </div>
          <div className="repository-empty">
            <GitBranch size={30} strokeWidth={1.4} aria-hidden="true" />
            <h3>Your engineering history starts here</h3>
            <p>
              GitHub integration is next. Once available, connect repositories to trace pull
              requests, build results and deployments in one place.
            </p>
            <Link href="/guide#next-phase" className="text-link">
              See what comes next
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
      <div className="foundation-details">
        <section>
          <h2>Available in this build</h2>
          <p>Manage workspace access and inspect your installation.</p>
          <ul className="plain-list">
            <li>Email accounts and revocable sessions</li>
            <li>Organizations, invitations and membership roles</li>
            <li>Live API and database readiness checks</li>
          </ul>
          <Link href="/app/settings" className="text-link">
            Manage your organization
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </section>
        <section>
          <h2>Next: connect GitHub</h2>
          <p>Phase 3 introduces the first engineering source.</p>
          <ul className="plain-list">
            <li>Repository access</li>
            <li>Historical synchronization</li>
            <li>Verified webhook ingestion</li>
          </ul>
          <Link href="/guide#next-phase" className="text-link">
            View the build sequence
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </section>
      </div>
      <SystemStatus compact />
    </>
  );
}
