"""
Page: Transacciones
View, filter, edit and delete individual transactions.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    init_db, get_transactions, get_categories, get_accounts,
    update_transaction, delete_transaction, insert_transaction,
)

st.set_page_config(page_title="Transacciones", page_icon="💳", layout="wide")
init_db()

st.title("💳 Transacciones")

# ---------------------------------------------------------------------------
# Filters sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Filtros")

    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Desde", value=today.replace(day=1))
    with col2:
        end = st.date_input("Hasta", value=today)

    categories = get_categories()
    cat_options = ["Todas"] + list(categories["name"])
    selected_cat = st.selectbox("Categoría", cat_options)

    type_options = {"Todas": None, "Ingresos": "income", "Gastos": "expense"}
    selected_type_label = st.selectbox("Tipo", list(type_options.keys()))
    selected_type = type_options[selected_type_label]

# ---------------------------------------------------------------------------
# Fetch data
# ---------------------------------------------------------------------------
df = get_transactions(
    start_date=start,
    end_date=end,
    category=None if selected_cat == "Todas" else selected_cat,
    transaction_type=selected_type,
)

# ---------------------------------------------------------------------------
# Summary strip
# ---------------------------------------------------------------------------
if not df.empty:
    income = df[df["transaction_type"] == "income"]["amount"].sum()
    expenses = df[df["transaction_type"] == "expense"]["amount"].abs().sum()
    balance = income - expenses

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", len(df))
    c2.metric("Ingresos", f"${income:,.0f}")
    c3.metric("Gastos", f"${expenses:,.0f}")
    c4.metric("Balance", f"${balance:,.0f}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Add transaction manually
# ---------------------------------------------------------------------------
with st.expander("➕ Agregar transacción manual"):
    accounts = get_accounts()
    acc_map = {f"{r['name']}": r["id"] for _, r in accounts.iterrows()} if not accounts.empty else {}

    with st.form("add_txn"):
        c1, c2 = st.columns(2)
        with c1:
            new_date = st.date_input("Fecha", value=date.today())
            new_desc = st.text_input("Descripción")
            new_merchant = st.text_input("Comercio / Lugar")
        with c2:
            new_amount = st.number_input("Monto (positivo=ingreso, negativo=gasto)", value=0.0, step=1000.0)
            new_cat = st.selectbox("Categoría", list(categories["name"]))
            new_type = st.selectbox("Tipo", ["expense", "income"])
            new_account = st.selectbox("Cuenta", list(acc_map.keys()) or ["Sin cuenta"])

        if st.form_submit_button("Agregar", type="primary"):
            insert_transaction(
                date=str(new_date),
                description=new_desc,
                amount=new_amount,
                category=new_cat,
                merchant=new_merchant,
                location="",
                account_id=acc_map.get(new_account),
                source_file="manual",
                transaction_type=new_type,
                notes="",
            )
            st.success("Transacción agregada")
            st.rerun()

# ---------------------------------------------------------------------------
# Transaction table
# ---------------------------------------------------------------------------
if df.empty:
    st.info("No hay transacciones para el período seleccionado.")
else:
    color_map = dict(zip(categories["name"], categories["color"]))

    display = df.copy()
    display["date"] = pd.to_datetime(display["date"], errors="coerce").dt.strftime("%d/%m/%Y")
    display["Monto"] = display.apply(
        lambda r: f"+${r['amount']:,.0f}" if r["transaction_type"] == "income"
                  else f"-${abs(r['amount']):,.0f}", axis=1
    )

    show_cols = ["id", "date", "description", "merchant", "location", "category", "Monto", "source_file"]
    available = [c for c in show_cols if c in display.columns]
    display = display[available]
    display.columns = ["ID", "Fecha", "Descripción", "Comercio", "Lugar", "Categoría", "Monto", "Fuente"][: len(available)]

    st.dataframe(display, use_container_width=True, hide_index=True)

    # --- Edit / Delete ---
    st.markdown("---")
    st.subheader("✏️ Editar / Eliminar")
    txn_ids = df["id"].tolist()
    if txn_ids:
        selected_id = st.selectbox("ID de transacción", txn_ids)
        row = df[df["id"] == selected_id].iloc[0]

        col_edit, col_del = st.columns([3, 1])

        with col_edit:
            with st.form("edit_form"):
                e_date = st.date_input("Fecha", value=pd.to_datetime(row["date"]).date())
                e_desc = st.text_input("Descripción", value=row.get("description", "") or "")
                e_merchant = st.text_input("Comercio", value=row.get("merchant", "") or "")
                e_location = st.text_input("Lugar", value=row.get("location", "") or "")
                e_cat = st.selectbox("Categoría", list(categories["name"]),
                                     index=list(categories["name"]).index(row["category"])
                                     if row["category"] in list(categories["name"]) else 0)
                e_amount = st.number_input("Monto", value=float(row["amount"]))
                e_type = st.selectbox("Tipo", ["expense", "income"],
                                      index=0 if row["transaction_type"] == "expense" else 1)
                e_notes = st.text_area("Notas", value=row.get("notes", "") or "")

                if st.form_submit_button("Guardar cambios", type="primary"):
                    update_transaction(
                        selected_id,
                        date=str(e_date),
                        description=e_desc,
                        merchant=e_merchant,
                        location=e_location,
                        category=e_cat,
                        amount=e_amount,
                        transaction_type=e_type,
                        notes=e_notes,
                    )
                    st.success("Guardado")
                    st.rerun()

        with col_del:
            st.markdown("<br><br><br><br><br><br>", unsafe_allow_html=True)
            if st.button("🗑️ Eliminar", type="secondary", use_container_width=True):
                delete_transaction(selected_id)
                st.success("Eliminada")
                st.rerun()
