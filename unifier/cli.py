"""Command line: suggest groups -> review -> apply the mapping.

    unifier suggest  responses.xlsx --column "Company" --out suggestions.csv
    (open suggestions.csv, fix 'canonical', set accept=n on wrong rows)
    unifier apply    responses.xlsx --column "Company" --mapping suggestions.csv --out clean.xlsx
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from unifier.io import read_table, write_table
from unifier.mapping import Mapping, unmatched
from unifier.suggest import SCORERS, suggest_groups


def _columns(df: pd.DataFrame, names: list[str]) -> list[str]:
    missing = [c for c in names if c not in df.columns]
    if missing:
        sys.exit(f"Column(s) not found: {missing}. Available: {list(df.columns)}")
    return names


def cmd_suggest(args) -> None:
    df = read_table(args.input, args.sheet)
    cols = _columns(df, args.column)
    mapping = Mapping.from_csv(args.mapping, transliterate=not args.no_transliterate) if args.mapping \
        else Mapping(transliterate=not args.no_transliterate)
    values = pd.concat([df[c] for c in cols])
    out = suggest_groups(values, threshold=args.threshold, scorer=args.scorer,
                         min_count=args.min_count, mapping=mapping)
    write_table(out, args.out)
    print(f"{out['group'].nunique() if len(out) else 0} candidate groups ({len(out)} spellings) -> {args.out}")
    print("Review it: correct 'canonical', set accept=n where the grouping is wrong, then run `unifier apply`.")


def cmd_apply(args) -> None:
    df = read_table(args.input, args.sheet)
    cols = _columns(df, args.column)
    mapping = Mapping.from_csv(args.mapping, transliterate=not args.no_transliterate)
    todo = []
    for col in cols:
        target = col if args.inplace else f"{col}{args.suffix}"
        df[target] = mapping.apply(df[col])
        before, after = df[col].nunique(), df[target].nunique()
        print(f"{col}: {before} distinct values -> {after}")
        todo.append(unmatched(df[col], mapping).assign(column=col))
    write_table(df, args.out)
    print(f"Unified file -> {args.out}")
    if args.unmatched:
        write_table(pd.concat(todo, ignore_index=True), args.unmatched)
        print(f"Values not in the mapping yet -> {args.unmatched}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="unifier", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("input", type=Path, help="CSV, TSV or Excel file")
    common.add_argument("--column", "-c", action="append", required=True,
                        help="column to unify (repeat for several columns sharing one mapping)")
    common.add_argument("--sheet", help="Excel sheet name (default: first)")
    common.add_argument("--no-transliterate", action="store_true",
                        help="keep Armenian / Cyrillic / accented letters as they are")

    s = sub.add_parser("suggest", parents=[common], help="fuzzy-group similar spellings for review")
    s.add_argument("--out", "-o", type=Path, default=Path("suggestions.csv"))
    s.add_argument("--threshold", "-t", type=float, default=85, help="similarity 0-100 (default 85)")
    s.add_argument("--scorer", choices=sorted(SCORERS), default="token_sort_ratio")
    s.add_argument("--min-count", type=int, default=1, help="skip groups mentioned fewer times")
    s.add_argument("--mapping", "-m", type=Path, help="existing mapping: its variants are skipped")
    s.set_defaults(func=cmd_suggest)

    a = sub.add_parser("apply", parents=[common], help="replace variants with canonical names")
    a.add_argument("--mapping", "-m", type=Path, required=True, help="CSV with variant,canonical")
    a.add_argument("--out", "-o", type=Path, required=True)
    a.add_argument("--suffix", default="_unified", help="new column suffix (default _unified)")
    a.add_argument("--inplace", action="store_true", help="overwrite the column instead")
    a.add_argument("--unmatched", "-u", type=Path, help="also write values the mapping does not cover")
    a.set_defaults(func=cmd_apply)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
