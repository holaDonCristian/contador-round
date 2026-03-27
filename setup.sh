#!/bin/bash
# Setup script for Finance Dashboard
# Run this once to set up the environment

echo "🚀 Configurando Finance Dashboard..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Instalación completa!"
echo ""
echo "Para iniciar el dashboard:"
echo "  source venv/bin/activate"
echo "  streamlit run app.py"
echo ""
echo "Para OCR en imágenes (opcional):"
echo "  macOS: brew install tesseract tesseract-lang"
echo "  Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-spa"
