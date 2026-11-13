from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DosageForm(Base):
    """A dosage form and its route (data/seed/dosage_forms.json)."""

    __tablename__ = "dosage_forms"
    __table_args__ = (
        CheckConstraint("route IN ('systemic', 'local')", name="ck_dosage_form_route"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    route: Mapped[str] = mapped_column(String(10))
