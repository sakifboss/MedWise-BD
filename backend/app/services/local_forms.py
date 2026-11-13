"""Generics that the catalog lists only in local forms (eye, ear, skin, mouth rinse).

DDInter lists interactions for medicines taken by mouth or injection. When every catalog brand
of a generic is a form whose route is "local" in data/seed/dosage_forms.json, that generic's
DDInter pairs are left out (scripts/extract_ddinter.py, checked by the import) and pages say why
instead. Adding a brand in a form taken by mouth or injection and re-running the extraction
brings the pairs back. A form missing from the routes counts as systemic, so it never hides
interactions.
"""

from collections.abc import Hashable, Iterable, Mapping
from typing import TypeVar

LOCAL = "local"

K = TypeVar("K", bound=Hashable)


def local_only_forms(
    brand_forms: Iterable[tuple[K, str]], routes: Mapping[str, str]
) -> dict[K, list[str]]:
    """Generic -> its forms, for each generic whose every brand form is local.

    brand_forms: (generic, dosage form) for every brand; routes: dosage form -> route.
    """
    forms: dict[K, set[str]] = {}
    for generic, form in brand_forms:
        forms.setdefault(generic, set()).add(form)
    return {
        generic: sorted(found)
        for generic, found in forms.items()
        if all(routes.get(form) == LOCAL for form in found)
    }
