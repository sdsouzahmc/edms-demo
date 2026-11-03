import streamlit as st
import db
import theme
from ocr_utils import extract_metadata, auto_name

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("1 · Correspondence & Document Intake Management",
             "Postal & email capture · registration · classification · QR verification")

tab1, tab2 = st.tabs(["📥 Register New Correspondence", "📋 Incoming/Outgoing Register"])

with tab1:
    st.markdown(f"{theme.tag_custom('Custom intake portal')} {theme.tag_ms('Outlook integration (simulated)')}",
                unsafe_allow_html=True)
    st.write("")
    with st.form("intake_form"):
        c1, c2 = st.columns(2)
        with c1:
            direction = st.selectbox("Direction", ["Incoming", "Outgoing"])
            channel = st.selectbox("Channel", ["Postal Mail", "Email / Outlook"])
            sender = st.text_input("Sender", placeholder="e.g. Ministry of Public Health")
            recipient = st.text_input("Recipient", placeholder="e.g. Compliance Officer")
            subject = st.text_input("Subject", placeholder="e.g. Annual Facility License Renewal")
        with c2:
            department = st.selectbox("Assign to Department", db.DEPARTMENTS)
            classification = st.selectbox("Classification", db.CLASSIFICATIONS,
                                           help="Internal / External / Regulatory — per SOW §2.4")
            security_level = st.selectbox("Security Level", db.SECURITY_LEVELS)
            language = st.selectbox("Language", ["English", "Arabic"])
        body = st.text_area("Content / Notes (captured text)", height=120,
                             placeholder="Paste or type the letter content — this becomes searchable full text.")
        submitted = st.form_submit_button("Register Correspondence", type="primary")

    if submitted:
        if not subject:
            st.error("Subject is required.")
        else:
            meta = extract_metadata(body) if body else {}
            title = auto_name(meta, subject)
            doc_id, code = db.create_document(
                title=title or subject, department=department, classification=classification,
                security_level=security_level, doc_type="Correspondence",
                source="Postal" if channel.startswith("Postal") else "Email",
                language=language, body_text=body or subject,
                created_by=theme.current_user(), sender=sender, recipient=recipient,
            )
            db.log_correspondence(doc_id, direction, channel, sender, recipient, subject,
                                   theme.current_user())
            st.session_state["last_intake_doc"] = doc_id
            st.success(f"✅ Registered as **{code}** — routed to {department} for review.")
            if meta:
                st.caption("Auto-extracted metadata: " + ", ".join(f"**{k}**: {v}" for k, v in meta.items()))
            st.rerun()

    if "last_intake_doc" in st.session_state:
        doc = db.get_document(st.session_state["last_intake_doc"])
        if doc:
            st.markdown("---")
            st.markdown('<div class="efs-section-title">🔖 Document Number & QR Verification</div>',
                         unsafe_allow_html=True)
            cc1, cc2 = st.columns([2, 1])
            with cc1:
                st.markdown(f"""
                <div class="efs-card">
                <b>Document Code:</b> {doc['doc_code']}<br>
                <b>Status:</b> {theme.pill(doc['status'])}<br>
                <b>Department:</b> {doc['department']} &nbsp;|&nbsp; <b>Classification:</b> {doc['classification']}<br>
                <b>Registered by:</b> {doc['created_by']} on {doc['created_at']}
                </div>
                """, unsafe_allow_html=True)
                st.info("A QR verification code is generated automatically once the document is **released** "
                        "(see Workflow & Approvals, then Document Control). This proves the document is a "
                        "true copy at point of use.")
            with cc2:
                st.page_link("wg4_workflow.py", label="→ Continue to Workflow & Approvals")

with tab2:
    corr = db.get_correspondence()
    st.markdown(f"**{len(corr)}** correspondence entries logged")
    if corr:
        for r in corr[:50]:
            c1, c2, c3 = st.columns([0.5, 3, 1])
            with c1:
                icon = "📨" if r["direction"] == "Incoming" else "📤"
                st.markdown(f"<div style='font-size:1.4rem'>{icon}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{r['subject']}** — {r['doc_code']}  \n"
                             f"<span style='color:#6B7280;font-size:0.85rem'>"
                             f"{r['direction']} · {r['channel']} · {r['sender']} → {r['recipient']} · "
                             f"logged by {r['logged_by']} at {r['logged_at']}</span>",
                             unsafe_allow_html=True)
            with c3:
                st.markdown(theme.pill(r["status"]), unsafe_allow_html=True)
            st.divider()
    else:
        st.info("No correspondence registered yet. Use the form above to log one.")
