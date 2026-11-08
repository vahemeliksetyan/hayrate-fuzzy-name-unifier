# hayrate-fuzzy-name-unifier

**Clean up messy, hand-typed names in Python and Excel: group dozens of spellings of the same
company, university, vendor or answer, fix the groups in Excel, and turn every spelling into
one standard name.** Built for the Hayrate employer survey in Armenia, usable on any column of
free text. It uses normalization, transliteration (Armenian, Cyrillic, accented Latin) and
fuzzy matching with [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz).

```
"Microsoft Corp."  "MICROSOFT CORPORATION"  "Microsfot"  "Micro soft"       ->  Microsoft
"Nestlé S.A."      "NESTLE"                 "nestle"                        ->  Nestlé
"Яндекс"           "Yandex LLC"             "ООО Яндекс"  "Yandeks"         ->  Yandex
"Ameriabank"       "AMERIA BANK"            "Ամերիա բանկ"  "<<Ameriabank>>" ->  Ameria Bank
"n/a"   "-"   "don't know"   "Չկա"                                          ->  (empty)
```

## How it works: two runs and an Excel edit in between

**Run 1: group similar names.** The script reads your file, normalizes every name and groups
the ones that look alike. It writes `groups.xlsx`: **one column per group**, most frequent
spelling first. **The last value of each column is the target name.**

| Group 1 | Group 2 | Group 3 |
|---|---|---|
| Microsoft | Google | Amazon |
| Microsoft Corporation | Google Inc. | Amazon.Com |
| Micro Soft | Gogle | Amazn |
| Microsfot | Google Llc | Amazon Inc |
| **Microsoft** ← target | **Google** ← target | **Amazon** ← target |

**Edit in Excel.** Treat it like a whiteboard:

