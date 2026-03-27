"""
PDF parser — extracts text with pdfplumber and searches for transaction rows.
Works with most Chilean bank cartolas (BCI, Santander, BancoEstado, Scotiabank, etc.)
The regex patterns cover the most common layouts.
Add new patterns to TRANSACTION_PATTERNS if your bank uses a different format.
"""

import io
import re
from datetime import datetime

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# Each pattern must have named groups: date, description, amount
# Optional groups: credit (positive amounts / incomes)
TRANSACTION_PATTERNS = [
    # Format: DD/MM/YYYY  Description  Amount (e.g., -1.234,56 or 1.234,56)
    re.compile(
        r"(?P<date>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<description>[A-Za-z0-9\s\.\-áéíóúÁÉÍÓÚñÑ,&'*#@]{3,60}?)\s+"
        r"(?P<amount>-?[\d\.]+,\d{2})",
        re.IGNORECASE,
    ),
    # Format: DD-MM-YYYY  Description  Amount
    re.compile(
        r"(?P<date>\d{2}-\d{2}-\d{4})\s+"
        r"(?P<description>[A-Za-z0-9\s\.\-áéíóúÁÉÍÓÚñÑ,&'*#@]{3,60}?)\s+"
        r"(?P<amount>-?[\d\.]+,\d{2})",
        re.IGNORECASE,
    ),
    # Format: DD/MM/YY ...
    re.compile(
        r"(?P<date>\d{2}/\d{2}/\d{2})\s+"
        r"(?P<description>[A-Za-z0-9\s\.\-áéíóúÁÉÍÓÚñÑ,&'*#@]{3,60}?)\s+"
        r"(?P<amount>-?[\d\.]+,\d{2})",
        re.IGNORECASE,
    ),
    # Format with debit/credit separated by spaces (some cartolas)
    re.compile(
        r"(?P<date>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<description>.{5,50}?)\s+"
        r"(?P<debit>[\d\.]+,\d{2})?\s*"
        r"(?P<credit>[\d\.]+,\d{2})?$",
        re.IGNORECASE | re.MULTILINE,
    ),
]


def _parse_date(raw: str) -> str | None:
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_chilean_amount(raw: str) -> float | None:
    """Converts '1.234,56' or '-1.234,56' to float."""
    s = raw.strip()
    negative = s.startswith("-")
    s = s.lstrip("-").replace(".", "").replace(",", ".")
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def parse(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse a PDF file (bank cartola) and return transaction dicts."""
    if not HAS_PDFPLUMBER:
        return []

    results = []
    seen = set()  # avoid duplicates from multi-column layouts

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"

                # Also try table extraction
                for table in page.extract_tables():
                    if not table:
                        continue
                    rows = _parse_table(table)
                    for row in rows:
                        key = (row["date"], row["description"], row["amount"])
                        if key not in seen:
                            seen.add(key)
                            results.append(row)

            # Regex fallback on full text
            regex_results = _parse_text(full_text)
            for row in regex_results:
                key = (row["date"], row["description"], row["amount"])
                if key not in seen:
                    seen.add(key)
                    results.append(row)

    except Exception:
        pass

    return results


def _parse_table(table: list[list]) -> list[dict]:
    """Try to extract transactions from a pdfplumber table."""
    if not table or len(table) < 2:
        return []

    results = []
    # Use first row as header
    header = [str(c or "").lower().strip() for c in table[0]]

    date_idx = _find_idx(header, ["fecha", "date", "dia"])
    desc_idx = _find_idx(header, ["descripcion", "glosa", "detalle", "description"])
    amount_idx = _find_idx(header, ["monto", "amount", "cargo", "abono"])
    debit_idx = _find_idx(header, ["cargo", "debito", "egreso"])
    credit_idx = _find_idx(header, ["abono", "credito", "ingreso"])

    if date_idx is None:
        return []

    for row in table[1:]:
        if not row or len(row) <= date_idx:
            continue

        date_raw = str(row[date_idx] or "").strip()
        date_str = _parse_date(date_raw)
        if not date_str:
            continue

        description = str(row[desc_idx] or "").strip() if desc_idx is not None else ""

        amount = None
        t_type = "expense"

        if debit_idx is not None and credit_idx is not None:
            debit_raw = str(row[debit_idx] or "").strip() if debit_idx < len(row) else ""
            credit_raw = str(row[credit_idx] or "").strip() if credit_idx < len(row) else ""
            debit = _parse_chilean_amount(debit_raw) if debit_raw else None
            credit = _parse_chilean_amount(credit_raw) if credit_raw else None
            if credit and credit > 0:
                amount = credit
                t_type = "income"
            elif debit and debit > 0:
                amount = -debit
                t_type = "expense"
        elif amount_idx is not None and amount_idx < len(row):
            amount = _parse_chilean_amount(str(row[amount_idx] or ""))
            if amount is not None:
                t_type = "income" if amount > 0 else "expense"

        if amount is not None:
            results.append({
                "date":             date_str,
                "description":      description,
                "amount":           amount,
                "merchant":         "",
                "location":         "",
                "transaction_type": t_type,
            })

    return results


def _parse_text(text: str) -> list[dict]:
    """Regex-based extraction from raw text."""
    results = []
    for pattern in TRANSACTION_PATTERNS:
        for match in pattern.finditer(text):
            d = match.groupdict()
            date_str = _parse_date(d.get("date", ""))
            if not date_str:
                continue

            description = (d.get("description") or "").strip()

            # Handle patterns with separate debit/credit groups
            if "debit" in d or "credit" in d:
                credit_raw = (d.get("credit") or "").strip()
                debit_raw = (d.get("debit") or "").strip()
                if credit_raw:
                    amount = _parse_chilean_amount(credit_raw)
                    t_type = "income"
                elif debit_raw:
                    amount = _parse_chilean_amount(debit_raw)
                    if amount:
                        amount = -abs(amount)
                    t_type = "expense"
                else:
                    continue
            else:
                amount = _parse_chilean_amount(d.get("amount", ""))
                if amount is None:
                    continue
                t_type = "income" if amount > 0 else "expense"

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


def _find_idx(header: list[str], candidates: list[str]) -> int | None:
    for i, col in enumerate(header):
        if any(c in col for c in candidates):
            return i
    return None
