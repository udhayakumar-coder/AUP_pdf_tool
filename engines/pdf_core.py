"""Core PDF manipulation engine for AUP_pdf_tool.

Covers: Compress (slider), Merge PDF, Merge PDF & Image, Split, Crop, Organize,
Rotate, Remove Pages, Extract Pages, Extract Images, Add Page Number,
Add Watermark, Unlock PDF, Protect PDF, PDF to Text, and Page Thumbnails.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import List, Optional, Sequence, Tuple

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass


def get_page_count(pdf_bytes: bytes) -> int:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def parse_page_ranges(range_str: str, total_pages: int) -> List[int]:
    """Parse 1-indexed page ranges like '1-3, 5, 7-9' into 0-indexed page indices."""
    if not range_str or not range_str.strip():
        return list(range(total_pages))
    indices: List[int] = []
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            start = max(1, int(bounds[0].strip()))
            end = min(total_pages, int(bounds[1].strip()))
            if start <= end:
                indices.extend(range(start - 1, end))
            else:
                indices.extend(range(start - 1, end - 2, -1))
        else:
            p = int(part)
            if 1 <= p <= total_pages:
                indices.append(p - 1)
    return indices


def render_page_thumbnails(pdf_bytes: bytes, max_pages: int = 24, dpi: int = 72) -> List[bytes]:
    """Render PDF page thumbnails as PNG bytes for visual previews in Streamlit."""
    thumbs: List[bytes] = []
    if fitz is not None:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            for idx in range(min(len(doc), max_pages)):
                pix = doc[idx].get_pixmap(matrix=mat, alpha=False)
                thumbs.append(pix.tobytes("png"))
        finally:
            doc.close()
        return thumbs

    if pdfium is not None:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            scale = dpi / 72.0
            for idx in range(min(len(doc), max_pages)):
                page = doc[idx]
                pil_img = page.render(scale=scale).to_pil()
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                thumbs.append(buf.getvalue())
        finally:
            doc.close()
        return thumbs

    return thumbs


def _find_ghostscript() -> Optional[str]:
    for cmd in ("gs", "gswin64c", "gswin32c"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def compress_pdf(pdf_bytes: bytes, quality_level: int = 60) -> bytes:
    """Compress PDF using a slider value (10 = maximum compression, 95 = high quality).

    Uses Ghostscript when available for true image downsampling & stream compression,
    with PyMuPDF/pypdf lossless + stream compression fallback.
    """
    quality_level = max(10, min(95, int(quality_level)))
    gs_bin = _find_ghostscript()

    if gs_bin:
        if quality_level <= 30:
            preset = "/screen"
            img_dpi = 72
        elif quality_level <= 55:
            preset = "/ebook"
            img_dpi = 120
        elif quality_level <= 80:
            preset = "/printer"
            img_dpi = 180
        else:
            preset = "/prepress"
            img_dpi = 240

        with tempfile.TemporaryDirectory(prefix="aup_gs_") as tmp:
            in_path = os.path.join(tmp, "input.pdf")
            out_path = os.path.join(tmp, "output.pdf")
            with open(in_path, "wb") as f:
                f.write(pdf_bytes)

            cmd = [
                gs_bin,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={preset}",
                "-dDownsampleColorImages=true",
                f"-dColorImageResolution={img_dpi}",
                "-dDownsampleGrayImages=true",
                f"-dGrayImageResolution={img_dpi}",
                "-dDownsampleMonoImages=true",
                f"-dMonoImageResolution={img_dpi}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={out_path}",
                in_path,
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
            if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                with open(out_path, "rb") as f:
                    compressed = f.read()
                return compressed if len(compressed) < len(pdf_bytes) else pdf_bytes

    # Fallback 1: PyMuPDF garbage collection + deflate + image recompression
    if fitz is not None:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            out_buf = io.BytesIO()
            doc.save(out_buf, garbage=4, deflate=True, clean=True)
            compressed = out_buf.getvalue()
            return compressed if len(compressed) < len(pdf_bytes) else pdf_bytes
        finally:
            doc.close()

    # Fallback 2: pypdf content stream compression & image quality reduction
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for page in writer.pages:
        try:
            page.compress_content_streams(level=9)
        except Exception:
            pass
    try:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    except Exception:
        pass
    out = io.BytesIO()
    writer.write(out)
    compressed = out.getvalue()
    return compressed if len(compressed) < len(pdf_bytes) else pdf_bytes


def merge_pdfs(pdf_files: Sequence[bytes]) -> bytes:
    """Merge multiple PDF byte payloads in the given order."""
    writer = PdfWriter()
    for data in pdf_files:
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _image_bytes_to_single_page_pdf(img_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(img_bytes))
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def merge_pdf_and_images(items: Sequence[Tuple[str, bytes]]) -> bytes:
    """Combine mixed PDFs and images into a single PDF preserving input order.

    Args:
        items: list of (filename, raw_bytes) tuples.
    """
    writer = PdfWriter()
    for filename, data in items:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            for page in reader.pages:
                writer.add_page(page)
        else:
            img_pdf = _image_bytes_to_single_page_pdf(data)
            reader = PdfReader(io.BytesIO(img_pdf))
            for page in reader.pages:
                writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def split_pdf(
    pdf_bytes: bytes,
    mode: str = "ranges",
    ranges_str: str = "",
    fixed_step: int = 1,
) -> Tuple[bytes, str, str]:
    """Split PDF by fixed page count or custom ranges.

    Returns: (output_bytes, filename, mime_type)
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    chunks: List[Tuple[str, List[int]]] = []

    if mode == "fixed":
        step = max(1, int(fixed_step))
        for start in range(0, total, step):
            end = min(total, start + step)
            chunks.append((f"pages_{start + 1}_to_{end}.pdf", list(range(start, end))))
    else:
        raw_parts = [p.strip() for p in ranges_str.split(",") if p.strip()]
        if not raw_parts:
            chunks = [(f"page_{i + 1}.pdf", [i]) for i in range(total)]
        else:
            for idx, part in enumerate(raw_parts, start=1):
                pages = parse_page_ranges(part, total)
                if pages:
                    safe_label = re.sub(r"[^0-9a-zA-Z_-]+", "_", part)
                    chunks.append((f"part_{idx}_pages_{safe_label}.pdf", pages))

    if len(chunks) == 1:
        writer = PdfWriter()
        for p in chunks[0][1]:
            writer.add_page(reader.pages[p])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue(), chunks[0][0], "application/pdf"

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, page_indices in chunks:
            writer = PdfWriter()
            for p in page_indices:
                writer.add_page(reader.pages[p])
            pbuf = io.BytesIO()
            writer.write(pbuf)
            zf.writestr(fname, pbuf.getvalue())
    return zip_buf.getvalue(), "split_pdfs.zip", "application/zip"


