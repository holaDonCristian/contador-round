"""
Image parser — uses pytesseract (OCR) to extract text from images,
then applies the same regex patterns as the PDF parser.
Requires: pip install pytesseract Pillow
And:       brew install tesseract tesseract-lang  (macOS)
           sudo apt-get install tesseract-ocr tesseract-ocr-spa  (Linux)
"""

import io

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

from src.parsers.pdf_parser import _parse_text


def is_available() -> bool:
    """Returns True if OCR dependencies are installed."""
    if not HAS_PILLOW or not HAS_TESSERACT:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def parse(file_bytes: bytes, filename: str) -> list[dict]:
    """
    Extract transactions from an image using OCR.
    Supports PNG, JPG, JPEG, TIFF, BMP, GIF.
    """
    if not HAS_PILLOW:
        return []
    if not HAS_TESSERACT:
        return []

    try:
        image = Image.open(io.BytesIO(file_bytes))

        # Improve OCR accuracy: convert to grayscale, increase contrast
        image = image.convert("L")

        # Try Spanish + English OCR for Chilean bank documents
        configs = [
            "--psm 6 -l spa+eng",
            "--psm 4 -l spa+eng",
            "--psm 11 -l spa+eng",
        ]

        best_text = ""
        best_len = 0
        for cfg in configs:
            try:
                text = pytesseract.image_to_string(image, config=cfg)
                if len(text) > best_len:
                    best_text = text
                    best_len = len(text)
            except Exception:
                continue

        if not best_text:
            return []

        return _parse_text(best_text)

    except Exception:
        return []
