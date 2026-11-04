import streamlit as st
import db
import db_ext
import rfp_data
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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 My Approval Queue", "📊 Workflow Dashboard", "🔀 All Documents in Flight",
                                        "🛠 Workflow Designer", "⚡ Ad-hoc Routing"])

with tab1:
    import delegation
    pending = delegation.pending_for_user(theme.current_user())
    _away = delegation.is_away(theme.current_user())
    if _away:
        st.warning(f"🏖 You are marked out of office until **{_away['end_date']}** — your approvals are visible to **{_away['delegate']}**. "
                   "Manage on page 19 · Approval Delegation.")
    for _r in delegation.covering(theme.current_user()):
        st.info(f"🤝 Covering for **{_r['delegator']}** until {_r['end_date']} — their approvals are listed below with a delegation tag.")
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
            {(' &nbsp;·&nbsp; ⏱ SLA ' + str(w['sla_hours']) + 'h') if w['sla_hours'] else ''}{' &nbsp;·&nbsp; ✍ e-signature required' if w['esign_required'] else ''}
            {('<br><span style="color:#1F6F78;font-weight:700">🏖 On behalf of ' + w['on_behalf_of'] + ' (delegation)</span>') if w.get('on_behalf_of') else ''}
            </div>
            """, unsafe_allow_html=True)
            import signing
            _sp = signing.ensure(theme.current_user())
            p1, p2 = st.columns([1.2, 2])
            pin = p1.text_input("Signature PIN", type="password", key=f"pin_{w['id']}", placeholder="Signature PIN", max_chars=12,
                                label_visibility="collapsed")
            p2.caption(f"✍ Approving applies your **e-signature** (image) and a **digital signature** (certificate …{_sp['serial'][-6:]}). "
                       + ("Demo PIN: 1234 — change it on My Signature." if _sp["is_demo"] else "Enter your signature PIN."))
            cc1, cc2, cc3, cc4 = st.columns([1.2, 1, 1.4, 1.4])
            with cc1:
                if st.button("✍ Sign & Approve", key=f"appr_{w['id']}", type="primary"):
                    _ob = w.get("on_behalf_of") if w.get("on_behalf_of") in theme.ROLES else None
                    ok_, res_ = signing.sign(w["document_id"], theme.current_user(), w["stage"], pin, "Approved", _ob)
                    if not ok_:
                        st.error(res_)
                        st.stop()
                    sig = res_["short"]
                    db.advance_workflow(w["document_id"], "approve", theme.current_user(),
                                         f"Approved via e-signature {sig}" + (f" — on behalf of {w['on_behalf_of']}" if w.get("on_behalf_of") else ""), workflow_id=w["id"])
                    if w.get("on_behalf_of"):
                        delegation.record_action(w["document_id"], theme.current_user(), w["on_behalf_of"], "Approved", w["stage"])
                    nxt = db.get_document(w["document_id"])
                    for sub in set(db_ext.subscribers_of(w["document_id"], nxt["classification"])):
                        db_ext.notify(sub, f"{nxt['doc_code']} moved to {nxt['status']}.", w["document_id"], "approval")
                    st.toast(f"Signed & approved · e-signature {sig}")
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
                    db.advance_workflow(w["document_id"], "reject", theme.current_user(), (reason or "No reason given") + (f" — on behalf of {w['on_behalf_of']}" if w.get("on_behalf_of") else ""), workflow_id=w["id"])
                    if w.get("on_behalf_of"):
                        delegation.record_action(w["document_id"], theme.current_user(), w["on_behalf_of"], "Rejected", w["stage"])
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


with tab4:
    st.markdown('<div class="efs-section-title">Configure approval chains per department & document type</div>',
                unsafe_allow_html=True)
    st.caption("Chains are configurable without code. New documents of the chosen department/type follow the saved chain "
               "(Draft first, Released last). Finance sign-off is added automatically for financial document types.")
    c1, c2 = st.columns(2)
    with c1:
        dpt = st.selectbox("Department", rfp_data.DEPARTMENTS, key="wd_dept")
    with c2:
        dtype = st.selectbox("Document type (blank = department default)", [""] + rfp_data.DOC_TYPES, key="wd_type")
    current = db_ext.stages_for(dpt, dtype)
    st.markdown("Current chain:")
    st.markdown('<div class="efs-stepper">' + '<span class="efs-arrow">→</span>'.join(
        f'<span class="efs-step">{x}</span>' for x in current) + "</div>", unsafe_allow_html=True)
    optional = ["Department Review", "Legal Review", "Quality Review", "Clinical Review", "Approval", "Finance Sign-off",
                "Executive Approval", "Acknowledgment"]
    middle = st.multiselect("Intermediate stages (in order)", optional, default=[x for x in current if x not in ("Draft", "Released")],
                            key=f"wd_mid_{dpt}_{dtype}")
    if st.button("💾 Save workflow", disabled=not (theme.is_admin() or theme.current_profile()["dept"] == dpt)):
        db_ext.save_template(dpt, dtype, ["Draft"] + middle + ["Released"], theme.current_user())
        db.log_audit(None, theme.current_user(), "Workflow Configured", f"{dpt} / {dtype or 'default'}: " + " → ".join(middle))
        st.success("Workflow saved. Register a new document for this department to see it in action.")
        st.rerun()
    st.markdown("**Saved templates**")
    for t in db_ext.list_templates():
        st.markdown(f"- **{t['department']}** · {t['doc_type'] or 'default'} → " + " → ".join(__import__('json').loads(t["stages"])))

with tab5:
    st.markdown('<div class="efs-section-title">Ad-hoc process — when the next best action is unpredictable</div>',
                unsafe_allow_html=True)
    st.caption("A knowledge worker can pull any department into a document on the fly (parallel review / acknowledgment).")
    docs = [d for d in db.get_documents() if d["status"] not in ("Archived",)]
    if docs:
        dsel = st.selectbox("Document", [f"{d['doc_code']} — {d['title']}" for d in docs], key="adhoc_doc")
        targets = st.multiselect("Request review / acknowledgment from", rfp_data.DEPARTMENTS, key="adhoc_depts")
        note = st.text_input("Instruction", placeholder="e.g. Please confirm contract clauses by Thursday")
        if st.button("⚡ Send ad-hoc request", disabled=not targets):
            d = db.get_document_by_code(dsel.split(" — ")[0])
            recipients = [n for n, p in rfp_data.ROLES.items() if p["dept"] in targets]
            for n in recipients:
                db_ext.notify(n, f"Ad-hoc review requested on {d['doc_code']}: {note or 'please review'}", d["id"], "approval")
            db.log_audit(d["id"], theme.current_user(), "Ad-hoc Routing", f"Routed to {', '.join(targets)}: {note}")
            st.success(f"Request sent to {', '.join(targets)} ({len(recipients)} user(s) notified).")
