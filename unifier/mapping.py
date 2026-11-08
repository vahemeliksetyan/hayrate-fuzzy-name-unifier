"""Mapping tables: a two-column CSV (variant, canonical) that says which spellings mean what."""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from unifier.normalize import clean_text, is_missing, match_key

# Typed answers that mean "nothing" in most surveys and forms (compared on match_key).
DEFAULT_NO_ANSWER = {
    "", "-", "n a", "na", "none", "null", "nil", "no", "nothing", "unknown", "not applicable",
    "dont know", "don t know", "idk", "x",
    # Armenian (transliterated): չկա, չգիտեմ, ոչ, չունեմ
    "chka", "chkan", "chgitem", "der chgitem", "och", "chunem",
    # Russian (transliterated): нет, не знаю
    "net", "ne znayu",
}


class Mapping:
    """variant -> canonical lookup that ignores case, spacing, punctuation, script and legal forms."""

    def __init__(self, pairs: dict[str, str] | None = None, no_answer: set[str] | None = None,
                 transliterate: bool = True, drop_legal_suffixes: bool = True):
        self.transliterate = transliterate
        self.drop_legal_suffixes = drop_legal_suffixes
        self.no_answer = {self.key(v) for v in (DEFAULT_NO_ANSWER if no_answer is None else no_answer)}
        self._lookup: dict[str, str] = {}
        for variant, canonical in (pairs or {}).items():
            self.add(variant, canonical)

    def key(self, value) -> str:
        return match_key(value, self.transliterate, self.drop_legal_suffixes)

    def add(self, variant: str, canonical: str) -> None:
        k = self.key(variant)
        if k in self._lookup and self._lookup[k] != canonical:
            warnings.warn(f"{variant!r} maps to both {self._lookup[k]!r} and {canonical!r}; keeping the first")
            return
        self._lookup[k] = canonical
        self._lookup.setdefault(self.key(canonical), canonical)

    @property
    def canonicals(self) -> set[str]:
        return set(self._lookup.values())

    def __len__(self) -> int:
        return len(self._lookup)

    def unify(self, value):
        """Canonical name if known; cleaned text if not; None for empty / "no answer"."""
        if is_missing(value):
            return None
        k = self.key(value)
        if k in self.no_answer:
            return None
        canonical = self._lookup.get(k)
        if canonical is None:
            return clean_text(value, self.transliterate)
        return None if self.key(canonical) in self.no_answer else canonical

    def is_known(self, value) -> bool:
        return self.key(value) in self._lookup

    def apply(self, series: pd.Series) -> pd.Series:
        return series.map(self.unify)

    # --- files ---

    @classmethod
    def from_csv(cls, path: str | Path, **kwargs) -> "Mapping":
        table = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = {"variant", "canonical"} - set(table.columns)
        if missing:
            raise ValueError(f"{path} needs columns 'variant' and 'canonical' (missing: {missing})")
        if "accept" in table.columns:  # a reviewed suggestions file
            table = table[table["accept"].str.strip().str.lower().isin({"y", "yes", "1", "true"})]
        pairs = dict(zip(table["variant"].str.strip(), table["canonical"].str.strip()))
        return cls(pairs, **kwargs)


def unmatched(series: pd.Series, mapping: Mapping) -> pd.DataFrame:
    """Values no mapping row covers, most frequent first: the to-do list for the next pass."""
    values = series.dropna().map(lambda v: clean_text(v, mapping.transliterate))
    values = values[values.map(lambda v: not mapping.is_known(v) and mapping.key(v) not in mapping.no_answer)]
    return values.value_counts().rename_axis("value").reset_index(name="count")
