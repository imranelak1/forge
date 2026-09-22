"""Explicit workflow attempts and independent deployment/status evidence."""

from alembic import op

revision = "0007_cicd"
down_revision = "0006_analytics"
branch_labels = None
depends_on = None

TABLES = (
    "workflow_runs",
    "workflow_jobs",
    "workflow_run_pull_requests",
    "deployment_environments",
    "deployments",
    "deployment_statuses",
)
COVERAGE = {
    "repositories": ("ci", "deployments"),
    "workflow_runs": ("jobs", "links"),
    "deployments": ("statuses",),
}


def upgrade() -> None:
    op.execute("""
        ALTER TABLE forge.repositories ADD COLUMN ci_window_since timestamptz,
            ADD COLUMN ci_window_until timestamptz,
            ADD COLUMN deployments_window_since timestamptz,
            ADD COLUMN deployments_window_until timestamptz;
        CREATE TABLE forge.workflow_runs (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            provider_run_id bigint NOT NULL CHECK (provider_run_id>0),
            run_attempt integer NOT NULL CHECK (run_attempt>0),
            provider_workflow_id bigint NOT NULL CHECK (provider_workflow_id>0),
            run_number bigint, actor_login varchar(100), name text NOT NULL, path text,
            event varchar(80) NOT NULL, head_branch varchar(255),
            head_sha varchar(40) NOT NULL CHECK (head_sha ~ '^[a-f0-9]{40}$'),
            commit_id uuid, status varchar(40) NOT NULL, conclusion varchar(40),
            created_at timestamptz NOT NULL, queued_at timestamptz, started_at timestamptz,
            completed_at timestamptz, completion_source varchar(30)
                CHECK (completion_source IN ('provider','jobs')),
            updated_at timestamptz NOT NULL, html_url text NOT NULL,
            provider_pull_requests jsonb NOT NULL DEFAULT '[]'::jsonb,
            observed_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,repository_id,id),
            UNIQUE (organization_id,repository_id,provider_run_id,run_attempt),
            FOREIGN KEY (organization_id,repository_id)
                REFERENCES forge.repositories(organization_id,id),
            FOREIGN KEY (organization_id,repository_id,commit_id)
                REFERENCES forge.commits(organization_id,repository_id,id)
        );
        CREATE TABLE forge.workflow_jobs (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            workflow_run_id uuid NOT NULL,
            provider_job_id bigint NOT NULL CHECK (provider_job_id>0),
            name text NOT NULL, status varchar(40) NOT NULL, conclusion varchar(40),
            started_at timestamptz, completed_at timestamptz, html_url text NOT NULL,
            labels jsonb NOT NULL DEFAULT '[]'::jsonb, steps jsonb NOT NULL DEFAULT '[]'::jsonb,
            failure_category varchar(40) NOT NULL DEFAULT 'unknown',
            observed_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,workflow_run_id,provider_job_id),
            FOREIGN KEY (organization_id,repository_id,workflow_run_id)
                REFERENCES forge.workflow_runs(organization_id,repository_id,id)
        );
        CREATE TABLE forge.workflow_run_pull_requests (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            workflow_run_id uuid NOT NULL, pull_request_id uuid NOT NULL,
            source varchar(30) NOT NULL DEFAULT 'provider', PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,workflow_run_id,pull_request_id),
            FOREIGN KEY (organization_id,repository_id,workflow_run_id)
                REFERENCES forge.workflow_runs(organization_id,repository_id,id),
            FOREIGN KEY (organization_id,repository_id,pull_request_id)
                REFERENCES forge.pull_requests(organization_id,repository_id,id)
        );
        CREATE TABLE forge.deployment_environments (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            name varchar(255) NOT NULL, classification varchar(16)
                CHECK (classification IN ('production','nonproduction')),
            updated_by uuid REFERENCES forge.users(id),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,repository_id,id),
            UNIQUE (organization_id,repository_id,name),
            FOREIGN KEY (organization_id,repository_id)
                REFERENCES forge.repositories(organization_id,id)
        );
        CREATE TABLE forge.deployments (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            provider_id bigint NOT NULL CHECK (provider_id>0), environment_id uuid NOT NULL,
            environment varchar(255) NOT NULL, production_environment boolean,
            transient_environment boolean, sha varchar(40) NOT NULL CHECK (sha ~ '^[a-f0-9]{40}$'),
            ref text NOT NULL, task varchar(100) NOT NULL, description text,
            creator_login varchar(100), created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL, html_url text NOT NULL, commit_id uuid,
            workflow_run_id uuid, workflow_provider_id bigint, workflow_attempt integer,
            workflow_link_source varchar(30), observed_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,repository_id,id),
            UNIQUE (organization_id,repository_id,provider_id),
            FOREIGN KEY (organization_id,repository_id)
                REFERENCES forge.repositories(organization_id,id),
            FOREIGN KEY (organization_id,repository_id,environment_id)
                REFERENCES forge.deployment_environments(organization_id,repository_id,id),
            FOREIGN KEY (organization_id,repository_id,commit_id)
                REFERENCES forge.commits(organization_id,repository_id,id),
            FOREIGN KEY (organization_id,repository_id,workflow_run_id)
                REFERENCES forge.workflow_runs(organization_id,repository_id,id)
        );
        CREATE TABLE forge.deployment_statuses (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            deployment_id uuid NOT NULL, provider_id bigint NOT NULL CHECK (provider_id>0),
            state varchar(40) NOT NULL, description text, environment varchar(255),
            creator_login varchar(100), created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL, html_url text NOT NULL,
            observed_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,deployment_id,provider_id),
            FOREIGN KEY (organization_id,repository_id,deployment_id)
                REFERENCES forge.deployments(organization_id,repository_id,id)
        );
        CREATE INDEX workflow_runs_completed ON forge.workflow_runs
            (organization_id,repository_id,completed_at,id);
        CREATE INDEX workflow_runs_updated ON forge.workflow_runs
            (organization_id,repository_id,updated_at,id);
        CREATE INDEX workflow_prs_pr ON forge.workflow_run_pull_requests
            (organization_id,pull_request_id,workflow_run_id);
        CREATE INDEX deployments_created ON forge.deployments
            (organization_id,repository_id,created_at,id);
        CREATE INDEX deployment_statuses_time ON forge.deployment_statuses
            (organization_id,deployment_id,created_at,provider_id,id);
    """)
    for table, prefixes in COVERAGE.items():
        for prefix in prefixes:
            op.execute(f"""ALTER TABLE forge.{table}
                ADD COLUMN {prefix}_status varchar(16) NOT NULL DEFAULT 'pending'
                    CHECK ({prefix}_status IN
                        ('pending','partial','complete','failed','unavailable')),
                ADD COLUMN {prefix}_error varchar(80), ADD COLUMN {prefix}_synced_at timestamptz""")
    tenant = "nullif(current_setting('forge.organization_id',true),'')::uuid"
    for table in TABLES:
        op.execute(f"ALTER TABLE forge.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE forge.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_access ON forge.{table} "
            f"USING (organization_id={tenant}) WITH CHECK (organization_id={tenant})"
        )
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON forge.{table} TO forge_app")


def downgrade() -> None:
    op.execute("""DELETE FROM forge.jobs WHERE kind='enrichment' AND payload->>'kind' IN
        ('ci_repository','deployments_repository','workflow_discovery','workflow_run',
         'deployment','cicd_links')""")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE forge.{table}")
    for prefix in ("ci", "deployments"):
        for suffix in ("status", "error", "synced_at", "window_since", "window_until"):
            op.execute(f"ALTER TABLE forge.repositories DROP COLUMN {prefix}_{suffix}")
