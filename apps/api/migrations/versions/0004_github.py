"""Tenant-isolated GitHub sources and durable ingestion work."""

from alembic import op

revision = "0004_github"
down_revision = "0003_oauth"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "integrations",
    "repositories",
    "sync_runs",
    "webhook_inbox",
    "jobs",
    "pull_requests",
    "commits",
    "events",
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE forge.github_app_authorizations (
            id uuid PRIMARY KEY, state_hash varchar(64) NOT NULL UNIQUE,
            browser_hash varchar(64) NOT NULL,
            organization_id uuid NOT NULL REFERENCES forge.organizations(id),
            user_id uuid NOT NULL REFERENCES forge.users(id),
            session_id uuid NOT NULL REFERENCES forge.auth_sessions(id),
            expires_at timestamptz NOT NULL, used_at timestamptz,
            token_ciphertext text, completed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX github_authorizations_session ON forge.github_app_authorizations
            (organization_id,user_id,session_id,expires_at);
        CREATE TABLE forge.integrations (
            organization_id uuid NOT NULL REFERENCES forge.organizations(id), id uuid NOT NULL,
            provider varchar(16) NOT NULL DEFAULT 'github' CHECK (provider='github'),
            installation_id bigint NOT NULL CHECK (installation_id>0),
            account_login varchar(100) NOT NULL, account_type varchar(30) NOT NULL,
            status varchar(24) NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','suspended','disconnected','needs_attention')),
            last_error varchar(80), created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,installation_id)
        );
        -- Global routing contains no provider credentials or engineering payloads.
        CREATE TABLE forge.github_installation_bindings (
            installation_id bigint PRIMARY KEY CHECK (installation_id>0),
            organization_id uuid NOT NULL, integration_id uuid NOT NULL,
            FOREIGN KEY (organization_id,integration_id)
                REFERENCES forge.integrations(organization_id,id)
        );
        CREATE TABLE forge.repositories (
            organization_id uuid NOT NULL, id uuid NOT NULL, integration_id uuid NOT NULL,
            provider_id bigint NOT NULL CHECK (provider_id>0),
            owner varchar(100) NOT NULL, name varchar(100) NOT NULL,
            full_name varchar(201) NOT NULL, html_url text NOT NULL,
            description text, language varchar(100), default_branch varchar(255) NOT NULL,
            is_private boolean NOT NULL, archived boolean NOT NULL,
            authorized boolean NOT NULL DEFAULT true, selected boolean NOT NULL DEFAULT false,
            pushed_at timestamptz, last_synced_at timestamptz, catalog_run_id uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,provider_id),
            UNIQUE (organization_id,id,integration_id),
            FOREIGN KEY (organization_id,integration_id)
                REFERENCES forge.integrations(organization_id,id)
        );
        CREATE INDEX repositories_integration ON forge.repositories
            (organization_id,integration_id,id);
        CREATE TABLE forge.sync_runs (
            organization_id uuid NOT NULL, id uuid NOT NULL, integration_id uuid NOT NULL,
            repository_id uuid, kind varchar(16) NOT NULL
                CHECK (kind IN ('catalog','history','incremental')),
            status varchar(16) NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','running','retrying','succeeded','partial',
                    'failed','canceled')),
            stage varchar(20) NOT NULL
                CHECK (stage IN ('repositories','pull_requests','commits')),
            since timestamptz NOT NULL, until timestamptz NOT NULL,
            checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb,
            repositories_processed integer NOT NULL DEFAULT 0 CHECK (repositories_processed>=0),
            pull_requests_processed integer NOT NULL DEFAULT 0 CHECK (pull_requests_processed>=0),
            commits_processed integer NOT NULL DEFAULT 0 CHECK (commits_processed>=0),
            requested_by uuid REFERENCES forge.users(id),
            created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz,
            finished_at timestamptz, next_retry_at timestamptz, error_code varchar(80),
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,id,integration_id),
            FOREIGN KEY (organization_id,integration_id)
                REFERENCES forge.integrations(organization_id,id),
            FOREIGN KEY (organization_id,repository_id,integration_id)
                REFERENCES forge.repositories(organization_id,id,integration_id),
            CHECK ((kind='catalog' AND repository_id IS NULL)
                OR (kind<>'catalog' AND repository_id IS NOT NULL)),
            CHECK (since<=until)
        );
        CREATE UNIQUE INDEX sync_runs_active_repository ON forge.sync_runs
            (organization_id,repository_id) WHERE repository_id IS NOT NULL
                AND status IN ('queued','running','retrying');
        CREATE UNIQUE INDEX sync_runs_active_catalog ON forge.sync_runs
            (organization_id,integration_id) WHERE kind='catalog'
                AND status IN ('queued','running','retrying');
        CREATE INDEX sync_runs_repository ON forge.sync_runs
            (organization_id,repository_id,id);
        CREATE TABLE forge.webhook_receipts (
            delivery_id uuid PRIMARY KEY, digest varchar(64) NOT NULL, event varchar(80) NOT NULL,
            status varchar(20) NOT NULL CHECK (status IN ('queued','ignored','processed','failed')),
            reason varchar(80), organization_id uuid, integration_id uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (organization_id,integration_id)
                REFERENCES forge.integrations(organization_id,id)
        );
        CREATE TABLE forge.webhook_inbox (
            organization_id uuid NOT NULL, id uuid NOT NULL
                REFERENCES forge.webhook_receipts(delivery_id),
            integration_id uuid NOT NULL, payload jsonb NOT NULL, event varchar(80) NOT NULL,
            status varchar(20) NOT NULL CHECK (status IN ('queued','ignored','processed','failed')),
            reason varchar(80), created_at timestamptz NOT NULL DEFAULT now(),
            processed_at timestamptz, PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,id,integration_id),
            FOREIGN KEY (organization_id,integration_id)
                REFERENCES forge.integrations(organization_id,id)
        );
        CREATE TABLE forge.jobs (
            organization_id uuid NOT NULL, id uuid NOT NULL, integration_id uuid NOT NULL,
            sync_run_id uuid, inbox_id uuid, kind varchar(16) NOT NULL
                CHECK (kind IN ('sync','webhook')),
            dedup_key text NOT NULL, state varchar(16) NOT NULL DEFAULT 'queued'
                CHECK (state IN ('queued','running','retry','succeeded','dead','canceled')),
            available_at timestamptz NOT NULL DEFAULT now(), lease_until timestamptz,
            lease_token uuid, fence bigint NOT NULL DEFAULT 0,
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts>=0),
            payload jsonb NOT NULL DEFAULT '{}'::jsonb, last_error varchar(80),
            created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,dedup_key),
            FOREIGN KEY (organization_id,integration_id)
                REFERENCES forge.integrations(organization_id,id),
            FOREIGN KEY (organization_id,sync_run_id,integration_id)
                REFERENCES forge.sync_runs(organization_id,id,integration_id),
            FOREIGN KEY (organization_id,inbox_id,integration_id)
                REFERENCES forge.webhook_inbox(organization_id,id,integration_id),
            CHECK ((kind='sync' AND sync_run_id IS NOT NULL AND inbox_id IS NULL)
                OR (kind='webhook' AND inbox_id IS NOT NULL AND sync_run_id IS NULL))
        );
        CREATE INDEX jobs_available ON forge.jobs (available_at,created_at)
            WHERE state IN ('queued','retry');
        CREATE INDEX jobs_expired ON forge.jobs (lease_until) WHERE state='running';
        CREATE TABLE forge.pull_requests (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            provider_id bigint NOT NULL CHECK (provider_id>0), number integer NOT NULL
                CHECK (number>0), title text NOT NULL,
            state varchar(8) NOT NULL CHECK (state IN ('open','closed')),
            draft boolean NOT NULL, author_login varchar(100), head_sha varchar(40) NOT NULL,
            base_ref varchar(255) NOT NULL, opened_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL, closed_at timestamptz, merged_at timestamptz,
            html_url text NOT NULL, PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,repository_id,number),
            FOREIGN KEY (organization_id,repository_id)
                REFERENCES forge.repositories(organization_id,id)
        );
        CREATE TABLE forge.commits (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            sha varchar(40) NOT NULL CHECK (sha ~ '^[a-f0-9]{40}$'),
            message text NOT NULL, author_login varchar(100), authored_at timestamptz,
            committed_at timestamptz NOT NULL, html_url text NOT NULL,
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,repository_id,sha),
            FOREIGN KEY (organization_id,repository_id)
                REFERENCES forge.repositories(organization_id,id)
        );
        CREATE TABLE forge.events (
            organization_id uuid NOT NULL, id uuid NOT NULL, integration_id uuid NOT NULL,
            repository_id uuid, source_key text NOT NULL, kind varchar(80) NOT NULL,
            occurred_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,source_key),
            FOREIGN KEY (organization_id,integration_id)
                REFERENCES forge.integrations(organization_id,id),
            FOREIGN KEY (organization_id,repository_id,integration_id)
                REFERENCES forge.repositories(organization_id,id,integration_id)
        );
        GRANT SELECT, INSERT, UPDATE, DELETE ON forge.github_app_authorizations TO forge_app;
        GRANT SELECT, INSERT ON forge.github_installation_bindings TO forge_app;
        GRANT SELECT, INSERT, UPDATE ON forge.webhook_receipts TO forge_app;
    """)
    tenant = "nullif(current_setting('forge.organization_id',true),'')::uuid"
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE forge.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE forge.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_access ON forge.{table} "
            f"USING (organization_id={tenant}) WITH CHECK (organization_id={tenant})"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON forge.{table} TO forge_app")
    # Only this bounded dispatcher can select work across tenants. It returns routing
    # metadata, never a payload. The worker sets tenant context before all other SQL.
    op.execute("""
        CREATE POLICY job_dispatch ON forge.jobs TO forge_migrator USING (true) WITH CHECK (true);
        CREATE FUNCTION forge.claim_job(owner_token uuid)
        RETURNS TABLE (organization_id uuid, id uuid, fence bigint)
        LANGUAGE SQL SECURITY DEFINER SET search_path=pg_catalog,forge,pg_temp AS $$
            WITH candidate AS (
                SELECT j.organization_id,j.id FROM forge.jobs j
                WHERE (j.state IN ('queued','retry') AND j.available_at<=now())
                    OR (j.state='running' AND j.lease_until<=now())
                ORDER BY j.available_at,j.created_at,j.id
                FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE forge.jobs j SET state='running',lease_token=owner_token,
                lease_until=now()+interval '60 seconds',fence=j.fence+1,attempts=j.attempts+1
            FROM candidate c WHERE j.organization_id=c.organization_id AND j.id=c.id
            RETURNING j.organization_id,j.id,j.fence
        $$;
        REVOKE ALL ON FUNCTION forge.claim_job(uuid) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION forge.claim_job(uuid) TO forge_app;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION forge.claim_job(uuid)")
    for table in ("events", "commits", "pull_requests", "jobs", "webhook_inbox"):
        op.execute(f"DROP TABLE forge.{table}")
    op.execute("DROP TABLE forge.webhook_receipts")
    for table in ("sync_runs", "repositories", "github_installation_bindings", "integrations"):
        op.execute(f"DROP TABLE forge.{table}")
    op.execute("DROP TABLE forge.github_app_authorizations")
