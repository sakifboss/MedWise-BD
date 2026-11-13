from datetime import date

from pydantic import BaseModel


class BrandIndexItem(BaseModel):
    code: str  # stable across deploys
    id: int  # this deploy's database id (only to migrate old saved lists on the device)
    name: str
    generic_id: int
    generic: str
    strength: str
    dosage_form: str
    manufacturer: str
    price_per_unit: float
    price_checked_on: date | None
    rank: int  # in its compared group (same generic, strength and dosage form)
    group_size: int
    approvals: int  # stringent regulators that approved a plant of the manufacturer (0-4)


class BrandIndex(BaseModel):
    brands: list[BrandIndexItem]
