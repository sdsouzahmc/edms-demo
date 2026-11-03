import streamlit as st
import db
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("4 · Workflow & Approvals Workgroup",
             "Multi-level approval chain · delegation · e-signature · SLA monitoring")

st.markdown(f"{theme.tag_ms('Power Automate workflow engine')}", unsafe_allow_html=True)
st.write("")

profile = theme.current_profile()
is_admin = theme.is_admin()

tab1, tab2, tab3 = st.tabs(["📥 My Approval Queue", "📊 Workflow Dashboard", "🔀 All Documents in Flight"])

with tab1:
    pending = db.get_pending_for_assignee(profile["dept"], is_admin)
    st.markdown(f"**{len(pending)}** item(s) awaiting action" +
                (" (Administrator view — all departments)" if is_admin else f" for **{profile['dept']}**"))
    st.write("")
    if not pending:
        st.info("Nothing pending for your role right now. Try switching user in the sidebar, or register "
                 "a new document on the Correspondence & Intake page.")
    for w in pending:
        with st.container():
            st.markdown(f"""
            <div class="efs-card">
            <b>{w['title']}</b> — {w['doc_code']}<br>
            Stage: <b>{w['stage']}</b> &nbsp;·&nbsp; Department: {w['department']} &nbsp;·&nbsp;
            Classification: {w['classification']}
            </div>
            """, unsafe_allow_html=True)
            cc1, cc2, cc3, cc4 = st.columns([1, 1, 1.4, 1.4])
            with cc1:
                if st.button("✅ Approve", key=f"appr_{w['id']}", type="primary"):
                    db.advance_workflow(w["document_id"], "approve", theme.current_user(),
                                         "Approved via e-signature")
                    st.rerun()
            with cc2:
                if st.button("❌ Reject", key=f"rej_{w['id']}"):
                    st.session_state[f"reject_box_{w['id']}"] = True
            with cc3:
                delegate_to = st.selectbox("Delegate to", list(theme.ROLES.keys()),
                                            key=f"deleg_{w['id']}", label_visibility="collapsed",
                                            placeholder="Delegate to…")
            with cc4:
                if st.button("↪ Delegate", key=f"delegbtn_{w['id']}"):
                    db.delegate_stage(w["document_id"], theme.current_user(), delegate_to)
                    st.success(f"Delegated to {delegate_to}")
                    st.rerun()
            if st.session_state.get(f"reject_box_{w['id']}"):
                reason = st.text_input("Rejection reason", key=f"reason_{w['id']}")
                if st.button("Confirm Rejection", key=f"confirm_rej_{w['id']}"):
                    db.advance_workflow(w["document_id"], "reject", theme.current_user(), reason or "No reason given")
                    st.session_state[f"reject_box_{w['id']}"] = False
                    st.rerun()
            st.divider()

with tab2:
    docs = db.get_documents()
    st.markdown('<div class="efs-section-title">Workflow stage distribution</div>', unsafe_allow_html=True)
    stage_counts = {}
    for d in docs:
        stage_counts[d["status"]] = stage_counts.get(d["status"], 0) + 1
    cols = st.columns(len(db.WORKFLOW_STAGES) + 2)
    all_stages = db.WORKFLOW_STAGES + ["Rejected", "Archived"]
    for i, stage in enumerate(all_stages):
        theme.metric_card(stage, stage_counts.get(stage, 0), cols[i])

    st.write("")
    st.markdown('<div class="efs-section-title">Example scenario — HR Policy Approval chain</div>',
                 unsafe_allow_html=True)
    st.markdown("""
    <div class="efs-stepper">
        <span class="efs-step done">Draft</span><span class="efs-arrow">→</span>
        <span class="efs-step done">Department Review</span><span class="efs-arrow">→</span>
        <span class="efs-step active">Approval</span><span class="efs-arrow">→</span>
        <span class="efs-step">Finance Sign-off</span><span class="efs-arrow">→</span>
        <span class="efs-step">Released</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Each stage supports parallel approvals, delegation, escalation on SLA breach, and "
               "automatic email notifications (Outlook/Power Automate) to the next assignee.")

with tab3:
    docs = db.get_documents()
    for d in docs:
        wf = db.get_workflow(d["id"])
        st.markdown(f"**{d['doc_code']} — {d['title']}**  ({d['department']})")
        stepper_html = '<div class="efs-stepper">'
        for i, stage in enumerate(db.WORKFLOW_STAGES):
            w = next((x for x in wf if x["stage"] == stage), None)
            cls = "done" if w and w["status"] == "done" else ("active" if w and w["status"] == "active" else "")
            if d["status"] == "Rejected" and w and w["status"] == "rejected":
                cls = ""
            stepper_html += f'<span class="efs-step {cls}">{stage}</span>'
            if i < len(db.WORKFLOW_STAGES) - 1:
                stepper_html += '<span class="efs-arrow">→</span>'
        stepper_html += "</div>"
        st.markdown(stepper_html, unsafe_allow_html=True)
        st.divider()
