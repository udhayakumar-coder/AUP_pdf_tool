"""Automated verification suite for AUP_pdf_tool (74 tools)."""

from __future__ import annotations

import io
import os
import py_compile
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PIL import Image
from pypdf import PdfReader

from engines import get_system_health
from engines.ebook_engine import cbz_to_pdf
from engines.image_engine import images_to_pdf, pdf_to_images
from engines.office_engine import (
    csv_to_pdf,
    office_to_pdf,
    pdf_to_csv,
    pdf_to_doc,
    pdf_to_docx,
    pdf_to_excel,
    pdf_to_odp,
    pdf_to_odt,
    pdf_to_ppt,
    pdf_to_pptx,
    pdf_to_rtf,
    pdf_to_xls,
    txt_to_pdf,
)
from engines.pdf_core import (
    add_page_numbers,
    add_watermark,
    compress_pdf,
    crop_pdf,
    extract_images_from_pdf,
    extract_pages,
    get_page_count,
    merge_pdf_and_images,
    merge_pdfs,
    organize_pdf,
    pdf_to_text,
    protect_pdf,
    remove_pages,
    rotate_pdf,
    split_pdf,
    unlock_pdf,
)
from engines.pro_tools import (
    compress_to_target_kb,
    grayscale_pdf,
    html_or_url_to_pdf,
    id_card_to_pdf,
    repair_and_flatten_pdf,
    sign_and_seal_pdf,
)
from engines.registry import TOOLS


def _make_sample_image(fmt: str = "PNG", color=(37, 99, 235)) -> bytes:
    im = Image.new("RGB", (320, 200), color)
    buf = io.BytesIO()
    im.save(buf, format=fmt)
    return buf.getvalue()