- put every name that means the same thing into one column; move names between columns if needed;
- delete names that don't belong, or the whole column if the group is wrong;
- type extra variants in by hand;
- make **the last cell** the spelling you want in the final data;
- for answers that mean "nothing" (n/a, -, don't know), make the last cell `none`.

**Run 2: fix all values.** Run the same command again. Every name in a column is replaced by
that column's last value, in every row of your data. You get `<file>_unified.xlsx` with a new
`<column>_unified` column next to the original, and `new_groups.xlsx` with groups among any
names still not covered. Copy the columns you want into `groups.xlsx` and run again. Next
year, reuse the same `groups.xlsx`, and only the new spellings show up.

```bash
unifier run survey.xlsx --column "Company"      # run 1: creates groups.xlsx
# ... edit groups.xlsx in Excel, save ...
unifier run survey.xlsx --column "Company"      # run 2: creates survey_unified.xlsx
```

**Why not merge automatically?** Similar spelling does not always mean the same entity. In the
Hayrate survey, "Acba Bank" and "Ameria Bank" score as very similar, but they are different
banks. Fully automatic fuzzy matching would merge them silently. Here a person sees every group
before it touches the data.

## Do you have this problem?

You have a column that people typed by hand, and you need to count, rank, group or join on it:

- **Survey analysis:** "Which company would you like to work for?", "Other (please specify): ___",
  "Your university / faculty / city". Answers come back as `Google`, `google llc`, `Gogle`,
  `GOOGLE Inc.`, and the counts are split across all of them.
- **Employer and university rankings:** each company's votes are spread across its spellings,
  so the ranking is wrong until they are merged.
- **CRM and sales data:** the same customer was entered five times with different spellings, so
  revenue per account is wrong.
- **Accounting and procurement:** vendor names on invoices (`Amazon.com, Inc.`, `AMAZON`,
  `Amazn`) need to roll up to one supplier for spend analysis.
- **HR and recruiting:** past employers, schools and job titles typed by candidates.
- **Research and public data:** institution or company names from several sources that must be
  merged or matched (entity resolution / record linkage).
- **Multilingual data:** the same name typed in Armenian, Russian or Latin script, with or
  without accents.

Excel find-and-replace, long chains of `df.replace([...])` calls and OpenRefine all work once.
This keeps every decision in one Excel file you can reuse, share and re-run.

## What happens to each name

```
1. clean      trim, single spaces, remove invisible characters, Title Case;
              Armenian / Cyrillic -> Latin; é -> e
2. match key  lower case, no punctuation, no legal forms (LLC, Inc., S.A., CJSC, GmbH, ООО, ՓԲԸ...)
              -> "Amazon.com, Inc." and "AMAZON.COM" are the same name
3. group      fuzzy-match the keys (rapidfuzz), most frequent spelling leads each group
4. apply      every name whose key is in a column -> that column's last value;
              names in no column are kept in their cleaned form; "no answer" -> empty
```

Because matching uses the key, one cell in `groups.xlsx` covers every capitalization, spacing,
punctuation and script of that name.

## Install

```bash
git clone https://github.com/vahemeliksetyan/hayrate-fuzzy-name-unifier.git
cd hayrate-fuzzy-name-unifier
pip install -e .          # installs the `unifier` command; or: pip install -r requirements.txt
```

Python 3.9+, with pandas, openpyxl and rapidfuzz. `python -m unifier ...` works without installing.

## Try it in one minute

```bash
cp examples/quickstart/companies_messy.csv .
unifier run companies_messy.csv --column company --threshold 80     # run 1 -> groups.xlsx
cp examples/quickstart/groups.xlsx .                                # stands in for your Excel edit
unifier run companies_messy.csv --column company --threshold 80     # run 2
```

```
Round 2: applying groups.xlsx
  company: 41 distinct values -> 8
Unified data -> companies_messy_unified.csv
```

Compare your round-1 `groups.xlsx` with the edited
[`examples/quickstart/groups.xlsx`](examples/quickstart/groups.xlsx). The edit merged the two
Yandex groups, added `Deloitte & Touche`, and changed targets like `Deloitte Llp` → `Deloitte`
and `Nestle` → `Nestlé`.

### Options

| Option | What it does |
|---|---|
| `--column` / `-c` (repeatable) | Several columns share one `groups.xlsx`, e.g. 1st, 2nd and 3rd choice |
| `--threshold 0-100` | How similar two names must be to land in one group (default 85; lower = bigger groups) |
| `--scorer` | `ratio` (typos), `token_sort_ratio` (word order, default), `token_set_ratio` (extra words), `WRatio` |
| `--groups` / `-g` | Use a groups workbook other than `groups.xlsx` next to the input |
| `--inplace` | Overwrite the column instead of adding `<column>_unified` |
| `--no-transliterate` | Keep non-Latin text as it is |
| `--sheet` | Excel sheet to read |

The two steps also exist separately: `unifier suggest` (make groups) and `unifier apply`
(use them). A plain `variant,canonical` CSV works as the mapping too.

## Use it from Python / pandas

```python
import pandas as pd
from unifier import Mapping, suggest_groups, write_groups

df = pd.read_excel("survey.xlsx")

# Run 1: groups workbook to edit
write_groups(suggest_groups(df["employer"], threshold=80), "groups.xlsx")

# Run 2: apply the edited workbook
mapping = Mapping.from_file("groups.xlsx")
df["employer_clean"] = mapping.apply(df["employer"])
```

## Case study: Hayrate 2024, Armenia's most attractive employers

[`examples/hayrate_2024/`](examples/hayrate_2024/) is the project this tool came from. Hayrate
is an annual survey by Grant Thornton Armenia and the Armenian HR Association that ranks the
employers university students most want to work for. Students typed up to three employers by
hand, in Armenian and Latin script. A single bank appeared in at least 15 different spellings,
so until they were merged its votes were split and the ranking was wrong.

The example contains:

- `mappings/companies.xlsx`, `faculties.xlsx`, `universities.xlsx`: groups workbooks in the
  format above (58 company groups, 23 faculty groups, 12 university groups), plus company type
  and industry tags;
- `run.py`: the survey pipeline (fold "Other: ___" answers back in, unify five employer columns
  with one workbook, tag type and industry, weighted ranking with 3/2/1 points for 1st/2nd/3rd
  choice, key-factor and sector tables);
- `data/survey_sample.xlsx`: **demo data, not the survey results** (see below).

```bash
python examples/hayrate_2024/run.py
```

**About the data:** the real survey responses are private and are not in this repository, and
neither are the real counts or rankings. `survey_sample.xlsx` uses the survey's answer options
and messy spellings, but every column was resampled independently with random weights. No row
is a real respondent, and the numbers it produces are random.

## Repository layout

```
unifier/               the library and the `unifier` command
  normalize.py         clean text, match key, transliteration (Armenian, Cyrillic, accents)
  suggest.py           fuzzy grouping with rapidfuzz
  groups.py            groups workbook: write it, read it (last value = target)
  mapping.py           apply groups to data, "no answer" handling, unmatched report
  cli.py               `unifier run` / `suggest` / `apply`
examples/quickstart/   messy company names (English, Russian, French) + an edited groups.xlsx
examples/hayrate_2024/ survey case study: groups workbooks, demo data, full pipeline
tests/                 pytest
```

## Related terms

Fuzzy string matching, name standardization, data deduplication, entity resolution, record
linkage, string similarity, company name normalization, clean survey open-ended responses,
group similar names in Excel, map spelling variants to a canonical name, pandas data cleaning,
OpenRefine-style clustering in Python, Armenian and Russian transliteration, Hayrate.

## License

[MIT](LICENSE). Company names in the examples belong to their owners.
