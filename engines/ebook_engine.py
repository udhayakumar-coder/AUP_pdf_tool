"""eBook & Comic Book <-> PDF conversion engine for AUP_pdf_tool.

Covers:
- To PDF: eBook (auto), EPUB, MOBI, AZW, AZW3, DJVU, CBZ, CBR, FB2, RTF, CHM, LIT
- From PDF: PDF to eBook (selectable), PDF to EPUB, PDF to MOBI, PDF to AZW3, PDF to FB2, PDF to RTF
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from typing import List, Optional, Tuple

from engines.image_engine import images_to_pdf
from engines.office_engine import libreoffice_convert, pdf_to_rtf as office_pdf_to_rtf

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".jfif"}


def _find_calibre() -> Optional[str]:
    return shutil.which("ebook-convert")


def calibre_convert(file_bytes: bytes, input_filename: str, target_ext: str, timeout: int = 120) -> bytes:
    """Convert between eBook formats and PDF using Calibre's ebook-convert CLI."""
    calibre_bin = _find_calibre()
    if not calibre_bin:
        raise RuntimeError(
            "Calibre ('ebook-convert') is not installed on this machine. "
            "On Streamlit Cloud, ensure 'calibre' is listed in packages.txt."
        )

    ext = os.path.splitext(input_filename)[1].lower() or ".epub"
    with tempfile.TemporaryDirectory(prefix="aup_calibre_") as tmp:
        in_path = os.path.join(tmp, f"input{ext}")
        out_path = os.path.join(tmp, f"output.{target_ext.lstrip('.')}")
        with open(in_path, "wb") as f:
            f.write(file_bytes)

        env = {**os.environ, "HOME": tmp, "TMPDIR": tmp, "QT_QPA_PLATFORM": "offscreen"}
        cmd = [calibre_bin, in_path, out_path]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            err = (proc.stderr or proc.stdout or "Calibre conversion failed").strip()
            raise RuntimeError(f"Calibre conversion to .{target_ext} failed: {err}")

        with open(out_path, "rb") as f:
            return f.read()


def cbz_to_pdf(cbz_bytes: bytes) -> bytes:
    """Convert CBZ (ZIP comic archive) directly to PDF without requiring Calibre."""
    images: List[Tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(cbz_bytes)) as zf:
        names = sorted(zf.namelist())
        for name in names:
            if name.endswith("/") or "__MACOSX" in name:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in IMAGE_EXTS:
                images.append((name, zf.read(name)))
    if not images:
        raise ValueError("No image pages found inside the CBZ archive.")
    return images_to_pdf(images, page_size="Auto")


def cbr_to_pdf(cbr_bytes: bytes, filename: str = "comic.cbr") -> bytes:
    """Convert CBR (RAR comic archive) to PDF using Calibre or 7z/unrar extraction."""
    if _find_calibre():
        return calibre_convert(cbr_bytes, filename, "pdf")

    extractor = shutil.which("7z") or shutil.which("unrar") or shutil.which("unrar-free")
    if not extractor:
        raise RuntimeError(
            "CBR conversion requires Calibre ('ebook-convert') or 7z/unrar. "
            "Include 'calibre' and 'p7zip-full' in packages.txt."
        )

    with tempfile.TemporaryDirectory(prefix="aup_cbr_") as tmp:
        in_path = os.path.join(tmp, "comic.cbr")
        out_dir = os.path.join(tmp, "extracted")
        os.makedirs(out_dir, exist_ok=True)
        with open(in_path, "wb") as f:
            f.write(cbr_bytes)

        if os.path.basename(extractor).startswith("7z"):
            cmd = [extractor, "x", in_path, f"-o{out_dir}", "-y"]
        else:
            cmd = [extractor, "x", "-y", in_path, out_dir]
        subprocess.run(cmd, capture_output=True, timeout=90)

        images: List[Tuple[str, bytes]] = []
        for root, _, files in os.walk(out_dir):
            for fn in sorted(files):
                if os.path.splitext(fn)[1].lower() in IMAGE_EXTS:
                    full = os.path.join(root, fn)
                    with open(full, "rb") as f:
                        images.append((fn, f.read()))
        if not images:
            raise ValueError("No image pages could be extracted from the CBR archive.")
        return images_to_pdf(images, page_size="Auto")


def djvu_to_pdf(djvu_bytes: bytes, filename: str = "book.djvu") -> bytes:
    """Convert DJVU to PDF using DjVuLibre (ddjvu) with Calibre fallback."""
    ddjvu = shutil.which("ddjvu")
    if ddjvu:
        with tempfile.TemporaryDirectory(prefix="aup_djvu_") as tmp:
            in_path = os.path.join(tmp, "input.djvu")
            out_path = os.path.join(tmp, "output.pdf")
            with open(in_path, "wb") as f:
                f.write(djvu_bytes)
            proc = subprocess.run(
                [ddjvu, "-format=pdf", "-quality=85", in_path, out_path],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                with open(out_path, "rb") as f:
                    return f.read()

    if _find_calibre():
        return calibre_convert(djvu_bytes, filename, "pdf")

    raise RuntimeError(
        "DJVU conversion requires DjVuLibre ('ddjvu') or Calibre. "
        "Ensure 'djvulibre-bin' is listed in packages.txt."
    )


def ebook_to_pdf(file_bytes: bytes, filename: str) -> bytes:
    """Convert any supported eBook format (EPUB, MOBI, AZW, AZW3, DJVU, CBZ, CBR, FB2, RTF, CHM, LIT) to PDF."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".cbz":
        return cbz_to_pdf(file_bytes)
    if ext == ".cbr":
        return cbr_to_pdf(file_bytes, filename)
    if ext == ".djvu":
        return djvu_to_pdf(file_bytes, filename)
    if ext == ".rtf":
        try:
            return libreoffice_convert(file_bytes, filename, "pdf")
        except Exception:
            return calibre_convert(file_bytes, filename, "pdf")
    return calibre_convert(file_bytes, filename, "pdf")


def pdf_to_ebook(pdf_bytes: bytes, target_format: str = "epub") -> bytes:
    """Convert PDF to EPUB, MOBI, AZW3, FB2, or RTF."""
    fmt = target_format.lower().lstrip(".")
    if fmt == "rtf":
        try:
            return office_pdf_to_rtf(pdf_bytes)
        except Exception:
            return calibre_convert(pdf_bytes, "input.pdf", "rtf")
    return calibre_convert(pdf_bytes, "input.pdf", fmt)