def crop_pdf(
    pdf_bytes: bytes,
    left_pct: float = 0.0,
    right_pct: float = 0.0,
    top_pct: float = 0.0,
    bottom_pct: float = 0.0,
    pages_str: str = "",
) -> bytes:
    """Crop selected (or all) pages by percentage margins."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    target_pages = set(parse_page_ranges(pages_str, total)) if pages_str.strip() else set(range(total))

    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx in target_pages:
            box = page.mediabox
            llx = float(box.lower_left[0])
            lly = float(box.lower_left[1])
            urx = float(box.upper_right[0])
            ury = float(box.upper_right[1])
            w = urx - llx
            h = ury - lly
            new_llx = llx + w * (left_pct / 100.0)
            new_urx = urx - w * (right_pct / 100.0)
            new_lly = lly + h * (bottom_pct / 100.0)
            new_ury = ury - h * (top_pct / 100.0)
            if new_llx < new_urx and new_lly < new_ury:
                page.mediabox.lower_left = (new_llx, new_lly)
                page.mediabox.upper_right = (new_urx, new_ury)
                page.cropbox.lower_left = (new_llx, new_lly)
                page.cropbox.upper_right = (new_urx, new_ury)
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def organize_pdf(pdf_bytes: bytes, order_str: str) -> bytes:
    """Rearrange PDF pages according to a 1-indexed comma-separated order string."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    indices = parse_page_ranges(order_str, total)
    if not indices:
        raise ValueError("Please specify at least one valid page number.")
    writer = PdfWriter()
    for idx in indices:
        writer.add_page(reader.pages[idx])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def rotate_pdf(pdf_bytes: bytes, angle: int = 90, pages_str: str = "") -> bytes:
    """Rotate selected (or all) PDF pages clockwise by 90, 180, or 270 degrees."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    target_pages = set(parse_page_ranges(pages_str, total)) if pages_str.strip() else set(range(total))
    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx in target_pages:
            page.rotate(int(angle))
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def remove_pages(pdf_bytes: bytes, pages_to_remove: str) -> bytes:
    """Remove single or multiple 1-indexed pages from a PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    remove_set = set(parse_page_ranges(pages_to_remove, total))
    remaining = [i for i in range(total) if i not in remove_set]
    if not remaining:
        raise ValueError("Cannot remove every page from the PDF.")
    writer = PdfWriter()
    for idx in remaining:
        writer.add_page(reader.pages[idx])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def extract_pages(pdf_bytes: bytes, pages_str: str) -> bytes:
    """Extract selected pages into a new standalone PDF."""
    return organize_pdf(pdf_bytes, pages_str)


