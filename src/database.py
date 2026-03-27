"""
Database module — all SQLite access lives here.
To change the DB location, update DB_PATH.
To add a new field, add it to the schema and update the relevant functions.
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "finance.db"

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                type        TEXT    NOT NULL DEFAULT 'bank',
                balance     REAL    DEFAULT 0,
                currency    TEXT    DEFAULT 'CLP',
                color       TEXT    DEFAULT '#4CAF50',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                date             TEXT    NOT NULL,
                description      TEXT,
                amount           REAL    NOT NULL,
                category         TEXT    DEFAULT 'Otros',
                merchant         TEXT,
                location         TEXT,
                account_id       INTEGER,
                source_file      TEXT,
                transaction_type TEXT,
                notes            TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL UNIQUE,
                color    TEXT    DEFAULT '#888888',
                icon     TEXT    DEFAULT '📦',
                keywords TEXT    DEFAULT '[]'
            );
        """)
        _seed_categories(conn)


def _seed_categories(conn: sqlite3.Connection) -> None:
    defaults = [
        ("Alimentación",    "#FF6B6B", "🛒",
         ["supermercado", "almacen", "jumbo", "lider", "unimarc", "santa isabel",
          "tottus", "market", "minimarket", "restaurant", "comida", "cafe",
          "panaderia", "carniceria", "verduleria", "feria", "delivery"]),
        ("Transporte",      "#4ECDC4", "🚌",
         ["bip", "metro", "uber", "cabify", "bolt", "taxi", "bus", "tren",
          "combustible", "bencina", "copec", "shell", "petroplus", "gasolina"]),
        ("Salud",           "#45B7D1", "🏥",
         ["farmacia", "clinica", "hospital", "medico", "doctor", "salud",
          "cruz verde", "ahumada", "salcobrand", "dental", "oftalmolog"]),
        ("Entretenimiento", "#96CEB4", "🎭",
         ["cine", "teatro", "netflix", "spotify", "amazon", "apple", "gaming",
          "juego", "bar", "pub", "disco", "steam"]),
        ("Servicios",       "#F0C040", "💡",
         ["luz", "agua", "gas", "internet", "telefono", "celular", "entel",
          "movistar", "claro", "wom", "vtr", "enel", "aguas andinas"]),
        ("Hogar",           "#DDA0DD", "🏠",
         ["arriendo", "renta", "muebles", "electrodomestico", "sodimac",
          "easy", "ferreteria", "mejoras", "pinturas"]),
        ("Ropa",            "#F0E68C", "👗",
         ["falabella", "ripley", "paris", "zara", "hm", "ropa", "calzado",
          "zapato", "zapatilla", "vestido"]),
        ("Educación",       "#87CEEB", "📚",
         ["colegio", "universidad", "curso", "libro", "instituto", "clases",
          "matricula", "mensualidad"]),
        ("Banco",           "#D3D3D3", "💰",
         ["comision", "cargo", "interes", "cuota", "seguro", "mantencion"]),
        ("Ingresos",        "#90EE90", "💵",
         ["sueldo", "salario", "honorario", "pago", "deposito",
          "transferencia recibida", "abono"]),
        ("Otros",           "#C0C0C0", "📦", []),
    ]
    for name, color, icon, keywords in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name, color, icon, keywords) VALUES (?,?,?,?)",
            (name, color, icon, json.dumps(keywords, ensure_ascii=False))
        )


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def get_categories() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM categories ORDER BY name", conn)


def get_category_map() -> dict:
    """Returns {name: {color, icon, keywords}} for quick lookups."""
    df = get_categories()
    result = {}
    for _, row in df.iterrows():
        result[row["name"]] = {
            "color":    row["color"],
            "icon":     row["icon"],
            "keywords": json.loads(row["keywords"] or "[]"),
        }
    return result


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def get_accounts() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM accounts ORDER BY name", conn)


def insert_account(name: str, account_type: str, balance: float,
                   currency: str, color: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO accounts (name, type, balance, currency, color) VALUES (?,?,?,?,?)",
            (name, account_type, balance, currency, color)
        )


def update_account(account_id: int, name: str, account_type: str,
                   balance: float, currency: str, color: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE accounts SET name=?, type=?, balance=?, currency=?, color=? WHERE id=?",
            (name, account_type, balance, currency, color, account_id)
        )


