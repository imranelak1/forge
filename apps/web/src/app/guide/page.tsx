import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export const metadata: Metadata = { title: "Setup guide" };

export default function GuidePage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Setup guide</h1>
          <p>Run the foundation locally and understand what comes next.</p>
        </div>
      </div>
      <div className="guide-content">
        <section>
          <h2>Start your installation</h2>
          <p>
            From the repository root, generate local database credentials and start the three
            services. Docker Desktop must be running.
          </p>
          <pre>
            <code>
              {"node scripts/configure.mjs\ndocker compose up -d --build\ndocker compose ps"}
            </code>
          </pre>
          <p>
            The configuration command creates <code>.env</code> once and leaves an existing file
            unchanged. Keep that file private. The first build downloads the application
            dependencies.
          </p>
          <Link className="text-link" href="/system">
            Check service readiness
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </section>
        <section id="troubleshooting">
          <h2>When a service is unavailable</h2>
          <p>
            Inspect the backend and database logs. Confirm the ports in <code>.env</code> are
            available and the configured credentials match the initialized database.
          </p>
          <pre>
            <code>
              {"docker compose logs --tail=80 backend postgres\ndocker compose up -d --build"}
            </code>
          </pre>
          <p>
            Changing passwords in <code>.env</code> does not change an existing database role’s
            password. Follow the rotation procedure in the repository’s development guide. Avoid
            removing the database volume to solve a connection problem.
          </p>
          <p>
            If the schema check needs attention, inspect the migration startup logs. Restarting the
            backend retries the serialized migration step.
          </p>
        </section>
        <section id="next-phase">
          <h2>Build sequence</h2>
          <p>
            Forge is being implemented one phase at a time. This installation contains the
            foundation only.
          </p>
          <ol className="phase-list">
            <li>
              <span>Phase 1</span>
              <div>
                <strong>Project foundation</strong>
                <p>Application shell, API, PostgreSQL, migrations and local containers.</p>
              </div>
              <span className="current-phase">Current</span>
            </li>
            <li>
              <span>Phase 2</span>
              <div>
                <strong>Authentication & organizations</strong>
                <p>Secure sessions, team membership and tenant isolation.</p>
              </div>
            </li>
            <li>
              <span>Phase 3</span>
              <div>
                <strong>GitHub integration</strong>
                <p>Repository access, historical synchronization and verified webhooks.</p>
              </div>
            </li>
            <li>
              <span>Phases 4–9</span>
              <div>
                <strong>Intelligence & automation</strong>
                <p>
                  PR, CI, test and error analytics, lifecycle evidence, alerts and pipeline
                  responses.
                </p>
              </div>
            </li>
          </ol>
        </section>
        <section>
          <h2>Your data stays explicit</h2>
          <p>
            No sample metrics or customer records are bundled into this build. Later demo history
            will be labeled synthetic and stored in the same database models as connected data. An
            unconnected source will always remain distinct from a healthy source with no activity.
          </p>
        </section>
      </div>
    </>
  );
}
