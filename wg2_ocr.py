import streamlit as st
from PIL import Image
import db
import db_ext
import distribution as dist
import theme
from ocr_utils import run_ocr, extract_metadata, auto_name
from sample_docs import generate_samples, ASSETS_DIR
import os

db.init_db()
dist.init_dist()
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
        with st.spinner("Running Tesseract OCR engine…"):
            text = run_ocr(img, lang=lang_map[lang_choice])
        st.session_state["ocr_res"] = {"n": st.session_state.get("ocr_res", {}).get("n", 0) + 1, "text": text, "img": img,
                                       "source": source_name, "lang": lang_map[lang_choice], "zonal": zonal, "file_to": file_to}

res = st.session_state.get("ocr_res")
if res:
    n_ = res["n"]
    st.image(res["img"], caption="Image sent to OCR (after enhancement" + (" · zonal crop" if res["zonal"] else "") + ")", width=300)
    st.markdown('<div class="efs-section-title">✅ OCR Result — Operator Verification</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Extracted text (editable before save)**")
        edited_text = st.text_area("OCR text", value=res["text"].strip(), height=320, label_visibility="collapsed", key=f"ocr_text_{n_}")
    meta = extract_metadata(edited_text)
    auto_title = auto_name(meta, res["source"])
    decision = dist.analyse(edited_text, auto_title, meta.get("Sender", ""))
    with c2:
        st.markdown("**Auto-extracted metadata**")
        if meta:
            for k, v in meta.items():
                st.markdown(f"- **{k}**: {v}")
        else:
            st.caption("No structured fields detected automatically — operator can fill in manually below.")
        st.markdown("**Suggested auto-generated filename**")
        st.code(auto_title or "UNTITLED-DOC")
        st.markdown("**📬 Automatic distribution (content rules)**")
        if decision["hits"]:
            top = decision["hits"][0]
            st.success(f"Rule **{top['rule']['name']}** matched ({', '.join(top['matched'][:4])}) → **{decision['primary']}**"
                       + (f"; copies to {', '.join(decision['copies'])}" if decision["copies"] else ""))
        else:
            st.warning("No distribution rule matched — the item will go to the triage queue.")
        auto = st.checkbox("Distribute automatically on save (recommended)", value=True, key=f"auto_{n_}")
        pdept = decision["primary"] if (auto and decision["primary"]) else db.DEPARTMENTS[0]
        dept = st.selectbox("Assign to Department", db.DEPARTMENTS, index=db.DEPARTMENTS.index(pdept) if pdept in db.DEPARTMENTS else 0,
                            key=f"ocr_dept_{n_}_{pdept}", disabled=auto and bool(decision["primary"]))
        classification = st.selectbox("Classification", db.CLASSIFICATIONS,
                                      index=db.CLASSIFICATIONS.index(decision["classification"]) if auto and decision["classification"] else 0,
                                      key=f"ocr_class_{n_}_{decision['classification']}")
        sec = st.selectbox("Security Level", db.SECURITY_LEVELS, key=f"ocr_sec_{n_}")

        if st.button("💾 Save as new document (bulk-scan ready)", type="primary", key=f"save_{n_}"):
            doc_id, code = db.create_document(
                title=auto_title or (res["source"] or "Scanned Document"),
                department=dept, classification=classification, security_level=sec,
                doc_type=(decision["doc_type"] if auto and decision["doc_type"] else "Scanned Correspondence"), source="Scan",
                language="Arabic" if res["lang"] == "ara" else "English",
                body_text=edited_text, created_by=theme.current_user(),
                sender=meta.get("Sender", ""), recipient="",
            )
            db.log_audit(doc_id, theme.current_user(), "OCR Capture", f"Captured via Tesseract ({res['lang']}) from {res['source']}")
            if auto:
                dist.distribute(doc_id, theme.current_user(), apply_dept=True, notify=True, text=edited_text)
            for extra in res["file_to"]:
                if extra != dept:
                    db.log_audit(doc_id, theme.current_user(), "Filed to Additional Location", extra)
                    for n, p in db_ext.rfp_data.ROLES.items():
                        if p["dept"] == extra:
                            db_ext.notify(n, f"Scanned document {code} filed to your department.", doc_id, "info")
            if res["file_to"]:
                st.info("Also filed to: " + ", ".join(res["file_to"]))
            st.success(f"Saved as **{code}**" + (f" and auto-distributed to **{decision['primary']}**" if auto and decision["primary"] else "")
                       + ". It is already in the search index — try the Search & Retrieval page.")

st.markdown("---")
st.markdown('<div class="efs-section-title">⚡ Straight-through batch: scan → OCR → classify → distribute → index</div>', unsafe_allow_html=True)
st.caption("Bulk scanning with no operator keystrokes: every sample page is read by OCR, classified from its content, filed, routed by the "
           "distribution rules and added to the search index. Anything the rules cannot place lands in the triage queue.")
if st.button("▶ Run batch on all sample scans"):
    files = [f for f in (sorted(os.listdir(ASSETS_DIR)) if os.path.isdir(ASSETS_DIR) else []) if f.endswith(".png")]
    if len(files) < 8:
        generate_samples()
        files = sorted(f for f in os.listdir(ASSETS_DIR) if f.endswith(".png"))
    rows = []
    bar = st.progress(0.0)
    for i, f in enumerate(files):
        im = Image.open(os.path.join(ASSETS_DIR, f)).convert("RGB")
        txt = run_ocr(im, lang="eng").strip()
        mt = extract_metadata(txt)
        ttl = auto_name(mt, f)
        dec = dist.analyse(txt, ttl, mt.get("Sender", ""))
        did, code = db.create_document(ttl or f, dec["primary"] or "Medical Records", dec["classification"] or "External", "Internal",
                                       dec["doc_type"] or "Letter", "Scan", "English", txt, theme.current_user(), sender=mt.get("Sender", ""))
        db.log_audit(did, theme.current_user(), "OCR Capture", f"Batch capture from {f}")
        dist.distribute(did, theme.current_user(), apply_dept=True, notify=True, text=txt)
        rows.append({"Scan": f, "Document": code, "Words read": len(txt.split()), "Rule": dec["hits"][0]["rule"]["name"] if dec["hits"] else "— none —",
                     "Routed to": dec["primary"] or "Triage queue", "Copies": ", ".join(dec["copies"]) or "—"})
        bar.progress((i + 1) / len(files))
    st.session_state["batch_rows"] = rows
if st.session_state.get("batch_rows"):
    import pandas as pd
    st.dataframe(pd.DataFrame(st.session_state["batch_rows"]), use_container_width=True, hide_index=True)
    st.success("Batch complete — all pages are searchable by their OCR text and delivered to their departments. "
               "See ‘12 · Auto-Distribution’ for the log, and Search with ‘Scanned / OCR documents only’.")
