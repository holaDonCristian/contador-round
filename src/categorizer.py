"""
Automatic transaction categorizer.
Uses keyword matching (case-insensitive, accent-insensitive).
To add keywords, update the categories table in the DB or edit _seed_categories in database.py.
"""

import json
import unicodedata


def _normalize(text: str) -> str:
    """Lowercase + remove accents for comparison."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def categorize(description: str, merchant: str = "", category_map: dict = None) -> str:
    """
    Returns the best matching category name for a transaction.
    category_map: {name: {keywords: [...], ...}} — pass the result of db.get_category_map()
    Falls back to 'Otros' if nothing matches.
    """
    if category_map is None:
        from src.database import get_category_map
        category_map = get_category_map()

    text = _normalize(f"{description} {merchant}")

    # Check 'Ingresos' first — if it looks like income, skip expense categories
    income_keywords = category_map.get("Ingresos", {}).get("keywords", [])
    for kw in income_keywords:
        if _normalize(kw) in text:
            return "Ingresos"

    # Check all other categories
    for cat_name, cat_data in category_map.items():
        if cat_name in ("Ingresos", "Otros"):
            continue
        for kw in cat_data.get("keywords", []):
            if _normalize(kw) in text:
                return cat_name

    return "Otros"


def detect_transaction_type(amount: float, description: str = "") -> str:
    """
    Returns 'income' or 'expense' based on amount sign and description hints.
    Parsers should call this when they cannot determine the type from file structure.
    """
    desc_lower = _normalize(description)
    income_hints = ["abono", "deposito", "sueldo", "salario", "honorario",
                    "transferencia recibida", "pago recibido", "ingreso"]

    if amount > 0:
        for hint in income_hints:
            if hint in desc_lower:
                return "income"
        # Positive amounts in bank statements are usually income
        return "income"

    return "expense"


def extract_merchant(description: str) -> tuple[str, str]:
    """
    Attempts to split a raw description into (merchant, location).
    Returns (merchant, location) — location may be empty.
    Many bank cartolas have formats like:
      "COMPRA JUMBO LAS CONDES"
      "PAGO UBER *TRIP SANTIAGO"
    """
    if not description:
        return ("", "")

    # Strip common prefixes
    prefixes = [
        "compra en ", "compra ", "pago a ", "pago ", "cargo ",
        "debito ", "credito ", "transferencia a ", "transferencia ",
    ]
    text = description.strip()
    text_lower = text.lower()

    for prefix in prefixes:
        if text_lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    # Many descriptions end with a city/location separated by space
    # Heuristic: last word(s) that look like a location
    parts = text.split()
    if len(parts) >= 3:
        merchant = " ".join(parts[:-1])
        location = parts[-1]
    else:
        merchant = text
        location = ""

    return (merchant.title(), location.title())
