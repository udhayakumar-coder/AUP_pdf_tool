"""Pro & CSC e-Services PDF tools for AUP_pdf_tool.

Covers the 7 extra high-utility tools:
1. Compress PDF to Exact Target Size (KB)
2. ID Card Front & Back to Single-Page A4 PDF (Aadhaar / PAN / Voter ID)
3. OCR PDF (Tamil + English)
4. Sign & Seal PDF (transparent signature/stamp placement)
5. Color to Black & White (Grayscale) PDF
6. HTML / URL to PDF
7. Repair & Flatten PDF (fix structure + lock forms + strip metadata)
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import urllib.request
from typing import Optional, Tuple

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from engines.image_engine import pdf_to_images
from engines.pdf_core import compress_pdf

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import weasyprint
except ImportError:
    weasyprint = None

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass


def _render_pdf_pages_pil(pdf_bytes: bytes, dpi: int = 120):
    pages = []
    if fitz is not None:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pages.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        finally:
            doc.close()
        return pages

    if pdfium is not None:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            for i in range(len(doc)):
                pages.append(doc[i].render(scale=dpi / 72.0).to_pil().convert("RGB"))
        finally:
            doc.close()
        return pages

    raise RuntimeError("Neither PyMuPDF (fitz) nor pypdfium2 is available to render PDF pages.")


def _pil_pages_to_jpeg_pdf(pages, quality: int = 70, grayscale: bool = False) -> bytes:
    """Pack PIL pages as JPEG-compressed PDF pages."""
    out = io.BytesIO()
    c = None
    for idx, im in enumerate(pages):
        work = ImageOps.grayscale(im).convert("RGB") if grayscale else im.convert("RGB")
        w, h = work.size
        # Keep physical page dimensions proportional at 72pt/inch (approximate A4 ratio)
        pw, ph = float(w) * 72.0 / 120.0, float(h) * 72.0 / 120.0
        if c is None:
            c = canvas.Canvas(out, pagesize=(pw, ph))
        else:
            c.setPageSize((pw, ph))
        buf = io.BytesIO()
        work.save(buf, format="JPEG", quality=quality, optimize=True)
        buf.seek(0)
        c.drawImage(ImageReader(buf), 0, 0, width=pw, height=ph)
        c.showPage()
    if c is not None:
        c.save()
    return out.getvalue()


def compress_to_target_kb(pdf_bytes: bytes, target_kb: int = 200) -> Tuple[bytes, bool]:
    """Iteratively compress a PDF to fit under target_kb (e.g. 100 KB / 200 KB for govt portals).

    Returns: (compressed_bytes, met_target)
    """
    target_bytes = max(20, int(target_kb)) * 1024
    if len(pdf_bytes) <= target_bytes:
        return pdf_bytes, True

    best = pdf_bytes

    # Pass 1: Try standard Ghostscript / lossless compression presets first
    for q in (70, 50, 30, 15):
        candidate = compress_pdf(pdf_bytes, quality_level=q)
        if len(candidate) < len(best):
            best = candidate
        if len(best) <= target_bytes:
            return best, True

    # Pass 2: Rasterize pages at progressively lower DPI & JPEG quality to guarantee target KB
    for dpi in (120, 96, 72, 60):
        try:
            pages = _render_pdf_pages_pil(pdf_bytes, dpi=dpi)
        except Exception:
            break
        for jq in (70, 50, 35, 22):
            candidate = _pil_pages_to_jpeg_pdf(pages, quality=jq, grayscale=False)
            if len(candidate) < len(best):
                best = candidate
            if len(best) <= target_bytes:
                return best, True

    return best, len(best) <= target_bytes


def id_card_to_pdf(
    front_bytes: bytes,
    back_bytes: Optional[bytes] = None,
    layout: str = "Stacked (Vertical)",
    draw_border: bool = True,
    card_scale: float = 1.0,
) -> bytes:
    """Place Front & Back ID card photos (Aadhaar / PAN / Voter ID) on a print-ready A4 page."""
    pw, ph = A4  # 210mm x 297mm
    # Standard CR80 ID card dimensions: 85.6mm x 54mm
    card_w = 85.6 * mm * card_scale
    card_h = 54.0 * mm * card_scale

    def _prepare_card(raw: bytes) -> ImageReader:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        # Auto-rotate portrait card photos to landscape
        if im.height > im.width * 1.15:
            im = im.rotate(90, expand=True)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        return ImageReader(buf)

    front_reader = _prepare_card(front_bytes)
    back_reader = _prepare_card(back_bytes) if back_bytes else None

    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)

    def _draw_slot(reader: ImageReader, x: float, y: float, label: str):
        c.drawImage(reader, x, y, width=card_w, height=card_h, preserveAspectRatio=True, anchor="c")
        if draw_border:
            c.setStrokeColor(colors.HexColor("#94A3B8"))
            c.setLineWidth(0.6)
            c.setDash(3, 2)
            c.rect(x, y, card_w, card_h)
            c.setDash()
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + card_w / 2.0, y - 12, label)

    if back_reader is None:
        x = (pw - card_w) / 2.0
        y = ph - 45 * mm - card_h
        _draw_slot(front_reader, x, y, "Front Side")
    elif layout == "Side-by-Side (Horizontal)":
        gap = 10 * mm
        total_w = card_w * 2 + gap
        if total_w > pw - 20 * mm:
            shrink = (pw - 20 * mm - gap) / (card_w * 2)
            card_w *= shrink
            card_h *= shrink
            total_w = card_w * 2 + gap
        x1 = (pw - total_w) / 2.0
        x2 = x1 + card_w + gap
        y = ph - 55 * mm - card_h
        _draw_slot(front_reader, x1, y, "Front Side")
        _draw_slot(back_reader, x2, y, "Back Side")
    else:
        gap = 18 * mm
        x = (pw - card_w) / 2.0
        y1 = ph - 45 * mm - card_h
        y2 = y1 - gap - card_h
        _draw_slot(front_reader, x, y1, "Front Side")
        _draw_slot(back_reader, x, y2, "Back Side")

    c.showPage()
    c.save()
    return out.getvalue()


def ocr_pdf(
    pdf_bytes: bytes,
    lang: str = "eng",
    output_mode: str = "Searchable PDF",
    dpi: int = 200,
) -> Tuple[bytes, str]:
    """Run Tesseract OCR (English / Tamil / Tamil+English) on a scanned PDF.

    Returns: (output_bytes, extracted_text_preview)
    """
    if pytesseract is None or shutil.which("tesseract") is None:
        raise RuntimeError(
            "Tesseract OCR is not installed on this machine. "
            "On Streamlit Cloud, ensure 'tesseract-ocr' and 'tesseract-ocr-tam' are in packages.txt."
        )

    pages = _render_pdf_pages_pil(pdf_bytes, dpi=dpi)
    extracted_parts = []

    if output_mode == "Extracted Text (.txt)":
        for idx, im in enumerate(pages, start=1):
            txt = pytesseract.image_to_string(im, lang=lang)
            extracted_parts.append(f"--- Page {idx} ---\n{txt.strip()}")
        full_text = "\n\n".join(extracted_parts)
        return full_text.encode("utf-8"), full_text

    # Searchable PDF mode: merge Tesseract per-page searchable PDFs
    writer = PdfWriter()
    for idx, im in enumerate(pages, start=1):
        pdf_chunk = pytesseract.image_to_pdf_or_hocr(im, extension="pdf", lang=lang)
        reader = PdfReader(io.BytesIO(pdf_chunk))
        for p in reader.pages:
            writer.add_page(p)
        txt = pytesseract.image_to_string(im, lang=lang)
        extracted_parts.append(f"--- Page {idx} ---\n{txt.strip()}")

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), "\n\n".join(extracted_parts)


def sign_and_seal_pdf(
    pdf_bytes: bytes,
    stamp_bytes: bytes,
    target_page: str = "Last Page",
    x_pct: float = 72.0,
    y_pct: float = 12.0,
    width_pct: float = 22.0,
    remove_white_bg: bool = True,
) -> bytes:
    """Place a signature or shop seal PNG/JPG onto a specific page (or all pages) of a PDF."""
    im = Image.open(io.BytesIO(stamp_bytes)).convert("RGBA")
    if remove_white_bg:
        pixels = im.getdata()
        new_pixels = [
            (r, g, b, 0) if (r > 235 and g > 235 and b > 235) else (r, g, b, a)
            for (r, g, b, a) in pixels
        ]
        im.putdata(new_pixels)

    tmp_dir = tempfile.TemporaryDirectory(prefix="aup_sign_")
    try:
        stamp_path = os.path.join(tmp_dir.name, "stamp.png")
        im.save(stamp_path, format="PNG")
        iw, ih = im.size

        reader = PdfReader(io.BytesIO(pdf_bytes))
        total = len(reader.pages)

        if target_page == "All Pages":
            page_indices = set(range(total))
        elif target_page == "First Page":
            page_indices = {0}
        elif target_page == "Last Page":
            page_indices = {total - 1}
        else:
            p = max(1, min(total, int(target_page)))
            page_indices = {p - 1}

        writer = PdfWriter()
        for idx, page in enumerate(reader.pages):
            if idx in page_indices:
                pw = float(page.mediabox.width)
                ph = float(page.mediabox.height)
                dw = pw * (width_pct / 100.0)
                dh = dw * (ih / max(1, iw))
                x = pw * (x_pct / 100.0)
                y = ph * (y_pct / 100.0)

                overlay_buf = io.BytesIO()
                c = canvas.Canvas(overlay_buf, pagesize=(pw, ph))
                c.drawImage(stamp_path, x, y, width=dw, height=dh, mask="auto")
                c.save()
                overlay = PdfReader(io.BytesIO(overlay_buf.getvalue()))
                page.merge_page(overlay.pages[0])
            writer.add_page(page)

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    finally:
        tmp_dir.cleanup()


def grayscale_pdf(pdf_bytes: bytes, dpi: int = 150, high_contrast: bool = False) -> bytes:
    """Convert a color PDF to clean Black & White / Grayscale to save print ink."""
    pages = _render_pdf_pages_pil(pdf_bytes, dpi=dpi)
    out = io.BytesIO()
    c = None
    for im in pages:
        gray = ImageOps.grayscale(im)
        if high_contrast:
            gray = ImageOps.autocontrast(gray, cutoff=2)
        rgb_gray = gray.convert("RGB")
        w, h = rgb_gray.size
        pw, ph = float(w) * 72.0 / dpi, float(h) * 72.0 / dpi
        if c is None:
            c = canvas.Canvas(out, pagesize=(pw, ph))
        else:
            c.setPageSize((pw, ph))
        buf = io.BytesIO()
        rgb_gray.save(buf, format="JPEG", quality=88, optimize=True)
        buf.seek(0)
        c.drawImage(ImageReader(buf), 0, 0, width=pw, height=ph)
        c.showPage()
    if c is not None:
        c.save()
    return out.getvalue()


def html_or_url_to_pdf(html_content: Optional[str] = None, url: Optional[str] = None) -> bytes:
    """Convert HTML code/file or a webpage URL to PDF via WeasyPrint or wkhtmltopdf."""
    if url and not html_content:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AUP-PDF-Tool"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        html_content = raw.decode("utf-8", errors="replace")

    if not html_content or not html_content.strip():
        raise ValueError("Please provide HTML content or a valid URL.")

    if weasyprint is not None:
        return weasyprint.HTML(string=html_content, base_url=url or None).write_pdf()

    wk_bin = shutil.which("wkhtmltopdf")
    if wk_bin:
        with tempfile.TemporaryDirectory(prefix="aup_html_") as tmp:
            in_html = os.path.join(tmp, "input.html")
            out_pdf = os.path.join(tmp, "output.pdf")
            with open(in_html, "w", encoding="utf-8") as f:
                f.write(html_content)
            proc = subprocess.run([wk_bin, "--quiet", in_html, out_pdf], capture_output=True, timeout=60)
            if proc.returncode == 0 and os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 0:
                with open(out_pdf, "rb") as f:
                    return f.read()

    # Fallback: strip tags to clean text PDF using BeautifulSoup + txt_to_pdf
    from bs4 import BeautifulSoup
    from engines.office_engine import txt_to_pdf

    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    clean_text = soup.get_text(separator="\n")
    return txt_to_pdf(clean_text.encode("utf-8"))


def repair_and_flatten_pdf(
    pdf_bytes: bytes,
    flatten_forms: bool = True,
    strip_metadata: bool = True,
) -> bytes:
    """Repair PDF structure, optionally flatten interactive forms/annotations, and clean metadata."""
    working = pdf_bytes

    # Step 1: Try qpdf structural repair if available
    qpdf_bin = shutil.which("qpdf")
    if qpdf_bin:
        with tempfile.TemporaryDirectory(prefix="aup_qpdf_") as tmp:
            in_p = os.path.join(tmp, "in.pdf")
            out_p = os.path.join(tmp, "out.pdf")
            with open(in_p, "wb") as f:
                f.write(working)
            proc = subprocess.run([qpdf_bin, "--warning-exit-0", in_p, out_p], capture_output=True, timeout=60)
            if proc.returncode in (0, 3) and os.path.exists(out_p) and os.path.getsize(out_p) > 0:
                with open(out_p, "rb") as f:
                    working = f.read()

    # Step 2: Flatten forms by re-rendering pages if requested
    if flatten_forms:
        pages = _render_pdf_pages_pil(working, dpi=150)
        working = _pil_pages_to_jpeg_pdf(pages, quality=90, grayscale=False)

    # Step 3: Clean rewrite + metadata stripping
    reader = PdfReader(io.BytesIO(working), strict=False)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    if strip_metadata:
        writer.add_metadata({})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
