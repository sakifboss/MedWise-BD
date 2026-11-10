from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.brand import Brand


class Generic(Base):
    __tablename__ = "generics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    drug_class: Mapped[str] = mapped_column(String(200))
    indications: Mapped[list[str]] = mapped_column(JSON, default=list)
    dosage_forms: Mapped[list[str]] = mapped_column(JSON, default=list)
    side_effects: Mapped[list[str]] = mapped_column(JSON, default=list)
    precautions: Mapped[list[str]] = mapped_column(JSON, default=list)
    how_to_take: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Reviewed Bangla translations; None means "not translated yet, show English".
    drug_class_bn: Mapped[str | None] = mapped_column(String(200), nullable=True)
    indications_bn: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    side_effects_bn: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    precautions_bn: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    how_to_take_bn: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    brands: Mapped[list["Brand"]] = relationship(back_populates="generic")
