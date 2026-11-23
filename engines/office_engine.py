"""Office, Text, CSV, and Document <-> PDF conversion engine for AUP_pdf_tool.

Covers:
- To PDF: Word (DOCX/DOC), DOC, DOCM, PowerPoint (PPTX/PPT), PPT, PPSX,
          Excel (XLSX/XLS), XLS, ODT, ODS, ODP, WPS, PAGES, HWP, RTF, CSV, TXT
- From PDF: PDF to Word (DOCX), PDF to DOC, PDF to ODT, PDF to RTF,
            PDF to PowerPoint (PPTX), PDF to PPT, PDF to ODP,
            PDF to Excel (XLSX), PDF to XLS, PDF to CSV
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from typing import List, Optional

import openpyxl
import pandas as pd
import pdfplumber
from docx import Document as DocxDocument
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from pdf2docx import Converter as Pdf2DocxConverter
except ImportError:
    Pdf2DocxConverter = None


def _find_libreoffice() -> Optional[str]:
    for cmd in ("soffice", "libreoffice"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def libreoffice_convert(file_bytes: bytes, input_filename: str, target_ext: str, timeout: int = 90) -> bytes:
    """Convert a document using LibreOffice headless with an isolated temp user profile."""
    lo_bin = _find_libreoffice()
    if not lo_bin:
        raise RuntimeError(
            "LibreOffice is not installed on this server. Add 'libreoffice' to packages.txt on Streamlit Cloud."
        )

    ext = os.path.splitext(input_filename)[1].lower() or ".bin"
    with tempfile.TemporaryDirectory(prefix="aup_lo_") as tmp:
        profile_dir = os.path.join(tmp, "lo_profile")
        os.makedirs(profile_dir, exist_ok=True)
        in_path = os.path.join(tmp, f"input{ext}")
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir, exist_ok=True)

        with open(in_path, "wb") as f:
            f.write(file_bytes)

        env = {**os.environ, "HOME": tmp, "TMPDIR": tmp}
        cmd = [
            lo_bin,
            f"-env:UserInstallation=file://{profile_dir}",
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--convert-to",
            target_ext,
            "--outdir",
            out_dir,
            in_path,
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
        expected = os.path.join(out_dir, f"input.{target_ext}")
        if not os.path.exists(expected):
            # Pick any matching file created in out_dir
            candidates = [f for f in os.listdir(out_dir) if f.lower().endswith(f".{target_ext.lower()}")]
            if candidates:
                expected = os.path.join(out_dir, candidates[0])
            else:
                err = (proc.stderr or proc.stdout or "Unknown LibreOffice error").strip()
                raise RuntimeError(f"LibreOffice conversion to .{target_ext} failed: {err}")

        with open(expected, "rb") as f:
            result = f.read()
        if not result:
            raise RuntimeError(f"LibreOffice produced an empty .{target_ext} file.")
        return result


def txt_to_pdf(text_bytes: bytes, font_size: int = 10) -> bytes:
    """Convert UTF-8 / Latin-1 plain text file to a clean paginated PDF."""
    try:
        text = text_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = text_bytes.decode("latin-1", errors="replace")

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontName = "Helvetica"
    body.fontSize = font_size
    body.leading = font_size + 4

    story = []
    for line in text.splitlines():
        safe = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("  ", "&nbsp;&nbsp;")
        )
        if safe.strip():
            story.append(Paragraph(safe, body))
        else:
            story.append(Spacer(1, font_size))
    if not story:
        story.append(Paragraph("(Empty text file)", body))

    doc.build(story)
    return out.getvalue()


def csv_to_pdf(csv_bytes: bytes) -> bytes:
    """Convert CSV file into a clean formatted landscape PDF table."""
    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = csv_bytes.decode("latin-1", errors="replace")

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return txt_to_pdf(b"(Empty CSV file)")

    # Normalize column counts
    max_cols = max(len(r) for r in rows)
    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

    out = io.BytesIO()
    page_sz = landscape(A4) if max_cols > 5 else A4
    doc = SimpleDocTemplate(out, pagesize=page_sz, leftMargin=24, rightMargin=24, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"]
    cell_style.fontSize = 8 if max_cols > 6 else 9
    cell_style.leading = 10

    table_data = []
    for r_idx, row in enumerate(norm_rows):
        formatted_row = []
        for cell in row:
            safe = str(cell).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if r_idx == 0:
                safe = f"<b>{safe}</b>"
            formatted_row.append(Paragraph(safe, cell_style))
        table_data.append(formatted_row)

    avail_w = page_sz[0] - 48
    col_widths = [avail_w / max_cols] * max_cols
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    doc.build([tbl])
    return out.getvalue()


def pages_to_pdf(file_bytes: bytes, filename: str = "document.pages") -> bytes:
    """Convert Apple Pages (.pages) to PDF using embedded QuickLook preview or LibreOffice."""
    # Many .pages files are ZIP packages containing QuickLook/Preview.pdf
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            for name in zf.namelist():
                if name.lower().endswith("preview.pdf"):
                    pdf_data = zf.read(name)
                    if pdf_data.startswith(b"%PDF"):
                        return pdf_data
    except zipfile.BadZipFile:
        pass

    return libreoffice_convert(file_bytes, filename, "pdf")


def hwp_to_pdf(file_bytes: bytes, filename: str = "document.hwp") -> bytes:
    """Convert Hangul Word Processor (.hwp) to PDF via LibreOffice or pyhwp text extraction fallback."""
    try:
        return libreoffice_convert(file_bytes, filename, "pdf")
    except Exception as lo_err:
        # Fallback: try hwp5txt CLI (from pyhwp package)
        hwp_bin = shutil.which("hwp5txt")
        if hwp_bin:
            with tempfile.TemporaryDirectory(prefix="aup_hwp_") as tmp:
                in_path = os.path.join(tmp, "input.hwp")
                with open(in_path, "wb") as f:
                    f.write(file_bytes)
                proc = subprocess.run([hwp_bin, in_path], capture_output=True, timeout=60)
                if proc.returncode == 0 and proc.stdout:
                    return txt_to_pdf(proc.stdout)
        raise RuntimeError(
            f"HWP conversion requires LibreOffice HWP filter or pyhwp ('hwp5txt'). Details: {lo_err}"
        ) from lo_err


def office_to_pdf(file_bytes: bytes, filename: str) -> bytes:
    """Route any office/document format to PDF."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".txt":
        return txt_to_pdf(file_bytes)
    if ext == ".csv":
        return csv_to_pdf(file_bytes)
    if ext == ".pages":
        return pages_to_pdf(file_bytes, filename)
    if ext == ".hwp":
        return hwp_to_pdf(file_bytes, filename)
    return libreoffice_convert(file_bytes, filename, "pdf")


