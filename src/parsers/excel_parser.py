"""
Excel parser — supports .xlsx and .xls bank exports.
Delegates to the CSV parser logic after reading with pandas.
"""

import io

import pandas as pd

from src.parsers.csv_parser import (
    _find_col, _parse_amount, _parse_date,
    DATE_COLS, DESC_COLS, AMOUNT_COLS, DEBIT_COLS, CREDIT_COLS,
)


def parse(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse an Excel file and return a list of transaction dicts."""
    results = []

    try:
        # Try all sheets, use the one with most rows
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        best_df = None
        best_rows = 0
        for sheet in xls.sheet_names:
            try:
                df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, dtype=str)
                if len(df) > best_rows:
                    best_df = df
                    best_rows = len(df)
            except Exception:
                continue
        if best_df is None:
            return []
        df = best_df
    except Exception:
        return []

    df.columns = [str(c).strip() for c in df.columns]

    date_col = _find_col(df, DATE_COLS)
    desc_col = _find_col(df, DESC_COLS)
    debit_col = _find_col(df, DEBIT_COLS)
    credit_col = _find_col(df, CREDIT_COLS)
    amount_col = _find_col(df, AMOUNT_COLS)

    if not date_col:
        return []

    for _, row in df.iterrows():
        date_str = _parse_date(row.get(date_col, ""))
        if not date_str:
            continue

        description = str(row.get(desc_col, "")).strip() if desc_col else ""
        amount = None
        t_type = "expense"

        if debit_col and credit_col:
            debit = _parse_amount(row.get(debit_col))
            credit = _parse_amount(row.get(credit_col))
            if credit and credit > 0:
                amount = credit
                t_type = "income"
            elif debit and debit > 0:
                amount = -debit
                t_type = "expense"
        elif amount_col:
            amount = _parse_amount(row.get(amount_col))
            if amount is None:
                continue
            t_type = "income" if amount > 0 else "expense"
        else:
            continue

        if amount is None:
            continue

        results.append({
            "date":             date_str,
            "description":      description,
            "amount":           amount,
            "merchant":         "",
            "location":         "",
            "transaction_type": t_type,
        })

    return results
