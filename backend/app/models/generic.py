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

    brands: Mapped[list["Brand"]] = relationship(back_populates="generic")
