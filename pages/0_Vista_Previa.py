"""
Page: Vista Previa / Demo
One-click preview of all dashboard features using generated demo data.
"""

import sys
import calendar
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    init_db,
    get_transactions,
    get_accounts,
    get_categories,
    get_summary,
    get_category_summary,
    get_merchant_summary,
    get_monthly_summary,
)
from src.demo_data import generate_demo_data
from src.search import search_transactions

st.set_page_config(page_title="Vista Previa", page_icon="🎬", layout="wide")
init_db()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🎬 Vista Previa del Dashboard")
st.caption("Carga datos de demostración y revisa cada módulo funcionando en vivo.")

# ---------------------------------------------------------------------------
# Launch button
# ---------------------------------------------------------------------------
col_btn, col_info = st.columns([2, 5])

with col_btn:
    months = st.selectbox("Meses de datos demo", [2, 3, 4, 6], index=1)
    launch = st.button("▶️ Iniciar Preview", type="primary", use_container_width=True)

with col_info:
    st.info(
        "Este botón genera transacciones de ejemplo (compras, sueldos, servicios, etc.) "
        "y muestra todos los módulos del dashboard funcionando.\n\n"
        "Puedes ejecutarlo cuantas veces quieras — reemplaza los datos demo anteriores."
    )

if launch:
    with st.spinner(f"Generando {months} meses de datos de demostración..."):
        generate_demo_data(months=months)
    st.success(f"✅ Datos cargados — {months} meses de transacciones generadas")
    st.rerun()

# ---------------------------------------------------------------------------
# Check if there's data to show
# ---------------------------------------------------------------------------
df_all = get_transactions()
accounts = get_accounts()

if df_all.empty:
    st.markdown("---")
    st.markdown(
        """
        ### Sin datos aún
        Presiona **▶️ Iniciar Preview** para generar datos de demostración
        y ver todos los módulos funcionando aquí mismo.
        """
    )
    st.stop()

# ---------------------------------------------------------------------------
# Live preview — all modules
# ---------------------------------------------------------------------------
st.markdown("---")

summary = get_summary()
df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")

# ── 1. Métricas ─────────────────────────────────────────────────────────────
st.subheader("1️⃣ Métricas Globales")
c1, c2, c3, c4 = st.columns(4)
c1.metric("💵 Ingresos totales",  f"${summary['income']:,.0f}")
c2.metric("💸 Gastos totales",    f"${summary['expenses']:,.0f}")
c3.metric("💳 Balance",           f"${summary['balance']:,.0f}",
          delta=f"${summary['balance']:,.0f}")
c4.metric("🐷 Tasa de ahorro",    f"{summary['savings_rate']:.1f}%")

st.markdown("---")

# ── 2. Cuentas ───────────────────────────────────────────────────────────────
st.subheader("2️⃣ Cuentas Registradas")
if not accounts.empty:
    acc_cols = st.columns(min(len(accounts), 4))
    for i, (_, acc) in enumerate(accounts.iterrows()):
        icon = {"bank": "🏦", "cash": "💵", "credit": "💳"}.get(acc["type"], "💰")
        acc_cols[i % 4].metric(
            f"{icon} {acc['name']}",
            f"${acc['balance']:,.0f}",
            delta=acc["currency"],
        )
else:
    st.info("Sin cuentas registradas.")

st.markdown("---")

# ── 3. Ingresos vs Gastos por Mes ────────────────────────────────────────────
st.subheader("3️⃣ Ingresos vs Gastos por Mes")
monthly = get_monthly_summary()

