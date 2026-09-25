import pytest
from rapidfuzz import fuzz

from app.services.transliterate import (
    contains_bangla,
    phonetic_key,
    to_latin,
    transliterate_bangla,
)


@pytest.mark.parametrize(
    ("bangla", "latin"),
    [
        ("নাপা", "napa"),
        ("সেফিক্সিম", "sefiksim"),
        ("প্যারাসিটামল", "parasitamol"),
        ("৫০০", "500"),
    ],
)
def test_transliterate_bangla(bangla: str, latin: str) -> None:
    assert transliterate_bangla(bangla) == latin


@pytest.mark.parametrize(
    ("bangla", "english"),
    [
        ("প্যারাসিটামল", "Paracetamol"),
        ("সেফিক্সিম", "Cefixime"),
        ("অ্যামলোডিপিন", "Amlodipine"),
        ("মেটফরমিন", "Metformin"),
        ("সিপ্রোফ্লক্সাসিন", "Ciprofloxacin"),
        ("ওমিপ্রাজল", "Omeprazole"),
        ("মন্টিলুকাস্ট", "Montelukast"),
    ],
)
def test_bangla_names_match_english_names_phonetically(bangla: str, english: str) -> None:
    assert fuzz.WRatio(phonetic_key(to_latin(bangla)), phonetic_key(english)) >= 85


@pytest.mark.parametrize(
    ("a", "b"),
    [("Cefixime", "sefiksim"), ("Pheno", "feno"), ("Zimax", "jimaks"), ("Pyrolin", "pirolin")],
)
def test_phonetic_key_collapses_spelling_variants(a: str, b: str) -> None:
    assert phonetic_key(a) == phonetic_key(b)


def test_latin_input_passes_through_unchanged() -> None:
    assert not contains_bangla("Napa 500")
    assert to_latin("Napa 500") == "Napa 500"
