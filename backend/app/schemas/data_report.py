from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReportReason = Literal["wrong_price", "not_sold", "wrong_manufacturer", "other"]


class DataReportIn(BaseModel):
    """A fixed reason only; there is no field for free text or anything about the person."""

    model_config = ConfigDict(extra="forbid")

    brand_id: int = Field(gt=0)
    reason: ReportReason


class DataReportSaved(BaseModel):
    saved: bool = True
