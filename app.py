"""AUP_pdf_tool — All-in-One 74-Tool PDF & Document Suite built with Streamlit."""

from __future__ import annotations

import os
import sys
from typing import List, Tuple

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import streamlit as st

from engines import get_system_health
from engines.ebook_engine import ebook_to_pdf, pdf_to_ebook
from engines.image_engine import images_to_pdf, pdf_to_images
from engines.office_engine import (
    office_to_pdf,
    pdf_to_csv,
    pdf_to_doc,
    pdf_to_docx,
    pdf_to_excel,
    pdf_to_odp,
    pdf_to_odt,
    pdf_to_ppt,
    pdf_to_pptx,
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
    render_page_thumbnails,
    rotate_pdf,
    split_pdf,
    unlock_pdf,
)
from engines.pro_tools import (
    compress_to_target_kb,
    grayscale_pdf,
    html_or_url_to_pdf,
    id_card_to_pdf,
    ocr_pdf,
    repair_and_flatten_pdf,
    sign_and_seal_pdf,
)
from engines.registry import ALL_IMG_EXTS, CATEGORIES, TOOL_BY_SLUG, TOOLS, ToolSpec

st.set_page_config(
    page_title="AUP PDF Tool — 74-in-1 PDF Suite",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
.aup-hero {
    background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #2563EB 100%);
    color: #FFFFFF;
    padding: 1.5rem 2rem;
    border-radius: 14px;
    margin-bottom: 1.25rem;
}
.aup-hero h1 {
    margin: 0;
    font-size: 1.9rem;
    font-weight: 800;
    letter-spacing: -0.02em;
}
.aup-hero p {
    margin: 0.35rem 0 0 0;
    opacity: 0.92;
    font-size: 0.98rem;
}
.tool-card {
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 0.9rem 1rem;
    background: #FFFFFF;
    min-height: 118px;
    margin-bottom: 0.35rem;
}
.tool-card-title {
    font-weight: 700;
    font-size: 1.02rem;
    color: #0F172A;
    margin-bottom: 0.25rem;
}
.tool-card-desc {
    font-size: 0.84rem;
    color: #475569;
    line-height: 1.35;
}
.tool-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.12rem 0.5rem;
    border-radius: 999px;
    background: #EFF6FF;
    color: #1D4ED8;
    margin-top: 0.45rem;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "active_tool" not in st.session_state:
    st.session_state.active_tool = None


def _fmt_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def _stem(filename: str) -> str:
    return os.path.splitext(filename)[0] or "output"


def _mime_for(ext: str) -> str:
    mapping = {
        "pdf": "application/pdf",
        "zip": "application/zip",
        "txt": "text/plain",
        "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ppt": "application/vnd.ms-powerpoint",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "odt": "application/vnd.oasis.opendocument.text",
        "odp": "application/vnd.oasis.opendocument.presentation",
        "rtf": "application/rtf",
        "epub": "application/epub+zip",
        "mobi": "application/x-mobipocket-ebook",
        "azw3": "application/octet-stream",
        "fb2": "application/xml",
    }
    return mapping.get(ext.lower().lstrip("."), "application/octet-stream")


def _show_thumbnails(pdf_bytes: bytes) -> None:
    try:
        total = get_page_count(pdf_bytes)
        st.caption(f"Document loaded: **{total} page(s)** | Size: **{_fmt_size(len(pdf_bytes))}**")
        thumbs = render_page_thumbnails(pdf_bytes, max_pages=12, dpi=60)
        if thumbs:
            with st.expander(f"Preview Pages (showing {len(thumbs)} of {total})", expanded=False):
                cols = st.columns(4)
                for idx, png in enumerate(thumbs):
                    cols[idx % 4].image(png, caption=f"Page {idx + 1}", use_container_width=True)
    except Exception:
        pass


def render_sidebar() -> Tuple[str, str]:
    with st.sidebar:
        st.markdown("## 📄 AUP PDF Tool")
        st.caption(f"{len(TOOLS)}-in-1 PDF, Image, Office, eBook & CSC Suite")

        if st.button(f"🏠 All {len(TOOLS)} Tools Dashboard", use_container_width=True):
            st.session_state.active_tool = None
            st.rerun()

        st.divider()
        search_q = st.text_input("🔍 Quick Search Tool", placeholder="e.g. Target KB, ID Card, OCR, Word...")
        selected_cat = st.radio("Category", CATEGORIES, index=0)

        st.divider()
        with st.expander("⚙️ Engine Status", expanded=False):
            health = get_system_health()
            for name, ok in health.items():
                icon = "✅" if ok else "⚠️"
                st.write(f"{icon} {name}")
            st.caption("Missing CLI engines install automatically on Streamlit Cloud via `packages.txt`.")

    return search_q.strip().lower(), selected_cat


def render_dashboard(search_q: str, selected_cat: str) -> None:
    st.markdown(
        f"""
        <div class="aup-hero">
            <h1>📄 AUP PDF Tool</h1>
            <p>All {len(TOOLS)} PDF, Image, Office, eBook &amp; CSC e-Services tools in one fast Streamlit workspace.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    filtered = [
        t
        for t in TOOLS
        if (selected_cat == "All Tools" or t.category == selected_cat)
        and (
            not search_q
            or search_q in t.name.lower()
            or search_q in t.description.lower()
            or search_q in t.category.lower()
            or any(search_q in ext for ext in t.accept_exts)
        )
    ]

    st.caption(f"Showing **{len(filtered)}** of **{len(TOOLS)}** tools")

    if not filtered:
        st.info("No matching tool found. Try clearing the search filter.")
        return

    cols_per_row = 3
    for row_start in range(0, len(filtered), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, tool in enumerate(filtered[row_start : row_start + cols_per_row]):
            with cols[col_idx]:
                st.markdown(
                    f"""
                    <div class="tool-card">
                        <div class="tool-card-title">{tool.icon} {tool.name}</div>
                        <div class="tool-card-desc">{tool.description}</div>
                        <span class="tool-badge">{tool.category}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(f"Open {tool.name}", key=f"open_{tool.slug}", use_container_width=True):
                    st.session_state.active_tool = tool.slug
                    st.rerun()


def render_tool_workspace(tool: ToolSpec) -> None:
    top_col1, top_col2 = st.columns([1, 5])
    with top_col1:
        if st.button("← Back to All Tools", use_container_width=True):
            st.session_state.active_tool = None
            st.rerun()
    with top_col2:
        st.markdown(f"### {tool.icon} {tool.name}")
        st.caption(f"{tool.description}  •  Category: **{tool.category}**")

    st.divider()
    h = tool.handler

    # --- Custom Input Tools (ID Card Dual Upload / HTML & URL Input) ---
    if h == "id_card_to_pdf":
        c1, c2 = st.columns(2)
        front_f = c1.file_uploader("Upload Front Side Photo (Required)", type=ALL_IMG_EXTS, key="id_front")
        back_f = c2.file_uploader("Upload Back Side Photo (Optional)", type=ALL_IMG_EXTS, key="id_back")
        o1, o2, o3 = st.columns(3)
        layout = o1.selectbox("A4 Layout", ["Stacked (Vertical)", "Side-by-Side (Horizontal)"])
        scale = o2.slider("Card Scale", 0.8, 1.5, 1.0, 0.05)
        border = o3.checkbox("Show Cut Border", value=True)
        if front_f and st.button("🪪 Generate Print-Ready A4 PDF", type="primary"):
            try:
                with st.spinner("Formatting ID Card on A4..."):
                    out_bytes = id_card_to_pdf(
                        front_f.getvalue(),
                        back_f.getvalue() if back_f else None,
                        layout=layout,
                        draw_border=border,
                        card_scale=scale,
                    )
                st.success("Print-ready A4 ID Card PDF created!")
                st.download_button(
                    "⬇️ Download ID Card PDF",
                    data=out_bytes,
                    file_name="AUP_ID_Card_A4.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            except Exception as exc:
                st.error(f"Failed: {exc}")
        return

    if h == "html_to_pdf":
        src_mode = st.radio("Input Source", ["Webpage URL", "Upload HTML File", "Paste HTML Code"], horizontal=True)
        url_val = None
        html_val = None
        if src_mode == "Webpage URL":
            url_val = st.text_input("Enter Webpage URL", placeholder="https://example.com")
        elif src_mode == "Upload HTML File":
            hf = st.file_uploader("Upload .html / .htm File", type=["html", "htm"])
            if hf:
                html_val = hf.getvalue().decode("utf-8", errors="replace")
        else:
            html_val = st.text_area("Paste HTML Code", height=220, placeholder="<h1>Hello AUP E-Services</h1>")

        if st.button("🌐 Convert to PDF", type="primary"):
            try:
                with st.spinner("Rendering HTML to PDF..."):
                    out_bytes = html_or_url_to_pdf(html_content=html_val, url=url_val)
                st.success("PDF generated!")
                st.download_button(
                    "⬇️ Download PDF",
                    data=out_bytes,
                    file_name="webpage_to_pdf.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            except Exception as exc:
                st.error(f"Conversion failed: {exc}")
        return

    # --- Standard File Uploader for All Other 72 Tools ---
    uploaded = st.file_uploader(
        f"Upload file{'s' if tool.multiple else ''} ({', '.join('.' + e for e in tool.accept_exts)})",
        type=tool.accept_exts,
        accept_multiple_files=tool.multiple,
        key=f"uploader_{tool.slug}",
    )

    if not uploaded:
        st.info("Upload your file(s) above to configure options and start processing.")
        return

    files: List = uploaded if isinstance(uploaded, list) else [uploaded]
    first_file = files[0]
    first_bytes = first_file.getvalue()

    if len(files) == 1 and first_file.name.lower().endswith(".pdf") and h not in ("unlock_pdf", "repair_flatten_pdf"):
        _show_thumbnails(first_bytes)

    try:
        # ---------------- CSC & PRO HANDLERS ----------------
        if h == "compress_to_target_kb":
            c1, c2 = st.columns([2, 1])
            preset = c1.selectbox(
                "Common Portal Presets",
                ["Custom", "100 KB (PAN / Photo Doc)", "200 KB (TNeGA / LIC)", "300 KB (Passport / TNPSC)", "500 KB"],
            )
            preset_map = {"100 KB (PAN / Photo Doc)": 100, "200 KB (TNeGA / LIC)": 200, "300 KB (Passport / TNPSC)": 300, "500 KB": 500}
            default_kb = preset_map.get(preset, 200)
            target_kb = c2.number_input("Target Max Size (KB)", min_value=20, max_value=10000, value=default_kb, step=10)
            if st.button(f"🎯 Compress Under {int(target_kb)} KB", type="primary"):
                with st.spinner("Optimizing PDF to hit target KB..."):
                    out_bytes, met = compress_to_target_kb(first_bytes, target_kb=int(target_kb))
                m1, m2, m3 = st.columns(3)
                m1.metric("Original Size", _fmt_size(len(first_bytes)))
                m2.metric("New Size", _fmt_size(len(out_bytes)))
                m3.metric("Target Status", "Hit Target ✅" if met else "Best Possible ⚠️")
                st.download_button(
                    "⬇️ Download Compressed PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_{int(target_kb)}kb.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "ocr_pdf":
            c1, c2, c3 = st.columns(3)
            lang_label = c1.selectbox("OCR Language", ["English (eng)", "Tamil (tam)", "Tamil + English (tam+eng)"])
            lang_code = {"English (eng)": "eng", "Tamil (tam)": "tam", "Tamil + English (tam+eng)": "tam+eng"}[lang_label]
            out_mode = c2.selectbox("Output Format", ["Searchable PDF", "Extracted Text (.txt)"])
            dpi = c3.slider("Scan DPI", 120, 300, 200, 20)
            if st.button("🔎 Run OCR", type="primary"):
                with st.spinner("Running Tesseract OCR..."):
                    out_bytes, preview_txt = ocr_pdf(first_bytes, lang=lang_code, output_mode=out_mode, dpi=dpi)
                st.text_area("OCR Extracted Text Preview", preview_txt[:4000], height=200)
                if out_mode == "Searchable PDF":
                    st.download_button(
                        "⬇️ Download Searchable PDF",
                        data=out_bytes,
                        file_name=f"{_stem(first_file.name)}_ocr.pdf",
                        mime="application/pdf",
                        type="primary",
                    )
                else:
                    st.download_button(
                        "⬇️ Download OCR Text (.txt)",
                        data=out_bytes,
                        file_name=f"{_stem(first_file.name)}_ocr.txt",
                        mime="text/plain",
                        type="primary",
                    )

        elif h == "sign_seal_pdf":
            stamp_file = st.file_uploader("Upload Signature or Shop Seal (PNG / JPG)", type=["png", "jpg", "jpeg"])
            c1, c2, c3 = st.columns(3)
            page_choice = c1.selectbox("Apply On", ["Last Page", "First Page", "All Pages", "Specific Page"])
            specific_p = c2.number_input("Page Number", min_value=1, value=1) if page_choice == "Specific Page" else 1
            rm_bg = c3.checkbox("Auto-Remove White Background", value=True)
            s1, s2, s3 = st.columns(3)
            x_pct = s1.slider("Horizontal Position X (%)", 0, 90, 70)
            y_pct = s2.slider("Vertical Position Y (% from bottom)", 0, 90, 10)
            w_pct = s3.slider("Stamp Width (% of page)", 5, 60, 22)
            if stamp_file and st.button("✍️ Place Signature / Seal", type="primary"):
                target_arg = str(int(specific_p)) if page_choice == "Specific Page" else page_choice
                with st.spinner("Placing signature/seal..."):
                    out_bytes = sign_and_seal_pdf(
                        first_bytes,
                        stamp_file.getvalue(),
                        target_page=target_arg,
                        x_pct=x_pct,
                        y_pct=y_pct,
                        width_pct=w_pct,
                        remove_white_bg=rm_bg,
                    )
                st.success("Signature / Seal applied!")
                st.download_button(
                    "⬇️ Download Signed PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_signed.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "grayscale_pdf":
            c1, c2 = st.columns(2)
            dpi = c1.slider("Print Resolution (DPI)", 96, 300, 150, 12)
            hc = c2.checkbox("High-Contrast Ink-Saver Mode", value=True)
            if st.button("🖨️ Convert to Black & White", type="primary"):
                with st.spinner("Converting to Grayscale..."):
                    out_bytes = grayscale_pdf(first_bytes, dpi=dpi, high_contrast=hc)
                st.success("Converted to Black & White PDF!")
                st.download_button(
                    "⬇️ Download B&W PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_bw.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "repair_flatten_pdf":
            c1, c2 = st.columns(2)
            flatten = c1.checkbox("Flatten Form Fields & Annotations", value=True)
            strip_meta = c2.checkbox("Strip Document Metadata", value=True)
            if st.button("🛠️ Repair & Flatten PDF", type="primary"):
                with st.spinner("Repairing and flattening PDF..."):
                    out_bytes = repair_and_flatten_pdf(first_bytes, flatten_forms=flatten, strip_metadata=strip_meta)
                st.success("PDF repaired and cleaned!")
                st.download_button(
                    "⬇️ Download Repaired PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_repaired.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        # ---------------- CORE PDF HANDLERS ----------------
        elif h == "compress_pdf":
            quality = st.slider(
                "Compression Level (Lower = Smaller Size, Higher = Better Quality)",
                min_value=10,
                max_value=95,
                value=55,
                step=5,
            )
            if st.button("🗜️ Compress PDF Now", type="primary"):
                with st.spinner("Compressing PDF..."):
                    out_bytes = compress_pdf(first_bytes, quality_level=quality)
                orig_sz, new_sz = len(first_bytes), len(out_bytes)
                saved_pct = max(0.0, (1.0 - new_sz / max(1, orig_sz)) * 100.0)
                m1, m2, m3 = st.columns(3)
                m1.metric("Original Size", _fmt_size(orig_sz))
                m2.metric("Compressed Size", _fmt_size(new_sz))
                m3.metric("Saved", f"{saved_pct:.1f}%")
                st.download_button(
                    "⬇️ Download Compressed PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_compressed.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h in ("merge_pdf", "merge_pdf_image"):
            st.write(f"**{len(files)} file(s) selected.** Adjust order below if needed:")
            order_names = [f"{idx + 1}. {f.name}" for idx, f in enumerate(files)]
            selected_order = st.multiselect(
                "File merge order (remove & re-add to reorder)",
                options=order_names,
                default=order_names,
            )
            ordered_files = [files[int(label.split(".", 1)[0]) - 1] for label in selected_order]
            if st.button("🔗 Merge Into Single PDF", type="primary", disabled=len(ordered_files) < 1):
                with st.spinner("Merging files..."):
                    if h == "merge_pdf":
                        out_bytes = merge_pdfs([f.getvalue() for f in ordered_files])
                    else:
                        out_bytes = merge_pdf_and_images([(f.name, f.getvalue()) for f in ordered_files])
                st.success(f"Merged {len(ordered_files)} file(s) ({_fmt_size(len(out_bytes))}).")
                st.download_button(
                    "⬇️ Download Merged PDF",
                    data=out_bytes,
                    file_name="AUP_merged.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "split_pdf":
            mode = st.radio("Split Mode", ["Specified Page Ranges", "Fixed Page Interval"], horizontal=True)
            if mode == "Specified Page Ranges":
                ranges_str = st.text_input("Page Ranges (comma-separated)", value="1-2, 3-4", help="Example: 1-3, 4-6, 7")
                fixed_step = 1
                mode_key = "ranges"
            else:
                fixed_step = st.number_input("Pages per split file", min_value=1, max_value=500, value=1)
                ranges_str = ""
                mode_key = "fixed"
            if st.button("✂️ Split PDF", type="primary"):
                with st.spinner("Splitting PDF..."):
                    out_bytes, out_name, out_mime = split_pdf(
                        first_bytes, mode=mode_key, ranges_str=ranges_str, fixed_step=int(fixed_step)
                    )
                st.success("PDF split completed!")
                st.download_button(
                    f"⬇️ Download {out_name}",
                    data=out_bytes,
                    file_name=out_name,
                    mime=out_mime,
                    type="primary",
                )

        elif h == "crop_pdf":
            c1, c2, c3, c4 = st.columns(4)
            left_pct = c1.slider("Left Crop (%)", 0, 40, 5)
            right_pct = c2.slider("Right Crop (%)", 0, 40, 5)
            top_pct = c3.slider("Top Crop (%)", 0, 40, 5)
            bottom_pct = c4.slider("Bottom Crop (%)", 0, 40, 5)
            pages_str = st.text_input("Pages to Crop (leave blank for all pages)", placeholder="e.g. 1, 3-5")
            if st.button("📐 Crop PDF", type="primary"):
                with st.spinner("Cropping pages..."):
                    out_bytes = crop_pdf(first_bytes, left_pct, right_pct, top_pct, bottom_pct, pages_str)
                st.success("Cropping completed!")
                st.download_button(
                    "⬇️ Download Cropped PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_cropped.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "organize_pdf":
            total = get_page_count(first_bytes)
            default_order = ", ".join(str(i) for i in range(1, total + 1))
            order_str = st.text_input("New Page Order (1-indexed)", value=default_order, help="Example: 3, 1, 2, 4")
            if st.button("🗂️ Rearrange Pages", type="primary"):
                with st.spinner("Organizing PDF..."):
                    out_bytes = organize_pdf(first_bytes, order_str)
                st.success("Pages rearranged!")
                st.download_button(
                    "⬇️ Download Organized PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_organized.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "rotate_pdf":
            angle = st.selectbox("Rotation Angle (Clockwise)", [90, 180, 270], index=0)
            pages_str = st.text_input("Pages to Rotate (leave blank for all)", placeholder="e.g. 1, 3-5")
            if st.button("🔄 Rotate PDF", type="primary"):
                with st.spinner("Rotating pages..."):
                    out_bytes = rotate_pdf(first_bytes, angle=int(angle), pages_str=pages_str)
                st.success("Rotation completed!")
                st.download_button(
                    "⬇️ Download Rotated PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_rotated.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "remove_pages":
            pages_to_del = st.text_input("Pages to Remove", placeholder="e.g. 2, 4-6")
            if st.button("🗑️ Remove Selected Pages", type="primary"):
                with st.spinner("Removing pages..."):
                    out_bytes = remove_pages(first_bytes, pages_to_del)
                st.success("Selected pages removed!")
                st.download_button(
                    "⬇️ Download Updated PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_pages_removed.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "extract_pages":
            pages_to_ext = st.text_input("Pages to Extract", value="1", placeholder="e.g. 1-3, 5")
            if st.button("📤 Extract Pages", type="primary"):
                with st.spinner("Extracting pages..."):
                    out_bytes = extract_pages(first_bytes, pages_to_ext)
                st.success("Pages extracted!")
                st.download_button(
                    "⬇️ Download Extracted PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_extracted.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "extract_images":
            if st.button("🖼️ Extract Embedded Images", type="primary"):
                with st.spinner("Extracting images..."):
                    zip_bytes, count = extract_images_from_pdf(first_bytes)
                if count == 0:
                    st.warning("No embedded images were found in this PDF.")
                else:
                    st.success(f"Extracted {count} embedded image(s)!")
                    st.download_button(
                        "⬇️ Download Images (ZIP)",
                        data=zip_bytes,
                        file_name=f"{_stem(first_file.name)}_images.zip",
                        mime="application/zip",
                        type="primary",
                    )

        elif h == "add_page_number":
            c1, c2, c3 = st.columns(3)
            pos = c1.selectbox(
                "Position",
                ["bottom-center", "bottom-right", "bottom-left", "top-center", "top-right", "top-left"],
            )
            fmt = c2.selectbox("Format", ["{n} / {total}", "Page {n}", "{n}", "Page {n} of {total}"])
            font_sz = c3.slider("Font Size", 8, 24, 11)
            start_num = st.number_input("Start Number", min_value=1, value=1)
            if st.button("🔢 Add Page Numbers", type="primary"):
                with st.spinner("Adding page numbers..."):
                    out_bytes = add_page_numbers(
                        first_bytes, position=pos, fmt=fmt, font_size=font_sz, start_number=int(start_num)
                    )
                st.success("Page numbers added!")
                st.download_button(
                    "⬇️ Download Numbered PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_numbered.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "add_watermark":
            wm_type = st.radio("Watermark Type", ["Text Watermark", "Image Watermark"], horizontal=True)
            c1, c2 = st.columns(2)
            opacity = c1.slider("Opacity", 0.05, 1.0, 0.25, 0.05)
            angle = c2.slider("Rotation Angle", -90, 90, 45, 5)
            wm_text = "AUP E-SERVICES"
            wm_font = 42
            wm_color = "#64748B"
            wm_img_bytes = None

            if wm_type == "Text Watermark":
                wm_text = st.text_input("Watermark Text", value="CONFIDENTIAL")
                col_a, col_b = st.columns(2)
                wm_font = col_a.slider("Font Size", 16, 96, 42)
                wm_color = col_b.color_picker("Color", "#64748B")
            else:
                wm_img = st.file_uploader("Upload Watermark Image (PNG/JPG)", type=["png", "jpg", "jpeg"])
                if wm_img:
                    wm_img_bytes = wm_img.getvalue()

            if st.button("💧 Apply Watermark", type="primary"):
                with st.spinner("Applying watermark..."):
                    out_bytes = add_watermark(
                        first_bytes,
                        text=wm_text,
                        font_size=wm_font,
                        opacity=opacity,
                        angle=angle,
                        color_hex=wm_color,
                        image_bytes=wm_img_bytes,
                    )
                st.success("Watermark applied!")
                st.download_button(
                    "⬇️ Download Watermarked PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_watermarked.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        # ---------------- IMAGES <-> PDF HANDLERS ----------------
        elif h == "images_to_pdf":
            c1, c2, c3 = st.columns(3)
            page_sz = c1.selectbox("Page Size", ["Auto", "A4", "Letter"])
            orient = c2.selectbox("Orientation", ["Portrait", "Landscape"])
            margin = c3.slider("Margin (pt)", 0, 72, 18)
            if st.button("📄 Convert Image(s) to PDF", type="primary"):
                with st.spinner("Converting images to PDF..."):
                    out_bytes = images_to_pdf(
                        [(f.name, f.getvalue()) for f in files],
                        page_size=page_sz,
                        orientation=orient,
                        margin_pt=margin,
                    )
                st.success(f"Created PDF from {len(files)} image file(s)!")
                st.download_button(
                    "⬇️ Download PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h in ("pdf_to_image", "pdf_to_jpg"):
            c1, c2 = st.columns(2)
            fmt = "JPG" if h == "pdf_to_jpg" else c1.selectbox("Output Image Format", ["PNG", "JPG", "WEBP"])
            dpi = c2.slider("Resolution (DPI)", 72, 300, 150, 12)
            jpg_q = st.slider("JPG/WEBP Quality", 50, 100, 90) if fmt in ("JPG", "WEBP") else 90
            if st.button(f"🖼️ Convert PDF to {fmt}", type="primary"):
                with st.spinner(f"Rendering PDF pages to {fmt}..."):
                    zip_bytes, count = pdf_to_images(first_bytes, img_format=fmt, dpi=dpi, jpg_quality=jpg_q)
                st.success(f"Converted {count} page(s) to {fmt}!")
                st.download_button(
                    f"⬇️ Download {fmt} Images (ZIP)",
                    data=zip_bytes,
                    file_name=f"{_stem(first_file.name)}_{fmt.lower()}.zip",
                    mime="application/zip",
                    type="primary",
                )

        # ---------------- SECURITY & TEXT HANDLERS ----------------
        elif h == "txt_to_pdf":
            font_sz = st.slider("Font Size", 8, 18, 10)
            if st.button("📄 Convert TXT to PDF", type="primary"):
                with st.spinner("Generating PDF..."):
                    out_bytes = txt_to_pdf(first_bytes, font_size=font_sz)
                st.success("Converted TXT to PDF!")
                st.download_button(
                    "⬇️ Download PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "pdf_to_text":
            if st.button("📄 Extract Text from PDF", type="primary"):
                with st.spinner("Extracting text..."):
                    extracted = pdf_to_text(first_bytes)
                st.text_area("Extracted Text Preview", extracted[:4000], height=240)
                st.download_button(
                    "⬇️ Download TXT File",
                    data=extracted.encode("utf-8"),
                    file_name=f"{_stem(first_file.name)}.txt",
                    mime="text/plain",
                    type="primary",
                )

        elif h == "unlock_pdf":
            pwd = st.text_input("Enter Current PDF Password", type="password")
            if st.button("🔓 Unlock PDF", type="primary"):
                with st.spinner("Unlocking PDF..."):
                    out_bytes = unlock_pdf(first_bytes, pwd)
                st.success("PDF unlocked successfully!")
                st.download_button(
                    "⬇️ Download Unlocked PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}_unlocked.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h == "protect_pdf":
            pwd = st.text_input("Set Password to Protect PDF", type="password")
            pwd2 = st.text_input("Confirm Password", type="password")
            if st.button("🔒 Protect PDF", type="primary"):
                if not pwd or pwd != pwd2:
                    st.error("Passwords must match and cannot be empty.")
                else:
                    with st.spinner("Encrypting PDF (AES-256)..."):
                        out_bytes = protect_pdf(first_bytes, pwd)
                    st.success("PDF encrypted with AES-256!")
                    st.download_button(
                        "⬇️ Download Protected PDF",
                        data=out_bytes,
                        file_name=f"{_stem(first_file.name)}_protected.pdf",
                        mime="application/pdf",
                        type="primary",
                    )

        # ---------------- OFFICE <-> PDF HANDLERS ----------------
        elif h == "office_to_pdf":
            if st.button(f"📄 Convert {tool.name}", type="primary"):
                with st.spinner("Converting document to PDF..."):
                    out_bytes = office_to_pdf(first_bytes, first_file.name)
                st.success("Conversion completed!")
                st.download_button(
                    "⬇️ Download PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h in ("pdf_to_docx", "pdf_to_doc", "pdf_to_odt", "pdf_to_excel", "pdf_to_xls", "pdf_to_csv"):
            fn_map = {
                "pdf_to_docx": pdf_to_docx,
                "pdf_to_doc": pdf_to_doc,
                "pdf_to_odt": pdf_to_odt,
                "pdf_to_excel": pdf_to_excel,
                "pdf_to_xls": pdf_to_xls,
                "pdf_to_csv": pdf_to_csv,
            }
            if st.button(f"⚡ Convert to .{tool.target_ext.upper()}", type="primary"):
                with st.spinner(f"Converting PDF to .{tool.target_ext.upper()}..."):
                    out_bytes = fn_map[h](first_bytes)
                st.success("Conversion completed!")
                st.download_button(
                    f"⬇️ Download .{tool.target_ext.upper()}",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}.{tool.target_ext}",
                    mime=_mime_for(tool.target_ext),
                    type="primary",
                )

        elif h in ("pdf_to_pptx", "pdf_to_ppt", "pdf_to_odp"):
            mode = st.radio(
                "Slide Conversion Mode",
                ["Preserve Exact Visual Layout (HD Slide Images)", "Editable Text Slides"],
                horizontal=True,
            )
            editable = mode == "Editable Text Slides"
            fn_map = {"pdf_to_pptx": pdf_to_pptx, "pdf_to_ppt": pdf_to_ppt, "pdf_to_odp": pdf_to_odp}
            if st.button(f"📽️ Convert to .{tool.target_ext.upper()}", type="primary"):
                with st.spinner(f"Converting PDF to .{tool.target_ext.upper()}..."):
                    out_bytes = fn_map[h](first_bytes, editable_text=editable)
                st.success("Presentation created!")
                st.download_button(
                    f"⬇️ Download .{tool.target_ext.upper()}",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}.{tool.target_ext}",
                    mime=_mime_for(tool.target_ext),
                    type="primary",
                )

        # ---------------- EBOOK <-> PDF HANDLERS ----------------
        elif h == "ebook_to_pdf":
            if st.button(f"📚 Convert {tool.name}", type="primary"):
                with st.spinner("Converting eBook to PDF..."):
                    out_bytes = ebook_to_pdf(first_bytes, first_file.name)
                st.success("eBook converted to PDF!")
                st.download_button(
                    "⬇️ Download PDF",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}.pdf",
                    mime="application/pdf",
                    type="primary",
                )

        elif h in ("pdf_to_ebook", "pdf_to_ebook_select"):
            target = (
                st.selectbox("Select Target eBook Format", ["epub", "mobi", "azw3", "fb2", "rtf"])
                if h == "pdf_to_ebook_select"
                else tool.target_ext
            )
            if st.button(f"📚 Convert PDF to .{target.upper()}", type="primary"):
                with st.spinner(f"Converting PDF to .{target.upper()}..."):
                    out_bytes = pdf_to_ebook(first_bytes, target_format=target)
                st.success(f"Converted to .{target.upper()}!")
                st.download_button(
                    f"⬇️ Download .{target.upper()}",
                    data=out_bytes,
                    file_name=f"{_stem(first_file.name)}.{target}",
                    mime=_mime_for(target),
                    type="primary",
                )

    except Exception as exc:
        st.error(f"Conversion failed: {exc}")


def main() -> None:
    search_q, selected_cat = render_sidebar()
    if st.session_state.active_tool and st.session_state.active_tool in TOOL_BY_SLUG:
        render_tool_workspace(TOOL_BY_SLUG[st.session_state.active_tool])
    else:
        render_dashboard(search_q, selected_cat)


if __name__ == "__main__":
    main()
