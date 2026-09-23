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
          <p>Run Forge locally, set up your organization and understand what comes next.</p>
        </div>
      </div>
      <div className="guide-content">
        <section>
          <h2>Start your installation</h2>
          <p>
            From the repository root, generate local credentials and start the application, database
            and background worker. Docker Desktop must be running.
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
        <section>
          <h2>Set up your workspace</h2>
          <p>
            Create an account, then name your organization. Organization settings let owners and
            admins invite teammates and manage their roles. Account settings show email verification
            and active browser sessions.
          </p>
          <p>
            Invitation links require a verified account with the same email address. Open
            verification and password reset links in your browser. In local development, email is
            saved to the configured mail outbox; SMTP delivery requires its own configuration.
          </p>
          <Link className="text-link" href="/app">
            Open your workspace
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </section>
        <section id="github-app">
          <h2>Connect GitHub repositories</h2>
          <p>
            Repository access uses a GitHub App, configured separately from GitHub sign-in. The
            installation administrator must register the app and add its credentials to the private
            environment file. Follow <code>docs/github-setup.md</code> in the repository for the
            required permissions, callback address and webhook setup.
          </p>
          <p>
            Once configured, an organization owner or admin with a verified Forge email can open
            Integrations, install the app on GitHub and authorize their GitHub account. Choose the
            installation for your organization, wait for its repository catalog, then select
            repositories and save.
          </p>
          <p>
            History imports run in the background, starting with the last 90 days. Repositories
            shows progress, imported pull requests and commits, and retry actions. Webhooks update
            selected repositories as changes arrive. CI workflows show distinct run attempts and
            jobs; Deployments shows provider records and their first successful status.
          </p>
          <p>
            The overview compares cycle time, review wait and approval-to-merge for the same merged
            pull requests. Open the included or excluded samples to inspect reviews and lifecycle
            evidence. Refresh data after a sync finishes. Optional Issues read permission enables
            issue history and explicit links; missing permission leaves PR and commit imports
            available.
          </p>
          <p>
            For CI and deployment evidence, the GitHub App administrator must enable Actions and
            Deployments read permissions in GitHub App settings, and the installation owner must
            approve the new access. Subscribe to workflow run, workflow job, deployment and
            deployment status events for timely updates. Then sync the selected repository in Forge.
            Until that access is available, the corresponding source remains unavailable.
          </p>
          <p>
            Environment classification uses each deployment’s provider flag. A verified Forge owner
            or admin can set an explicit repository environment override; removing it restores the
            provider flag. A name such as “production” never establishes classification on its own,
            and successful CI never counts as a deployment.
          </p>
          <Link className="text-link" href="/app/integrations">
            Open integrations
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </section>
        <section id="test-reports">
          <h2>Upload JUnit test reports</h2>
          <p>
            Open Tests, then Report uploads and policy. Select a connected repository. A verified
            organization owner or admin can issue a repository-scoped CI token. Copy its credential
            into your CI secret store immediately; Forge shows it only once. Demo repositories
            cannot receive live reports.
          </p>
          <p>
            Import the GitHub workflow attempt before uploading its report. Submit raw JUnit XML
            directly to the backend API, using the provider workflow run ID and attempt number. The
            example below uses shell environment variables for the API origin, organization,
            repository, run and credential.
          </p>
          <pre>
            <code>
              {
                'curl --fail-with-body \\\n  -H "Authorization: Bearer $FORGE_CI_TOKEN" \\\n  -H "Content-Type: application/xml" \\\n  --data-binary @report.xml \\\n  "$FORGE_API_ORIGIN/api/v1/organizations/$FORGE_ORGANIZATION/repositories/$FORGE_REPOSITORY/test-reports?workflow_run_id=$GITHUB_RUN_ID&run_attempt=$GITHUB_RUN_ATTEMPT&report_key=unit-tests&shard=default"'
              }
            </code>
          </pre>
          <p>
            For a local command, the backend origin is http://localhost:8000. Hosted CI needs a
            reachable API origin. Reports are processed in the background; use Refresh data in Tests
            to inspect results. Tokens can upload only, so inspect reports with your Forge account.
          </p>
          <p>
            Keep report key and shard stable across replay. Corrected content requires an explicit
            supersedes report ID; it does not silently add a second result. Send XML up to 10 MiB,
            not an archive. Failure messages and test metadata can contain source-authored sensitive
            details: upload only intended report content. See <code>docs/junit-setup.md</code> for
            limits, corrections and CI integration.
          </p>
          <p>
            Pass rate excludes skipped cases and uses final explicit retries from the latest
            completed workflow attempts. Missing reports remain unknown. Potential-flakiness results
            expose their sample counts, transitions and repository policy; they are evidence for
            investigation rather than a diagnosis.
          </p>
          <Link className="text-link" href="/app/tests/settings">
            Open report upload settings
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
            foundation, account access, organizations, GitHub repository ingestion, pull request
            analytics, CI and deployment evidence, and uploaded test intelligence.
          </p>
          <ol className="phase-list">
            <li>
              <span>Phase 1</span>
              <div>
                <strong>Project foundation</strong>
                <p>Application shell, API, PostgreSQL, migrations and local containers.</p>
              </div>
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
              <span>Phase 4</span>
              <div>
                <strong>Pull requests & commit analytics</strong>
                <p>
                  Timing distributions, sample coverage, reviews, lifecycle history, explicit
                  relationships and changed-file metadata.
                </p>
              </div>
            </li>
            <li>
              <span>Phase 5</span>
              <div>
                <strong>CI & deployments</strong>
                <p>
                  Distinct workflow attempts, job evidence, outcome and timing metrics,
                  first-success deployments and explicit environment classification.
                </p>
              </div>
            </li>
            <li>
              <span>Phase 6</span>
              <div>
                <strong>Test intelligence</strong>
                <p>
                  JUnit reports, suite and case evidence, pass rates, potential-flakiness policies
                  and scoped CI upload credentials.
                </p>
              </div>
              <span className="current-phase">Current</span>
            </li>
            <li>
              <span>Phases 7–9</span>
              <div>
                <strong>Intelligence & automation</strong>
                <p>
                  Production-error analytics, lifecycle correlation, alerts and pipeline responses.
                </p>
              </div>
            </li>
          </ol>
        </section>
        <section>
          <h2>Your data stays explicit</h2>
          <p>
            Demo organizations contain clearly labeled generated history in the same database models
            as connected records. Their metrics use the same queries; live GitHub data stays
            separate. Missing review or issue evidence is shown explicitly, and unavailable timing
            samples are never displayed as zero.
          </p>
        </section>
      </div>
    </>
  );
}
