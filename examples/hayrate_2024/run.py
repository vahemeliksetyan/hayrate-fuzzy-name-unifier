"""Case study: Hayrate 2024 student survey (Armenia) -> unified employer names -> ranking.

Students typed up to three employers they would like to work for. The same company came
back in dozens of spellings, in Armenian and Latin script. This script runs the full
pipeline on the sample in data/ (synthetic, see README) with the real mapping tables.

    python examples/hayrate_2024/run.py [--input survey.xlsx] [--output outputs/hayrate]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from unifier import Mapping, match_key, suggest_groups, unmatched  # noqa: E402

MAPPINGS = HERE / "mappings"

# Survey export column (Armenian) -> English.
COLUMNS = {
    "Համալսարան": "university", "Unnamed: 1": "university_other",
    "Կրթական ծրագիր": "degree_level", "Կրթական համակարգ": "study_mode", "Կուրս": "year_of_study",
    "Ֆակուլտետ": "faculty", "Աշխատանքի առկայություն": "is_employed",
    "Աշխատանքի տեսակ": "employment_type", "Unnamed: 8": "employment_type_other",
    "Աշխատանքի ոլորտ": "work_sector",
    "Պետական": "rank_public", "Մասնավոր": "rank_private", "Հասարակական": "rank_ngo",
    "Նախըտնտրելի ընկերություն 1": "preferred_employer_1",
    "Նախըտնտրելի ընկերություն 2": "preferred_employer_2",
    "Նախըտնտրելի ընկերություն 3": "preferred_employer_3",
    **{f"Կարևորագույն գործոն {i}": f"key_factor_{i}" for i in range(1, 12)},
    "Ընտանիքի անդամ": "family_member_employed", "Ընտանիքի անդամի ընկերություն": "family_member_employer",
    "Աշխատել եք նախընտրած վայրում": "worked_at_preferred", "Ձեր ընկերության անուն": "current_employer",
}
PREFERRED = ["preferred_employer_1", "preferred_employer_2", "preferred_employer_3"]
EMPLOYER_COLUMNS = PREFERRED + ["family_member_employer", "current_employer"]
KEY_FACTORS = [f"key_factor_{i}" for i in range(1, 12)]
WEIGHTS = {"preferred_employer_1": 3, "preferred_employer_2": 2, "preferred_employer_3": 1}
OTHER_UNIVERSITY = "Այլ (խնդրում ենք ստորև նշել անունը)"
OTHER_EMPLOYMENT = "Այլ"


def load(path) -> pd.DataFrame:
    df = pd.read_excel(path)
    return df[list(COLUMNS)].rename(columns=COLUMNS)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["university_raw"] = df["university"]
    for col, other, label in [("university", "university_other", OTHER_UNIVERSITY),
                              ("employment_type", "employment_type_other", OTHER_EMPLOYMENT)]:
        is_other = df[col].astype("string").str.strip() == label
        df.loc[is_other, col] = df.loc[is_other, other]
    # Universities keep their official Armenian names, so no transliteration here.
    universities = Mapping.from_csv(MAPPINGS / "universities.csv", transliterate=False)
    df["university"] = df["university"].map(lambda v: universities.unify(v) if isinstance(v, str) else v)
    df.loc[df["university"] == "Response", "university"] = pd.NA  # stray header cell in the export
    return df.drop(columns=["university_other", "employment_type_other"])


def unify(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    companies = Mapping.from_csv(MAPPINGS / "companies.csv")
    for col in EMPLOYER_COLUMNS:
        df[col] = companies.apply(df[col])
    df["faculty"] = Mapping.from_csv(MAPPINGS / "faculties.csv").apply(df["faculty"])
    return df


def classify(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for name in ["company_type", "company_field"]:
        table = pd.read_csv(MAPPINGS / f"{name}.csv", dtype=str)
        lookup = {match_key(c): cat for c, cat in zip(table["company"], table["category"])}
        for col in PREFERRED:
            df[f"{col}_{name.split('_')[1]}"] = df[col].map(lambda v: lookup.get(match_key(v)) if isinstance(v, str) else None)
    return df


def employer_ranking(df: pd.DataFrame, top_n: int = 25) -> pd.DataFrame:
    """3 points per first choice, 2 per second, 1 per third."""
    parts = {}
    for col, w in WEIGHTS.items():
        counts = df[col].value_counts()
        parts[f"{col}_mentions"] = counts
        parts[f"{col}_points"] = counts * w
    table = pd.DataFrame(parts).fillna(0).astype(int)
    table["mentions"] = table[[f"{c}_mentions" for c in WEIGHTS]].sum(axis=1)
    table["score"] = table[[f"{c}_points" for c in WEIGHTS]].sum(axis=1)
    table = table.sort_values(["score", "mentions"], ascending=False).head(top_n)
    table.index.name = "employer"
    table.insert(0, "rank", range(1, len(table) + 1))
    return table.reset_index()


def key_factors(df: pd.DataFrame) -> pd.DataFrame:
    answered = df[KEY_FACTORS].notna().any(axis=1).sum()
    rows = [{"factor": (df[c].dropna().mode().iloc[0] if df[c].notna().any() else c) if c != KEY_FACTORS[-1]
             else "Other (free text)", "respondents": int(df[c].notna().sum())} for c in KEY_FACTORS]
    out = pd.DataFrame(rows).sort_values("respondents", ascending=False)
    out["share"] = (out["respondents"] / max(answered, 1)).round(3)
    return out


def sector_preference(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, label in [("rank_public", "Public"), ("rank_private", "Private"), ("rank_ngo", "NGO")]:
        r = df[col].value_counts()
        rows.append({"sector": label, "ranked_1st": int(r.get(1, 0)), "ranked_2nd": int(r.get(2, 0)),
                     "ranked_3rd": int(r.get(3, 0)),
                     "score": int(r.get(1, 0) * 3 + r.get(2, 0) * 2 + r.get(3, 0))})
    return pd.DataFrame(rows).sort_values("score", ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=HERE / "data" / "survey_sample.xlsx")
    parser.add_argument("--output", type=Path, default=Path("outputs") / "hayrate")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    raw = load(args.input)
    df = classify(unify(clean(raw)))
    df.to_excel(args.output / "responses_clean.xlsx", index=False)

    ranking = employer_ranking(df)
    with pd.ExcelWriter(args.output / "results.xlsx") as xl:
        ranking.to_excel(xl, sheet_name="employer_ranking", index=False)
        key_factors(df).to_excel(xl, sheet_name="key_factors", index=False)
        sector_preference(df).to_excel(xl, sheet_name="sector_preference", index=False)
        df["university"].value_counts().to_frame("respondents").to_excel(xl, sheet_name="universities")
        df["faculty"].value_counts().to_frame("respondents").to_excel(xl, sheet_name="faculties")

    companies = Mapping.from_csv(MAPPINGS / "companies.csv")
    names = pd.concat([raw[c] for c in PREFERRED])
    unmatched(names, companies).to_excel(args.output / "unmatched_employers.xlsx", index=False)
    suggest_groups(names, threshold=80, mapping=companies, min_count=3).to_excel(
        args.output / "suggested_groups.xlsx", index=False)

    before = names.dropna().nunique()
    after = pd.concat([df[c] for c in PREFERRED]).dropna().nunique()
    print(f"{len(df)} responses | distinct employer spellings: {before} -> {after} after unification")
    print(ranking[["rank", "employer", "score", "mentions"]].head(10).to_string(index=False))
    print(f"Outputs -> {args.output}/")


if __name__ == "__main__":
    main()
