"""Repository-scoped machine credentials and durable, tenant-isolated JUnit evidence."""

from alembic import op

revision = "0008_test_reports"
down_revision = "0007_cicd"
branch_labels = None
depends_on = None
TABLES = (
    "service_tokens",
    "test_policies",
    "test_reports",
    "test_suites",
    "test_identities",
    "test_executions",
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE forge.service_tokens (
            organization_id uuid NOT NULL,id uuid NOT NULL,repository_id uuid NOT NULL,
            name varchar(100) NOT NULL,token_hash char(64) NOT NULL UNIQUE,
            token_prefix varchar(24) NOT NULL,scope varchar(40) NOT NULL
                CHECK(scope='test_reports:write'),created_by uuid NOT NULL REFERENCES
                forge.users(id),
            created_at timestamptz NOT NULL DEFAULT now(),expires_at timestamptz NOT NULL,
            revoked_at timestamptz,last_used_at timestamptz,
            PRIMARY KEY(organization_id,id),UNIQUE(organization_id,repository_id,id),
            CHECK(expires_at>created_at),
            FOREIGN KEY(organization_id,repository_id) REFERENCES
            forge.repositories(organization_id,id)
        );
        CREATE TABLE forge.test_policies (
            organization_id uuid NOT NULL,id uuid NOT NULL,repository_id uuid NOT NULL,
            version integer NOT NULL DEFAULT 1 CHECK(version>0),
            window_days integer NOT NULL DEFAULT 14 CHECK(window_days BETWEEN 2 AND 90),
            min_executions integer NOT NULL DEFAULT 10 CHECK(min_executions BETWEEN 2 AND 1000),
            failure_rate_low double precision NOT NULL DEFAULT .05,
            failure_rate_high double precision NOT NULL DEFAULT .95,
            min_transitions integer NOT NULL DEFAULT 2 CHECK(min_transitions BETWEEN 1 AND 100),
            excluded_branches jsonb NOT NULL DEFAULT '[]'
            CHECK(jsonb_typeof(excluded_branches)='array'),
            updated_by uuid REFERENCES forge.users(id),updated_at timestamptz NOT NULL DEFAULT
            now(),
            PRIMARY KEY(organization_id,id),UNIQUE(organization_id,repository_id),
            CHECK(0<failure_rate_low AND failure_rate_low<failure_rate_high AND
            failure_rate_high<1),
            FOREIGN KEY(organization_id,repository_id) REFERENCES
            forge.repositories(organization_id,id)
        );
        CREATE TABLE forge.test_reports (
            organization_id uuid NOT NULL,id uuid NOT NULL,repository_id uuid NOT NULL,
            workflow_run_id uuid NOT NULL,service_token_id uuid,
            report_key varchar(200) NOT NULL,shard varchar(200) NOT NULL DEFAULT 'default',
            framework varchar(80) NOT NULL DEFAULT 'junit',environment varchar(255),branch
            varchar(255),
            commit_sha char(40) NOT NULL CHECK(commit_sha ~ '^[a-f0-9]{40}$'),
            content_sha256 char(64) NOT NULL,size_bytes integer NOT NULL
                CHECK(size_bytes BETWEEN 1 AND 10485760),
            status varchar(16) NOT NULL DEFAULT 'queued'
                CHECK(status IN ('queued','processing','completed','failed')),
            error_code varchar(80),warnings jsonb NOT NULL DEFAULT '[]'
                CHECK(jsonb_typeof(warnings)='array'),declared_total integer,
            case_count integer NOT NULL DEFAULT 0 CHECK(case_count>=0),
            execution_count integer NOT NULL DEFAULT 0 CHECK(execution_count>=0),
            passed_count integer NOT NULL DEFAULT 0 CHECK(passed_count>=0),
            failed_count integer NOT NULL DEFAULT 0 CHECK(failed_count>=0),
            error_count integer NOT NULL DEFAULT 0 CHECK(error_count>=0),
            skipped_count integer NOT NULL DEFAULT 0 CHECK(skipped_count>=0),
            duration_seconds double precision CHECK(duration_seconds>=0 AND
            duration_seconds<'Infinity'),
            supersedes_id uuid,superseded_by_id uuid,received_at timestamptz NOT NULL DEFAULT now(),
            processed_at timestamptz,occurred_at timestamptz NOT NULL,
            time_source varchar(24) NOT NULL CHECK(time_source IN ('workflow_completion',
            'received')),
            payload_expires_at timestamptz NOT NULL,payload bytea,
            PRIMARY KEY(organization_id,id),UNIQUE(organization_id,repository_id,id),
            UNIQUE(organization_id,repository_id,workflow_run_id,report_key,shard,content_sha256),
            CHECK(payload IS NULL OR octet_length(payload)<=14681088),
            FOREIGN KEY(organization_id,repository_id) REFERENCES
            forge.repositories(organization_id,id),
            FOREIGN KEY(organization_id,repository_id,workflow_run_id)
                REFERENCES forge.workflow_runs(organization_id,repository_id,id),
            FOREIGN KEY(organization_id,repository_id,service_token_id)
                REFERENCES forge.service_tokens(organization_id,repository_id,id),
            FOREIGN KEY(organization_id,repository_id,supersedes_id)
                REFERENCES forge.test_reports(organization_id,repository_id,id),
            FOREIGN KEY(organization_id,repository_id,superseded_by_id)
                REFERENCES forge.test_reports(organization_id,repository_id,id)
        );
        CREATE TABLE forge.test_suites (
            organization_id uuid NOT NULL,id uuid NOT NULL,repository_id uuid NOT NULL,
            report_id uuid NOT NULL,source_key varchar(100) NOT NULL,parent_id uuid,
            path jsonb NOT NULL CHECK(jsonb_typeof(path)='array'),name text NOT NULL,ordinal
            integer NOT NULL,
            declared_counts jsonb NOT NULL DEFAULT '{}',case_count integer NOT NULL,
            passed_count integer NOT NULL,failed_count integer NOT NULL,error_count integer NOT
            NULL,
            skipped_count integer NOT NULL,PRIMARY KEY(organization_id,id),
            UNIQUE(organization_id,report_id,source_key),UNIQUE(organization_id,repository_id,
            report_id,id),
            FOREIGN KEY(organization_id,repository_id,report_id)
                REFERENCES forge.test_reports(organization_id,repository_id,id),
            FOREIGN KEY(organization_id,repository_id,report_id,parent_id)
                REFERENCES forge.test_suites(organization_id,repository_id,report_id,id)
        );
        CREATE TABLE forge.test_identities (
            organization_id uuid NOT NULL,id uuid NOT NULL,repository_id uuid NOT NULL,
            framework varchar(80) NOT NULL,identity_key char(64) NOT NULL,
            identity_quality varchar(16) NOT NULL CHECK(identity_quality IN ('exact','fallback',
            'ambiguous')),
            classname text,name text NOT NULL,file text,parameterization text,
            created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(organization_id,id),
            UNIQUE(organization_id,repository_id,framework,identity_key),
            UNIQUE(organization_id,repository_id,id),
            FOREIGN KEY(organization_id,repository_id) REFERENCES
            forge.repositories(organization_id,id)
        );
        CREATE TABLE forge.test_executions (
            organization_id uuid NOT NULL,id uuid NOT NULL,repository_id uuid NOT NULL,
            report_id uuid NOT NULL,suite_id uuid NOT NULL,test_identity_id uuid NOT NULL,
            ordinal integer NOT NULL,source_ordinal integer NOT NULL,retry_ordinal integer NOT NULL
                CHECK(retry_ordinal>=0),is_final boolean NOT NULL,
            outcome varchar(10) NOT NULL CHECK(outcome IN ('passed','failed','error','skipped')),
            failure_message varchar(2048),
            duration_seconds double precision CHECK(duration_seconds>=0 AND
            duration_seconds<'Infinity'),
            PRIMARY KEY(organization_id,id),UNIQUE(organization_id,report_id,ordinal),
            UNIQUE(organization_id,report_id,test_identity_id,retry_ordinal),
            FOREIGN KEY(organization_id,repository_id,report_id)
                REFERENCES forge.test_reports(organization_id,repository_id,id),
            FOREIGN KEY(organization_id,repository_id,report_id,suite_id)
                REFERENCES forge.test_suites(organization_id,repository_id,report_id,id),
            FOREIGN KEY(organization_id,repository_id,test_identity_id)
                REFERENCES forge.test_identities(organization_id,repository_id,id)
        );
        CREATE INDEX test_reports_time ON forge.test_reports(organization_id,repository_id,
        occurred_at,id);
        CREATE INDEX test_reports_workflow ON forge.test_reports(organization_id,workflow_run_id);
        CREATE INDEX test_executions_identity ON forge.test_executions(organization_id,
        test_identity_id,report_id);
        ALTER TABLE forge.jobs DROP CONSTRAINT jobs_check,DROP CONSTRAINT jobs_kind_check,
            ADD COLUMN test_report_id uuid,
            ADD CONSTRAINT jobs_report_fk FOREIGN KEY(organization_id,repository_id,test_report_id)
                REFERENCES forge.test_reports(organization_id,repository_id,id),
            ADD CONSTRAINT jobs_kind_check CHECK(kind IN ('sync','webhook','enrichment',
            'test_report')),
            ADD CONSTRAINT jobs_check CHECK(
                (kind='sync' AND sync_run_id IS NOT NULL AND inbox_id IS NULL
                    AND repository_id IS NULL AND test_report_id IS NULL)
                OR(kind='webhook' AND inbox_id IS NOT NULL AND sync_run_id IS NULL
                    AND repository_id IS NULL AND test_report_id IS NULL)
                OR(kind='enrichment' AND repository_id IS NOT NULL AND sync_run_id IS NULL
                    AND inbox_id IS NULL AND test_report_id IS NULL)
                OR(kind='test_report' AND repository_id IS NOT NULL AND test_report_id IS NOT NULL
                    AND sync_run_id IS NULL AND inbox_id IS NULL));
    """)
    tenant = "nullif(current_setting('forge.organization_id',true),'')::uuid"
    for table in TABLES:
        op.execute(f"ALTER TABLE forge.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE forge.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_access ON forge.{table} "
            f"USING(organization_id={tenant}) WITH CHECK(organization_id={tenant})"
        )
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON forge.{table} TO forge_app")
    # Expiry/cancellation maintenance is bounded and returns a count, never tenant data or XML.
    op.execute("""
        CREATE POLICY report_cleanup ON forge.test_reports TO forge_migrator USING(true) WITH
        CHECK(true);
        CREATE FUNCTION forge.clear_test_payloads() RETURNS bigint LANGUAGE SQL SECURITY DEFINER
        SET search_path=pg_catalog,forge,pg_temp AS $$
          WITH candidates AS (
            SELECT j.organization_id,j.id,j.test_report_id FROM forge.jobs j
            JOIN forge.test_reports r ON r.organization_id=j.organization_id AND
            r.id=j.test_report_id
            WHERE j.kind='test_report' AND r.payload IS NOT NULL AND
              (r.payload_expires_at<=now() OR j.state IN ('canceled','dead')
                OR r.status IN ('completed','failed'))
            ORDER BY j.created_at,j.id FOR UPDATE OF j SKIP LOCKED LIMIT 100
          ), canceled AS (
            UPDATE forge.jobs j SET state=CASE WHEN j.state IN ('queued','running','retry')
                THEN 'canceled' ELSE j.state END,lease_token=NULL,lease_until=NULL,fence=j.fence+1,
                finished_at=coalesce(j.finished_at,now())
            FROM candidates c WHERE j.organization_id=c.organization_id AND j.id=c.id
            RETURNING j.organization_id,j.test_report_id
          ), cleared AS (
            UPDATE forge.test_reports r SET payload=NULL,
              status=CASE WHEN r.status IN ('queued','processing') THEN 'failed' ELSE r.status END,
              error_code=CASE WHEN r.status IN ('queued','processing') THEN
                CASE WHEN r.payload_expires_at<=now() THEN 'payload_expired' ELSE
                'ingestion_canceled' END
                ELSE r.error_code END,processed_at=coalesce(r.processed_at,now())
            FROM canceled c WHERE r.organization_id=c.organization_id AND r.id=c.test_report_id
            RETURNING 1
          ) SELECT count(*) FROM cleared
        $$;
        REVOKE ALL ON FUNCTION forge.clear_test_payloads() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION forge.clear_test_payloads() TO forge_app;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION forge.clear_test_payloads()")
    op.execute("DELETE FROM forge.jobs WHERE kind='test_report'")
    op.execute(
        "ALTER TABLE forge.jobs DROP CONSTRAINT jobs_check,DROP CONSTRAINT jobs_kind_check, "
        "DROP COLUMN test_report_id"
    )
    op.execute("""ALTER TABLE forge.jobs ADD CONSTRAINT jobs_kind_check
        CHECK(kind IN ('sync','webhook','enrichment')),ADD CONSTRAINT jobs_check CHECK(
        (kind='sync' AND sync_run_id IS NOT NULL AND inbox_id IS NULL AND repository_id IS NULL)
        OR(kind='webhook' AND inbox_id IS NOT NULL AND sync_run_id IS NULL AND repository_id IS
        NULL)
        OR(kind='enrichment' AND repository_id IS NOT NULL AND sync_run_id IS NULL AND inbox_id
        IS NULL))""")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE forge.{table}")