def pdf_to_docx(pdf_bytes: bytes) -> bytes:
    """Convert PDF to editable DOCX using pdf2docx (layout-preserving) with python-docx fallback."""
    if Pdf2DocxConverter is not None:
        with tempfile.TemporaryDirectory(prefix="aup_p2d_") as tmp:
            in_path = os.path.join(tmp, "in.pdf")
            out_path = os.path.join(tmp, "out.docx")
            with open(in_path, "wb") as f:
                f.write(pdf_bytes)
            cv = Pdf2DocxConverter(in_path)
            try:
                cv.convert(out_path, start=0, end=None)
            finally:
                cv.close()
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                with open(out_path, "rb") as f:
                    return f.read()

    # Fallback: extract text & tables with pdfplumber into python-docx
    doc = DocxDocument()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages):
            if idx > 0:
                doc.add_page_break()
            text = page.extract_text() or ""
            for line in text.splitlines():
                doc.add_paragraph(line)
            for table in page.extract_tables() or []:
                if not table:
                    continue
                cols = max(len(r) for r in table)
                t = doc.add_table(rows=len(table), cols=cols)
                for r_i, row in enumerate(table):
                    for c_i, val in enumerate(row):
                        t.cell(r_i, c_i).text = str(val or "")
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def pdf_to_doc(pdf_bytes: bytes) -> bytes:
    docx_bytes = pdf_to_docx(pdf_bytes)
    return libreoffice_convert(docx_bytes, "converted.docx", "doc")


