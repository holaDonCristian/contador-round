"""
Page: Análisis
Charts: category breakdown, monthly trends, merchant ranking, location map, savings projection.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    init_db, get_transactions, get_categories,
    get_category_summary, get_merchant_summary, get_monthly_summary,
)

st.set_page_config(page_title="Análisis", page_icon="📊", layout="wide")
init_db()

st.title("📊 Análisis de Gastos")

# ---------------------------------------------------------------------------
# Period selector
# ---------------------------------------------------------------------------
def period_to_dates(label):
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
    return None, None

period = st.selectbox(
    "Período",
    ["Este mes", "Mes anterior", "Últimos 3 meses", "Este año", "Todo"],
    horizontal=True,
)
start_date, end_date = period_to_dates(period)

df = get_transactions(start_date, end_date)
cats_df = get_categories()
color_map = dict(zip(cats_df["name"], cats_df["color"]))

if df.empty:
    st.info("No hay datos. Carga archivos o genera datos de prueba desde el Dashboard.")
    st.stop()

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["month"] = df["date"].dt.to_period("M").astype(str)
df["week"] = df["date"].dt.to_period("W").astype(str)

expenses_df = df[df["transaction_type"] == "expense"].copy()
income_df = df[df["transaction_type"] == "income"].copy()

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗂️ Categorías", "📅 Mensual", "🏪 Comercios", "📍 Lugares", "💰 Proyección"
])

# ── Tab 1: Categories ──────────────────────────────────────────────────────
with tab1:
    cat_summary = get_category_summary(start_date, end_date)

    if cat_summary.empty:
        st.info("Sin gastos registrados.")
    else:
        colors = [color_map.get(c, "#888888") for c in cat_summary["category"]]

        c1, c2 = st.columns(2)

        with c1:
            fig = go.Figure(go.Pie(
                labels=cat_summary["category"],
                values=cat_summary["total"],
                hole=0.4,
                marker_colors=colors,
                textinfo="label+percent",
                hovertemplate="%{label}<br>$%{value:,.0f}<extra></extra>",
            ))
            fig.update_layout(
                title="Distribución de Gastos",
                height=400,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig2 = px.bar(
                cat_summary.sort_values("total"),
                x="total",
                y="category",
                orientation="h",
                color="category",
                color_discrete_map=color_map,
                labels={"total": "Monto ($)", "category": "Categoría"},
                title="Ranking de Gastos",
            )
            fig2.update_layout(
                showlegend=False,
                height=400,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            fig2.update_traces(hovertemplate="$%{x:,.0f}<extra></extra>")
            st.plotly_chart(fig2, use_container_width=True)

        # Category detail table
        st.subheader("Detalle por Categoría")
        cat_summary["Porcentaje"] = (cat_summary["total"] / cat_summary["total"].sum() * 100).round(1)
        cat_summary["Promedio"] = (cat_summary["total"] / cat_summary["count"]).round(0)
        display = cat_summary.copy()
        display.columns = ["Categoría", "Total ($)", "Transacciones", "% del Total", "Promedio ($)"]
        display["Total ($)"] = display["Total ($)"].apply(lambda x: f"${x:,.0f}")
        display["Promedio ($)"] = display["Promedio ($)"].apply(lambda x: f"${x:,.0f}")
        st.dataframe(display, use_container_width=True, hide_index=True)


# ── Tab 2: Monthly ─────────────────────────────────────────────────────────
with tab2:
    monthly = get_monthly_summary()

    if monthly.empty:
        st.info("Sin datos mensuales.")
    else:
        income_m = monthly[monthly["transaction_type"] == "income"].set_index("month")["total"]
        expense_m = monthly[monthly["transaction_type"] == "expense"].set_index("month")["total"]
        all_months = sorted(set(income_m.index) | set(expense_m.index))

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Ingresos",
            x=all_months,
            y=[income_m.get(m, 0) for m in all_months],
            marker_color="#38ef7d",
        ))
        fig.add_trace(go.Bar(
            name="Gastos",
            x=all_months,
            y=[expense_m.get(m, 0) for m in all_months],
            marker_color="#f45c43",
        ))

        balance_vals = [income_m.get(m, 0) - expense_m.get(m, 0) for m in all_months]
        fig.add_trace(go.Scatter(
            name="Balance",
            x=all_months,
            y=balance_vals,
            mode="lines+markers",
            line=dict(color="#4776E6", width=2),
            marker=dict(size=8),
            yaxis="y2",
        ))

        fig.update_layout(
            title="Ingresos vs Gastos vs Balance Mensual",
            barmode="group",
            height=450,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis2=dict(overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Monthly category heatmap
        if not expenses_df.empty:
            st.subheader("Gastos por Categoría y Mes")
            pivot = (
                expenses_df.groupby(["month", "category"])["amount"]
                .apply(lambda x: abs(x.sum()))
                .reset_index()
                .pivot(index="category", columns="month", values="amount")
                .fillna(0)
            )
            fig_heat = px.imshow(
                pivot,
                color_continuous_scale="RdYlGn_r",
                labels=dict(color="$"),
                title="Mapa de calor: gastos por categoría/mes",
                aspect="auto",
            )
            fig_heat.update_layout(height=400)
            st.plotly_chart(fig_heat, use_container_width=True)


# ── Tab 3: Merchants ───────────────────────────────────────────────────────
with tab3:
    merchant_summary = get_merchant_summary(start_date, end_date, top_n=20)

    if merchant_summary.empty:
        st.info("Sin datos de comercios.")
    else:
        fig = px.bar(
            merchant_summary.sort_values("total"),
            x="total",
            y="merchant",
            orientation="h",
            color="total",
            color_continuous_scale="Reds",
            labels={"total": "Total Gastado ($)", "merchant": "Comercio"},
            title="Top Comercios por Gasto",
            text=merchant_summary.sort_values("total")["total"].apply(lambda x: f"${x:,.0f}"),
        )
        fig.update_layout(
            showlegend=False,
            height=500,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

        # Treemap
        st.subheader("Mapa de árbol por Comercio")
        if not expenses_df.empty:
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
                    title="Treemap: Gasto por Categoría / Comercio",
                )
                fig_tree.update_layout(height=500)
                st.plotly_chart(fig_tree, use_container_width=True)


# ── Tab 4: Locations ───────────────────────────────────────────────────────
with tab4:
    if not expenses_df.empty and "location" in expenses_df.columns:
        loc_df = expenses_df[expenses_df["location"].str.strip() != ""].copy()
        if not loc_df.empty:
            loc_summary = (
                loc_df.groupby("location")["amount"]
                .apply(lambda x: abs(x.sum()))
                .reset_index()
                .sort_values("amount", ascending=False)
            )
            loc_summary.columns = ["Lugar", "Total ($)"]

            fig = px.bar(
                loc_summary.head(15),
                x="Lugar",
                y="Total ($)",
                color="Total ($)",
                color_continuous_scale="Blues",
                title="Gastos por Lugar/Sector",
            )
            fig.update_layout(
                height=400,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            loc_summary["Total ($)"] = loc_summary["Total ($)"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(loc_summary, use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos de ubicación. Los comercios deben tener un lugar asignado.")
    else:
        st.info("Sin datos de ubicación disponibles.")


# ── Tab 5: Savings Projection ──────────────────────────────────────────────
with tab5:
    monthly_income = income_df["amount"].sum() / max(len(df["month"].unique()), 1)
    monthly_expenses = expenses_df["amount"].abs().sum() / max(len(df["month"].unique()), 1)
    monthly_savings = monthly_income - monthly_expenses

    st.subheader("Proyección de Ahorro")
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingreso mensual promedio", f"${monthly_income:,.0f}")
    c2.metric("Gasto mensual promedio", f"${monthly_expenses:,.0f}")
    c3.metric("Ahorro mensual", f"${monthly_savings:,.0f}")

    # Projection chart
    months_ahead = st.slider("Meses a proyectar", 3, 36, 12)
    goal = st.number_input("Meta de ahorro ($)", value=float(monthly_savings * 12), step=100000.0)

    projection = [monthly_savings * (i + 1) for i in range(months_ahead)]
    months_labels = [f"Mes {i+1}" for i in range(months_ahead)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months_labels, y=projection,
        mode="lines+markers",
        name="Ahorro acumulado",
        fill="tozeroy",
        fillcolor="rgba(56, 239, 125, 0.2)",
        line=dict(color="#38ef7d", width=2),
    ))
    fig.add_hline(y=goal, line_dash="dash", line_color="#f45c43",
                  annotation_text=f"Meta: ${goal:,.0f}")
    fig.update_layout(
        title=f"Proyección de Ahorro — {months_ahead} meses",
        height=400,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis_title="$",
    )
    st.plotly_chart(fig, use_container_width=True)

    if monthly_savings > 0:
        months_to_goal = goal / monthly_savings
        st.info(f"⏱️ A este ritmo alcanzas tu meta en **{months_to_goal:.1f} meses**")
    elif monthly_savings <= 0:
        st.error("⚠️ Los gastos superan los ingresos. Revisa tus categorías de mayor gasto.")

    # Savings recommendations
    st.subheader("💡 Recomendaciones")
    cat_summary = get_category_summary(start_date, end_date)
    if not cat_summary.empty and monthly_income > 0:
        for _, row in cat_summary.head(5).iterrows():
            pct = row["total"] / (monthly_income * len(df["month"].unique())) * 100
            if pct > 15:
                st.warning(f"**{row['category']}** representa el {pct:.1f}% de tus ingresos — considera reducirlo.")
