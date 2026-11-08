"""Group similar spellings with fuzzy matching, as suggestions for a person to review.

Similar spelling does not always mean the same thing: "Acba Bank" and "Ameria Bank" score
high on most similarity measures but are two different banks. So this step never changes
data. It writes candidate groups with an ``accept`` column; you check them, mark the
right ones, and the reviewed file becomes (or extends) your mapping.
"""
from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz, process

from unifier.mapping import DEFAULT_NO_ANSWER, Mapping
from unifier.normalize import clean_text

SCORERS = {
    "ratio": fuzz.ratio,                        # typos: "Digitain" ~ "Digitan"
    "token_sort_ratio": fuzz.token_sort_ratio,  # + word order: "Bank Ameria" ~ "Ameria Bank"
    "token_set_ratio": fuzz.token_set_ratio,    # + extra words: "Ameria Bank Yerevan" ~ "Ameria Bank"
    "WRatio": fuzz.WRatio,                      # rapidfuzz's blend; most lenient
}


def suggest_groups(values: pd.Series, threshold: float = 85, scorer: str = "token_sort_ratio",
                   min_count: int = 1, mapping: Mapping | None = None) -> pd.DataFrame:
    """Cluster values; each value joins the most similar existing group above ``threshold``.

    Values are visited from most to least frequent, so a group's first member (its suggested
    canonical name) is its most common spelling. Values a ``mapping`` already covers are
    skipped, so repeated runs only show what is still new.
    """
    if scorer not in SCORERS:
        raise ValueError(f"scorer must be one of {sorted(SCORERS)}")
    mapping = mapping or Mapping(no_answer=DEFAULT_NO_ANSWER)
    score = SCORERS[scorer]

    cleaned = values.dropna().map(lambda v: clean_text(v, mapping.transliterate))
    cleaned = cleaned[cleaned.map(lambda v: mapping.key(v) not in mapping.no_answer and not mapping.is_known(v))]
    counts = cleaned.value_counts()

    leaders: list[str] = []          # match key of each group's first member
    members: list[list[tuple]] = []  # (value, count, similarity)
    for value, count in counts.items():
        key = mapping.key(value)
        best = process.extractOne(key, leaders, scorer=score, score_cutoff=threshold) if leaders else None
        if best:
            members[best[2]].append((value, int(count), round(best[1], 1)))
        else:
            leaders.append(key)
            members.append([(value, int(count), 100.0)])

    rows = []
    for gid, group in enumerate(members, start=1):
        total = sum(c for _, c, _ in group)
        if len(group) < 2 or total < min_count:
            continue
        for value, count, similarity in group:
            rows.append({"group": gid, "variant": value, "count": count, "similarity": similarity,
                         "canonical": group[0][0], "group_total": total, "accept": "y"})
    columns = ["group", "variant", "count", "similarity", "canonical", "group_total", "accept"]
    out = pd.DataFrame(rows, columns=columns)
    return out.sort_values(["group_total", "group", "count"], ascending=[False, True, False]).reset_index(drop=True)
