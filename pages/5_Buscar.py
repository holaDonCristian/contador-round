"""
Page: Buscar
AI-style fuzzy search across all transactions.
Examples:
  "energetica"         → finds Red Bull, Monster, etc.
  "farmacia marzo"     → pharmacy transactions in March
  "uber > 5000"        → Uber trips over $5,000
  "jumbo 2024"         → Jumbo transactions in 2024
  "alimentacion < 3000"→ food expenses under $3,000
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, get_transactions
from src.search import search_transactions, format_search_result

st.set_page_config(page_title="Buscar", page_icon="🔍", layout="wide")
init_db()

st.title("🔍 Búsqueda Inteligente")
st.caption("Busca por descripción, comercio, categoría o lugar. Soporta fechas y montos.")

# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------
with st.expander("💡 Ejemplos de búsqueda"):
    examples = [
        ("energetica", "Encuentra todas las bebidas energéticas"),
        ("farmacia marzo", "Gastos en farmacias del mes de marzo"),
        ("uber > 5000", "Viajes en Uber de más de $5.000"),
        ("netflix 2024", "Pagos de Netflix en el 2024"),
        ("alimentacion < 3000", "Compras de comida menores a $3.000"),
        ("jumbo providencia", "Compras en Jumbo en Providencia"),
    ]
    for query, desc in examples:
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button(f'🔎 "{query}"', key=f"ex_{query}"):
                st.session_state["search_query"] = query
        with col2:
            st.caption(desc)

st.markdown("---")

# ---------------------------------------------------------------------------
# Search input
# ---------------------------------------------------------------------------
query = st.text_input(
    "¿Qué buscas?",
    value=st.session_state.get("search_query", ""),
    placeholder='Ej: "energetica", "farmacia marzo", "uber > 5000"',
    label_visibility="visible",
)

sensitivity = st.slider(
    "Sensibilidad de búsqueda",
    min_value=30, max_value=100, value=55, step=5,
    help="Menor = más resultados (más permisivo). Mayor = más exacto.",
)

if query:
    st.session_state["search_query"] = query

# ---------------------------------------------------------------------------
# Search and display
# ---------------------------------------------------------------------------
if query:
    all_df = get_transactions()  # fetch all, filter in search

    with st.spinner("Buscando..."):
        results = search_transactions(all_df, query, threshold=sensitivity)

    if results.empty:
        st.warning(f"No se encontraron resultados para **'{query}'**. Intenta con menos sensibilidad o términos diferentes.")
    else:
        total = results["amount"].abs().sum()
        income_total = results[results["transaction_type"] == "income"]["amount"].sum()
        expense_total = results[results["transaction_type"] == "expense"]["amount"].abs().sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Resultados", len(results))
        c2.metric("Total gastos", f"${expense_total:,.0f}")
        c3.metric("Total ingresos", f"${income_total:,.0f}")

        st.markdown("---")

        # Results as readable cards
        st.subheader("Resultados")
        results_display = results.copy()
        results_display["date"] = pd.to_datetime(results_display["date"], errors="coerce")
        results_display = results_display.sort_values("date", ascending=False)

        for _, row in results_display.iterrows():
            date_str = row["date"].strftime("%d/%m/%Y") if pd.notna(row["date"]) else "—"
            desc = row.get("description", "") or ""
            merchant = row.get("merchant", "") or ""
            location = row.get("location", "") or ""
            amount = abs(row.get("amount", 0))
            cat = row.get("category", "") or ""
            t_type = row.get("transaction_type", "expense")

            name = merchant if merchant else desc
            sign = "+" if t_type == "income" else "-"
            color = "#2E7D32" if t_type == "income" else "#C62828"

            loc_str = f" · 📍 {location}" if location else ""
            with st.container():
                col_info, col_amount = st.columns([4, 1])
                with col_info:
                    st.markdown(
                        f"**{name}** &nbsp;&nbsp; "
                        f"<span style='color:gray;font-size:0.9em'>{date_str} · 🏷️ {cat}{loc_str}</span>",
                        unsafe_allow_html=True
                    )
                    if desc and desc != merchant:
                        st.caption(desc)
                with col_amount:
                    st.markdown(
                        f"<h3 style='color:{color};text-align:right'>{sign}${amount:,.0f}</h3>",
                        unsafe_allow_html=True
                    )
                st.divider()

        # Mini chart of results
        if len(results) > 1:
            st.subheader("📊 Distribución de resultados")
            c1, c2 = st.columns(2)

            with c1:
                # By category
                cat_agg = (
                    results_display[results_display["transaction_type"] == "expense"]
                    .groupby("category")["amount"]
                    .apply(lambda x: abs(x.sum()))
                    .reset_index()
                )
                if not cat_agg.empty:
                    fig = px.pie(cat_agg, values="amount", names="category",
                                 title="Por Categoría", hole=0.4)
                    fig.update_layout(height=300, margin=dict(l=0,r=0,t=40,b=0))
                    st.plotly_chart(fig, use_container_width=True)

            with c2:
                # Over time
                results_display["month"] = results_display["date"].dt.to_period("M").astype(str)
                time_agg = (
                    results_display.groupby("month")["amount"]
                    .apply(lambda x: abs(x.sum()))
                    .reset_index()
                )
                if not time_agg.empty:
                    fig2 = px.bar(time_agg, x="month", y="amount",
                                  title="Por Mes", labels={"amount": "$", "month": "Mes"})
                    fig2.update_layout(
                        height=300,
                        margin=dict(l=0,r=0,t=40,b=0),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig2, use_container_width=True)

else:
    st.markdown("""
    ### Cómo usar el buscador

    Escribe cualquier término relacionado con tus transacciones:

    - **Nombre del producto**: `energetica`, `pizza`, `netflix`
    - **Comercio**: `jumbo`, `uber`, `farmacia`
    - **Categoría**: `alimentacion`, `transporte`, `salud`
    - **Mes**: `marzo`, `enero`, `diciembre`
    - **Año**: `2024`, `2025`
    - **Monto**: `> 10000` (mayor que), `< 5000` (menor que)
    - **Combinado**: `uber marzo > 3000`

    El buscador es **tolerante a errores** — no importa si escribes sin acentos
    o con errores pequeños de ortografía.
    """)
