"""
Generates realistic demo transactions for testing the dashboard.
Call generate_demo_data() to populate the DB with sample data.
"""

import random
from datetime import date, timedelta

from src.database import delete_all_transactions, insert_account, get_accounts, insert_transactions_batch
from src.categorizer import categorize

MERCHANTS = [
    ("Jumbo Las Condes",        "Alimentación", "Las Condes",    -38000),
    ("Unimarc Providencia",     "Alimentación", "Providencia",   -15000),
    ("McDonald's",              "Alimentación", "Centro",         -5900),
    ("Uber Eats Delivery",      "Alimentación", "Online",         -9800),
    ("Farmacia Cruz Verde",     "Salud",        "Ñuñoa",          -8500),
    ("Clínica Dávila",          "Salud",        "Recoleta",      -45000),
    ("Metro Santiago",          "Transporte",   "Santiago",         -800),
    ("Uber Trip",               "Transporte",   "Santiago",        -4200),
    ("Copec Bencina",           "Transporte",   "Pudahuel",       -55000),
    ("Netflix",                 "Entretenimiento", "Online",       -8990),
    ("Spotify",                 "Entretenimiento", "Online",       -4999),
    ("Cine Hoyts",              "Entretenimiento", "Mall",         -6500),
    ("Enel Distribución",       "Servicios",    "Online",         -35000),
    ("VTR Internet",            "Servicios",    "Online",         -28000),
    ("Movistar Móvil",          "Servicios",    "Online",         -19990),
    ("Sodimac",                 "Hogar",        "Maipú",          -62000),
    ("Falabella Ropa",          "Ropa",         "Parque Arauco",  -35000),
    ("Universidad de Chile",    "Educación",    "Santiago",       -95000),
    ("Starbucks",               "Alimentación", "Providencia",     -4500),
    ("Almacén La Abundancia",   "Alimentación", "Barrio",          -3200),
    ("Red Bull Energética",     "Alimentación", "Tienda",          -1890),
    ("Pan de Yema Panadería",   "Alimentación", "Local",           -1200),
    ("Pizza Hut",               "Alimentación", "Delivery",        -12500),
    ("Farmacia Salcobrand",     "Salud",        "Centro",          -6700),
    ("Easy Hogar",              "Hogar",        "Pudahuel",        -42000),
]

INCOMES = [
    ("Sueldo Empresa XYZ",   1_800_000),
    ("Honorarios Freelance",   350_000),
    ("Transferencia Recibida", 120_000),
]


def generate_demo_data(months: int = 3) -> None:
    """Clears existing transactions and inserts demo data for `months` months."""
    delete_all_transactions()

    # Ensure at least one account exists
    accounts = get_accounts()
    if accounts.empty:
        insert_account("Banco BCI", "bank", 1_250_000, "CLP", "#1565C0")
        insert_account("Efectivo", "cash", 85_000, "CLP", "#2E7D32")
        accounts = get_accounts()

    account_id = int(accounts.iloc[0]["id"])
    rows = []
    today = date.today()

    for m in range(months - 1, -1, -1):
        # Pick a month
        first = (today.replace(day=1) - timedelta(days=30 * m)).replace(day=1)
        last_day = (first.replace(month=first.month % 12 + 1, day=1) - timedelta(days=1)
                    if first.month < 12
                    else first.replace(month=12, day=31))

        # Income on day 1 and 15
        for inc_day, (desc, amount) in [(1, INCOMES[0]), (15, INCOMES[1])]:
            d = first.replace(day=min(inc_day, last_day.day))
            rows.append(_make_row(d, desc, amount, "Ingresos", desc, "", account_id, "demo", "income"))

        # Random expenses throughout the month
        num_expenses = random.randint(25, 40)
        for _ in range(num_expenses):
            day = random.randint(1, last_day.day)
            d = first.replace(day=day)
            merchant_info = random.choice(MERCHANTS)
            name, cat, loc, base_amount = merchant_info
            amount = base_amount * random.uniform(0.85, 1.2)
            amount = round(amount / 100) * 100  # round to nearest 100
            rows.append(_make_row(d, name, amount, cat, name, loc, account_id, "demo", "expense"))

    insert_transactions_batch(rows)


def _make_row(d, description, amount, category, merchant, location,
              account_id, source_file, transaction_type) -> dict:
    return {
        "date":             str(d),
        "description":      description,
        "amount":           float(amount),
        "category":         category,
        "merchant":         merchant,
        "location":         location,
        "account_id":       account_id,
        "source_file":      source_file,
        "transaction_type": transaction_type,
        "notes":            "",
    }
