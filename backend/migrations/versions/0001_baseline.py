"""Baseline: the request log and data reports, as they were before Alembic.

On the live database both tables already exist with rows: this revision then changes nothing and
only starts recording the migration version. On an empty database it creates them.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _exists("medicine_requests"):
        op.create_table(
            "medicine_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("query", sa.String(80), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("requested_on", sa.Date(), nullable=False),
        )
        op.create_index("ix_medicine_requests_requested_on", "medicine_requests", ["requested_on"])
    if not _exists("data_reports"):
        op.create_table(
            "data_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("brand_id", sa.Integer(), nullable=False),
            sa.Column("brand_name", sa.String(200), nullable=False),
            sa.Column("manufacturer", sa.String(200), nullable=False),
            sa.Column("strength", sa.String(50), nullable=False),
            sa.Column("dosage_form", sa.String(50), nullable=False),
            sa.Column("reason", sa.String(30), nullable=False),
            sa.Column("reported_on", sa.Date(), nullable=False),
        )
        op.create_index("ix_data_reports_reported_on", "data_reports", ["reported_on"])


def downgrade() -> None:
    # Never drop the durable tables automatically (they hold the only copy of these rows).
    raise RuntimeError("The baseline cannot be downgraded; restore a Neon backup branch instead.")
