import streamlit as st
import db
import distribution as dist
import db_ext
import rfp_data
import theme
from ocr_utils import extract_metadata, auto_name

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("1 · Correspondence & Document Intake Management",
             "Postal & email capture · registration · classification · QR verification")

tab1, tab2, tab3 = st.tabs(["📥 Register New Correspondence", "📋 Incoming/Outgoing Register", "📤 Outgoing Dispatch Tracker"])

with tab1:
    st.markdown(f"{theme.tag_custom('Custom intake portal')} {theme.tag_ms('Outlook integration (simulated)')}",
                unsafe_allow_html=True)
    st.write("")
    with st.form("intake_form"):
        c1, c2 = st.columns(2)
        with c1:
            direction = st.selectbox("Direction", ["Incoming", "Outgoing", "Internal"])
            kind = st.selectbox("Kind", ["Letter", "Memo", "Email", "Circular", "Telegram / Transaction"])
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
            copies = st.multiselect("Distribute copies to units", rfp_data.DEPARTMENTS)
        body = st.text_area("Content / Notes (captured text)", height=120,
                             placeholder="Paste or type the letter content — this becomes searchable full text.")
        auto = st.checkbox("📬 Route automatically by content (overrides the department above when a distribution rule matches)", value=True)
        submitted = st.form_submit_button("Register Correspondence", type="primary")

    if submitted:
        if not subject:
            st.error("Subject is required.")
        else:
            meta = extract_metadata(body) if body else {}
            title = auto_name(meta, subject)
            doc_id, code = db.create_document(
                title=title or subject, department=department, classification=classification,
                security_level=security_level,
                doc_type={"Memo": "Memo", "Circular": "Circular", "Email": "Memo"}.get(kind, "Regulatory Letter" if classification == "Regulatory" else "Letter"),
                source="Postal" if channel.startswith("Postal") else "Email",
                language=language, body_text=body or subject,
                created_by=theme.current_user(), sender=sender, recipient=recipient,
            )
            db.log_correspondence(doc_id, direction, channel, sender, recipient, subject,
                                   theme.current_user())
            st.session_state["last_intake_doc"] = doc_id
            routed = None
            if auto:
                routed = dist.distribute(doc_id, theme.current_user(), apply_dept=True, notify=True)
            for n, p in rfp_data.ROLES.items():
                if not routed or not routed["hits"]:
                  if p["dept"] in copies or p["dept"] == department:
                      db_ext.notify(n, f"New {classification.lower()} {kind.lower()} registered: {code} — {subject}", doc_id, "info")
            if copies:
                db.log_audit(doc_id, theme.current_user(), "Copies Distributed", "Copies sent to: " + ", ".join(copies))
            if direction == "Outgoing":
                db_ext.create_dispatch(doc_id, classification, kind, recipient, ", ".join(copies), theme.current_user())
            if routed and routed["hits"]:
                st.success(f"✅ Registered as **{code}** — auto-routed to **{routed['primary']}**"
                           + (f", copies to {', '.join(routed['copies'])}" if routed["copies"] else "") + f" (rule: {routed['hits'][0]['rule']['name']}).")
            else:
                st.success(f"✅ Registered as **{code}** — routed to {department} for review." + (" No distribution rule matched, so it is in the triage queue." if auto else ""))
            if meta:
                st.caption("Auto-extracted metadata: " + ", ".join(f"**{k}**: {v}" for k, v in meta.items()))

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

with tab3:
    st.markdown('<div class="efs-section-title">Controlled dispatch — approval → release → recipient</div>', unsafe_allow_html=True)
    st.caption("Outgoing items are tracked through Drafted → Approved → Released → Dispatched, with who approved and "
               "released each one, by category (internal / external / regulatory).")
    rows = db_ext.list_dispatch()
    cats = st.multiselect("Category", ["Internal", "External", "Regulatory"], default=["Internal", "External", "Regulatory"])
    for x in [r for r in rows if r["category"] in cats]:
        steps = db_ext.DISPATCH_STEPS
        idx = steps.index(x["status"])
        html = '<div class="efs-stepper">' + '<span class="efs-arrow">→</span>'.join(
            f'<span class="efs-step {"done" if i < idx or x["status"] == "Dispatched" else ("active" if i == idx else "")}">{s_}</span>'
            for i, s_ in enumerate(steps)) + "</div>"
        st.markdown(f"""<div class="efs-card"><b>{x['doc_code']} — {x['title']}</b><br>
        {x['category']} · {x['kind']} → <b>{x['recipient']}</b>{' · cc: ' + x['copies_to'] if x['copies_to'] else ''}<br>
        <span style="font-size:0.8rem;color:#6B7280">approved by {x['approved_by'] or '—'} · released by {x['released_by'] or '—'} ·
        dispatched {x['dispatched_at'] or '—'}</span>{html}</div>""", unsafe_allow_html=True)
        if x["status"] != "Dispatched":
            nxt = steps[idx + 1]
            if st.button(f"Mark as {nxt}", key=f"disp_{x['id']}"):
                db_ext.advance_dispatch(x["id"], theme.current_user())
                st.rerun()
    if not rows:
        st.info("No outgoing items yet — register one with Direction = Outgoing.")
