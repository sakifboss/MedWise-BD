from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.brand import Brand


class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    who_gmp: Mapped[bool] = mapped_column(Boolean)
    export_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    regulated_market_exports: Mapped[int] = mapped_column(Integer)
    compliance_score: Mapped[float] = mapped_column(Float)
    recall_count: Mapped[int] = mapped_column(Integer)
    market_share: Mapped[float] = mapped_column(Float)
    years_active: Mapped[int] = mapped_column(Integer)

    brands: Mapped[list["Brand"]] = relationship(back_populates="manufacturer")
