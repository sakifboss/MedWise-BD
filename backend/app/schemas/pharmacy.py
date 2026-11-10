from pydantic import BaseModel


class PharmacyOut(BaseModel):
    id: int
    name: str
    name_bn: str | None
    lat: float
    lon: float
    address: str | None
    # Only numbers that may be shown (OSM, or a partner who agreed); never hidden ones.
    phone: str | None
    # The number comes from OpenStreetMap and may be out of date.
    phone_from_osm: bool
    is_partner: bool


class AreaOut(BaseModel):
    id: int
    name: str
    name_bn: str | None
    lat: float
    lon: float


class PharmaciesResponse(BaseModel):
    city: str
    # south, west, north, east: distances are only meaningful inside this box.
    bbox: tuple[float, float, float, float]
    pharmacies: list[PharmacyOut]
    areas: list[AreaOut]
