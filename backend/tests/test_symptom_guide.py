"""P10 symptom guide: strict model answers, fallbacks, safety checks, rules, the API and privacy."""

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import symptom_guide as api
from app.core.config import get_settings
from app.main import app
from app.schemas.symptom_guide import SymptomGuideIn
from app.services.gemini import GeminiUnavailable
from app.services.symptom_guide import load_words, request_body, run_guide

SECRET = "symptom-test-secret"
SPECIALTIES = {
    "general_medicine": "Adults, general problems",
    "paediatrics": "Children",
    "obstetrics_gynaecology": "Pregnancy",
    "dermatology": "Skin, hair and nails",
    "cardiology": "Heart",
}
CATALOG = ["Napa", "Seclo", "Paracetamol", "Max Pro", "Fast", "Montair"]
WORDS = load_words(get_settings().symptom_words_path)
SECRET_TEXT = "itchy red patches on both elbows zq7"  # marker to look for in logs


def answers(**changes: Any) -> SymptomGuideIn:
    base = {
        "text": "Itchy red patches on both elbows",
        "since": "weeks",
        "severity": "mild",
        "age_group": "adult",
        "pregnant": "no",
    }
    return SymptomGuideIn(**{**base, **changes})


def model(**changes: Any) -> str:
    """A model answer (JSON text); `note` changes merge into the note."""
    note = {
        "main_problem": "Itchy red patches on both elbows",
        "duration": "About two weeks",
        "other_symptoms": ["Dry skin"],
        **changes.pop("note", {}),
    }
    return json.dumps(
        {"specialty": "dermatology", "red_flag_suspected": False, "note": note, **changes}
    )


def guide(reply: str | Exception | None, **answer_changes: Any):
    def generate(body: dict) -> str:
        if isinstance(reply, Exception):
            raise reply
        return reply  # type: ignore[return-value]

    return run_guide(
        answers(**answer_changes),
        SPECIALTIES,
        CATALOG,
        WORDS,
        None if reply is None else generate,
    )


# ---------------------------------------------------------------- the model's answer


def test_a_valid_answer_is_used() -> None:
    r = guide(model())
    assert (r.emergency, r.specialty, r.note_written_by, r.reason) == (
        False,
        "dermatology",
        "ai",
        "ok",
    )
    assert r.note.main_problem == "Itchy red patches on both elbows"
    assert r.note.other_symptoms == ["Dry skin"]


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ("not json at all", "invalid_answer"),
        (model(diagnosis="eczema"), "invalid_answer"),  # extra key
        (model(note={"advice": "rest"}), "invalid_answer"),  # extra key in the note
        (model(note={"main_problem": "x" * 121}), "invalid_answer"),  # too long
        (model(note={"other_symptoms": ["a"] * 9}), "invalid_answer"),  # too many
        (model(red_flag_suspected="false"), "invalid_answer"),  # not a real boolean
        (model(specialty="oncology"), "unknown_specialty"),
        (GeminiUnavailable(503, []), "ai_unavailable"),
        (None, "ai_unavailable"),  # no key configured
    ],
)
def test_bad_answers_use_the_fallback(reply: Any, reason: str) -> None:
    r = guide(reply)
    assert r.reason == reason
    assert (r.emergency, r.specialty, r.note_written_by) == (False, "general_medicine", "answers")
    assert r.note.main_problem == "Itchy red patches on both elbows"  # the person's own words
    assert r.note.duration == "1 to 4 weeks"
    assert r.note.other_symptoms == []


@pytest.mark.parametrize(
    ("note", "reason"),
    [
        ({"other_symptoms": ["Took Napa yesterday"]}, "medicine_name"),
        ({"main_problem": "Has been taking paracetamol"}, "medicine_name"),
        ({"main_problem": "নাপা খেয়েছেন"}, "medicine_name"),  # Bangla script
        ({"other_symptoms": ["Uses max pro"]}, "medicine_name"),  # two-word brand
        ({"other_symptoms": ["500 mg at night"]}, "dose"),
        ({"other_symptoms": ["two tablets twice a day"]}, "dose"),
        ({"duration": "1+0+1 for a week"}, "dose"),
        ({"main_problem": "দিনে ৩ বার মাথাব্যথা"}, "dose"),
        ({"main_problem": "Probably eczema"}, "diagnosis_word"),
        ({"main_problem": "Looks like a skin infection"}, "diagnosis_word"),
        ({"main_problem": "ডেঙ্গু মনে হচ্ছে"}, "diagnosis_word"),
    ],
)
def test_a_note_with_a_medicine_dose_or_diagnosis_is_dropped(note: dict, reason: str) -> None:
    r = guide(model(note=note))
    assert r.reason == reason
    assert r.note_written_by == "answers"
    assert r.specialty == "dermatology"  # the specialty itself was valid


def test_everyday_words_are_not_mistaken_for_medicines() -> None:
    note = {"main_problem": "Heart beating fast when climbing stairs", "other_symptoms": []}
    r = guide(model(specialty="cardiology", note=note))
    assert (r.reason, r.note_written_by) == ("ok", "ai")


# ---------------------------------------------------------------- warnings and fixed rules


def test_the_model_can_add_a_warning() -> None:
    r = guide(model(red_flag_suspected=True))
    assert r.emergency and r.specialty is None and r.note is None


def test_a_warning_counts_even_in_an_invalid_answer() -> None:
    assert guide(model(red_flag_suspected=True, extra="x")).emergency
    assert guide(model(red_flag_suspected=True, specialty="unknown")).emergency


def test_children_go_to_paediatrics_whatever_the_model_says() -> None:
    r = guide(model(specialty="dermatology"), age_group="child", pregnant="not_applicable")
    assert (r.specialty, r.rule) == ("paediatrics", "child")
    assert guide("not json", age_group="child").specialty == "paediatrics"


