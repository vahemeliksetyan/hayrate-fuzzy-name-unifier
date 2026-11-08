"""Read and write CSV / Excel by file extension."""
from pathlib import Path

import pandas as pd


def read_table(path, sheet=None) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet or 0)
    if path.suffix.lower() == ".tsv":
        return pd.read_csv(path, sep="\t")
    return pd.read_csv(path)


def write_table(df: pd.DataFrame, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, sep="\t" if path.suffix.lower() == ".tsv" else ",")
