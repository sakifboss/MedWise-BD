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
    stringent_approvals: Mapped[list[str]] = mapped_column(JSON, default=list)
    export_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    export_country_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regulated_market_exports: Mapped[int] = mapped_column(Integer)
    compliance_score: Mapped[float] = mapped_column(Float)
    recall_count: Mapped[int] = mapped_column(Integer)
    recall_data_available: Mapped[bool] = mapped_column(Boolean, default=True)
    market_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    years_active: Mapped[int] = mapped_column(Integer)
    source_urls: Mapped[list[str]] = mapped_column(JSON, default=list)

    @property
    def export_country_total(self) -> int:
        """Number of export countries: the explicit count if given, else the list length."""
        if self.export_country_count is not None:
            return self.export_country_count
        return len(self.export_countries)

    brands: Mapped[list["Brand"]] = relationship(back_populates="manufacturer")
