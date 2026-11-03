import streamlit as st
from PIL import Image
import db
import theme
from ocr_utils import run_ocr, extract_metadata, auto_name
from sample_docs import generate_samples
import os

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("2 · OCR & Intelligent Capture Workgroup",
             "Real Tesseract OCR engine — English & Arabic — with auto metadata extraction")

st.markdown(f"{theme.tag_custom('Custom OCR pipeline (Tesseract, self-hosted)')}", unsafe_allow_html=True)
st.write("")

st.markdown('<div class="efs-section-title">📄 Scan or Upload a Document</div>', unsafe_allow_html=True)

col_a, col_b = st.columns([1, 1])
with col_a:
    st.caption("Option 1 — use a synthetic sample scanned letter (generated for this demo)")
    if st.button("🖨️ Generate sample scanned letters"):
        with st.spinner("Rendering sample scans..."):
            paths = generate_samples()
        st.session_state["sample_paths"] = paths
        st.success(f"Generated {len(paths)} sample scans.")

    sample_paths = st.session_state.get("sample_paths", [])
    if not sample_paths:
        existing = [os.path.join("assets", f) for f in os.listdir("assets")] if os.path.isdir("assets") else []
        sample_paths = [p for p in existing if p.endswith(".png")]
    chosen = None
    if sample_paths:
        names = [os.path.basename(p) for p in sample_paths]
        pick = st.selectbox("Choose a sample scan", names)
        chosen = next(p for p in sample_paths if os.path.basename(p) == pick)
        st.image(chosen, caption=pick, use_container_width=True)

with col_b:
    st.caption("Option 2 — upload your own image (png/jpg) to OCR")
    uploaded = st.file_uploader("Upload scanned document", type=["png", "jpg", "jpeg"])
    if uploaded:
        st.image(uploaded, caption=uploaded.name, use_container_width=True)

st.markdown("---")
lang_choice = st.radio("OCR Language", ["English + Arabic (auto)", "English only", "Arabic only"],
                        horizontal=True)
lang_map = {"English + Arabic (auto)": "eng+ara", "English only": "eng", "Arabic only": "ara"}

with st.expander("🎚 Capture station controls — image enhancement, zonal OCR, multi-location filing"):
    e1, e2, e3 = st.columns(3)
    with e1:
        bright = st.slider("Brightness", 0.5, 1.8, 1.0, 0.05)
        contrast = st.slider("Contrast", 0.5, 2.5, 1.0, 0.05)
    with e2:
        despeckle = st.checkbox("De-speckle", value=False)
        sharpen = st.checkbox("Sharpen / line clean-up", value=False)
        deskew = st.number_input("De-skew rotation (degrees)", -10.0, 10.0, 0.0, 0.5)
    with e3:
        zonal = st.checkbox("Zonal OCR (read only a region)", value=False)
        zy0, zy1 = st.slider("Vertical zone (% of page)", 0, 100, (0, 100), disabled=not zonal)
    file_to = st.multiselect("Also file a copy to (multiple archive / workflow locations)", db.DEPARTMENTS, key="ocr_multi")

run_clicked = st.button("▶ Run OCR Extraction", type="primary")

if run_clicked:
    img = None
    source_name = None
    if uploaded is not None:
        img = Image.open(uploaded).convert("RGB")
        source_name = uploaded.name
    elif chosen:
        img = Image.open(chosen).convert("RGB")
        source_name = os.path.basename(chosen)

    if img is None:
        st.error("Select or upload an image first.")
    else:
        from PIL import ImageEnhance, ImageFilter
        img = ImageEnhance.Brightness(img).enhance(bright)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        if deskew:
            img = img.rotate(deskew, expand=True, fillcolor="white")
        if despeckle:
            img = img.filter(ImageFilter.MedianFilter(3))
        if sharpen:
            img = img.filter(ImageFilter.SHARPEN)
        if zonal:
            w_, h_ = img.size
            img = img.crop((0, int(h_ * zy0 / 100), w_, max(int(h_ * zy1 / 100), int(h_ * zy0 / 100) + 20)))
        st.image(img, caption="Image sent to OCR (after enhancement" + (" · zonal crop" if zonal else "") + ")", width=300)
        with st.spinner("Running Tesseract OCR engine…"):
            text = run_ocr(img, lang=lang_map[lang_choice])
        meta = extract_metadata(text)
        auto_title = auto_name(meta, source_name)

        st.markdown('<div class="efs-section-title">✅ OCR Result — Operator Verification</div>',
                     unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Extracted text (editable before save)**")
            edited_text = st.text_area("OCR text", value=text.strip(), height=320, label_visibility="collapsed")
        with c2:
            st.markdown("**Auto-extracted metadata**")
            if meta:
                for k, v in meta.items():
                    st.markdown(f"- **{k}**: {v}")
            else:
                st.caption("No structured fields detected automatically — operator can fill in manually below.")
            st.markdown("**Suggested auto-generated filename**")
            st.code(auto_title or "UNTITLED-DOC")

            dept = st.selectbox("Assign to Department", db.DEPARTMENTS, key="ocr_dept")
            classification = st.selectbox("Classification", db.CLASSIFICATIONS, key="ocr_class")
            sec = st.selectbox("Security Level", db.SECURITY_LEVELS, key="ocr_sec")

            if st.button("💾 Save as new document (bulk-scan ready)", type="primary"):
                doc_id, code = db.create_document(
                    title=auto_title or (source_name or "Scanned Document"),
                    department=dept, classification=classification, security_level=sec,
                    doc_type="Scanned Correspondence", source="Scan",
                    language="Arabic" if lang_map[lang_choice] == "ara" else "English",
                    body_text=edited_text, created_by=theme.current_user(),
                    sender=meta.get("Sender", ""), recipient="",
                )
                db.log_audit(doc_id, theme.current_user(), "OCR Capture",
                              f"Captured via Tesseract ({lang_map[lang_choice]}) from {source_name}")
                import db_ext
                for extra in file_to:
                    if extra != dept:
                        db.log_audit(doc_id, theme.current_user(), "Filed to Additional Location", extra)
                        for n, p in db_ext.rfp_data.ROLES.items():
                            if p["dept"] == extra:
                                db_ext.notify(n, f"Scanned document {code} filed to your department.", doc_id, "info")
                if file_to:
                    st.info("Also filed to: " + ", ".join(file_to))
                st.success(f"Saved as **{code}**. Fully searchable via OCR'd text — try the Search & Retrieval page.")

st.markdown("---")
st.markdown('<div class="efs-section-title">🗂️ Batch / Bulk Scanning</div>', unsafe_allow_html=True)
st.markdown("""
<div class="efs-card">
The production pipeline supports bulk scanning: a watched folder or scanner feed is processed
automatically — each page is OCR'd, auto-classified by content/naming convention, and queued
for operator verification before entering the repository. This demo shows the single-document
path above; the batch path uses the same engine in a loop with a review queue.
</div>
""", unsafe_allow_html=True)