if not monthly.empty:
    income_m = monthly[monthly["transaction_type"] == "income"].set_index("month")["total"]
    expense_m = monthly[monthly["transaction_type"] == "expense"].set_index("month")["total"]
    all_months = sorted(set(income_m.index) | set(expense_m.index))
    balance_vals = [income_m.get(m, 0) - expense_m.get(m, 0) for m in all_months]

    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Bar(
        name="Ingresos", x=all_months,
        y=[income_m.get(m, 0) for m in all_months],
        marker_color="#38ef7d",
    ))
    fig_monthly.add_trace(go.Bar(
        name="Gastos", x=all_months,
        y=[expense_m.get(m, 0) for m in all_months],
        marker_color="#f45c43",
    ))
    fig_monthly.add_trace(go.Scatter(
        name="Balance", x=all_months, y=balance_vals,
        mode="lines+markers",
        line=dict(color="#4776E6", width=2),
        yaxis="y2",
    ))
    fig_monthly.update_layout(
        barmode="group",
        height=380,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

st.markdown("---")

# ── 4. Categorías ────────────────────────────────────────────────────────────
st.subheader("4️⃣ Gastos por Categoría")
cat_summary = get_category_summary()
cats_df = get_categories()
color_map = dict(zip(cats_df["name"], cats_df["color"]))

if not cat_summary.empty:
    col_pie, col_bar = st.columns(2)

    with col_pie:
        colors = [color_map.get(c, "#888888") for c in cat_summary["category"]]
        fig_pie = go.Figure(go.Pie(
            labels=cat_summary["category"],
            values=cat_summary["total"],
            hole=0.4,
            marker_colors=colors,
            textinfo="label+percent",
            hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
        ))
        fig_pie.update_layout(
            title="Distribución",
            height=360,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_bar:
        fig_bar = px.bar(
            cat_summary.sort_values("total"),
            x="total", y="category", orientation="h",
            color="category", color_discrete_map=color_map,
            labels={"total": "$", "category": ""},
            title="Ranking",
        )
        fig_bar.update_layout(
            showlegend=False, height=360,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=40, b=0),
        )
        fig_bar.update_traces(hovertemplate="$%{x:,.0f}<extra></extra>")
        st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# ── 5. Top Comercios ─────────────────────────────────────────────────────────
st.subheader("5️⃣ Top Comercios")
merchant_summary = get_merchant_summary(top_n=12)

if not merchant_summary.empty:
    col_merch, col_tree = st.columns(2)

    with col_merch:
        fig_merch = px.bar(
            merchant_summary.sort_values("total"),
            x="total", y="merchant", orientation="h",
            color="total", color_continuous_scale="Reds",
            labels={"total": "$", "merchant": ""},
            title="Gasto por Comercio",
        )
        fig_merch.update_layout(
            showlegend=False, height=380,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig_merch, use_container_width=True)

    with col_tree:
        expenses_df = df_all[df_all["transaction_type"] == "expense"].copy()
        merch_cat = (
            expenses_df.groupby(["merchant", "category"])["amount"]
            .apply(lambda x: abs(x.sum()))
            .reset_index()
        )
        merch_cat.columns = ["merchant", "category", "total"]
        merch_cat = merch_cat[merch_cat["merchant"].str.strip() != ""]

        if not merch_cat.empty:
            fig_tree = px.treemap(
                merch_cat,
                path=["category", "merchant"],
                values="total",
                color="total",
                color_continuous_scale="RdYlGn_r",
                title="Treemap por Categoría / Comercio",
            )
            fig_tree.update_layout(
                height=380,
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig_tree, use_container_width=True)

st.markdown("---")

# ── 6. Buscador ──────────────────────────────────────────────────────────────
st.subheader("6️⃣ Buscador Inteligente")
st.caption("Prueba la búsqueda fuzzy con los datos de demostración")

col_q, col_thresh = st.columns([4, 1])
with col_q:
    query = st.text_input(
        "Buscar transacción",
        placeholder='Ej: "energetica", "farmacia", "uber > 3000"',
        label_visibility="collapsed",
    )
with col_thresh:
    st.caption("Sensibilidad")
    threshold = st.slider("", 30, 100, 55, label_visibility="collapsed")

if query:
    results = search_transactions(df_all, query, threshold=threshold)
    if results.empty:
        st.warning(f"Sin resultados para '{query}'")
    else:
        st.success(f"🔍 {len(results)} resultado(s) para **'{query}'**")
        for _, row in results.head(8).iterrows():
            date_s = row["date"].strftime("%d/%m/%Y") if pd.notna(row["date"]) else "—"
            merchant = row.get("merchant", "") or row.get("description", "") or "—"
            amount = abs(row.get("amount", 0))
            cat = row.get("category", "")
            t_type = row.get("transaction_type", "expense")
            sign = "+" if t_type == "income" else "-"
            color = "#2E7D32" if t_type == "income" else "#C62828"
            col_i, col_a = st.columns([5, 1])
            col_i.markdown(
                f"**{merchant}** &nbsp; <span style='color:gray;font-size:0.85em'>{date_s} · {cat}</span>",
                unsafe_allow_html=True,
            )
            col_a.markdown(
                f"<div style='color:{color};text-align:right;font-weight:bold'>{sign}${amount:,.0f}</div>",
                unsafe_allow_html=True,
            )
else:
    st.markdown(
        "<div style='color:gray;font-size:0.9em'>Escribe algo arriba para probar el buscador.</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── 7. Calendario ────────────────────────────────────────────────────────────
st.subheader("7️⃣ Calendario del Mes Actual")

today = date.today()
first_day = today.replace(day=1)
last_day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])

df_month = df_all[
    (df_all["date"] >= pd.Timestamp(first_day)) &
    (df_all["date"] <= pd.Timestamp(last_day))
].copy()

daily_income = {}
daily_expense = {}

if not df_month.empty:
    df_month["day"] = df_month["date"].dt.day
    for day_num, group in df_month.groupby("day"):
        daily_income[day_num] = group[group["transaction_type"] == "income"]["amount"].sum()
        daily_expense[day_num] = group[group["transaction_type"] == "expense"]["amount"].abs().sum()

days_range = list(range(1, last_day.day + 1))
fig_cal = go.Figure()
fig_cal.add_trace(go.Bar(
    name="Ingresos", x=days_range,
    y=[daily_income.get(d, 0) for d in days_range],
    marker_color="#38ef7d",
))
fig_cal.add_trace(go.Bar(
    name="Gastos", x=days_range,
    y=[daily_expense.get(d, 0) for d in days_range],
    marker_color="#f45c43",
))
fig_cal.update_layout(
    title=f"Flujo diario — {calendar.month_name[today.month]} {today.year}",
    barmode="group",
    xaxis_title="Día",
    height=300,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=40, b=0),
)
st.plotly_chart(fig_cal, use_container_width=True)

st.markdown("---")

# ── 8. Últimas transacciones ─────────────────────────────────────────────────
st.subheader("8️⃣ Transacciones Recientes")
recent = df_all.sort_values("date", ascending=False).head(15).copy()
recent["Fecha"] = recent["date"].dt.strftime("%d/%m/%Y")
recent["Monto"] = recent.apply(
    lambda r: f"+${r['amount']:,.0f}" if r["transaction_type"] == "income"
              else f"-${abs(r['amount']):,.0f}",
    axis=1,
)
recent["Tipo"] = recent["transaction_type"].map(
    {"income": "✅ Ingreso", "expense": "🔴 Gasto"}
)
cols_show = ["Fecha", "description", "merchant", "category", "Monto", "Tipo"]
available = [c for c in cols_show if c in recent.columns]
display = recent[available].copy()
display.columns = ["Fecha", "Descripción", "Comercio", "Categoría", "Monto", "Tipo"][: len(available)]
st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")
st.success(
    "✅ **Preview completo.** Todos los módulos funcionan correctamente. "
    "Navega por el menú lateral para explorar cada sección en detalle."
)
