"""
Page: Calendario
Monthly calendar view showing daily income/expense summary.
"""

import sys
import calendar
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, get_transactions

st.set_page_config(page_title="Calendario", page_icon="📅", layout="wide")
init_db()

st.title("📅 Calendario Financiero")

# ---------------------------------------------------------------------------
# Month/Year selector
# ---------------------------------------------------------------------------
today = date.today()
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    month = st.selectbox("Mes", list(range(1, 13)),
                          index=today.month - 1,
                          format_func=lambda m: calendar.month_name[m])
with col2:
    year = st.selectbox("Año", list(range(today.year - 3, today.year + 1)),
                         index=3)

# ---------------------------------------------------------------------------
# Fetch data for the month
# ---------------------------------------------------------------------------
first_day = date(year, month, 1)
last_day = date(year, month, calendar.monthrange(year, month)[1])

df = get_transactions(start_date=first_day, end_date=last_day)

# Aggregate by day
daily_income = {}
daily_expense = {}
daily_txns = {}

if not df.empty:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["day"] = df["date"].dt.day

    for day_num, group in df.groupby("day"):
        income = group[group["transaction_type"] == "income"]["amount"].sum()
        expense = group[group["transaction_type"] == "expense"]["amount"].abs().sum()
        daily_income[day_num] = income
        daily_expense[day_num] = expense
        daily_txns[day_num] = group.to_dict("records")

# ---------------------------------------------------------------------------
# Calendar grid
# ---------------------------------------------------------------------------
month_name = calendar.month_name[month]
st.subheader(f"{month_name} {year}")

# Summary metrics for the month
total_income = sum(daily_income.values())
total_expense = sum(daily_expense.values())
total_balance = total_income - total_expense

c1, c2, c3 = st.columns(3)
c1.metric("💵 Ingresos del mes", f"${total_income:,.0f}")
c2.metric("💸 Gastos del mes", f"${total_expense:,.0f}")
c3.metric("💳 Balance", f"${total_balance:,.0f}", delta=f"${total_balance:,.0f}")

st.markdown("---")

# Render calendar
cal = calendar.monthcalendar(year, month)
day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

# Header row
header_cols = st.columns(7)
for i, day_name in enumerate(day_names):
    header_cols[i].markdown(f"<center><b>{day_name}</b></center>", unsafe_allow_html=True)

# Day cells
for week in cal:
    week_cols = st.columns(7)
    for i, day_num in enumerate(week):
        with week_cols[i]:
            if day_num == 0:
                st.markdown("&nbsp;", unsafe_allow_html=True)
                continue

            inc = daily_income.get(day_num, 0)
            exp = daily_expense.get(day_num, 0)
            txn_count = len(daily_txns.get(day_num, []))

            is_today = (day_num == today.day and month == today.month and year == today.year)
            border = "3px solid #4776E6" if is_today else "1px solid #ddd"
            bg = "#EEF2FF" if is_today else "#fff"

            income_html = f"<div style='color:#2E7D32;font-size:0.75em'>+${inc:,.0f}</div>" if inc else ""
            expense_html = f"<div style='color:#C62828;font-size:0.75em'>-${exp:,.0f}</div>" if exp else ""
            badge = f"<div style='background:#4776E6;color:white;border-radius:50%;width:16px;height:16px;font-size:0.65em;text-align:center;line-height:16px;margin:auto'>{txn_count}</div>" if txn_count else ""

            st.markdown(
                f"""
                <div style="
                    border: {border};
                    background: {bg};
                    border-radius: 8px;
                    padding: 6px;
                    min-height: 70px;
                    margin-bottom: 4px;
                ">
                    <div style='font-weight:bold;font-size:1em'>{day_num}</div>
                    {income_html}
                    {expense_html}
                    {badge}
                </div>
                """,
                unsafe_allow_html=True
            )

# ---------------------------------------------------------------------------
# Day detail
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("📋 Detalle por Día")

if not df.empty:
    available_days = sorted(daily_txns.keys())
    if available_days:
        selected_day = st.selectbox(
            "Selecciona un día",
            available_days,
            format_func=lambda d: f"{d} de {month_name}",
        )

        txns = daily_txns.get(selected_day, [])
        if txns:
            day_df = pd.DataFrame(txns)
            day_df = day_df[["description", "merchant", "category", "amount", "transaction_type"]].copy()
            day_df["Monto"] = day_df.apply(
                lambda r: f"+${r['amount']:,.0f}" if r["transaction_type"] == "income"
                          else f"-${abs(r['amount']):,.0f}", axis=1
            )
            day_df["Tipo"] = day_df["transaction_type"].map(
                {"income": "✅ Ingreso", "expense": "🔴 Gasto"}
            )
            day_df = day_df[["description", "merchant", "category", "Monto", "Tipo"]]
            day_df.columns = ["Descripción", "Comercio", "Categoría", "Monto", "Tipo"]
            st.dataframe(day_df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay transacciones este mes.")
else:
    st.info("No hay datos para este mes. Carga archivos o genera datos de prueba.")

# ---------------------------------------------------------------------------
# Daily timeline chart
# ---------------------------------------------------------------------------
if daily_expense or daily_income:
    st.markdown("---")
    st.subheader("📈 Flujo Diario")

    days_range = list(range(1, last_day.day + 1))
    inc_vals = [daily_income.get(d, 0) for d in days_range]
    exp_vals = [daily_expense.get(d, 0) for d in days_range]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Ingresos", x=days_range, y=inc_vals,
        marker_color="#38ef7d",
    ))
    fig.add_trace(go.Bar(
        name="Gastos", x=days_range, y=exp_vals,
        marker_color="#f45c43",
    ))
    fig.update_layout(
        title=f"Ingresos y Gastos diarios — {month_name} {year}",
        barmode="group",
        xaxis_title="Día",
        yaxis_title="Monto ($)",
        height=350,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
