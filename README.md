# fuzzy-name-unifier

**Clean up messy, hand-typed names in Python: turn dozens of spellings of the same company,
university, vendor or answer into one standard name.** It uses text normalization,
transliteration (Armenian, Cyrillic, accented Latin) and fuzzy matching with
[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz). A person reviews the matches before they
change any data. Works with CSV and Excel, from the command line or from pandas.

```
"Microsoft Corp."  "MICROSOFT CORPORATION"  "Microsfot"  "Micro soft"       ->  Microsoft
"Nestlé S.A."      "NESTLE"                 "nestle"                        ->  Nestlé
"Яндекс"           "Yandex LLC"             "ООО Яндекс"  "Yandeks"         ->  Yandex
"Ameriabank"       "AMERIA BANK"            "Ամերիա բանկ"  "<<Ameriabank>>" ->  Ameria Bank
"n/a"   "-"   "don't know"   "Չկա"                                          ->  (empty)
```

## Do you have this problem?

You have a column people typed by hand, and now you need to count, group or join on it:

- **Survey analysis:** "Which company would you like to work for?", "Other (please specify): ___",
  "Your university / school / city". Answers come back as `Google`, `google llc`, `Gogle`,
  `GOOGLE Inc.`, and the counts are split.
- **CRM and sales data:** the same customer was entered five times with different spellings, so
  revenue per account is wrong.
- **Accounting and procurement:** vendor names on invoices (`Amazon.com, Inc.`, `AMAZON`,
  `Amazn`) need to roll up to one supplier for spend analysis.
- **HR and recruiting:** past employers, schools and job titles typed by candidates.
- **Research and public data:** institution or company names from several sources that must be
  merged or matched (entity resolution / record linkage).
- **Multilingual data:** the same name typed in Armenian, Russian or Latin script, with or
  without accents.

You may have tried Excel find-and-replace, a long chain of `df.replace([...])` calls, or
OpenRefine. This tool keeps every rule in one reviewable CSV file, re-runs in seconds on next
year's data, and tells you exactly what is still unmatched.

## How it works

```
messy column
  1. normalize   trim, single spaces, remove invisible characters, Title Case;
                 Armenian / Cyrillic -> Latin; é -> e
  2. match key   lower case, no punctuation, no legal forms (LLC, Inc., S.A., CJSC, GmbH, ООО, ՓԲԸ...)
                 -> "Amazon.com, Inc." and "amazoncom" become the same key
  3. suggest     fuzzy-group the remaining spellings (rapidfuzz) -> suggestions.csv for review
  4. review      you fix the canonical names and reject wrong groups (accept = n)
  5. apply       replace every known variant with its canonical name; list what is still unmatched
```

**Why review?** Similar spelling does not always mean the same entity. In the Hayrate case study
below, "Acba Bank" and "Ameria Bank" score as very similar, but they are different banks. Fully
automatic fuzzy matching silently merges them; this tool shows you the groups first.

## Install

```bash
git clone https://github.com/vahemeliksetyan/fuzzy-name-unifier.git
cd fuzzy-name-unifier
pip install -e .          # installs the `unifier` command; or: pip install -r requirements.txt
```

Python 3.9+, with pandas, openpyxl and rapidfuzz.

## Quick start (command line)

```bash
# 1. Suggest groups of similar spellings in one or more columns
unifier suggest examples/quickstart/companies_messy.csv --column company --threshold 80 --out suggestions.csv

# 2. Open suggestions.csv in Excel: fix "canonical", set accept=n on wrong rows, save

# 3. Apply it: adds company_unified next to company, and lists values not covered yet
unifier apply examples/quickstart/companies_messy.csv --column company \
    --mapping suggestions.csv --out companies_clean.csv --unmatched todo.csv
```

With the reviewed mapping in [`examples/quickstart/mapping.csv`](examples/quickstart/mapping.csv):

