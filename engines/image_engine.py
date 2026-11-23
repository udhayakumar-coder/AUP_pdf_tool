"""Image <-> PDF conversion engine for AUP_pdf_tool.

Covers: Image to PDF, JPG to PDF, AVIF to PDF, HEIC to PDF, HEIF to PDF,
TIFF to PDF (including multi-page TIFF), JFIF to PDF, PDF to Image, PDF to JPG.
"""

from __future__ import annotations

import io
import zipfile
from typing import List, Sequence, Tuple

from PIL import Image, ImageSequence
from reportlab.lib.pagesizes import A4, LETTER, landscape
from reportlab.lib.utils import ImageReader
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


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        alpha = img.split()[-1] if img.mode in ("RGBA", "LA") else None
        bg.paste(img, mask=alpha)
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def images_to_pdf(
    image_files: Sequence[Tuple[str, bytes]],
    page_size: str = "Auto",
    orientation: str = "Portrait",
    margin_pt: int = 18,
) -> bytes:
    """Convert one or more images (including multi-frame TIFF, HEIC, HEIF, AVIF, JFIF, JPG, PNG) to a single PDF."""
    frames: List[Image.Image] = []
    for filename, data in image_files:
        try:
            im = Image.open(io.BytesIO(data))
            for frame in ImageSequence.Iterator(im):
                frames.append(_to_rgb(frame.copy()))
        except Exception as exc:
            raise ValueError(
                f"Could not decode image '{filename}'. For HEIC/HEIF/AVIF ensure pillow-heif is installed. ({exc})"
            ) from exc

    if not frames:
        raise ValueError("No valid images were provided.")

    if page_size == "Auto":
        out = io.BytesIO()
        frames[0].save(out, format="PDF", save_all=True, append_images=frames[1:], resolution=150.0)
        return out.getvalue()

    base_size = A4 if page_size == "A4" else LETTER
    if orientation == "Landscape":
        base_size = landscape(base_size)
    pw, ph = base_size

    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(pw, ph))
    avail_w = max(10.0, pw - 2 * margin_pt)
    avail_h = max(10.0, ph - 2 * margin_pt)

    for frame in frames:
        iw, ih = frame.size
        scale = min(avail_w / iw, avail_h / ih)
        dw, dh = iw * scale, ih * scale
        x = (pw - dw) / 2.0
        y = (ph - dh) / 2.0
        img_buf = io.BytesIO()
        frame.save(img_buf, format="JPEG", quality=92)
        img_buf.seek(0)
        c.drawImage(ImageReader(img_buf), x, y, width=dw, height=dh)
        c.showPage()

    c.save()
    return out.getvalue()


def pdf_to_images(
    pdf_bytes: bytes,
    img_format: str = "PNG",
    dpi: int = 150,
    jpg_quality: int = 90,
) -> Tuple[bytes, int]:
    """Render each page of a PDF to an image (PNG/JPG/WEBP) and package into a ZIP."""
    fmt_upper = img_format.upper()
    pil_fmt = "JPEG" if fmt_upper in ("JPG", "JPEG") else fmt_upper
    ext = "jpg" if pil_fmt == "JPEG" else fmt_upper.lower()

    pil_pages: List[Image.Image] = []
    if fitz is not None:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pil_pages.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        finally:
            doc.close()
    elif pdfium is not None:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            scale = dpi / 72.0
            for i in range(len(doc)):
                pil_pages.append(doc[i].render(scale=scale).to_pil().convert("RGB"))
        finally:
            doc.close()
    else:
        raise RuntimeError("Neither PyMuPDF (fitz) nor pypdfium2 is available to render PDF pages.")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, im in enumerate(pil_pages, start=1):
            buf = io.BytesIO()
            save_kwargs = {"quality": jpg_quality} if pil_fmt in ("JPEG", "WEBP") else {}
            im.save(buf, format=pil_fmt, **save_kwargs)
            zf.writestr(f"page_{idx:03d}.{ext}", buf.getvalue())

    return zip_buf.getvalue(), len(pil_pages)
