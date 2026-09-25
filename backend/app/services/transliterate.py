"""Bangla -> Latin transliteration and a phonetic key for fuzzy name matching.

Medicine names are mostly loanwords, so this aims for "sounds like the English name"
rather than a formal romanisation. Exact spelling does not matter much because results
are fuzzy-matched on phonetic keys.
"""

import re

_BANGLA = re.compile(r"[ঀ-৿]")
_HASANT = "্"
_YA = "য"

_INDEPENDENT_VOWELS = {
    "অ": "o", "আ": "a", "ই": "i", "ঈ": "i", "উ": "u", "ঊ": "u",
    "ঋ": "ri", "এ": "e", "ঐ": "oi", "ও": "o", "ঔ": "ou",
}  # fmt: skip
_VOWEL_SIGNS = {
    "া": "a", "ি": "i", "ী": "i", "ু": "u", "ূ": "u",
    "ৃ": "ri", "ে": "e", "ৈ": "oi", "ো": "o", "ৌ": "ou",
}  # fmt: skip
_CONSONANTS = {
    "ক": "k", "খ": "kh", "গ": "g", "ঘ": "gh", "ঙ": "ng",
    "চ": "ch", "ছ": "chh", "জ": "j", "ঝ": "jh", "ঞ": "n",
    "ট": "t", "ঠ": "th", "ড": "d", "ঢ": "dh", "ণ": "n",
    "ত": "t", "থ": "th", "দ": "d", "ধ": "dh", "ন": "n",
    "প": "p", "ফ": "f", "ব": "b", "ভ": "bh", "ম": "m",
    "য": "j", "র": "r", "ল": "l", "শ": "sh", "ষ": "sh",
    "স": "s", "হ": "h", "ড়": "r", "ঢ়": "rh", "য়": "y",
}  # fmt: skip
_SIGNS = {"ং": "ng", "ঃ": "h", "ঁ": "", "ৎ": "t"}
_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
# Nukta forms that may arrive decomposed.
_NUKTA = {"ড়": "ড়", "ঢ়": "ঢ়", "য়": "য়"}


def contains_bangla(text: str) -> bool:
    return bool(_BANGLA.search(text))


def _prepare(text: str) -> str:
    for decomposed, composed in _NUKTA.items():
        text = text.replace(decomposed, composed)
    # "অ্যা" is the Bangla spelling of an English "a" sound (e.g. অ্যামলোডিপিন).
    return text.replace("অ্যা", "আ").translate(_DIGITS)


def transliterate_bangla(text: str) -> str:
    chars = _prepare(text)
    out: list[str] = []
    for i, ch in enumerate(chars):
        prev = chars[i - 1] if i > 0 else ""
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if ch in _CONSONANTS:
            # "্য" (ya-phala) after a consonant only colours the vowel; drop it.
            if not (ch == _YA and prev == _HASANT):
                out.append(_CONSONANTS[ch])
            # Inherent vowel between consonants; silent at the end of a word.
            if nxt in _CONSONANTS:
                out.append("o")
        elif ch in _VOWEL_SIGNS:
            out.append(_VOWEL_SIGNS[ch])
        elif ch in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[ch])
        elif ch in _SIGNS:
            out.append(_SIGNS[ch])
        elif ch != _HASANT:
            out.append(ch)
    return "".join(out)


_PHONETIC_RULES: list[tuple[str, str]] = [
    (r"[^a-z0-9]", ""),
    (r"ph", "f"),
    (r"sh", "s"),
    (r"ch", "c"),
    (r"([kgjtdb])h", r"\1"),
    (r"c(?=[eiy])", "s"),
    (r"[cq]", "k"),
    (r"x", "ks"),
    (r"z", "j"),
    (r"v", "b"),
    (r"y", "i"),
    (r"ee", "i"),
    (r"oo", "u"),
    (r"(.)\1+", r"\1"),
    (r"(?<=...)e$", ""),  # silent final e: "cefixime" -> "cefixim"
]


def phonetic_key(text: str) -> str:
    """Spelling-insensitive key so 'Cefixime', 'sefiksim' and 'সেফিক্সিম' collide."""
    key = text.lower()
    for pattern, replacement in _PHONETIC_RULES:
        key = re.sub(pattern, replacement, key)
    return key


def to_latin(query: str) -> str:
    return transliterate_bangla(query) if contains_bangla(query) else query
