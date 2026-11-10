from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RedFlag(Base):
    """One emergency sign, in the NHS's words. Ticking any of them stops the symptom guide."""

    __tablename__ = "red_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    group: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    text_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(String(300))


class Specialty(Base):
    """A kind of doctor the symptom guide can point to, described by body area, not by disease."""

    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    name_bn: Mapped[str | None] = mapped_column(String(120), nullable=True)
    covers: Mapped[str] = mapped_column(Text)
    covers_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
