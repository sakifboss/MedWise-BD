"""Data reports also store the stable brand code (R1). Existing rows keep NULL.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("data_reports")}
    if "brand_code" not in columns:
        with op.batch_alter_table("data_reports") as batch:
            batch.add_column(sa.Column("brand_code", sa.String(7), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("data_reports") as batch:
        batch.drop_column("brand_code")