def delete_account(account_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def get_transactions(
    start_date=None,
    end_date=None,
    category: str = None,
    account_id: int = None,
    transaction_type: str = None,
) -> pd.DataFrame:
    conditions = ["1=1"]
    params: list = []

    if start_date:
        conditions.append("date >= ?")
        params.append(str(start_date))
    if end_date:
        conditions.append("date <= ?")
        params.append(str(end_date))
    if category:
        conditions.append("category = ?")
        params.append(category)
    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    if transaction_type:
        conditions.append("transaction_type = ?")
        params.append(transaction_type)

    sql = f"SELECT * FROM transactions WHERE {' AND '.join(conditions)} ORDER BY date DESC"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def insert_transaction(
    date: str,
    description: str,
    amount: float,
    category: str,
    merchant: str,
    location: str,
    account_id,
    source_file: str,
    transaction_type: str,
    notes: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO transactions
               (date, description, amount, category, merchant, location,
                account_id, source_file, transaction_type, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (date, description, amount, category, merchant, location,
             account_id, source_file, transaction_type, notes)
        )


def insert_transactions_batch(rows: list[dict]) -> int:
    """Insert many transactions at once. Returns number inserted."""
    if not rows:
        return 0
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO transactions
               (date, description, amount, category, merchant, location,
                account_id, source_file, transaction_type, notes)
               VALUES (:date,:description,:amount,:category,:merchant,:location,
                       :account_id,:source_file,:transaction_type,:notes)""",
            rows
        )
    return len(rows)


def update_transaction(transaction_id: int, **kwargs) -> None:
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [transaction_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE transactions SET {fields} WHERE id=?", values)


def delete_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))


def delete_all_transactions() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions")


# ---------------------------------------------------------------------------
# Summary / Aggregations
# ---------------------------------------------------------------------------

def get_summary(start_date=None, end_date=None) -> dict:
    conditions = ["1=1"]
    params: list = []

    if start_date:
        conditions.append("date >= ?")
        params.append(str(start_date))
    if end_date:
        conditions.append("date <= ?")
        params.append(str(end_date))

    where = " AND ".join(conditions)

    with get_connection() as conn:
        income = conn.execute(
            f"SELECT COALESCE(SUM(amount),0) FROM transactions WHERE {where} AND transaction_type='income'",
            params
        ).fetchone()[0]

        expenses = conn.execute(
            f"SELECT COALESCE(SUM(ABS(amount)),0) FROM transactions WHERE {where} AND transaction_type='expense'",
            params
        ).fetchone()[0]

    balance = income - expenses
    savings_rate = (balance / income * 100) if income > 0 else 0.0

    return {
        "income":       float(income),
        "expenses":     float(expenses),
        "balance":      float(balance),
        "savings_rate": float(savings_rate),
    }


def get_monthly_summary() -> pd.DataFrame:
    sql = """
        SELECT
            substr(date,1,7)   AS month,
            transaction_type,
            SUM(ABS(amount))   AS total
        FROM transactions
        GROUP BY month, transaction_type
        ORDER BY month
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def get_category_summary(start_date=None, end_date=None) -> pd.DataFrame:
    conditions = ["transaction_type = 'expense'"]
    params: list = []
    if start_date:
        conditions.append("date >= ?")
        params.append(str(start_date))
    if end_date:
        conditions.append("date <= ?")
        params.append(str(end_date))
    where = " AND ".join(conditions)
    sql = f"""
        SELECT category, SUM(ABS(amount)) AS total, COUNT(*) AS count
        FROM transactions
        WHERE {where}
        GROUP BY category
        ORDER BY total DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_merchant_summary(start_date=None, end_date=None, top_n: int = 15) -> pd.DataFrame:
    conditions = ["transaction_type = 'expense'", "merchant IS NOT NULL", "merchant != ''"]
    params: list = []
    if start_date:
        conditions.append("date >= ?")
        params.append(str(start_date))
    if end_date:
        conditions.append("date <= ?")
        params.append(str(end_date))
    where = " AND ".join(conditions)
    sql = f"""
        SELECT merchant, SUM(ABS(amount)) AS total, COUNT(*) AS count
        FROM transactions
        WHERE {where}
        GROUP BY merchant
        ORDER BY total DESC
        LIMIT {top_n}
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)
