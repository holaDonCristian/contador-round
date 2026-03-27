"""
CSV parser — handles bank statement CSVs in various formats.
Tries to auto-detect columns for date, description, amount (debit/credit).
"""

import io
import re
import unicodedata
from datetime import datetime

import pandas as pd


def _norm_col(col: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(col).lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Candidate column names for each field
DATE_COLS = {"fecha", "date", "fecha operacion", "fecha transaccion", "fec", "dia"}
DESC_COLS = {"descripcion", "description", "detalle", "glosa", "concepto", "nombre", "comercio"}
AMOUNT_COLS = {"monto", "amount", "importe", "valor", "cargo", "abono", "debito", "credito"}
DEBIT_COLS = {"cargo", "debito", "egreso", "monto cargo", "gasto"}
CREDIT_COLS = {"abono", "credito", "ingreso", "monto abono"}


def _find_col(df: pd.DataFrame, candidates: set) -> str | None:
    for col in df.columns:
        if _norm_col(col) in candidates:
            return col
    return None


def _parse_amount(value) -> float | None:
    if pd.isna(value):
        return None
    s = str(value).strip().replace(" ", "")
    # Remove currency symbols and thousand separators, normalise decimal
    s = re.sub(r"[^\d,.\-]", "", s)
    s = s.replace(".", "").replace(",", ".")  # Chilean format 1.234,56 → 1234.56
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(value) -> str | None:
    raw = str(value).strip()
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y",
        "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse a CSV file and return a list of transaction dicts."""
    results = []

    # Try different encodings and separators
    for encoding in ("utf-8-sig", "latin-1", "utf-8"):
        for sep in (",", ";", "\t", "|"):
            try:
                df = pd.read_csv(
                    io.BytesIO(file_bytes),
                    sep=sep,
                    encoding=encoding,
                    dtype=str,
                    skip_blank_lines=True,
                )
                if len(df.columns) >= 2:
                    break
            except Exception:
                continue
        else:
            continue
        break
    else:
        return []

    df.columns = [str(c).strip() for c in df.columns]

    date_col = _find_col(df, DATE_COLS)
    desc_col = _find_col(df, DESC_COLS)
    amount_col = _find_col(df, AMOUNT_COLS)
    debit_col = _find_col(df, DEBIT_COLS)
    credit_col = _find_col(df, CREDIT_COLS)

    if not date_col:
        return []  # Cannot parse without a date column

    for _, row in df.iterrows():
        date_str = _parse_date(row.get(date_col, ""))
        if not date_str:
            continue

        description = str(row.get(desc_col, "")).strip() if desc_col else ""

        # Determine amount and type
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
