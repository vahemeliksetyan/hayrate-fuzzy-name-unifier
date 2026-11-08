"""The groups workbook: one column per group of similar names, last value = target name.

    Group 1          Group 2       Group 3
    Ameria Bank      Digitain      Picsart
    Ameriabank       Digitan       Piksart
    Amerya Bank      Dijiteyn      Picsart Academy
    Ameria Bank      Digitain      Picsart        <- last value in the column = the name to use

Edit it in Excel like a whiteboard: move a name to another column, delete names that do not
belong, add names by hand, change the last cell to the spelling you want, delete whole
columns you do not need. Every name in a column (including the last) becomes the last value.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

_HEADER = re.compile(r"^\s*(group\s*\d+|unnamed:?\s*\d*)\s*$", re.IGNORECASE)

INSTRUCTIONS = [
    "Each column is one group of names that look alike, most frequent first.",
    "The LAST filled cell of a column is the target: every name in that column becomes it.",
    "Wrong name in a group? Delete it, or move it to the right column.",
    "Want a different final spelling? Change the last cell.",
    "Missing a variant? Type it into the column (above the last cell).",
    "Group should not be merged at all? Delete the whole column.",
    "A group that means 'no answer' (n/a, -, none)? Make its last cell: none",
    "Save, then run the same command again to apply the groups to your data.",
]


def write_groups(suggestions: pd.DataFrame, path: str | Path) -> None:
    """suggestions (from suggest_groups) -> groups workbook (wide), plus counts and instructions."""
    columns = {}
    for i, (_, group) in enumerate(suggestions.groupby("group", sort=False), start=1):
        names = group["variant"].tolist()
        columns[f"Group {i}"] = names + [group["canonical"].iloc[0]]
    wide = pd.DataFrame({k: pd.Series(v, dtype=object) for k, v in columns.items()})
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as xl:
        wide.to_excel(xl, sheet_name="groups", index=False)
        suggestions[["group", "variant", "count", "similarity", "group_total"]].to_excel(
            xl, sheet_name="counts", index=False)
        pd.DataFrame({"how to edit": INSTRUCTIONS}).to_excel(xl, sheet_name="how to edit", index=False)


def read_groups(path: str | Path, sheet=0) -> dict[str, str]:
    """groups workbook -> {variant: target}. A header row of 'Group N' labels is optional."""
    table = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    if len(table) and all(pd.isna(v) or _HEADER.match(str(v)) for v in table.iloc[0]):
        table = table.iloc[1:]
    pairs: dict[str, str] = {}
    for col in table.columns:
        names = [str(v).strip() for v in table[col].dropna() if str(v).strip()]
        if not names:
            continue
        target = names[-1]
        for name in names:
            pairs[name] = target
    return pairs
