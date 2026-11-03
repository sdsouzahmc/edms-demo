import streamlit as st
import db
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

tabs = st.tabs(["✏️ Check-out / Check-in", "🕒 Version History", "🔍 Compare Versions", "📣 Publish / Obsolete"])

with tabs[0]:
    st.markdown('<div class="efs-section-title">Check-out, edit, check back in as a new version</div>',
                 unsafe_allow_html=True)
    if not locked_by:
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
