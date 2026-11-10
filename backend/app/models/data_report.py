from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import RequestsBase

REPORT_REASONS = ("wrong_price", "not_sold", "wrong_manufacturer", "other")


class DataReport(RequestsBase):
    """Someone told us a brand's data looks wrong. Only the brand, a fixed reason and the day:
    no free text, IP address, user agent, cookie or user id.

    Brand ids are reassigned when the seed import rebuilds the tables, so the brand's own details
    (name, manufacturer, strength, form) are saved too: the report still names the right brand.
    Lives in RequestsBase, so the seed import never drops it.
    """

    __tablename__ = "data_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(Integer)
    brand_name: Mapped[str] = mapped_column(String(200))
    manufacturer: Mapped[str] = mapped_column(String(200))
    strength: Mapped[str] = mapped_column(String(50))
    dosage_form: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(String(30))
    reported_on: Mapped[date] = mapped_column(Date, index=True)
