import streamlit as st
import db
import theme
import datetime as dt
import qrcode
import io

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("8 · Records Management, Archiving & Disposal Workgroup",
             "Retention schedules · automatic archiving · disposal approval · QR true-copy verification")

st.markdown(f"{theme.tag_custom('Retention automation engine')}", unsafe_allow_html=True)
st.write("")

tab1, tab2, tab3, tab4 = st.tabs(["⏳ Retention & Archive", "🗑️ Disposal Workflow",
                                    "📦 Archived Documents", "✅ QR Verification"])

with tab1:
    docs = db.get_documents()
    st.markdown('<div class="efs-section-title">Retention countdown</div>', unsafe_allow_html=True)
    today = dt.date.today()
    rows = []
    for d in docs:
        if d["expiry_date"]:
            days_left = (dt.date.fromisoformat(d["expiry_date"]) - today).days
            rows.append((d, days_left))
    rows.sort(key=lambda x: x[1])
    if not rows:
        st.info("No documents have a retention schedule assigned yet.")
    for d, days_left in rows:
        urgency = "🔴" if days_left < 0 else ("🟠" if days_left < 90 else "🟢")
        st.markdown(f"""
        <div class="efs-card">
        {urgency} <b>{d['doc_code']} — {d['title']}</b> ({d['department']})<br>
        Schedule: {d['retention_schedule']} &nbsp;·&nbsp; Expiry: {d['expiry_date']} &nbsp;·&nbsp;
        <b>{days_left} day(s) remaining</b> {"(OVERDUE)" if days_left < 0 else ""}
        {" &nbsp; 🔒 Legal Hold Active" if d['legal_hold'] else ""}
        </div>
        """, unsafe_allow_html=True)
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            if d["status"] != "Archived" and st.button("🗄️ Archive now", key=f"arc_{d['id']}"):
                db.archive_document(d["id"], theme.current_user())
                st.rerun()
        with cc2:
            hold_label = "🔓 Release Legal Hold" if d["legal_hold"] else "🔒 Apply Legal Hold"
            if st.button(hold_label, key=f"hold_{d['id']}"):
                db.toggle_legal_hold(d["id"], theme.current_user(), not d["legal_hold"])
                st.rerun()
        with cc3:
            st.caption(f"Retention: {d['retention_schedule'] or 'Not set'}")

with tab2:
    st.markdown('<div class="efs-section-title">Request disposal</div>', unsafe_allow_html=True)
    archived_docs = [d for d in db.get_documents() if d["status"] == "Archived"]
    if archived_docs:
        dmap = {f"{d['doc_code']} — {d['title']}": d for d in archived_docs}
        pick = st.selectbox("Select an archived document", list(dmap.keys()))
        target = dmap[pick]
        if target["legal_hold"]:
            st.error("🔒 This document is under legal hold and cannot be disposed.")
        else:
            reason = st.text_area("Disposal justification",
                                   placeholder="e.g. Retention period expired per approved schedule")
            if st.button("📝 Submit Disposal Request", type="primary"):
                db.request_disposal(target["id"], theme.current_user(), reason or "Retention expired")
                st.success("Disposal request submitted for approval.")
                st.rerun()
    else:
        st.caption("No archived documents available for disposal yet.")

    st.markdown("---")
    st.markdown('<div class="efs-section-title">Pending disposal approvals</div>', unsafe_allow_html=True)
    pending_disp = db.get_disposal_requests("Pending Approval")
    if not pending_disp:
        st.caption("No pending disposal requests.")
    for r in pending_disp:
        st.markdown(f"""
        <div class="efs-card">
        <b>{r['doc_code']} — {r['title']}</b> ({r['department']})<br>
        Requested by {r['requested_by']} on {r['requested_at']}<br>
        Reason: {r['reason']}
        {" &nbsp; 🔒 LEGAL HOLD — cannot approve" if r['legal_hold'] else ""}
        </div>
        """, unsafe_allow_html=True)
        if theme.is_admin():
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("✅ Approve Destruction", key=f"appd_{r['id']}", disabled=bool(r['legal_hold'])):
                    db.decide_disposal(r["id"], theme.current_user(), True)
                    st.rerun()
            with cc2:
                if st.button("❌ Reject Request", key=f"rejd_{r['id']}"):
                    db.decide_disposal(r["id"], theme.current_user(), False)
                    st.rerun()
        else:
            st.caption("Only an Administrator can approve destruction (segregation of duties).")

    st.markdown("---")
    st.markdown('<div class="efs-section-title">Approved — awaiting destruction evidence</div>',
                 unsafe_allow_html=True)
    approved = db.get_disposal_requests("Approved")
    for r in approved:
        st.markdown(f"**{r['doc_code']} — {r['title']}** — approved by {r['approved_by']} on {r['approved_at']}")
        if st.button("🧾 Log Secure Destruction Evidence", key=f"destroy_{r['id']}"):
            db.finalize_destruction(r["id"], theme.current_user())
            st.success("Destruction evidence logged to immutable audit trail.")
            st.rerun()

    st.markdown("---")
    st.markdown('<div class="efs-section-title">Destroyed — compliance evidence</div>', unsafe_allow_html=True)
    destroyed = db.get_disposal_requests("Destroyed")
    for r in destroyed:
        st.markdown(f"✅ {r['doc_code']} — {r['title']} — destroyed, evidence retained in audit log "
                     f"(approved by {r['approved_by']} on {r['approved_at']})")

with tab3:
    archived = [d for d in db.get_documents() if d["status"] == "Archived"]
    st.markdown(f"**{len(archived)}** document(s) in the archive library (separated from the active repository)")
    for d in archived:
        st.markdown(f"""
        <div class="efs-card">
        <b>{d['doc_code']} — {d['title']}</b> ({d['department']})<br>
        Archived on {d['archived_at']} &nbsp;·&nbsp; Retention: {d['retention_schedule']}
        </div>
        """, unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="efs-section-title">QR true-copy verification</div>', unsafe_allow_html=True)
    released = [d for d in db.get_documents() if d["qr_token"]]
    if not released:
        st.info("No documents have been released yet — release one via Workflow & Approvals to generate "
                "its QR verification code.")
    else:
        dmap = {f"{d['doc_code']} — {d['title']}": d for d in released}
        pick = st.selectbox("Select a released document", list(dmap.keys()))
        target = dmap[pick]
        qr_payload = f"EDMS-VERIFY:{target['doc_code']}:{target['qr_token']}"
        img = qrcode.make(qr_payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.image(buf.getvalue(), caption=f"QR for {target['doc_code']}", width=200)
        with c2:
            st.markdown(f"""
            <div class="efs-card">
            <b>{target['title']}</b><br>
            Document: {target['doc_code']} &nbsp;·&nbsp; Version: v{target['current_version']}<br>
            Released: {target['released_at']}<br>
            Verification token: <code>{target['qr_token']}</code>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("---")
        st.caption("Simulate scanning this code at point of use:")
        token_input = st.text_input("Enter / paste token to verify", value=target["qr_token"])
        if st.button("🔍 Verify"):
            found = db.find_by_qr(token_input)
            if found:
                st.success(f"✅ VERIFIED TRUE COPY — {found['doc_code']} · v{found['current_version']} · "
                           f"released {found['released_at']}")
                db.log_audit(found["id"], theme.current_user(), "QR Verified", "True-copy check performed")
            else:
                st.error("❌ Not found — this token does not match any released document.")
