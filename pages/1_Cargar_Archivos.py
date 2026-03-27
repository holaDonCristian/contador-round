"""
Page: Cargar Archivos
Upload PDF, CSV, Excel, or image files to extract transactions.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    init_db, get_accounts, get_categories,
    insert_transactions_batch, get_category_map,
)
from src.categorizer import categorize, extract_merchant
from src.parsers import csv_parser, excel_parser, pdf_parser, image_parser

st.set_page_config(page_title="Cargar Archivos", page_icon="📤", layout="wide")
init_db()

st.title("📤 Cargar Archivos")
st.caption("Soporta PDF (cartolas), CSV, Excel (.xlsx/.xls) e imágenes (JPG, PNG)")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
accounts = get_accounts()
categories = get_categories()

if accounts.empty:
    st.warning("⚠️ Primero crea una cuenta en **Cuentas**.")
    st.stop()

account_options = {f"{row['name']} ({row['type']})": row["id"] for _, row in accounts.iterrows()}
selected_account = st.selectbox("Cuenta destino", list(account_options.keys()))
account_id = account_options[selected_account]

# ---------------------------------------------------------------------------
# File uploader
# ---------------------------------------------------------------------------
uploaded_files = st.file_uploader(
    "Arrastra tus archivos aquí",
    type=["pdf", "csv", "xlsx", "xls", "png", "jpg", "jpeg", "tiff", "bmp"],
    accept_multiple_files=True,
    help="Puedes subir múltiples archivos a la vez",
)

if not uploaded_files:
    st.markdown("""
    ### ¿Qué archivos puedo subir?
    | Tipo | Descripción |
    |------|-------------|
    | 📄 PDF | Cartolas bancarias en PDF |
    | 📊 CSV | Exportaciones de banco en CSV |
    | 📗 Excel | Archivos .xlsx o .xls |
    | 🖼️ Imagen | Capturas de pantalla o fotos de cartolas |

    > **Tip:** La mayoría de bancos chilenos (BCI, Santander, BancoEstado, Scotiabank)
    > permiten exportar cartolas en PDF o CSV desde su banca en línea.
    """)
    st.stop()

# ---------------------------------------------------------------------------
# Process files
# ---------------------------------------------------------------------------
cat_map = get_category_map()
all_transactions = []

for uploaded_file in uploaded_files:
    file_bytes = uploaded_file.read()
    name = uploaded_file.name
    ext = Path(name).suffix.lower()

    with st.expander(f"📂 {name}", expanded=True):
        with st.spinner(f"Procesando {name}..."):
            try:
                if ext == ".csv":
                    rows = csv_parser.parse(file_bytes, name)
                elif ext in (".xlsx", ".xls"):
                    rows = excel_parser.parse(file_bytes, name)
                elif ext == ".pdf":
                    rows = pdf_parser.parse(file_bytes, name)
                elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
                    if image_parser.is_available():
                        rows = image_parser.parse(file_bytes, name)
                    else:
                        st.warning(
                            "OCR no disponible. Instala Tesseract:\n"
                            "- macOS: `brew install tesseract tesseract-lang`\n"
                            "- Linux: `sudo apt-get install tesseract-ocr tesseract-ocr-spa`"
                        )
                        rows = []
                else:
                    rows = []
            except Exception as e:
                st.error(f"Error procesando {name}: {e}")
                rows = []

        if not rows:
            st.warning("No se encontraron transacciones en este archivo.")
            continue

        # Enrich rows
        for row in rows:
            desc = row.get("description", "")
            merchant = row.get("merchant", "")

            if not merchant:
                merchant, location = extract_merchant(desc)
                row["merchant"] = merchant
                row["location"] = location or row.get("location", "")

            row["category"] = categorize(desc, merchant, cat_map)
            row["account_id"] = account_id
            row["source_file"] = name
            if "notes" not in row:
                row["notes"] = ""

        # Preview
        preview_df = pd.DataFrame(rows)
        preview_df = preview_df[["date", "description", "merchant", "category",
                                  "amount", "transaction_type"]].copy()
        preview_df.columns = ["Fecha", "Descripción", "Comercio", "Categoría",
                               "Monto", "Tipo"]

        st.success(f"✅ {len(rows)} transacciones encontradas")
        st.dataframe(preview_df, use_container_width=True, hide_index=True)
        all_transactions.extend(rows)

# ---------------------------------------------------------------------------
# Editable categories before saving
# ---------------------------------------------------------------------------
if all_transactions:
    st.markdown("---")
    st.subheader("✏️ Revisar y Ajustar Categorías")
    st.caption("Puedes cambiar la categoría antes de guardar")

    preview_df = pd.DataFrame(all_transactions)
    cat_names = list(categories["name"])

    edited_df = st.data_editor(
        preview_df[["date", "description", "merchant", "category", "amount", "transaction_type"]],
        column_config={
            "date":             st.column_config.TextColumn("Fecha"),
            "description":      st.column_config.TextColumn("Descripción"),
            "merchant":         st.column_config.TextColumn("Comercio"),
            "category":         st.column_config.SelectboxColumn("Categoría", options=cat_names),
            "amount":           st.column_config.NumberColumn("Monto", format="$%.0f"),
            "transaction_type": st.column_config.SelectboxColumn(
                "Tipo", options=["income", "expense"]
            ),
        },
        hide_index=True,
        use_container_width=True,
    )

    # Merge edited values back
    for i, row in edited_df.iterrows():
        all_transactions[i]["category"] = row["category"]
        all_transactions[i]["merchant"] = row["merchant"]
        all_transactions[i]["transaction_type"] = row["transaction_type"]

    st.markdown("---")
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("💾 Guardar Todo", type="primary", use_container_width=True):
            inserted = insert_transactions_batch(all_transactions)
            st.success(f"✅ {inserted} transacciones guardadas correctamente")
            st.balloons()
    with col2:
        st.caption(f"Total a guardar: **{len(all_transactions)}** transacciones")
