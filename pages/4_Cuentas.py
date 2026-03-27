"""
Page: Cuentas
Manage bank accounts and cash.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    init_db, get_accounts, insert_account,
    update_account, delete_account,
)

st.set_page_config(page_title="Cuentas", page_icon="🏦", layout="wide")
init_db()

st.title("🏦 Mis Cuentas")
st.caption("Administra tus cuentas bancarias, efectivo y tarjetas")

ACCOUNT_TYPES = {"bank": "🏦 Banco", "cash": "💵 Efectivo", "credit": "💳 Crédito", "investment": "📈 Inversión"}
CURRENCIES = ["CLP", "USD", "EUR", "UF"]
COLORS = {
    "Azul":     "#1565C0",
    "Verde":    "#2E7D32",
    "Rojo":     "#C62828",
    "Naranja":  "#E65100",
    "Morado":   "#6A1B9A",
    "Gris":     "#455A64",
    "Dorado":   "#F9A825",
    "Cian":     "#00838F",
}

# ---------------------------------------------------------------------------
# Current accounts
# ---------------------------------------------------------------------------
accounts = get_accounts()

if accounts.empty:
    st.info("No tienes cuentas registradas. Agrega una a continuación.")
else:
    st.subheader("Cuentas Registradas")
    total_clp = accounts[accounts["currency"] == "CLP"]["balance"].sum()
    st.metric("💼 Patrimonio Total (CLP)", f"${total_clp:,.0f}")

    cols = st.columns(min(len(accounts), 3))
    for i, (_, acc) in enumerate(accounts.iterrows()):
        type_label = ACCOUNT_TYPES.get(acc["type"], acc["type"])
        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="
                    background-color: {acc['color']};
                    padding: 20px;
                    border-radius: 12px;
                    color: white;
                    margin-bottom: 10px;
                ">
                    <h3 style="margin:0; color:white">{type_label}</h3>
                    <h2 style="margin:5px 0; color:white">{acc['name']}</h2>
                    <h1 style="margin:0; color:white">${acc['balance']:,.0f} {acc['currency']}</h1>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("---")

# ---------------------------------------------------------------------------
# Add account
# ---------------------------------------------------------------------------
with st.expander("➕ Agregar nueva cuenta", expanded=accounts.empty):
    with st.form("add_account"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Nombre de la cuenta", placeholder="Ej: BCI Vista, Efectivo")
            acc_type = st.selectbox("Tipo", list(ACCOUNT_TYPES.keys()),
                                    format_func=lambda x: ACCOUNT_TYPES[x])
            balance = st.number_input("Saldo actual", value=0.0, step=1000.0)
        with c2:
            currency = st.selectbox("Moneda", CURRENCIES)
            color_name = st.selectbox("Color de tarjeta", list(COLORS.keys()))
            color = COLORS[color_name]
            st.markdown(
                f'<div style="background:{color};height:40px;border-radius:8px;"></div>',
                unsafe_allow_html=True
            )

        if st.form_submit_button("Agregar cuenta", type="primary"):
            if not name.strip():
                st.error("El nombre no puede estar vacío.")
            else:
                insert_account(name.strip(), acc_type, balance, currency, color)
                st.success(f"Cuenta '{name}' agregada")
                st.rerun()

# ---------------------------------------------------------------------------
# Edit / Delete account
# ---------------------------------------------------------------------------
if not accounts.empty:
    st.markdown("---")
    st.subheader("✏️ Editar / Eliminar Cuenta")

    acc_options = {f"{r['name']} ({r['type']})": r["id"] for _, r in accounts.iterrows()}
    selected_label = st.selectbox("Selecciona una cuenta", list(acc_options.keys()))
    selected_id = acc_options[selected_label]
    acc_row = accounts[accounts["id"] == selected_id].iloc[0]

    with st.form("edit_account"):
        c1, c2 = st.columns(2)
        with c1:
            e_name = st.text_input("Nombre", value=acc_row["name"])
            e_type = st.selectbox(
                "Tipo", list(ACCOUNT_TYPES.keys()),
                index=list(ACCOUNT_TYPES.keys()).index(acc_row["type"])
                if acc_row["type"] in ACCOUNT_TYPES else 0,
                format_func=lambda x: ACCOUNT_TYPES[x]
            )
            e_balance = st.number_input("Saldo", value=float(acc_row["balance"]), step=1000.0)
        with c2:
            e_currency = st.selectbox(
                "Moneda", CURRENCIES,
                index=CURRENCIES.index(acc_row["currency"]) if acc_row["currency"] in CURRENCIES else 0
            )
            e_color_name = st.selectbox("Color", list(COLORS.keys()))
            e_color = COLORS[e_color_name]

        col_save, col_del = st.columns([3, 1])
        with col_save:
            if st.form_submit_button("Guardar cambios", type="primary"):
                update_account(selected_id, e_name, e_type, e_balance, e_currency, e_color)
                st.success("Cuenta actualizada")
                st.rerun()
        with col_del:
            if st.form_submit_button("🗑️ Eliminar"):
                delete_account(selected_id)
                st.success("Cuenta eliminada")
                st.rerun()
