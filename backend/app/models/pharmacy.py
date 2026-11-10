from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Pharmacy(Base):
    """A pharmacy in Sylhet city (OpenStreetMap or a team survey). No stock information."""

    __tablename__ = "pharmacies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    name_bn: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Already filtered by the import: only numbers allowed to be shown are stored.
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source: Mapped[str] = mapped_column(String(10))
    osm_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # OSM ids pass 2^31, so a 64-bit column.
    osm_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_partner: Mapped[bool] = mapped_column(Boolean, default=False)
    partner_since: Mapped[date | None] = mapped_column(Date, nullable=True)


class Area(Base):
    """A named area of Sylhet, for people who do not share their location."""

    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_bn: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