def test_pregnancy_goes_to_obstetrics_whatever_the_model_says() -> None:
    r = guide(model(specialty="dermatology"), pregnant="yes")
    assert (r.specialty, r.rule) == ("obstetrics_gynaecology", "pregnant")
    # The child rule comes first (the form hides the pregnancy question for children).
    assert guide(model(), age_group="child", pregnant="yes").specialty == "paediatrics"


def test_a_rule_never_hides_a_warning() -> None:
    r = guide(model(red_flag_suspected=True), age_group="child")
    assert r.emergency and r.specialty is None


def test_the_model_gets_only_the_answers_and_the_rules() -> None:
    body = request_body(answers(lang="bn"), SPECIALTIES)
    prompt = body["systemInstruction"]["parts"][0]["text"]
    sent = json.loads(body["contents"][0]["parts"][0]["text"])
    assert set(sent) == {"what they wrote", "since when", "how bad", "age group", "pregnant"}
    assert "Do NOT diagnose" in prompt and "Do NOT name any medicine" in prompt
    assert all(f"- {key}:" in prompt for key in SPECIALTIES)
    assert "Write the note in Bangla." in prompt
    assert body["generationConfig"]["responseMimeType"] == "application/json"


# ---------------------------------------------------------------- API


class FakeModel:
    def __init__(self) -> None:
        self.reply = model()
        self.calls = 0

    def __call__(self, body: dict) -> str:
        self.calls += 1
        return self.reply


@pytest.fixture
def fake(client: TestClient) -> Iterator[FakeModel]:
    fake_model = FakeModel()
    app.dependency_overrides[api.get_generator] = lambda: fake_model
    try:
        yield fake_model
    finally:
        app.dependency_overrides.pop(api.get_generator, None)


@pytest.fixture
def locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "frontend_shared_secret", SECRET)


BODY = {
    "text": SECRET_TEXT,
    "since": "weeks",
    "severity": "mild",
    "age_group": "adult",
    "pregnant": "no",
}


def post(client: TestClient, body: dict | None = None, **headers: str):
    named = {k.replace("_", "-"): v for k, v in headers.items()}
    return client.post(
        "/api/symptom-guide",
        json=body or BODY,
        headers={"X-MedWise-Frontend": SECRET, **named},
    )


def test_setup_lists_every_sign_and_specialty_in_both_languages(client: TestClient) -> None:
    seed = get_settings().seed_dir
    flags = json.loads((seed / "red_flags.json").read_text(encoding="utf-8"))["records"]
    specs = json.loads((seed / "specialties.json").read_text(encoding="utf-8"))["records"]
    en = client.get("/api/symptom-guide/setup").json()["data"]
    bn = client.get("/api/symptom-guide/setup", params={"lang": "bn"}).json()["data"]
    assert [f["id"] for f in en["red_flags"]] == [f["id"] for f in flags]  # NHS order kept
    assert en["red_flags"][0]["text"] == flags[0]["text"]
    assert bn["red_flags"][0]["text"] == flags[0]["text_bn"]
    assert len(en["specialties"]) == len(specs)
    assert bn["specialties"][0]["name"] == specs[0]["name_bn"]


def test_guide_endpoint_returns_the_result(client: TestClient, fake: FakeModel) -> None:
    r = post(client)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["emergency"] is False
    assert data["specialty"]["id"] == "dermatology"
    assert data["note_written_by"] == "ai"
    assert data["rule"] is None


def test_guide_endpoint_bangla_names(client: TestClient, fake: FakeModel) -> None:
    data = post(client, {**BODY, "lang": "bn"}).json()["data"]
    assert data["specialty"]["name"] == "চর্ম বিশেষজ্ঞ (ডার্মাটোলজি)"


def test_guide_endpoint_emergency(client: TestClient, fake: FakeModel) -> None:
    fake.reply = model(red_flag_suspected=True)
    data = post(client).json()["data"]
    assert data == {
        "emergency": True,
        "specialty": None,
        "note": None,
        "note_written_by": None,
        "rule": None,
    }


def test_guide_works_without_a_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    data = post(client).json()["data"]
    assert data["specialty"]["id"] == "general_medicine"
    assert data["note_written_by"] == "answers"


def test_only_our_frontend_may_call_it(client: TestClient, fake: FakeModel, locked: None) -> None:
    r = client.post("/api/symptom-guide", json=BODY)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"
    assert fake.calls == 0
    assert post(client).status_code == 200


def test_per_client_and_daily_limits(client: TestClient, fake: FakeModel, locked: None) -> None:
    for _ in range(get_settings().symptom_limit_per_hour):
        assert post(client, X_Forwarded_For="203.0.113.70").status_code == 200
    blocked = post(client, X_Forwarded_For="203.0.113.70")
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "rate_limited"
    assert post(client, X_Forwarded_For="203.0.113.71").status_code == 200  # someone else


def test_requests_are_checked_strictly(client: TestClient, fake: FakeModel) -> None:
    for bad in (
        {**BODY, "name": "Rahim"},  # no fields for personal details
        {**BODY, "severity": "very bad"},
        {**BODY, "text": "x" * 1001},
        {key: v for key, v in BODY.items() if key != "age_group"},
    ):
        r = post(client, bad)
        assert r.status_code == 422
        assert SECRET_TEXT not in r.text  # errors never echo what the person wrote
    assert fake.calls == 0


def test_the_text_is_never_logged(
    client: TestClient, fake: FakeModel, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    post(client)
    fake.reply = "not json"
    post(client)
    assert caplog.records  # something was captured at all (the check is not vacuous)
    assert all(SECRET_TEXT not in record.getMessage() for record in caplog.records)
    assert SECRET_TEXT not in caplog.text