def extract_images_from_pdf(pdf_bytes: bytes) -> Tuple[bytes, int]:
    """Extract all embedded images from a PDF and return (zip_bytes, image_count)."""
    zip_buf = io.BytesIO()
    count = 0

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if fitz is not None:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            seen_xrefs = set()
            try:
                for page_idx in range(len(doc)):
                    for img_info in doc[page_idx].get_images(full=True):
                        xref = img_info[0]
                        if xref in seen_xrefs:
                            continue
                        seen_xrefs.add(xref)
                        base = doc.extract_image(xref)
                        ext = base.get("ext", "png")
                        count += 1
                        zf.writestr(f"page_{page_idx + 1}_img_{count}.{ext}", base["image"])
            finally:
                doc.close()
        else:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page_idx, page in enumerate(reader.pages):
                for img_file in page.images:
                    count += 1
                    zf.writestr(f"page_{page_idx + 1}_{count}_{img_file.name}", img_file.data)

    return zip_buf.getvalue(), count


def add_page_numbers(
    pdf_bytes: bytes,
    position: str = "bottom-center",
    fmt: str = "{n} / {total}",
    font_size: int = 11,
    start_number: int = 1,
    margin: int = 24,
) -> bytes:
    """Stamp page numbers onto every page of a PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    writer = PdfWriter()

    for idx, page in enumerate(reader.pages):
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        overlay_buf = io.BytesIO()
        c = canvas.Canvas(overlay_buf, pagesize=(w, h))
        c.setFont("Helvetica", font_size)
        c.setFillColorRGB(0.2, 0.2, 0.2)

        label = fmt.format(n=idx + start_number, total=total + start_number - 1)
        y = margin if position.startswith("bottom") else h - margin - font_size
        if position.endswith("left"):
            c.drawString(margin, y, label)
        elif position.endswith("right"):
            c.drawRightString(w - margin, y, label)
        else:
            c.drawCentredString(w / 2.0, y, label)
        c.save()

        overlay_pdf = PdfReader(io.BytesIO(overlay_buf.getvalue()))
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def add_watermark(
    pdf_bytes: bytes,
    text: str = "CONFIDENTIAL",
    font_size: int = 42,
    opacity: float = 0.25,
    angle: int = 45,
    color_hex: str = "#888888",
    image_bytes: Optional[bytes] = None,
) -> bytes:
    """Overlay a text or image watermark across every page of a PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    tmp_img_path = None
    tmp_dir = None
    if image_bytes:
        tmp_dir = tempfile.TemporaryDirectory(prefix="aup_wm_")
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        # Apply opacity to alpha channel
        alpha = img.split()[3].point(lambda p: int(p * max(0.05, min(1.0, opacity))))
        img.putalpha(alpha)
        tmp_img_path = os.path.join(tmp_dir.name, "wm.png")
        img.save(tmp_img_path, format="PNG")
        img_w, img_h = img.size

    try:
        for page in reader.pages:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            overlay_buf = io.BytesIO()
            c = canvas.Canvas(overlay_buf, pagesize=(w, h))
            c.saveState()
            c.translate(w / 2.0, h / 2.0)
            c.rotate(angle)
            if tmp_img_path:
                max_dim = min(w, h) * 0.55
                scale = min(max_dim / img_w, max_dim / img_h)
                dw, dh = img_w * scale, img_h * scale
                c.drawImage(tmp_img_path, -dw / 2.0, -dh / 2.0, width=dw, height=dh, mask="auto")
            else:
                try:
                    c.setFillAlpha(max(0.05, min(1.0, opacity)))
                except Exception:
                    pass
                c.setFillColor(HexColor(color_hex))
                c.setFont("Helvetica-Bold", font_size)
                c.drawCentredString(0, 0, text or "WATERMARK")
            c.restoreState()
            c.save()

            overlay_pdf = PdfReader(io.BytesIO(overlay_buf.getvalue()))
            page.merge_page(overlay_pdf.pages[0])
            writer.add_page(page)
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def unlock_pdf(pdf_bytes: bytes, password: str) -> bytes:
    """Remove password protection from an encrypted PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if reader.is_encrypted:
        result = reader.decrypt(password)
        if result == 0:
            raise ValueError("Incorrect password. Unable to unlock this PDF.")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def protect_pdf(pdf_bytes: bytes, user_password: str, owner_password: Optional[str] = None) -> bytes:
    """Encrypt a PDF using AES-256 password protection."""
    if not user_password:
        raise ValueError("Please enter a password to protect the PDF.")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(
        user_password=user_password,
        owner_password=owner_password or user_password,
        algorithm="AES-256",
    )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract readable text from every page of a PDF."""
    if fitz is not None:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            parts = [f"--- Page {i + 1} ---\n{page.get_text('text')}" for i, page in enumerate(doc)]
            return "\n\n".join(parts)
        finally:
            doc.close()

    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = [f"--- Page {i + 1} ---\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages)]
    return "\n\n".join(parts)