```
company: 41 distinct values -> 8
```

(`python -m unifier ...` works without installing.) Useful options:

| Option | What it does |
|---|---|
| `--column` / `-c` (repeatable) | Several columns share one mapping, e.g. 1st, 2nd and 3rd choice |
| `--threshold 0-100` | Similarity needed to group two spellings (default 85) |
| `--scorer` | `ratio` (typos), `token_sort_ratio` (word order, default), `token_set_ratio` (extra words), `WRatio` |
| `--mapping` on `suggest` | Skip spellings your mapping already covers, so each run shows only new ones |
| `--inplace` on `apply` | Overwrite the column instead of adding `<column>_unified` |
| `--no-transliterate` | Keep non-Latin text as it is |
| `--sheet` | Excel sheet to read |

## Use it from Python / pandas

```python
import pandas as pd
from unifier import Mapping, suggest_groups, unmatched

df = pd.read_excel("survey.xlsx")

# Suggest groups to review
suggest_groups(df["employer"], threshold=80).to_csv("suggestions.csv", index=False)

# Apply a reviewed mapping (columns: variant, canonical[, accept])
mapping = Mapping.from_csv("suggestions.csv")
df["employer_clean"] = mapping.apply(df["employer"])

# What is still not covered?
print(unmatched(df["employer"], mapping).head(20))
```

The mapping file is plain CSV, so it lives in git, can be reviewed in a pull request, and grows
with every new batch of data:

```csv
variant,canonical
Microsoft Corporation,Microsoft
Microsfot,Microsoft
Amazon.com,Amazon
Яндекс,Yandex
```

Matching ignores case, spacing, punctuation, script and legal forms, so one row covers
`Microsfot`, `MICROSFOT` and `microsfot inc.`.

## Case study: Hayrate 2024, Armenia's most attractive employers

[`examples/hayrate_2024/`](examples/hayrate_2024/) is the real project this tool came from.
Hayrate is an annual survey by Grant Thornton Armenia and the Armenian HR Association that ranks
the employers university students most want to work for. Students typed up to three employers
by hand, in Armenian and Latin script. A single bank appeared in at least 15 different
spellings. Without unification, its votes were split and the ranking was wrong.

The example contains:

- the **real mapping tables** built for the survey: 276 company spellings, 309 faculty
  spellings, university branches, and company type and industry tags;
- `run.py`: the full pipeline (fold "Other: ___" answers back in, unify five employer columns,
  tag company type and field, weighted ranking with 3/2/1 points for 1st/2nd/3rd choice,
  key-factor and sector tables);
- a **sample dataset**: real answer text, random numbers (see below).

```bash
python examples/hayrate_2024/run.py
```

**About the sample data:** the real survey responses are private and are not in this repository.
`examples/hayrate_2024/data/survey_sample.xlsx` keeps the real answer options and the real messy
spellings, but each column was resampled independently with random weights. No row is a real
respondent, and the counts and rankings it produces are random. They are not the survey's results.

## Repository layout

```
unifier/               the library and CLI
  normalize.py         clean_text, match_key, transliteration (Armenian, Cyrillic, accents)
  mapping.py           Mapping: load CSV, apply, conflicts, unmatched report
  suggest.py           fuzzy grouping with rapidfuzz
  cli.py               `unifier suggest` / `unifier apply`
examples/quickstart/   messy company names in English, Russian and French + reviewed mapping
examples/hayrate_2024/ survey case study: real mappings, sample data, full pipeline
tests/                 pytest
```

## Related terms

Fuzzy string matching, name standardization, data deduplication, entity resolution, record
linkage, string similarity, company name normalization, cleaning survey open-ended responses,
mapping spelling variants to a canonical name, pandas data cleaning, Excel data cleaning,
OpenRefine-style clustering in Python, Armenian and Russian transliteration.

## License

[MIT](LICENSE). Company names in the examples belong to their owners.
