"""
AI-style fuzzy search for transactions.
Supports:
  - Fuzzy text matching on description, merchant, category, location
  - Natural language date filters ("marzo", "enero 2024")
  - Amount filters ("> 5000", "< 20000", "= 10000")
  - Combined: "energetica marzo > 2000"
"""

import re
import unicodedata
from datetime import date, datetime

import pandas as pd

try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# Month name → number (Spanish + English)
MONTH_NAMES = {
    "enero": 1, "january": 1, "jan": 1,
    "febrero": 2, "february": 2, "feb": 2,
    "marzo": 3, "march": 3, "mar": 3,
    "abril": 4, "april": 4, "apr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "june": 6, "jun": 6,
    "julio": 7, "july": 7, "jul": 7,
    "agosto": 8, "august": 8, "aug": 8,
    "septiembre": 9, "september": 9, "sep": 9, "sept": 9,
    "octubre": 10, "october": 10, "oct": 10,
    "noviembre": 11, "november": 11, "nov": 11,
    "diciembre": 12, "december": 12, "dec": 12,
}


def _normalize(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _extract_month_filter(tokens: list[str]) -> tuple[int | None, int | None]:
    """Returns (month_number, year) extracted from tokens, or (None, None)."""
    month = None
    year = None
    for token in tokens:
        if token in MONTH_NAMES:
            month = MONTH_NAMES[token]
        elif re.match(r"^\d{4}$", token):
            year = int(token)
    return month, year


def _extract_amount_filter(tokens: list[str]) -> tuple[str | None, float | None]:
    """Returns (operator, amount) like ('>', 5000.0) or (None, None)."""
    for i, token in enumerate(tokens):
        if token in (">", "<", "=", ">=", "<="):
            # Next token should be a number
            if i + 1 < len(tokens):
                raw = tokens[i + 1].replace(".", "").replace(",", ".")
                try:
                    return token, float(raw)
                except ValueError:
                    pass
        # Combined like ">5000"
        m = re.match(r"^(>=|<=|>|<|=)(\d[\d.,]*)$", token)
        if m:
            raw = m.group(2).replace(".", "").replace(",", ".")
            try:
                return m.group(1), float(raw)
            except ValueError:
                pass
    return None, None


def search_transactions(df: pd.DataFrame, query: str, threshold: int = 55) -> pd.DataFrame:
    """
    Main search function.
    - df: DataFrame from get_transactions() (all transactions)
    - query: free-text search string
    - threshold: fuzzy match score 0-100 (lower = more permissive)
    Returns filtered + scored DataFrame, sorted by relevance.
    """
    if df.empty or not query.strip():
        return df

    raw_tokens = _normalize(query).split()

    # Extract structured filters from tokens
    month, year = _extract_month_filter(raw_tokens)
    op, amount_val = _extract_amount_filter(raw_tokens)

    # Text tokens are what's left after removing month/year/amount filters
    skip = set()
    if month is not None:
        for t in raw_tokens:
            if t in MONTH_NAMES:
                skip.add(t)
    if year is not None:
        for t in raw_tokens:
            if re.match(r"^\d{4}$", t):
                skip.add(t)
    if op is not None:
        for t in raw_tokens:
            if t in (">", "<", "=", ">=", "<=") or re.match(r"^(>=|<=|>|<|=)\d", t):
                skip.add(t)
            elif re.match(r"^\d[\d.,]*$", t):
                skip.add(t)

    text_tokens = [t for t in raw_tokens if t not in skip]
    text_query = " ".join(text_tokens)

    # Apply structured filters first
    result = df.copy()

    if month is not None:
        result = result[pd.to_datetime(result["date"], errors="coerce").dt.month == month]
    if year is not None:
        result = result[pd.to_datetime(result["date"], errors="coerce").dt.year == year]
    if op is not None and amount_val is not None:
        abs_amounts = result["amount"].abs()
        if op == ">":
            result = result[abs_amounts > amount_val]
        elif op == ">=":
            result = result[abs_amounts >= amount_val]
        elif op == "<":
            result = result[abs_amounts < amount_val]
        elif op == "<=":
            result = result[abs_amounts <= amount_val]
        elif op == "=":
            result = result[(abs_amounts - amount_val).abs() < 1]

    if result.empty:
        return result

    # If no text query remains, return the filtered results
    if not text_query:
        return result

    # Fuzzy text matching
    def score_row(row) -> int:
        combined = _normalize(" ".join([
            str(row.get("description", "") or ""),
            str(row.get("merchant", "") or ""),
            str(row.get("category", "") or ""),
            str(row.get("location", "") or ""),
        ]))
        if not combined:
            return 0
        if HAS_RAPIDFUZZ:
            return max(
                fuzz.partial_ratio(text_query, combined),
                fuzz.token_set_ratio(text_query, combined),
            )
        else:
            # Fallback: simple substring check
            return 100 if text_query in combined else 0

    result = result.copy()
    result["_score"] = result.apply(score_row, axis=1)
    result = result[result["_score"] >= threshold]
    result = result.sort_values("_score", ascending=False).drop(columns=["_score"])

    return result


def format_search_result(row: pd.Series) -> str:
    """Formats a single result row as a human-readable string."""
    date_str = str(row.get("date", ""))[:10]
    desc = row.get("description", "") or ""
    merchant = row.get("merchant", "") or ""
    amount = abs(row.get("amount", 0))
    category = row.get("category", "") or ""
    t_type = row.get("transaction_type", "expense")

    sign = "+" if t_type == "income" else "-"
    name = merchant if merchant else desc

    return f"**{name}** — {date_str} — {sign}${amount:,.0f} CLP [{category}]"
