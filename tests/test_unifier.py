import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from unifier import Mapping, clean_text, match_key, suggest_groups, transliterate, unmatched

ROOT = Path(__file__).resolve().parents[1]
QUICKSTART = ROOT / "examples" / "quickstart"


@pytest.mark.parametrize("raw, expected", [
    ("Ֆինանսների նախարարություն", "Finansneri nakhararutyun"),  # Armenian, "ու" digraph
    ("Nakhararoւtyoւn", "Nakhararutyun"),                        # leftovers of naive transliteration
    ("Яндекс", "Yandeks"),                                       # Cyrillic
    ("Société Générale", "Societe Generale"),                    # accents
])
def test_transliterate(raw, expected):
    assert transliterate(raw) == expected


def test_clean_text_and_match_key():
    assert clean_text("  ameria​   BANK ") == "Ameria Bank"
    assert match_key("<<Ameriabank>> CJSC") == match_key("ameriabank") == "ameriabank"
    assert match_key("Nestlé S.A.") == match_key("nestle") == "nestle"
    assert match_key("Co") == "co"  # a name is never reduced to nothing
    assert clean_text(float("nan")) == "" and clean_text(None) == "" and clean_text(pd.NA) == ""


def test_mapping_unify():
    m = Mapping({"Ameriabank": "Ameria Bank", "Amerya bank": "Ameria Bank"})
    out = m.apply(pd.Series(["AMERIABANK", "Ամերիա բանկ", "ameria bank llc", "n/a", "-", None, "brand new co"]))
    assert out.tolist()[:3] == ["Ameria Bank"] * 3
    assert out.iloc[3:6].isna().all()
    assert out.iloc[6] == "Brand New Co"  # unknown names are cleaned, not dropped


def test_mapping_conflict_warns():
    with pytest.warns(UserWarning):
        Mapping({"Acme Inc": "Acme", "ACME": "Acme Corp"})


def test_reviewed_suggestions_respect_accept(tmp_path):
    path = tmp_path / "reviewed.csv"
    pd.DataFrame({"variant": ["Acba Bank", "Ameriabank"], "canonical": ["Ameria Bank", "Ameria Bank"],
                  "accept": ["n", "y"]}).to_csv(path, index=False)
    m = Mapping.from_csv(path)
    assert m.unify("Ameriabank") == "Ameria Bank"
    assert m.unify("Acba Bank") == "Acba Bank"


def test_suggest_groups_and_unmatched():
    values = pd.Series(["Microsoft"] * 5 + ["Microsfot", "Microsoft Corp.", "Google", "Gogle", "-"])
    groups = suggest_groups(values, threshold=80)
    ms = groups[groups["canonical"] == "Microsoft"]
    assert set(ms["variant"]) == {"Microsoft", "Microsfot", "Microsoft Corp."}
    assert "-" not in set(groups["variant"])
    todo = unmatched(values, Mapping({"Microsfot": "Microsoft"}))
    assert set(todo["value"]) == {"Google", "Gogle"}


def test_quickstart_cli(tmp_path):
    out = tmp_path / "clean.csv"
    subprocess.run([sys.executable, "-m", "unifier", "apply", str(QUICKSTART / "companies_messy.csv"),
                    "-c", "company", "-m", str(QUICKSTART / "mapping.csv"), "-o", str(out)],
                   check=True, cwd=ROOT, capture_output=True)
    unified = pd.read_csv(out)["company_unified"].dropna()
    assert set(unified) == {"Microsoft", "Google", "Amazon", "Coca-Cola", "Yandex", "Deloitte",
                            "Société Générale", "Nestlé"}


def test_hayrate_example_runs(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "examples" / "hayrate_2024" / "run.py"),
                             "--output", str(tmp_path)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    ranking = pd.read_excel(tmp_path / "results.xlsx", sheet_name="employer_ranking")
    assert ranking["score"].is_monotonic_decreasing and len(ranking) > 0
