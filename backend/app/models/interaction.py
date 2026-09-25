from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.generic import Generic

SEVERITIES = ("minor", "moderate", "major")


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (
        UniqueConstraint("generic_a_id", "generic_b_id"),
        # Pairs are stored in id order so each pair exists exactly once.
        CheckConstraint("generic_a_id < generic_b_id", name="ck_interaction_pair_order"),
        CheckConstraint(
            "severity IN ('minor', 'moderate', 'major')", name="ck_interaction_severity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    generic_a_id: Mapped[int] = mapped_column(
        ForeignKey("generics.id", ondelete="CASCADE"), index=True
    )
    generic_b_id: Mapped[int] = mapped_column(
        ForeignKey("generics.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)

    generic_a: Mapped[Generic] = relationship(foreign_keys=[generic_a_id])
    generic_b: Mapped[Generic] = relationship(foreign_keys=[generic_b_id])
