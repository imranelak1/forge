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
          1
        </span>
        <p>
          <strong>The foundation is in place.</strong> Workspace setup and authentication come next.
          Engineering data is not connected yet.
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
              Connect repositories after workspace setup to trace pull requests, build results, and
              deployments in one place.
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
          <p>The application foundation is ready to inspect.</p>
          <ul className="plain-list">
            <li>Responsive application shell</li>
            <li>Live API and database readiness checks</li>
            <li>Versioned schema and local setup guide</li>
          </ul>
          <Link href="/system" className="text-link">
            Inspect system status
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </section>
        <section>
          <h2>Next: your workspace</h2>
          <p>Phase 2 introduces the SaaS foundation.</p>
          <ul className="plain-list">
            <li>Email and password authentication</li>
            <li>Organizations and team memberships</li>
            <li>Roles and organization data isolation</li>
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
