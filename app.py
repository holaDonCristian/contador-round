"""
Finance Dashboard — Main Page (Home / Resumen)
Run with: streamlit run app.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.database import (
    init_db,
    get_summary,
    get_transactions,
    get_accounts,
    get_categories,
    get_category_summary,
    get_monthly_summary,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Finance Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Bootstrap DB
# ---------------------------------------------------------------------------
init_db()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt(amount: float) -> str:
    return f"${amount:,.0f}"


def date_range_to_dates(label: str) -> tuple:
    today = date.today()
    first = today.replace(day=1)
    if label == "Este mes":
        return first, today
    if label == "Mes anterior":
        last = first - timedelta(days=1)
        return last.replace(day=1), last
    if label == "Últimos 3 meses":
        return (today - timedelta(days=90)).replace(day=1), today
    if label == "Este año":
        return today.replace(month=1, day=1), today
    return None, None  # "Todo"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/money-bag.png", width=60)
st.sidebar.title("Finance Dashboard")
st.sidebar.caption("Auditoría Financiera Personal")
st.sidebar.markdown("---")

period = st.sidebar.selectbox(
    "Período",
    ["Este mes", "Mes anterior", "Últimos 3 meses", "Este año", "Todo"],
)
start_date, end_date = date_range_to_dates(period)

st.sidebar.markdown("---")
if st.sidebar.button("🧪 Cargar datos de prueba", help="Genera datos de ejemplo para explorar el dashboard"):
    from src.demo_data import generate_demo_data
    with st.spinner("Generando datos de demostración..."):
        generate_demo_data(months=4)
    st.sidebar.success("✅ Datos cargados")
    st.rerun()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📊 Dashboard Financiero Personal")
st.caption(f"Período: **{period}**")

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
summary = get_summary(start_date, end_date)

col1, col2, col3, col4 = st.columns(4)
col1.metric("💵 Ingresos",    fmt(summary["income"]))
col2.metric("💸 Gastos",      fmt(summary["expenses"]))
col3.metric("💳 Balance",     fmt(summary["balance"]),
            delta=fmt(summary["balance"]))
col4.metric("🐷 Tasa Ahorro", f"{summary['savings_rate']:.1f}%")

st.markdown("---")

# ---------------------------------------------------------------------------
# Charts row
# ---------------------------------------------------------------------------
df = get_transactions(start_date, end_date)

if df.empty:
    st.info(
        "No hay transacciones para mostrar.\n\n"
        "👉 Ve a **Cargar Archivos** para importar tus cartolas, "
        "o usa el botón **Cargar datos de prueba** en el panel izquierdo."
    )
else:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["month"] = df["date"].dt.to_period("M").astype(str)

    col_l, col_r = st.columns([3, 2])

    # --- Monthly bar chart ---
    with col_l:
        monthly = get_monthly_summary()
        if not monthly.empty:
            income_m = monthly[monthly["transaction_type"] == "income"]
            expense_m = monthly[monthly["transaction_type"] == "expense"]

            fig = go.Figure()
            if not income_m.empty:
                fig.add_trace(go.Bar(
                    name="Ingresos",
                    x=income_m["month"], y=income_m["total"],
                    marker_color="#38ef7d",
                ))
            if not expense_m.empty:
                fig.add_trace(go.Bar(
                    name="Gastos",
                    x=expense_m["month"], y=expense_m["total"],
                    marker_color="#f45c43",
                ))
            fig.update_layout(
                title="Ingresos vs Gastos por Mes",
                barmode="group",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=350,
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- Category donut ---
    with col_r:
        cat_summary = get_category_summary(start_date, end_date)
        cats_df = get_categories()
        color_map = dict(zip(cats_df["name"], cats_df["color"]))

        if not cat_summary.empty:
            colors = [color_map.get(c, "#888888") for c in cat_summary["category"]]
            fig_pie = go.Figure(go.Pie(
                labels=cat_summary["category"],
                values=cat_summary["total"],
                hole=0.45,
                marker_colors=colors,
                textinfo="label+percent",
                hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
            ))
            fig_pie.update_layout(
                title="Gastos por Categoría",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=350,
                margin=dict(l=0, r=0, t=40, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # --- Savings progress bar ---
    sr = summary["savings_rate"]
    target = 20.0  # 20% savings goal
    st.subheader("🎯 Meta de Ahorro")
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.progress(min(sr / 100, 1.0), text=f"Ahorro actual: {sr:.1f}% — Meta: {target}%")
    with col_b:
        if sr >= target:
            st.success(f"¡Meta cumplida!")
        else:
            st.warning(f"Faltan {target - sr:.1f}%")

    st.markdown("---")

    # --- Accounts summary ---
    accounts = get_accounts()
    if not accounts.empty:
        st.subheader("🏦 Resumen de Cuentas")
        cols = st.columns(min(len(accounts), 4))
        for i, (_, acc) in enumerate(accounts.iterrows()):
            icon = {"bank": "🏦", "cash": "💵", "credit": "💳"}.get(acc["type"], "💰")
            cols[i % 4].metric(
                f"{icon} {acc['name']}",
                fmt(acc["balance"]),
                delta=f"{acc['currency']}",
            )

        st.markdown("---")

    # --- Recent transactions ---
    st.subheader("🕐 Últimas Transacciones")
    recent = df.head(20).copy()
    recent["Fecha"] = recent["date"].dt.strftime("%d/%m/%Y")
    recent["Monto"] = recent.apply(
        lambda r: f"+{fmt(r['amount'])}" if r["transaction_type"] == "income"
                  else f"-{fmt(abs(r['amount']))}", axis=1
    )
    recent["Tipo"] = recent["transaction_type"].map(
        {"income": "✅ Ingreso", "expense": "🔴 Gasto"}
    )

    display = recent[["Fecha", "description", "merchant", "category", "Monto", "Tipo"]].copy()
    display.columns = ["Fecha", "Descripción", "Comercio", "Categoría", "Monto", "Tipo"]

    st.dataframe(display, use_container_width=True, hide_index=True)