def main() -> None:
    # 1. Syntax check all Python files
    for dirpath, _, filenames in os.walk(ROOT):
        for fn in filenames:
            if fn.endswith(".py"):
                py_compile.compile(os.path.join(dirpath, fn), doraise=True)
    print("[PASS] Syntax compilation passed for all .py files.")

    # 2. Verify exact 74 unique tools & handler coverage in app.py
    assert len(TOOLS) == 74, f"Expected 74 tools, got {len(TOOLS)}"
    assert len({t.slug for t in TOOLS}) == 74, "Duplicate tool slugs detected"
    with open(os.path.join(ROOT, "app.py"), "r", encoding="utf-8") as f:
        app_src = f.read()
    for t in TOOLS:
        assert f'"{t.handler}"' in app_src, f"Handler {t.handler} not wired in app.py"
    print("[PASS] All 74 tools registered with unique slugs and wired handlers.")

    # 3. Core PDF & Text tests
    pdf1 = txt_to_pdf(b"AUP PDF Tool Test Page 1\nSecond line of text.")
    pdf2 = txt_to_pdf(b"AUP PDF Tool Test Page 2\nMore content here.")
    assert get_page_count(pdf1) == 1
    assert "AUP PDF Tool" in pdf_to_text(pdf1)

    merged = merge_pdfs([pdf1, pdf2, pdf1])
    assert get_page_count(merged) == 3

    png_bytes = _make_sample_image("PNG")
    jpg_bytes = _make_sample_image("JPEG", color=(16, 185, 129))
    merged_mix = merge_pdf_and_images([("a.pdf", pdf1), ("b.png", png_bytes)])
    assert get_page_count(merged_mix) == 2

    split_bytes, split_name, _ = split_pdf(merged, mode="ranges", ranges_str="1-2, 3")
    assert split_name.endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(split_bytes)) as zf:
        assert len(zf.namelist()) == 2

    assert get_page_count(crop_pdf(merged, 5, 5, 5, 5)) == 3
    assert get_page_count(organize_pdf(merged, "3, 1, 2")) == 3
    assert get_page_count(rotate_pdf(merged, 90, "1, 3")) == 3
    assert get_page_count(remove_pages(merged, "2")) == 2
    assert get_page_count(extract_pages(merged, "1, 3")) == 2
    assert get_page_count(add_page_numbers(merged)) == 3
    assert get_page_count(add_watermark(merged, text="AUP E-SERVICES")) == 3
    assert get_page_count(add_watermark(merged, image_bytes=png_bytes)) == 3
    assert get_page_count(compress_pdf(merged, quality_level=50)) == 3

    protected = protect_pdf(pdf1, "secret123")
    assert PdfReader(io.BytesIO(protected)).is_encrypted
    unlocked = unlock_pdf(protected, "secret123")
    assert not PdfReader(io.BytesIO(unlocked)).is_encrypted
    print("[PASS] All Core PDF, Security & Text engine tests passed.")

    # 4. CSC & Pro Tools tests
    target_pdf, met = compress_to_target_kb(merged_mix, target_kb=100)
    assert get_page_count(target_pdf) == 2 and met

    id_stacked = id_card_to_pdf(png_bytes, jpg_bytes, layout="Stacked (Vertical)")
    id_side = id_card_to_pdf(png_bytes, jpg_bytes, layout="Side-by-Side (Horizontal)")
    assert get_page_count(id_stacked) == 1 and get_page_count(id_side) == 1

    signed = sign_and_seal_pdf(pdf1, png_bytes, target_page="Last Page")
    assert get_page_count(signed) == 1

    bw = grayscale_pdf(merged_mix, dpi=96, high_contrast=True)
    assert get_page_count(bw) == 2

    html_pdf = html_or_url_to_pdf(html_content="<h1>AUP E-Services</h1><p>Test HTML to PDF</p>")
    assert get_page_count(html_pdf) >= 1

    repaired = repair_and_flatten_pdf(pdf1, flatten_forms=True, strip_metadata=True)
    assert get_page_count(repaired) == 1
    print("[PASS] All CSC & Pro Tools (Target KB, ID Card, Sign/Seal, Grayscale, HTML, Repair/Flatten) passed.")

    # 5. Image <-> PDF & Extract Images tests
    img_pdf = images_to_pdf([("1.png", png_bytes), ("2.jpg", jpg_bytes)], page_size="A4")
    assert get_page_count(img_pdf) == 2
    ext_zip, ext_count = extract_images_from_pdf(img_pdf)
    assert ext_count >= 2 and len(ext_zip) > 0
    rendered_zip, rendered_count = pdf_to_images(img_pdf, img_format="JPG", dpi=96)
    assert rendered_count == 2 and len(rendered_zip) > 0
    print("[PASS] All Image <-> PDF & Extract Images tests passed.")

    # 6. Office & CSV <-> PDF tests
    csv_pdf = csv_to_pdf(b"Name,Service,Fee\nRavi,PAN Card,200\nPriya,Passport,500\n")
    assert get_page_count(csv_pdf) == 1
    assert b"Ravi" in pdf_to_csv(csv_pdf)
    assert len(pdf_to_excel(csv_pdf)) > 100
    docx_out = pdf_to_docx(pdf1)
    assert len(docx_out) > 100
    assert len(pdf_to_pptx(pdf1, editable_text=False, dpi=96)) > 100
    assert len(pdf_to_pptx(pdf1, editable_text=True)) > 100

    health = get_system_health()
    if health.get("LibreOffice (Office/ODT/WPS/RTF)"):
        assert office_to_pdf(docx_out, "sample.docx").startswith(b"%PDF")
        assert len(pdf_to_doc(pdf1)) > 100
        assert len(pdf_to_odt(pdf1)) > 100
        assert len(pdf_to_rtf(pdf1)) > 50
        assert len(pdf_to_xls(csv_pdf)) > 100
        assert len(pdf_to_ppt(pdf1, editable_text=True)) > 100
        assert len(pdf_to_odp(pdf1, editable_text=True)) > 100
        print("[PASS] LibreOffice round-trip tests passed.")

    # 7. CBZ to PDF test
    cbz_buf = io.BytesIO()
    with zipfile.ZipFile(cbz_buf, "w") as zf:
        zf.writestr("01.jpg", jpg_bytes)
        zf.writestr("02.png", png_bytes)
    assert get_page_count(cbz_to_pdf(cbz_buf.getvalue())) == 2
    print("[PASS] CBZ to PDF engine test passed.")
    print("ALL 74-TOOL VERIFICATION CHECKS PASSED!")


if __name__ == "__main__":
    main()
