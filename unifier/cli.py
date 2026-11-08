"""Unify messy names in two runs.

    unifier run survey.xlsx --column "Company"
        1st run: writes groups.xlsx - one column per group of similar names,
                 last value of each column = the name to use. Edit it in Excel.
        2nd run: same command again - every name in a column becomes its last value.
                 Writes survey_unified.xlsx and new_groups.xlsx for names still left.

Step by step instead: `unifier suggest` (make groups) and `unifier apply` (use them).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from unifier.groups import write_groups
from unifier.io import read_table, write_table
from unifier.mapping import Mapping, unmatched
from unifier.suggest import SCORERS, suggest_groups


def _columns(df: pd.DataFrame, names: list[str]) -> list[str]:
    missing = [c for c in names if c not in df.columns]
    if missing:
        sys.exit(f"Column(s) not found: {missing}. Available: {list(df.columns)}")
    return names


def _write_suggestions(out: pd.DataFrame, path: Path) -> None:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        write_groups(out, path)
    else:
        write_table(out, path)  # long format: variant, canonical, accept ...


def _suggest(df, cols, args, mapping=None) -> pd.DataFrame:
    values = pd.concat([df[c] for c in cols])
    return suggest_groups(values, threshold=args.threshold, scorer=args.scorer,
                          min_count=args.min_count, mapping=mapping or Mapping(transliterate=not args.no_transliterate))


def _apply(df, cols, mapping, args) -> pd.DataFrame:
    for col in cols:
        target = col if args.inplace else f"{col}{args.suffix}"
        df[target] = mapping.apply(df[col])
        print(f"  {col}: {df[col].nunique()} distinct values -> {df[target].nunique()}")
    return df


def cmd_run(args) -> None:
    df = read_table(args.input, args.sheet)
    cols = _columns(df, args.column)
    groups = args.groups or args.input.with_name("groups.xlsx")
    if not groups.exists():
        out = _suggest(df, cols, args)
        write_groups(out, groups)
        n = out["group"].nunique() if len(out) else 0
        print(f"Round 1: {n} groups of similar names -> {groups}")
        print("Open it, fix the columns (last value of each column = the name to use), save,")
        print("then run the same command again.")
        return
    mapping = Mapping.from_file(groups, transliterate=not args.no_transliterate)
    print(f"Round 2: applying {groups}")
    df = _apply(df, cols, mapping, args)
    out_path = args.out or args.input.with_name(f"{args.input.stem}_unified{args.input.suffix}")
    write_table(df, out_path)
    print(f"Unified data -> {out_path}")
    left = _suggest(df, cols, args, mapping=mapping)
    if len(left):
        new_groups = groups.with_name(f"new_{groups.name}")
        write_groups(left, new_groups)
        print(f"{left['group'].nunique()} new groups among names not covered yet -> {new_groups}")
        print(f"(copy the columns you want into {groups.name} and run again)")


def cmd_suggest(args) -> None:
    df = read_table(args.input, args.sheet)
    cols = _columns(df, args.column)
    mapping = Mapping.from_file(args.mapping, transliterate=not args.no_transliterate) if args.mapping else None
    out = _suggest(df, cols, args, mapping)
    _write_suggestions(out, args.out)
    print(f"{out['group'].nunique() if len(out) else 0} groups ({len(out)} spellings) -> {args.out}")


def cmd_apply(args) -> None:
    df = read_table(args.input, args.sheet)
    cols = _columns(df, args.column)
    mapping = Mapping.from_file(args.mapping, transliterate=not args.no_transliterate)
    df = _apply(df, cols, mapping, args)
    write_table(df, args.out)
    print(f"Unified data -> {args.out}")
    if args.unmatched:
        todo = pd.concat([unmatched(df[c], mapping).assign(column=c) for c in cols], ignore_index=True)
        write_table(todo, args.unmatched)
        print(f"Values not covered yet -> {args.unmatched}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="unifier", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("input", type=Path, help="CSV, TSV or Excel file")
    common.add_argument("--column", "-c", action="append", required=True,
                        help="column to unify (repeat for several columns sharing one set of groups)")
    common.add_argument("--sheet", help="Excel sheet name (default: first)")
    common.add_argument("--no-transliterate", action="store_true",
                        help="keep Armenian / Cyrillic / accented letters as they are")

    fuzzy = argparse.ArgumentParser(add_help=False)
    fuzzy.add_argument("--threshold", "-t", type=float, default=85, help="similarity 0-100 (default 85)")
    fuzzy.add_argument("--scorer", choices=sorted(SCORERS), default="token_sort_ratio")
    fuzzy.add_argument("--min-count", type=int, default=1, help="skip groups mentioned fewer times")

    output = argparse.ArgumentParser(add_help=False)
    output.add_argument("--suffix", default="_unified", help="new column suffix (default _unified)")
    output.add_argument("--inplace", action="store_true", help="overwrite the column instead")

    r = sub.add_parser("run", parents=[common, fuzzy, output],
                       help="1st run: make groups.xlsx; 2nd run: apply it")
    r.add_argument("--groups", "-g", type=Path, help="groups workbook (default: groups.xlsx next to input)")
    r.add_argument("--out", "-o", type=Path, help="unified file (default: <input>_unified)")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("suggest", parents=[common, fuzzy], help="make groups of similar names")
    s.add_argument("--out", "-o", type=Path, default=Path("groups.xlsx"),
                   help="groups.xlsx (columns) or .csv (variant,canonical rows)")
    s.add_argument("--mapping", "-m", type=Path, help="existing groups/mapping: covered names are skipped")
    s.set_defaults(func=cmd_suggest)

    a = sub.add_parser("apply", parents=[common, output], help="replace names using groups/mapping")
    a.add_argument("--mapping", "-m", type=Path, required=True, help="groups.xlsx or variant,canonical CSV")
    a.add_argument("--out", "-o", type=Path, required=True)
    a.add_argument("--unmatched", "-u", type=Path, help="also write values not covered yet")
    a.set_defaults(func=cmd_apply)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
