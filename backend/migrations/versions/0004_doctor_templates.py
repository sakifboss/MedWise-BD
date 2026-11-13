"""Doctor templates and favourite tests (R5). Adds a table and a column; nothing else changes.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("doctor_templates"):
        op.create_table(
            "doctor_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "doctor_id",
                sa.Integer(),
                sa.ForeignKey("doctors.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(60), nullable=False),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("tests", sa.Text(), nullable=False),
            sa.Column("advice", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("doctor_id", "name"),
        )
        op.create_index("ix_doctor_templates_doctor_id", "doctor_templates", ["doctor_id"])
    columns = {c["name"] for c in sa.inspect(bind).get_columns("doctors")}
    if "favourite_tests" not in columns:
        with op.batch_alter_table("doctors") as batch:
            batch.add_column(sa.Column("favourite_tests", sa.JSON(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("0004 cannot be downgraded automatically (it would delete templates).")
