import base64
import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.ocr import ExtractedMedicine, GeminiExtractor, parse_medicines

IMAGE = b"\xff\xd8\xff fake jpeg bytes"


def gemini_reply(payload: object) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


def make_extractor(
    handler: object, **settings: object
) -> tuple[GeminiExtractor, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator]

    config = Settings(
        gemini_api_key="test-key",
        gemini_model="main-model",
        gemini_fallback_models="backup-model",
        **settings,  # type: ignore[arg-type]
    )
    client = httpx.Client(transport=httpx.MockTransport(record))
    return GeminiExtractor(config, client), seen


# ---------------------------------------------------------------- parsing


def test_parse_keeps_only_name_and_strength() -> None:
    text = json.dumps(
        {
            "medicines": [
                {
                    "name": " Pyrolin ",
                    "strength": "500 mg",
                    "dose": "1+0+1",
                    "advice": "after meal",
                },
                {"name": "Omezol", "strength": None},
            ],
            "diagnosis": "fever",
        }
    )
    assert parse_medicines(text) == [
        ExtractedMedicine("Pyrolin", "500 mg"),
        ExtractedMedicine("Omezol", None),
    ]


def test_parse_drops_invalid_and_duplicate_rows() -> None:
    text = json.dumps(
        {
            "medicines": [
                {"name": ""},
                {"strength": "5 mg"},
                {"name": "x" * 500},
                {"name": "Napa", "strength": "500 mg"},
                {"name": "napa", "strength": "500 MG"},
                {"name": "Napa", "strength": ""},
            ]
        }
    )
    assert parse_medicines(text) == [
        ExtractedMedicine("Napa", "500 mg"),
        ExtractedMedicine("Napa", None),
    ]


def test_parse_caps_number_of_medicines() -> None:
    text = json.dumps({"medicines": [{"name": f"Med{i}"} for i in range(50)]})
    assert len(parse_medicines(text)) == 20


@pytest.mark.parametrize("text", ["not json", "[]", '{"medicines": "Napa"}'])
def test_parse_rejects_malformed_output(text: str) -> None:
    with pytest.raises(AppError) as exc:
        parse_medicines(text)
    assert exc.value.code == "ocr_failed"


# ---------------------------------------------------------------- Gemini calls


def test_request_sends_image_inline_with_schema() -> None:
    extractor, seen = make_extractor(
        lambda r: httpx.Response(200, json=gemini_reply({"medicines": []}))
    )
    extractor(IMAGE, "image/jpeg")

    request = seen[0]
    assert request.url.path.endswith("/models/main-model:generateContent")
    assert request.headers["x-goog-api-key"] == "test-key"
    assert "key=" not in str(request.url)  # key never in the URL (it could end up in logs)
    body = json.loads(request.content)
    inline = body["contents"][0]["parts"][0]["inline_data"]
    assert inline == {"mime_type": "image/jpeg", "data": base64.b64encode(IMAGE).decode()}
    schema = body["generationConfig"]["responseSchema"]["properties"]["medicines"]["items"]
    assert set(schema["properties"]) == {"name", "strength"}


def test_successful_extraction() -> None:
    reply = gemini_reply({"medicines": [{"name": "Pyrolin", "strength": "500 mg"}]})
    extractor, _ = make_extractor(lambda r: httpx.Response(200, json=reply))
    assert extractor.last_model is None
    assert extractor(IMAGE, "image/jpeg") == [ExtractedMedicine("Pyrolin", "500 mg")]
    assert extractor.last_model == "main-model"


def test_falls_back_to_next_model_when_overloaded() -> None:
    reply = gemini_reply({"medicines": [{"name": "Omezol", "strength": "20 mg"}]})

    def handler(request: httpx.Request) -> httpx.Response:
        if "main-model" in request.url.path:
            return httpx.Response(503, json={"error": {"message": "high demand"}})
        return httpx.Response(200, json=reply)

    extractor, seen = make_extractor(handler)
    assert extractor(IMAGE, "image/png") == [ExtractedMedicine("Omezol", "20 mg")]
    assert [r.url.path.split("/")[-1] for r in seen] == [
        "main-model:generateContent",
        "backup-model:generateContent",
    ]
    assert extractor.last_model == "backup-model"


@pytest.mark.parametrize(
    ("status", "code", "calls"),
    [
        (503, "ocr_unavailable", 2),  # all models overloaded
        (429, "ocr_busy", 2),
        (403, "ocr_unavailable", 1),  # bad key: no point trying other models
        (400, "ocr_failed", 1),
    ],
)
def test_api_errors(status: int, code: str, calls: int) -> None:
    extractor, seen = make_extractor(lambda r: httpx.Response(status, json={"error": {}}))
    with pytest.raises(AppError) as exc:
        extractor(IMAGE, "image/jpeg")
    assert exc.value.code == code
    assert len(seen) == calls


def test_blocked_response_without_candidates() -> None:
    blocked = {"promptFeedback": {"blockReason": "SAFETY"}}
    extractor, _ = make_extractor(lambda r: httpx.Response(200, json=blocked))
    with pytest.raises(AppError) as exc:
        extractor(IMAGE, "image/jpeg")
    assert exc.value.code == "ocr_failed"


def test_network_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    extractor, _ = make_extractor(fail)
    with pytest.raises(AppError) as exc:
        extractor(IMAGE, "image/jpeg")
    assert exc.value.code == "ocr_unavailable"


def test_missing_api_key() -> None:
    with pytest.raises(AppError) as exc:
        GeminiExtractor(Settings(gemini_api_key=""))
    assert exc.value.status == 503


def test_falls_back_to_next_model_after_timeout() -> None:
    reply = gemini_reply({"medicines": [{"name": "Montiva", "strength": "10 mg"}]})

    def handler(request: httpx.Request) -> httpx.Response:
        if "main-model" in request.url.path:
            raise httpx.ReadTimeout("hung")
        return httpx.Response(200, json=reply)

    extractor, seen = make_extractor(handler)
    assert extractor(IMAGE, "image/jpeg") == [ExtractedMedicine("Montiva", "10 mg")]
    assert len(seen) == 2


@pytest.mark.parametrize("pasted", ["  abc123\n", '"abc123"', "'abc123'"])
def test_api_key_is_cleaned(pasted: str) -> None:
    assert Settings(gemini_api_key=pasted).gemini_api_key == "abc123"
