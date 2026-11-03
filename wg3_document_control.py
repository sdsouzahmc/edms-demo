import streamlit as st
import db
import db_ext
import theme
import difflib

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("3 · Document Control & Version Management",
             "Check-in/out · version history · comparison · publish official version")

docs = db.get_documents()
if not docs:
    st.info("No documents yet — register one on the Correspondence & Intake page first.")
    st.stop()

doc_map = {f"{d['doc_code']} — {d['title']}": d["id"] for d in docs}
choice = st.selectbox("Select a document", list(doc_map.keys()))
doc_id = doc_map[choice]
doc = db.get_document(doc_id)
versions = db.get_versions(doc_id)

c1, c2 = st.columns([2, 1])
with c1:
    st.markdown(f"""
    <div class="efs-card">
    <b>{doc['title']}</b><br>
    {doc['doc_code']} &nbsp;·&nbsp; {doc['department']} &nbsp;·&nbsp; {doc['classification']}<br>
    Status: {theme.pill(doc['status'])} &nbsp;&nbsp; Current version: <b>v{doc['current_version']}</b>
    &nbsp;&nbsp; Published: {"✅ Yes" if doc['is_published'] else "— Draft only"}
    </div>
    """, unsafe_allow_html=True)
with c2:
    last_v = versions[0] if versions else None
    locked_by = last_v["checked_out_by"] if last_v else None
    if locked_by:
        st.warning(f"🔒 Checked out by **{locked_by}**")
    else:
        st.success("🔓 Available for check-out")

declared = db_ext.is_declared(doc_id)
tabs = st.tabs(["✏️ Check-out / Check-in", "🕒 Version History", "🔍 Compare Versions", "📣 Publish / Obsolete",
                "🖍 Viewer · Annotate · Redact", "🔏 Declare Record"])

with tabs[0]:
    st.markdown('<div class="efs-section-title">Check-out, edit, check back in as a new version</div>',
                 unsafe_allow_html=True)
    if declared:
        st.error("🔏 This is a declared record — it cannot be checked out or altered (including its metadata).")
    elif not locked_by:
        if st.button("🔒 Check Out for Editing", type="primary"):
            db.checkout_document(doc_id, theme.current_user())
            st.rerun()
    elif locked_by == theme.current_user() or theme.is_admin():
        st.text_area("Current content", value=doc["body_text"] or "", height=160, key="current_body", disabled=True)
        new_text = st.text_area("Edited content (new version)", value=doc["body_text"] or "", height=160)
        notes = st.text_input("Version notes", placeholder="What changed in this revision?")
        bump = st.radio("Version bump", ["minor (1.0 → 1.1)", "major (1.0 → 2.0)"], horizontal=True)
        bump_key = "major" if "major" in bump else "minor"
        if st.button("✅ Check In New Version", type="primary"):
            newv = db.checkin_new_version(doc_id, theme.current_user(), new_text, notes or "Revision", bump_key)
            st.success(f"Checked in as v{newv}. It's now in Draft status — publish it below to make it official.")
            st.rerun()
    else:
        st.info(f"Locked by {locked_by}. Only they (or an Administrator) can check it back in.")
        if theme.is_admin():
            if st.button("🔓 Admin override: force check-in / release lock"):
                db.checkin_new_version(doc_id, theme.current_user(), doc["body_text"], "Admin override release", "minor")
                st.rerun()

