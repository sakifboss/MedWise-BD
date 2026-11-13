import base64
import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.llm import output_text
from app.services.ocr import ExtractedMedicine, VisionExtractor, parse_medicines

IMAGE = b"\xff\xd8\xff fake jpeg bytes"


def openai_reply(payload: object) -> dict:
    """A Responses API answer with one message holding the JSON text."""
    return {
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps(payload)}],
            },
        ],
    }


def make_extractor(
    handler: object, **settings: object
) -> tuple[VisionExtractor, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator]

    config = Settings(
        openai_api_key="test-key",
        openai_model="main-model",
        openai_fallback_models="backup-model",
        **settings,  # type: ignore[arg-type]
    )
    client = httpx.Client(transport=httpx.MockTransport(record))
    return VisionExtractor(config, client), seen


def model_of(request: httpx.Request) -> str:
    return json.loads(request.content)["model"]


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


# ---------------------------------------------------------------- OpenAI calls


def test_request_sends_image_with_strict_schema_and_no_storage() -> None:
    extractor, seen = make_extractor(
        lambda r: httpx.Response(200, json=openai_reply({"medicines": []}))
    )
    extractor(IMAGE, "image/jpeg")

    request = seen[0]
    assert str(request.url) == "https://api.openai.com/v1/responses"
    assert request.headers["authorization"] == "Bearer test-key"
    assert "key" not in str(request.url)  # the key never goes in the URL (it could reach logs)
    body = json.loads(request.content)
    assert body["model"] == "main-model"
    assert body["store"] is False  # OpenAI keeps no copy of the response for later retrieval
    image = body["input"][0]["content"][1]
    data = base64.b64encode(IMAGE).decode()
    assert image == {
        "type": "input_image",
        "image_url": f"data:image/jpeg;base64,{data}",
        "detail": "high",
    }
    fmt = body["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    item = fmt["schema"]["properties"]["medicines"]["items"]
    assert set(item["properties"]) == {"name", "strength"}  # no field for doses or advice
    assert item["additionalProperties"] is False
    assert "Do NOT return dosage" in body["instructions"]


def test_successful_extraction() -> None:
    reply = openai_reply({"medicines": [{"name": "Pyrolin", "strength": "500 mg"}]})
    extractor, _ = make_extractor(lambda r: httpx.Response(200, json=reply))
    assert extractor.last_model is None
    assert extractor(IMAGE, "image/jpeg") == [ExtractedMedicine("Pyrolin", "500 mg")]
    assert extractor.last_model == "main-model"


def test_falls_back_to_next_model_when_overloaded() -> None:
    reply = openai_reply({"medicines": [{"name": "Omezol", "strength": "20 mg"}]})

    def handler(request: httpx.Request) -> httpx.Response:
        if model_of(request) == "main-model":
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json=reply)

    extractor, seen = make_extractor(handler)
    assert extractor(IMAGE, "image/png") == [ExtractedMedicine("Omezol", "20 mg")]
    assert [model_of(r) for r in seen] == ["main-model", "backup-model"]
    assert extractor.last_model == "backup-model"


@pytest.mark.parametrize(
    ("status", "code", "calls"),
    [
        (503, "ocr_unavailable", 2),  # all models overloaded
        (429, "ocr_busy", 2),
        (401, "ocr_unavailable", 1),  # bad key: no point trying other models
        (400, "ocr_failed", 1),
    ],
)
def test_api_errors(status: int, code: str, calls: int) -> None:
    extractor, seen = make_extractor(lambda r: httpx.Response(status, json={"error": {}}))
    with pytest.raises(AppError) as exc:
        extractor(IMAGE, "image/jpeg")
    assert exc.value.code == code
    assert len(seen) == calls


REFUSED = {
    "status": "completed",
    "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}],
}
INCOMPLETE = {
    "status": "incomplete",
    "incomplete_details": {"reason": "max_output_tokens"},
    "output": [],
}


@pytest.mark.parametrize("payload", [REFUSED, INCOMPLETE, {"status": "completed", "output": []}])
def test_refused_incomplete_or_empty_answers(payload: dict) -> None:
    extractor, _ = make_extractor(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(AppError) as exc:
        extractor(IMAGE, "image/jpeg")
    assert exc.value.code == "ocr_failed"


def test_output_text_joins_message_parts_and_skips_other_items() -> None:
    parts = [{"type": "output_text", "text": '{"a":'}, {"type": "output_text", "text": "1}"}]
    payload = {
        "status": "completed",
        "output": [{"type": "reasoning"}, {"type": "message", "content": parts}],
    }
    assert output_text(payload) == '{"a":1}'


def test_network_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    extractor, _ = make_extractor(fail)
    with pytest.raises(AppError) as exc:
        extractor(IMAGE, "image/jpeg")
    assert exc.value.code == "ocr_unavailable"


def test_missing_api_key() -> None:
    with pytest.raises(AppError) as exc:
        VisionExtractor(Settings(openai_api_key=""))
    assert exc.value.status == 503


def test_falls_back_to_next_model_after_timeout() -> None:
    reply = openai_reply({"medicines": [{"name": "Montiva", "strength": "10 mg"}]})

    def handler(request: httpx.Request) -> httpx.Response:
        if model_of(request) == "main-model":
            raise httpx.ReadTimeout("hung")
        return httpx.Response(200, json=reply)

    extractor, seen = make_extractor(handler)
    assert extractor(IMAGE, "image/jpeg") == [ExtractedMedicine("Montiva", "10 mg")]
    assert len(seen) == 2


def test_reasoning_effort_is_optional() -> None:
    extractor, seen = make_extractor(
        lambda r: httpx.Response(200, json=openai_reply({"medicines": []})),
        openai_reasoning_effort="",
    )
    extractor(IMAGE, "image/jpeg")
    assert "reasoning" not in json.loads(seen[0].content)


@pytest.mark.parametrize("pasted", ["  abc123\n", '"abc123"', "'abc123'"])
def test_api_key_is_cleaned(pasted: str) -> None:
    assert Settings(openai_api_key=pasted).openai_api_key == "abc123"
