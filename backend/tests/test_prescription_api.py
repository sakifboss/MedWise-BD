from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.prescription import detect_image_type, get_extractor
from app.core.errors import AppError
from app.main import app
from app.services.ocr import ExtractedMedicine

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class FakeOcr:
    """Stands in for Gemini. Tests set `medicines` or `error`; `calls` records requests."""

    def __init__(self) -> None:
        self.medicines: list[ExtractedMedicine] = []
        self.error: Exception | None = None
        self.calls: list[tuple[bytes, str]] = []

    def __call__(self, image: bytes, mime_type: str) -> list[ExtractedMedicine]:
        self.calls.append((image, mime_type))
        if self.error:
            raise self.error
        return self.medicines


@pytest.fixture
def ocr(client: TestClient) -> Iterator[FakeOcr]:
    fake = FakeOcr()
    app.dependency_overrides[get_extractor] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_extractor, None)


def upload(client: TestClient, data: bytes = JPEG, name: str = "rx.jpg", ctype: str = "image/jpeg"):
    return client.post("/api/prescription", files={"image": (name, data, ctype)})


def _data(response: Any) -> dict:
    body = response.json()
    assert response.status_code == 200, body
    return body["data"]


def _item(data: dict, name: str) -> dict:
    return next(i for i in data["items"] if i["extracted_name"] == name)


# ---------------------------------------------------------------- matching


def test_brand_with_matching_strength_is_suggested(client: TestClient, ocr: FakeOcr) -> None:
    ocr.medicines.append(ExtractedMedicine("Pyrolin", "500mg"))
    item = _item(_data(upload(client)), "Pyrolin")
    top = item["options"][item["suggested_index"]]
    assert item["suggested_index"] == 0
    assert (top["kind"], top["name"], top["strength"], top["dosage_form"]) == (
        "brand",
        "Pyrolin",
        "500 mg",
        "tablet",
    )
    assert top["strength_matches"] is True
    assert top["brand_id"] is not None


def test_generic_name_offers_presentations(client: TestClient, ocr: FakeOcr) -> None:
    ocr.medicines.append(ExtractedMedicine("Cefixime", "200 mg"))
    item = _item(_data(upload(client)), "Cefixime")
    top = item["options"][0]
    assert (top["kind"], top["generic_name"], top["strength"]) == ("generic", "Cefixime", "200 mg")
    assert top["brand_id"] is None
    assert item["suggested_index"] == 0


def test_strength_mismatch_is_not_auto_suggested(client: TestClient, ocr: FakeOcr) -> None:
    ocr.medicines.append(ExtractedMedicine("Omezol", "40 mg"))  # only 20 mg exists
    item = _item(_data(upload(client)), "Omezol")
    assert item["options"]
    assert item["suggested_index"] is None
    assert not any(o["strength_matches"] for o in item["options"])


def test_unknown_medicine_has_no_options(client: TestClient, ocr: FakeOcr) -> None:
    ocr.medicines.append(ExtractedMedicine("Qwxzt", None))
    item = _item(_data(upload(client)), "Qwxzt")
    assert item == {**item, "options": [], "suggested_index": None}


def test_empty_prescription(client: TestClient, ocr: FakeOcr) -> None:
    data = _data(upload(client))
    assert data["items"] == []
    assert "does not store" in data["note"]


# ---------------------------------------------------------------- upload validation


def test_image_type_detected_from_bytes_not_header(client: TestClient, ocr: FakeOcr) -> None:
    upload(client, PNG, name="photo.jpg", ctype="image/jpeg")
    assert ocr.calls[-1][1] == "image/png"


def test_rejects_non_image(client: TestClient, ocr: FakeOcr) -> None:
    response = upload(client, b"%PDF-1.7 not an image", name="rx.pdf", ctype="image/jpeg")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file"
    assert ocr.calls == []


def test_rejects_oversized_image(
    client: TestClient, ocr: FakeOcr, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0.001)  # ~1 KB
    response = upload(client, JPEG + b"\x00" * 5000)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_requires_file(client: TestClient, ocr: FakeOcr) -> None:
    response = client.post("/api/prescription")
    assert response.status_code == 422


def test_ocr_errors_use_envelope(client: TestClient, ocr: FakeOcr) -> None:
    ocr.error = AppError(429, "ocr_busy", "Too many prescriptions right now.")
    response = upload(client)
    assert response.status_code == 429
    assert response.json() == {
        "data": None,
        "error": {
            "code": "ocr_busy",
            "message": "Too many prescriptions right now.",
            "details": None,
        },
    }


def test_missing_key_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    response = upload(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ocr_unavailable"


def test_upload_is_not_written_to_disk(
    client: TestClient, ocr: FakeOcr, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    marker = b"UNIQUE-PRESCRIPTION-MARKER"
    upload(client, JPEG + marker)
    assert not any(marker in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (JPEG, "image/jpeg"),
        (PNG, "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"\x00\x00\x00\x18ftypheic", "image/heic"),
        (b"GIF89a", None),
    ],
)
def test_detect_image_type(data: bytes, expected: str | None) -> None:
    assert detect_image_type(data) == expected
