from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.generic import Generic
from app.models.manufacturer import Manufacturer


class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("name", "manufacturer_id", "strength", "dosage_form"),
        # Ranking compares brands sharing generic + strength + dosage form.
        Index("ix_brands_comparable", "generic_id", "strength", "dosage_form"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    generic_id: Mapped[int] = mapped_column(ForeignKey("generics.id", ondelete="CASCADE"))
    manufacturer_id: Mapped[int] = mapped_column(ForeignKey("manufacturers.id", ondelete="CASCADE"))
    strength: Mapped[str] = mapped_column(String(50))
    dosage_form: Mapped[str] = mapped_column(String(50))
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    generic: Mapped[Generic] = relationship(back_populates="brands")
    manufacturer: Mapped[Manufacturer] = relationship(back_populates="brands")
