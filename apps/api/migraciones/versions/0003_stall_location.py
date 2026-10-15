"""stalls.lat/lng (nullable; si es nulo se usa la del mercado)

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE stalls ADD COLUMN lat double precision, ADD COLUMN lng double precision")


def downgrade() -> None:
    op.execute("ALTER TABLE stalls DROP COLUMN lat, DROP COLUMN lng")
