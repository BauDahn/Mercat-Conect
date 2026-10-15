"""app_settings: ajustes persistentes (barandillas municipales)

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE app_settings (key text PRIMARY KEY, value jsonb NOT NULL, updated_at timestamptz)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_settings")