def pdf_to_odt(pdf_bytes: bytes) -> bytes:
    docx_bytes = pdf_to_docx(pdf_bytes)
    return libreoffice_convert(docx_bytes, "converted.docx", "odt")


def pdf_to_rtf(pdf_bytes: bytes) -> bytes:
    docx_bytes = pdf_to_docx(pdf_bytes)
    return libreoffice_convert(docx_bytes, "converted.docx", "rtf")


def pdf_to_excel(pdf_bytes: bytes) -> bytes:
    """Extract tables (or structured text lines) from PDF into a multi-sheet XLSX workbook."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            ws = wb.create_sheet(title=f"Page_{idx}")
            tables = page.extract_tables() or []
            if tables:
                for t_idx, table in enumerate(tables):
                    if t_idx > 0:
                        ws.append([])
                    for row in table:
                        ws.append([cell if cell is not None else "" for cell in row])
            else:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    ws.append([line])

    if not wb.sheetnames:
        ws = wb.create_sheet(title="Page_1")
        ws.append(["No extractable content found."])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def pdf_to_xls(pdf_bytes: bytes) -> bytes:
    xlsx_bytes = pdf_to_excel(pdf_bytes)
    return libreoffice_convert(xlsx_bytes, "converted.xlsx", "xls")


def pdf_to_csv(pdf_bytes: bytes) -> bytes:
    """Extract tables (or text rows) from PDF into a UTF-8 CSV file."""
    rows: List[List[str]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            if tables:
                for table in tables:
                    for row in table:
                        rows.append([str(c).strip() if c is not None else "" for c in row])
            else:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    if line.strip():
                        rows.append([line.strip()])

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def pdf_to_pptx(pdf_bytes: bytes, editable_text: bool = False, dpi: int = 150) -> bytes:
    """Convert PDF pages to a PowerPoint (.pptx) presentation.

    - editable_text=False (default): renders each PDF page as a crisp HD slide image.
    - editable_text=True: places extracted page text into editable PowerPoint text boxes.
    """
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    if editable_text:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                slide = prs.slides.add_slide(blank_layout)
                tb = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(12.333), Inches(6.5))
                tf = tb.text_frame
                tf.word_wrap = True
                text = page.extract_text() or "(No extractable text on this page)"
                for idx, line in enumerate(text.splitlines()):
                    p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                    p.text = line
                    p.font.size = Pt(14)
    else:
        pil_pages: List[Image.Image] = []
        if fitz is not None:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
                for page in doc:
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    pil_pages.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
            finally:
                doc.close()
        elif pdfium is not None:
            doc = pdfium.PdfDocument(pdf_bytes)
            try:
                for i in range(len(doc)):
                    pil_pages.append(doc[i].render(scale=dpi / 72.0).to_pil().convert("RGB"))
            finally:
                doc.close()
        else:
            raise RuntimeError("Neither PyMuPDF (fitz) nor pypdfium2 is available to render slides.")

        sw, sh = prs.slide_width, prs.slide_height
        for im in pil_pages:
            slide = prs.slides.add_slide(blank_layout)
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            buf.seek(0)
            iw, ih = im.size
            scale = min(sw / iw, sh / ih)
            dw, dh = int(iw * scale), int(ih * scale)
            left = int((sw - dw) / 2)
            top = int((sh - dh) / 2)
            slide.shapes.add_picture(buf, left, top, width=dw, height=dh)

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def pdf_to_ppt(pdf_bytes: bytes, editable_text: bool = False) -> bytes:
    pptx_bytes = pdf_to_pptx(pdf_bytes, editable_text=editable_text)
    return libreoffice_convert(pptx_bytes, "converted.pptx", "ppt")


def pdf_to_odp(pdf_bytes: bytes, editable_text: bool = False) -> bytes:
    pptx_bytes = pdf_to_pptx(pdf_bytes, editable_text=editable_text)
    return libreoffice_convert(pptx_bytes, "converted.pptx", "odp")
