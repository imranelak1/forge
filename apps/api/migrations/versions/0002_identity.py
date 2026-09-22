"""Identity, rotating sessions and tenant-isolated SaaS foundation."""

from alembic import op

revision = "0002_identity"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE forge.users (
            id uuid PRIMARY KEY, name varchar(100) NOT NULL, email varchar(254) NOT NULL UNIQUE,
            password_hash text NOT NULL, email_verified boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE forge.auth_sessions (
            id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES forge.users(id),
            csrf_hash varchar(64) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL, revoked_at timestamptz
        );
        CREATE INDEX auth_sessions_user ON forge.auth_sessions(user_id, id);
        CREATE TABLE forge.refresh_tokens (
            token_hash varchar(64) PRIMARY KEY,
            session_id uuid NOT NULL REFERENCES forge.auth_sessions(id),
            created_at timestamptz NOT NULL DEFAULT now(), used_at timestamptz
        );
        CREATE INDEX refresh_tokens_session ON forge.refresh_tokens(session_id);
        CREATE TABLE forge.identity_tokens (
            token_hash varchar(64) PRIMARY KEY, user_id uuid NOT NULL REFERENCES forge.users(id),
            purpose varchar(16) NOT NULL CHECK (purpose IN ('verify', 'reset')),
            expires_at timestamptz NOT NULL, used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX identity_tokens_user ON forge.identity_tokens(user_id, purpose);
        CREATE TABLE forge.rate_limits (
            key varchar(64) PRIMARY KEY, window_start timestamptz NOT NULL,
            attempts integer NOT NULL CHECK (attempts > 0)
        );
        CREATE TABLE forge.organizations (
            id uuid PRIMARY KEY, name varchar(100) NOT NULL,
            slug varchar(63) NOT NULL UNIQUE, is_demo boolean NOT NULL DEFAULT false,
            created_by uuid NOT NULL REFERENCES forge.users(id),
            created_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz
        );
        CREATE TABLE forge.memberships (
            id uuid NOT NULL, organization_id uuid NOT NULL REFERENCES forge.organizations(id),
            user_id uuid NOT NULL REFERENCES forge.users(id),
            role varchar(16) NOT NULL CHECK (role IN ('viewer','member','admin','owner')),
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id, id), UNIQUE (organization_id, user_id)
        );
        CREATE INDEX memberships_user ON forge.memberships(user_id, organization_id);
        CREATE TABLE forge.invitations (
            id uuid NOT NULL, organization_id uuid NOT NULL REFERENCES forge.organizations(id),
            email varchar(254) NOT NULL, role varchar(16) NOT NULL
                CHECK (role IN ('viewer','member','admin','owner')),
            token_hash varchar(64) NOT NULL UNIQUE, inviter_id uuid,
            expires_at timestamptz NOT NULL, used_at timestamptz, revoked_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id),
            FOREIGN KEY (organization_id,inviter_id)
                REFERENCES forge.memberships(organization_id,id)
                ON DELETE SET NULL (inviter_id)
        );
        CREATE INDEX invitations_email ON forge.invitations(email);
        CREATE TABLE forge.audit_events (
            id uuid NOT NULL, organization_id uuid NOT NULL REFERENCES forge.organizations(id),
            actor_id uuid NOT NULL REFERENCES forge.users(id), subject_id uuid,
            action varchar(80) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (organization_id,id)
        );
        CREATE INDEX audit_events_timeline ON forge.audit_events(organization_id, created_at, id);
        GRANT SELECT, INSERT, UPDATE, DELETE ON forge.users, forge.auth_sessions,
            forge.refresh_tokens, forge.identity_tokens, forge.rate_limits,
            forge.organizations, forge.memberships, forge.invitations TO forge_app;
        GRANT SELECT, INSERT ON forge.audit_events TO forge_app;
    """)
    # Settings are transaction-local. User context is set only after server session validation.
    tenant = "nullif(current_setting('forge.organization_id', true), '')::uuid"
    actor = "nullif(current_setting('forge.user_id', true), '')::uuid"
    for table in ("organizations", "memberships", "invitations", "audit_events"):
        op.execute(f"ALTER TABLE forge.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE forge.{table} FORCE ROW LEVEL SECURITY")
        column = "id" if table == "organizations" else "organization_id"
        op.execute(
            f"CREATE POLICY tenant_access ON forge.{table} "
            f"USING ({column} = {tenant}) WITH CHECK ({column} = {tenant})"
        )
    op.execute(
        "CREATE POLICY discover_memberships ON forge.memberships FOR SELECT "
        f"USING (user_id = {actor})"
    )
    op.execute(
        "CREATE POLICY discover_organizations ON forge.organizations FOR SELECT USING "
        f"(id IN (SELECT organization_id FROM forge.memberships WHERE user_id = {actor}))"
    )
    # Token lookup is bound to the verified user's stored email, never a client email.
    op.execute(
        "CREATE POLICY accept_invitation_lookup ON forge.invitations FOR SELECT USING "
        f"(email = (SELECT email FROM forge.users WHERE id = {actor} AND email_verified))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY discover_organizations ON forge.organizations")
    for table in (
        "audit_events",
        "invitations",
        "memberships",
        "organizations",
        "rate_limits",
        "identity_tokens",
        "refresh_tokens",
        "auth_sessions",
        "users",
    ):
        op.execute(f"DROP TABLE forge.{table}")
