"""Provider identities and single-use browser-bound authorization attempts."""

from alembic import op

revision = "0003_oauth"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE forge.users ALTER COLUMN password_hash DROP NOT NULL;
        CREATE TABLE forge.external_identities (
            provider varchar(16) NOT NULL CHECK (provider IN ('github', 'google')),
            subject varchar(255) NOT NULL,
            user_id uuid NOT NULL REFERENCES forge.users(id),
            email varchar(254) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (provider, subject), UNIQUE (user_id, provider)
        );
        CREATE TABLE forge.oauth_states (
            state_hash varchar(64) PRIMARY KEY,
            browser_hash varchar(64) NOT NULL,
            provider varchar(16) NOT NULL CHECK (provider IN ('github', 'google')),
            intent varchar(8) NOT NULL CHECK (intent IN ('login', 'link')),
            return_to varchar(2048) NOT NULL,
            user_id uuid REFERENCES forge.users(id),
            session_id uuid REFERENCES forge.auth_sessions(id),
            expires_at timestamptz NOT NULL, used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((intent = 'login' AND user_id IS NULL AND session_id IS NULL)
                OR (intent = 'link' AND user_id IS NOT NULL AND session_id IS NOT NULL))
        );
        CREATE INDEX oauth_states_expiry ON forge.oauth_states(expires_at);
        GRANT SELECT, INSERT ON forge.external_identities TO forge_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON forge.oauth_states TO forge_app;
    """)


def downgrade() -> None:
    # Refuse to remove the only sign-in method from accounts created using OAuth.
    # Operators must first arrange passwords or an intentional data migration.
    op.execute("ALTER TABLE forge.users ALTER COLUMN password_hash SET NOT NULL")
    op.execute("DROP TABLE forge.oauth_states")
    op.execute("DROP TABLE forge.external_identities")
