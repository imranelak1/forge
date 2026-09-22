"""Preserve separate installation histories and index payload retention work."""

from alembic import op

revision = "0005_github_access"
down_revision = "0004_github"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE forge.repositories
            DROP CONSTRAINT repositories_organization_id_provider_id_key;
        ALTER TABLE forge.repositories ADD CONSTRAINT repositories_integration_provider_unique
            UNIQUE (organization_id,integration_id,provider_id);
        CREATE INDEX webhook_inbox_retention ON forge.webhook_inbox
            (organization_id,processed_at,id)
            WHERE status='processed' AND payload<>'{}'::jsonb;
    """)


def downgrade() -> None:
    # Refuse contraction if reinstallations created multiple histories; never delete data.
    op.execute("""
        ALTER TABLE forge.repositories ADD CONSTRAINT repositories_organization_id_provider_id_key
            UNIQUE (organization_id,provider_id);
        ALTER TABLE forge.repositories DROP CONSTRAINT repositories_integration_provider_unique;
        DROP INDEX forge.webhook_inbox_retention;
    """)
