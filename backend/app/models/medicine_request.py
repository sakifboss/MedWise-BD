from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import RequestsBase

QUERY_MAX_LENGTH = 80
REQUEST_SOURCES = ("search", "prescription")


class MedicineRequest(RequestsBase):
    """A medicine someone asked us to add. Only the text, where it came from and the day:
    no IP address, user agent, cookie or user id."""

    __tablename__ = "medicine_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(QUERY_MAX_LENGTH))
    source: Mapped[str] = mapped_column(String(20))
    requested_on: Mapped[date] = mapped_column(Date, index=True)