with tabs[1]:
    st.markdown('<div class="efs-section-title">Full version history with audit metadata</div>',
                 unsafe_allow_html=True)
    for v in versions:
        status_color = {"Published": "pill-released", "Draft": "pill-draft", "Obsolete": "pill-disposed"}.get(v["status"], "pill-draft")
        st.markdown(f"""
        <div class="efs-card">
        <b>v{v['version_no']}</b> &nbsp; <span class="efs-pill {status_color}">{v['status']}</span><br>
        {v['notes'] or ''}<br>
        <span style="color:#6B7280;font-size:0.82rem">by {v['created_by']} on {v['created_at']}
        {" · 🔒 checked out by " + v['checked_out_by'] if v['checked_out_by'] else ""}</span>
        </div>
        """, unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="efs-section-title">Side-by-side comparison</div>', unsafe_allow_html=True)
    if len(versions) < 2:
        st.info("Need at least two versions to compare. Check in a new version first.")
    else:
        vmap = {f"v{v['version_no']} ({v['status']}) — {v['created_at']}": v for v in versions}
        cc1, cc2 = st.columns(2)
        with cc1:
            left_choice = st.selectbox("Compare (older)", list(vmap.keys()), index=min(1, len(vmap)-1))
        with cc2:
            right_choice = st.selectbox("With (newer)", list(vmap.keys()), index=0)
        left_v, right_v = vmap[left_choice], vmap[right_choice]
        diff = difflib.unified_diff(
            (left_v["body_snapshot"] or "").splitlines(),
            (right_v["body_snapshot"] or "").splitlines(),
            lineterm="", fromfile=f"v{left_v['version_no']}", tofile=f"v{right_v['version_no']}"
        )
        diff_text = "\n".join(diff) or "No textual differences detected."
        st.code(diff_text, language="diff")

with tabs[3]:
    st.markdown('<div class="efs-section-title">Publish official version / mark obsolete</div>',
                 unsafe_allow_html=True)
    st.write("Published version = finalized, available for viewing. Draft = editable, restricted to "
             "users with sufficient access.")
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("📣 Publish Current Version as Official", type="primary"):
            db.publish_version(doc_id, theme.current_user())
            st.success("Current version published as the official released version.")
            st.rerun()
    with cc2:
        obsolete_candidates = [v for v in versions if v["status"] != "Obsolete"]
        if obsolete_candidates:
            pick = st.selectbox("Mark a version obsolete",
                                 [f"v{v['version_no']} ({v['status']})" for v in obsolete_candidates])
            if st.button("🗑️ Mark Obsolete"):
                target = obsolete_candidates[[f"v{v['version_no']} ({v['status']})" for v in obsolete_candidates].index(pick)]
                db.mark_version_obsolete(doc_id, target["id"], theme.current_user())
                st.rerun()

with tabs[4]:
    user = theme.current_user()
    st.markdown('<div class="efs-section-title">Built-in viewer with secured annotation & redaction</div>', unsafe_allow_html=True)
    db_ext.log_view(user, doc_id)
    anns = db_ext.get_annotations(doc_id)
    can_see_through = theme.is_admin()
    visible_anns = [a for a in anns if not a["restricted"] or a["user"] == user or theme.is_admin()]
    vc1, vc2, vc3 = st.columns(3)
    with vc1:
        zoom = st.slider("Zoom", 80, 200, 110, step=10, help="Viewer zoom (%)")
    with vc2:
        show_ann = st.checkbox("Show annotations", value=True)
    with vc3:
        see_through = st.checkbox("See through redactions (admin only)", value=False, disabled=not can_see_through)

    import html as _h
    text = _h.escape(doc["body_text"] or "")
    if show_ann:
        for a in visible_anns:
            tgt = _h.escape(a["target"] or "")
            if not tgt or tgt not in text:
                continue
            if a["kind"] == "Highlight":
                text = text.replace(tgt, f"<mark>{tgt}</mark>")
            elif a["kind"] == "Underline":
                text = text.replace(tgt, f"<u>{tgt}</u>")
            elif a["kind"] == "Sticky note":
                text = text.replace(tgt, f"<mark style='background:#FFE9A8'>{tgt}</mark> <sup title='{_h.escape(a['text'] or '')}'>📝</sup>")
            elif a["kind"] == "Stamp":
                text = text.replace(tgt, f"{tgt} <span style='border:1px solid #B00020;color:#B00020;padding:0 4px;font-size:0.7rem'>{_h.escape(a['text'] or 'STAMP')}</span>")
    for a in visible_anns:
        if a["kind"] == "Redaction":
            tgt = _h.escape(a["target"] or "")
            if tgt and tgt in text:
                if see_through and can_see_through:
                    text = text.replace(tgt, f"<span style='background:#FBE3E7'>{tgt}</span>")
                else:
                    text = text.replace(tgt, f"<span title='Reason: {_h.escape(a['reason'] or '')}' style='background:#111;color:#111'>{'█' * max(4, len(tgt))}</span>")
    st.markdown(f"<div class='efs-card' style='font-size:{zoom}%;white-space:pre-wrap'>{text}</div>", unsafe_allow_html=True)

    st.markdown("**Add annotation** (the original is never changed — annotations are a removable layer)")
    a1, a2 = st.columns(2)
    with a1:
        kind = st.selectbox("Type", ["Highlight", "Underline", "Sticky note", "Stamp", "Redaction"])
        target = st.text_input("Text to mark (must appear in the document)", key="ann_target")
    with a2:
        note = st.text_input("Note / stamp text", key="ann_note", placeholder="e.g. APPROVED, REVIEWED")
        reason = st.selectbox("Redaction reason", ["Patient PII", "Patient PHI", "Commercial confidentiality", "Legal privilege", "Personal data (PDPPL)"],
                              disabled=(kind != "Redaction"))
        restricted = st.checkbox("Visible only to me and administrators", value=False)
    if st.button("➕ Add annotation", type="primary"):
        if not target or target not in (doc["body_text"] or ""):
            st.error("Text to mark must exactly match text in the document.")
        else:
            db_ext.add_annotation(doc_id, user, kind, note, target, reason if kind == "Redaction" else "", int(restricted))
            st.rerun()
    for a in visible_anns:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"{'🟨' if a['kind']=='Highlight' else '⬛' if a['kind']=='Redaction' else '📝'} **{a['kind']}** — “{a['target']}”"
                        f"{' · reason: ' + a['reason'] if a['reason'] else ''}{' · ' + a['text'] if a['text'] else ''}  \n"
                        f"<span style='color:#6B7280;font-size:0.8rem'>{a['user']} · {a['ts']}{' · restricted' if a['restricted'] else ''}</span>",
                        unsafe_allow_html=True)
        with c2:
            if a["user"] == user or theme.is_admin():
                if st.button("Remove", key=f"rmann_{a['id']}"):
                    db_ext.delete_annotation(a["id"])
                    st.rerun()
    reds = [a for a in anns if a["kind"] == "Redaction"]
    if reds and not declared and st.button("🔥 Publish redacted copy (burn in) as a new version"):
        burned = doc["body_text"] or ""
        for a in reds:
            burned = burned.replace(a["target"], "█" * max(4, len(a["target"])))
        newv = db.checkin_new_version(doc_id, user, burned, "Redacted copy — redactions burned in", "minor")
        st.success(f"Created v{newv} with redactions permanently applied (original version retained in history).")
        st.rerun()
    dl = (doc["body_text"] or "")
    st.download_button("🖨 Download / print without annotations", dl.encode("utf-8"), f"{doc['doc_code']}.txt")

with tabs[5]:
    user = theme.current_user()
    st.markdown('<div class="efs-section-title">Register & declare as an official record</div>', unsafe_allow_html=True)
    st.write("A declared record cannot be altered — content, metadata and check-out are all locked for every user, "
             "preserving integrity for audits and accreditation.")
    if declared:
        who, when = declared.split("|")
        st.success(f"🔏 Declared as a record by **{who}** on {when}. Immutable.")
    elif doc["status"] in ("Released", "Archived"):
        if st.button("🔏 Declare as record", type="primary"):
            db_ext.declare_record(doc_id, user)
            st.rerun()
    else:
        st.info("Only Released or Archived documents can be declared as records.")
