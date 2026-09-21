"""Create the operational namespace; tenant entities start in Phase 2."""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA forge AUTHORIZATION CURRENT_USER")
    op.execute("REVOKE ALL ON SCHEMA forge FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA forge TO forge_app")


def downgrade() -> None:
    # RESTRICT is intentional: never destroy later tables with CASCADE.
    op.execute("DROP SCHEMA forge RESTRICT")
