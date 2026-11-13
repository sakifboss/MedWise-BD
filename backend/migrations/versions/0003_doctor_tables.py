"""Doctor accounts (R2): doctors, chambers, sessions and password-reset tokens.

New tables only; the request log and data reports are not touched.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _doctor_fk() -> sa.Column:
    return sa.Column(
        "doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    if not _exists("doctors"):
        op.create_table(
            "doctors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(254), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(120), nullable=False),
            sa.Column("display_name_bn", sa.String(120), nullable=True),
            sa.Column("degrees", sa.String(200), nullable=False),
            sa.Column("specialty", sa.String(120), nullable=False),
            sa.Column("bmdc_number", sa.String(20), nullable=False),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("rejection_reason", sa.String(300), nullable=True),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column("verified_by", sa.String(10), nullable=True),
            sa.Column("verify_method", sa.String(200), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_login_day", sa.Date(), nullable=True),
            sa.CheckConstraint(
                "status IN ('pending', 'verified', 'rejected')", name="ck_doctor_status"
            ),
        )
    if not _exists("doctor_chambers"):
        op.create_table(
            "doctor_chambers",
            sa.Column("id", sa.Integer(), primary_key=True),
            _doctor_fk(),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("address", sa.String(300), nullable=False),
            sa.Column("hours", sa.String(200), nullable=False),
            sa.Column("phone", sa.String(20), nullable=True),
        )
        op.create_index("ix_doctor_chambers_doctor_id", "doctor_chambers", ["doctor_id"])
    if not _exists("doctor_sessions"):
        op.create_table(
            "doctor_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            _doctor_fk(),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_doctor_sessions_doctor_id", "doctor_sessions", ["doctor_id"])
    if not _exists("doctor_password_resets"):
        op.create_table(
            "doctor_password_resets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            _doctor_fk(),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_doctor_password_resets_doctor_id", "doctor_password_resets", ["doctor_id"]
        )


def downgrade() -> None:
    # Dropping these would delete doctor accounts; restore a Neon backup branch instead.
    raise RuntimeError("0003 cannot be downgraded automatically (it would delete doctor accounts).")
