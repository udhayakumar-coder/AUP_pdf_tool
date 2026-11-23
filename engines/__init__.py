"""AUP_pdf_tool engine package and runtime environment diagnostics."""

import importlib.util
import shutil
from typing import Dict


def get_system_health() -> Dict[str, bool]:
    """Return availability status of Python libraries and CLI conversion engines."""
    py_modules = {
        "pypdf": "pypdf",
        "PyMuPDF (fitz)": "fitz",
        "Pillow": "PIL",
        "pillow-heif (HEIC/AVIF)": "pillow_heif",
        "ReportLab": "reportlab",
        "pdfplumber": "pdfplumber",
        "pdf2docx": "pdf2docx",
        "python-docx": "docx",
        "python-pptx": "pptx",
        "openpyxl": "openpyxl",
        "pandas": "pandas",
        "pytesseract (OCR)": "pytesseract",
        "WeasyPrint (HTML->PDF)": "weasyprint",
    }
    status: Dict[str, bool] = {}
    for label, mod_name in py_modules.items():
        status[label] = importlib.util.find_spec(mod_name) is not None

    cli_tools = {
        "LibreOffice (Office/ODT/WPS/RTF)": ["soffice", "libreoffice"],
        "Calibre (EPUB/MOBI/AZW3/FB2/CHM/LIT)": ["ebook-convert"],
        "Ghostscript (High-Ratio Compression)": ["gs", "gswin64c", "gswin32c"],
        "Tesseract OCR (Tamil + English)": ["tesseract"],
        "QPDF (Repair PDF)": ["qpdf"],
        "DjVuLibre (DJVU)": ["ddjvu"],
        "Poppler (pdftoppm)": ["pdftoppm"],
    }
    for label, cmds in cli_tools.items():
        status[label] = any(shutil.which(cmd) is not None for cmd in cmds)

    return status
