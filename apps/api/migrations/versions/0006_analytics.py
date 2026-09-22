"""Repository-scoped engineering evidence and durable enrichment coverage."""

from alembic import op

revision = "0006_analytics"
down_revision = "0005_github_access"
branch_labels = None
depends_on = None

TABLES = (
    "pull_request_reviews",
    "pull_request_transitions",
    "pull_request_commits",
    "commit_files",
    "issues",
    "issue_pull_requests",
)
COVERAGE = {
    "repositories": ("issues",),
    "pull_requests": ("reviews", "transitions", "commits", "issues"),
    "commits": ("files",),
    "issues": ("links",),
}


def upgrade() -> None:
    op.execute("""
        ALTER TABLE forge.repositories ADD COLUMN is_demo boolean NOT NULL DEFAULT false;
        ALTER TABLE forge.pull_requests
            ADD COLUMN author_type varchar(30),
            ADD COLUMN merge_commit_sha varchar(40)
                CHECK (merge_commit_sha IS NULL OR merge_commit_sha ~ '^[a-f0-9]{40}$'),
            ADD COLUMN provider_commit_count integer CHECK (provider_commit_count>=0),
            ADD CONSTRAINT pull_requests_repository_identity
                UNIQUE (organization_id,repository_id,id);
        ALTER TABLE forge.commits
            ADD COLUMN additions integer CHECK (additions>=0),
            ADD COLUMN deletions integer CHECK (deletions>=0),
            ADD COLUMN total_changes integer CHECK (total_changes>=0),
            ADD CONSTRAINT commits_repository_identity UNIQUE (organization_id,repository_id,id);
        CREATE TABLE forge.pull_request_reviews (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            pull_request_id uuid NOT NULL, provider_id bigint NOT NULL CHECK (provider_id>0),
            reviewer_login varchar(100), reviewer_type varchar(30),
            state varchar(30) NOT NULL CHECK
                (state IN ('PENDING','COMMENTED','APPROVED','CHANGES_REQUESTED','DISMISSED')),
            original_state varchar(30) CHECK
                (original_state IN ('COMMENTED','APPROVED','CHANGES_REQUESTED')),
            submitted_at timestamptz, approved_at timestamptz, dismissed_at timestamptz,
            html_url text NOT NULL, observed_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,pull_request_id,provider_id),
            FOREIGN KEY (organization_id,repository_id,pull_request_id)
                REFERENCES forge.pull_requests(organization_id,repository_id,id)
        );
        CREATE TABLE forge.pull_request_transitions (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            pull_request_id uuid NOT NULL, provider_id bigint, source_key text NOT NULL,
            kind varchar(40) NOT NULL, occurred_at timestamptz NOT NULL,
            actor_login varchar(100), actor_type varchar(30), html_url text NOT NULL,
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,pull_request_id,source_key),
            FOREIGN KEY (organization_id,repository_id,pull_request_id)
                REFERENCES forge.pull_requests(organization_id,repository_id,id)
        );
        CREATE TABLE forge.pull_request_commits (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            pull_request_id uuid NOT NULL, commit_id uuid NOT NULL,
            relationship varchar(16) NOT NULL CHECK (relationship IN ('head','merge')),
            html_url text NOT NULL, PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,pull_request_id,commit_id,relationship),
            FOREIGN KEY (organization_id,repository_id,pull_request_id)
                REFERENCES forge.pull_requests(organization_id,repository_id,id),
            FOREIGN KEY (organization_id,repository_id,commit_id)
                REFERENCES forge.commits(organization_id,repository_id,id)
        );
        CREATE TABLE forge.commit_files (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            commit_id uuid NOT NULL, filename text NOT NULL, previous_filename text,
            status varchar(30) NOT NULL, additions integer CHECK (additions>=0),
            deletions integer CHECK (deletions>=0), changes integer CHECK (changes>=0),
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,commit_id,filename),
            FOREIGN KEY (organization_id,repository_id,commit_id)
                REFERENCES forge.commits(organization_id,repository_id,id)
        );
        CREATE TABLE forge.issues (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            provider_id bigint NOT NULL CHECK (provider_id>0), number integer NOT NULL
                CHECK (number>0), title text NOT NULL,
            state varchar(8) NOT NULL CHECK (state IN ('open','closed')),
            author_login varchar(100), author_type varchar(30), opened_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL, closed_at timestamptz, html_url text NOT NULL,
            PRIMARY KEY (organization_id,id), UNIQUE (organization_id,repository_id,id),
            UNIQUE (organization_id,repository_id,number),
            FOREIGN KEY (organization_id,repository_id)
                REFERENCES forge.repositories(organization_id,id)
        );
        CREATE TABLE forge.issue_pull_requests (
            organization_id uuid NOT NULL, id uuid NOT NULL, repository_id uuid NOT NULL,
            issue_id uuid NOT NULL, pull_request_id uuid NOT NULL,
            relationship varchar(16) NOT NULL CHECK (relationship='references'),
            source_key text NOT NULL, occurred_at timestamptz NOT NULL, html_url text NOT NULL,
            PRIMARY KEY (organization_id,id),
            UNIQUE (organization_id,issue_id,pull_request_id,source_key),
            FOREIGN KEY (organization_id,repository_id,pull_request_id)
                REFERENCES forge.pull_requests(organization_id,repository_id,id),
            FOREIGN KEY (organization_id,repository_id,issue_id)
                REFERENCES forge.issues(organization_id,repository_id,id)
        );
        ALTER TABLE forge.jobs DROP CONSTRAINT jobs_kind_check, DROP CONSTRAINT jobs_check;
        ALTER TABLE forge.jobs ADD COLUMN repository_id uuid,
            ADD CONSTRAINT jobs_repository_fk
                FOREIGN KEY (organization_id,repository_id,integration_id)
                REFERENCES forge.repositories(organization_id,id,integration_id),
            ADD CONSTRAINT jobs_kind_check CHECK (kind IN ('sync','webhook','enrichment')),
            ADD CONSTRAINT jobs_check CHECK (
                (kind='sync' AND sync_run_id IS NOT NULL
                    AND inbox_id IS NULL AND repository_id IS NULL)
                OR (kind='webhook' AND inbox_id IS NOT NULL
                    AND sync_run_id IS NULL AND repository_id IS NULL)
                OR (kind='enrichment' AND repository_id IS NOT NULL
                    AND sync_run_id IS NULL AND inbox_id IS NULL)
            );
        CREATE INDEX jobs_repository ON forge.jobs (organization_id,repository_id)
            WHERE repository_id IS NOT NULL;
        CREATE INDEX pull_requests_merged ON forge.pull_requests
            (organization_id,repository_id,merged_at,id) WHERE merged_at IS NOT NULL;
        CREATE INDEX pull_requests_opened ON forge.pull_requests
            (organization_id,opened_at,id);
        CREATE INDEX commits_committed ON forge.commits
            (organization_id,committed_at,id);
        CREATE INDEX reviews_submitted ON forge.pull_request_reviews
            (organization_id,pull_request_id,submitted_at,id);
        CREATE INDEX transitions_occurred ON forge.pull_request_transitions
            (organization_id,pull_request_id,occurred_at,id);
        CREATE INDEX pr_commits_commit ON forge.pull_request_commits
            (organization_id,commit_id,id);
        CREATE INDEX issue_links_pr ON forge.issue_pull_requests
            (organization_id,pull_request_id,id);
    """)
    for table, prefixes in COVERAGE.items():
        for prefix in prefixes:
            op.execute(f"""ALTER TABLE forge.{table}
                ADD COLUMN {prefix}_status varchar(16) NOT NULL DEFAULT 'pending'
                    CHECK ({prefix}_status IN
                        ('pending','partial','complete','failed','unavailable')),
                ADD COLUMN {prefix}_error varchar(80),
                ADD COLUMN {prefix}_synced_at timestamptz""")
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
    op.execute("DELETE FROM forge.jobs WHERE kind='enrichment'")
    op.execute("ALTER TABLE forge.jobs DROP CONSTRAINT jobs_check, DROP CONSTRAINT jobs_kind_check")
    op.execute("""ALTER TABLE forge.jobs DROP COLUMN repository_id,
        ADD CONSTRAINT jobs_kind_check CHECK (kind IN ('sync','webhook')),
        ADD CONSTRAINT jobs_check CHECK (
            (kind='sync' AND sync_run_id IS NOT NULL AND inbox_id IS NULL)
            OR (kind='webhook' AND inbox_id IS NOT NULL AND sync_run_id IS NULL))""")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE forge.{table}")
    for table, prefixes in COVERAGE.items():
        if table == "issues":
            continue
        for prefix in prefixes:
            for suffix in ("status", "error", "synced_at"):
                op.execute(f"ALTER TABLE forge.{table} DROP COLUMN {prefix}_{suffix}")
    op.execute("ALTER TABLE forge.repositories DROP COLUMN is_demo")
    op.execute("ALTER TABLE forge.pull_requests DROP CONSTRAINT pull_requests_repository_identity")
    op.execute("ALTER TABLE forge.commits DROP CONSTRAINT commits_repository_identity")
    op.execute(
        "ALTER TABLE forge.pull_requests DROP COLUMN author_type, "
        "DROP COLUMN merge_commit_sha, DROP COLUMN provider_commit_count"
    )
    op.execute(
        "ALTER TABLE forge.commits DROP COLUMN additions, "
        "DROP COLUMN deletions, DROP COLUMN total_changes"
    )
    for name in ("pull_requests_merged", "pull_requests_opened", "commits_committed"):
        op.execute(f"DROP INDEX forge.{name}")
