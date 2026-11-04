import json
import streamlit as st
import db
import db_ext
import rfp_data
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("10 · Administration & Integrations",
             "AD / SSO sync · Outlook · Office 365 · EMR · API · multi-site · DR · backup & point-in-time restore")

user = theme.current_user()
if not theme.is_admin():
    st.warning("Most controls here are Administrator-only. Switch to **Yusuf Al-Marri (Administrator)** in the sidebar "
               "to make changes; other roles have read-only access.")

tabs = st.tabs(["🔌 Integrations", "👥 Identity (AD / SSO)", "🏥 Sites, Storage & HA / DR", "💾 Backup & Recovery",
                "📈 Monitoring", "🧪 Demo scenario"])

with tabs[0]:
    st.markdown(f"{theme.tag_ms('Outlook · Office 365 · SharePoint')} {theme.tag_custom('EMR secure upload · REST API')}",
                unsafe_allow_html=True)
    st.write("")
    rows = [
        ("Microsoft Outlook", "Capture & archive official emails + attachments", "Connected (simulated)", "✅"),
        ("Active Directory / Entra ID", "SSO, RBAC, auto provisioning / de-provisioning", "Synced — see Identity tab", "✅"),
        ("Office 365 (Word / Excel / Teams / Groups)", "Create, edit, co-author; version synchronisation", "Connected (simulated)", "✅"),
        ("SharePoint", "Source repository for migration + foundation layer", "Connected (simulated)", "✅"),
        ("EMR", "Secure upload of patient documents; EDMS is the document repository", "Connected (simulated)", "✅"),
        ("REST / Graph API", "Third-party integration, reporting extensions (HTML/XML/JS)", "Available — see sample below", "✅"),
        ("CMIS", "Content Management Interoperability Services", "Not native — covered via Graph API / PnP connectors", "⚠️"),
    ]
    for name, what, state, icon in rows:
        st.markdown(f"<div class='efs-card'>{icon} <b>{name}</b> — {what}<br>"
                    f"<span style='color:#6B7280;font-size:0.82rem'>{state}</span></div>", unsafe_allow_html=True)

    st.markdown('<div class="efs-section-title">📧 Outlook capture — archive an email into the EDMS</div>', unsafe_allow_html=True)
    mails = [
        ("Ministry of Public Health", "Request for updated staff credentialing list",
         "Please send the updated credentialing list for all clinical staff by 30 November. Ref MOPH-2026-0522."),
        ("Gulf Medical Supplies W.L.L.", "Delivery schedule - PO-2026-0417",
         "Confirming delivery of PO-2026-0417 on 10/12/2026. Invoice to follow. Amount QAR 48,900."),
        ("Doha Facility Services", "Quarterly maintenance visit confirmation",
         "Our engineers will attend on 5 December for the quarterly visit under the maintenance contract."),
    ]
    pick = st.selectbox("Inbox (simulated)", [f"{m[0]} — {m[1]}" for m in mails])
    mail = mails[[f"{m[0]} — {m[1]}" for m in mails].index(pick)]
    st.caption(mail[2])
    dep = st.selectbox("File into department", rfp_data.DEPARTMENTS, key="mail_dept")
    if st.button("📥 Archive email to EDMS", type="primary"):
        doc_id, code = db.create_document(
            title=mail[1], department=dep, classification="External", security_level="Internal",
            doc_type="Memo", source="Email", language="English", body_text=mail[2], created_by=user,
            sender=mail[0], recipient=dep, retention_label="General Correspondence - 3 years")
        db.log_correspondence(doc_id, "Incoming", "Email / Outlook", mail[0], dep, mail[1], user)
        db.log_audit(doc_id, user, "Outlook Capture", "Email and attachments archived via Outlook integration")
        db_ext.notify(user, f"Email archived as {code}.", doc_id, "info")
        st.success(f"Archived as **{code}** with full audit trail.")

    st.markdown('<div class="efs-section-title">🧬 EMR — secure patient document upload</div>', unsafe_allow_html=True)
    st.caption("Patient documents received from the EMR are stored as Confidential medical records, "
               "restricted to Medical Records staff; infrastructure roles see masked values only (Security page).")
    if st.button("⬆ Receive sample patient document from EMR"):
        doc_id, code = db.create_document(
            title="EMR Discharge Summary (sample)", department="Medical Records", classification="Internal",
            security_level="Confidential", doc_type="Medical Record", source="Upload", language="English",
            body_text="Discharge summary. Patient: Ahmed S., QID 2910****5678, DOB 04/07/1988. "
                      "Programme completion; aftercare plan agreed.", created_by=user,
            sender="EMR", recipient="Medical Records", retention_label="Patient Record - 25 years")
        db.log_audit(doc_id, user, "EMR Upload", "Patient document received securely from EMR")
        st.success(f"Stored as **{code}** (Confidential).")

    st.markdown('<div class="efs-section-title">🔗 API — sample response</div>', unsafe_allow_html=True)
    st.code("GET /api/v1/documents?department=Finance&limit=2", language="http")
    sample = [{"doc_code": d["doc_code"], "title": d["title"], "status": d["status"], "version": d["current_version"],
               "department": d["department"]} for d in db.get_documents(department="Finance")[:2]]
    st.code(json.dumps({"count": len(sample), "items": sample}, indent=2, ensure_ascii=False), language="json")

with tabs[1]:
    st.markdown('<div class="efs-section-title">Directory synchronisation</div>', unsafe_allow_html=True)
    st.caption("Users and groups are synchronised from Active Directory; access follows the user's department and role. "
               "De-provisioning in AD disables EDMS access automatically.")
    if st.button("🔄 Sync from Active Directory", disabled=not theme.is_admin()):
        n = db_ext.sync_ad()
        db.log_audit(None, user, "AD Sync", f"{n} users and groups synchronised")
        st.success(f"{n} users synchronised.")
    for u in db_ext.list_ad():
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{u['display']}** · {u['department']}  \n<span style='color:#6B7280;font-size:0.8rem'>"
                        f"{u['username']} · groups: {u['groups']} · {u['status']} · last sync {u['last_sync']}</span>",
                        unsafe_allow_html=True)
        with c2:
            if u["status"] == "Active" and st.button("Disable", key=f"dis_{u['username']}", disabled=not theme.is_admin()):
                db_ext.deprovision(u["username"], user)
                st.rerun()
    if not db_ext.list_ad():
        st.info("No directory data yet — run a sync.")
    st.markdown('<div class="efs-section-title">Estimated users per department (planning, 2026-2030)</div>', unsafe_allow_html=True)
    st.dataframe([{"Department": k, "Estimated users": v} for k, v in rfp_data.DEPT_USERS.items()],
                 use_container_width=True, hide_index=True)
    st.caption(f"Total estimated users: {sum(rfp_data.DEPT_USERS.values())} · sized for at least 50 concurrent users.")

with tabs[2]:
    st.markdown('<div class="efs-section-title">Multi-site support</div>', unsafe_allow_html=True)
    for name, role, hosting, state in rfp_data.SITES:
        st.markdown(f"<div class='efs-card'>🏥 <b>{name}</b> — {role} · {hosting} · <b>{state}</b></div>", unsafe_allow_html=True)
    st.markdown('<div class="efs-section-title">Storage tiers & retention-capable storage</div>', unsafe_allow_html=True)
    st.dataframe([
        {"Tier": "Tier 1 — Active (SAN)", "Used for": "Current documents, workflows", "Retention lock": "No"},
        {"Tier": "Tier 2 — Nearline (NAS)", "Used for": "Released & archived documents", "Retention lock": "Yes (per schedule)"},
        {"Tier": "Tier 3 — Archive (CAS / WORM)", "Used for": "Declared records, legal hold, evidence", "Retention lock": "Yes (immutable)"},
    ], use_container_width=True, hide_index=True)
    st.markdown('<div class="efs-section-title">Environments, high availability & disaster recovery</div>', unsafe_allow_html=True)
    st.dataframe([
        {"Environment": e, "Location": loc, "Purpose": p}
        for e, loc, p in [
            ("Development", "On-prem / Azure", "Build & customisation"), ("Test", "On-prem / Azure", "UAT & regression"),
            ("Data Warehouse / Reporting", "Azure", "Power BI governance dashboards"), ("Training", "On-prem / Azure", "End-user training"),
            ("Production (HA cluster)", "Primary data centre", "Live service — load balanced, failover"),
            ("Disaster Recovery", "Secondary region (Qatar)", "Continuous replication, RTO/RPO per SLA")]],
        use_container_width=True, hide_index=True)
    c1, c2, c3 = st.columns(3)
    theme.metric_card("Availability target", "≥ 99.7%", c1)
    theme.metric_card("Replication", "Continuous", c2)
    theme.metric_card("Encryption", "TLS 1.2+ / AES-256", c3)

with tabs[3]:
    st.markdown('<div class="efs-section-title">Backup & point-in-time recovery</div>', unsafe_allow_html=True)
    st.caption("Snapshots act as recovery points. Restoring replaces the live database with the chosen point after taking "
               "an automatic pre-restore snapshot, and the restore itself is audited.")
    lbl = st.text_input("Snapshot label", value="Manual snapshot")
    if st.button("💾 Create backup now", disabled=not theme.is_admin()):
        db_ext.make_backup(lbl, user)
        db.log_audit(None, user, "Backup Created", lbl)
        st.success("Backup created.")
        st.rerun()
    for b in db_ext.list_backups():
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"💾 **{b['label']}** · {b['kind']} · {b['size_kb']} KB  \n"
                        f"<span style='color:#6B7280;font-size:0.8rem'>{b['created_at']} · by {b['created_by']}</span>",
                        unsafe_allow_html=True)
        with c2:
            if st.button("⏪ Restore", key=f"rb_{b['id']}", disabled=not theme.is_admin()):
                st.session_state["confirm_restore"] = b["id"]
        if st.session_state.get("confirm_restore") == b["id"]:
            st.warning(f"Restore the system to **{b['created_at']}**? Changes made after this point will be rolled back.")
            if st.button("Confirm restore", key=f"cr_{b['id']}", type="primary"):
                ok = db_ext.restore_backup(b["id"], user)
                st.session_state.pop("confirm_restore", None)
                if ok:
                    st.success("System restored to the selected recovery point.")
                    st.rerun()
                else:
                    st.error("Backup file not found.")

with tabs[4]:
    st.markdown('<div class="efs-section-title">Resource utilisation</div>', unsafe_allow_html=True)
    u = db_ext.storage_usage()
    c1, c2, c3, c4 = st.columns(4)
    theme.metric_card("Documents", u["documents"], c1)
    theme.metric_card("Versions", u["versions"], c2)
    theme.metric_card("Audit events", u["audit_events"], c3)
    theme.metric_card("Database size (KB)", u["db_kb"], c4)
    st.write("")
    import plotly.graph_objects as go
    dept = {r["department"]: r["n"] for r in db.stats()["by_dept"]}
    fig = go.Figure(go.Bar(x=list(dept.values()), y=list(dept.keys()), orientation="h", marker=dict(color="#2E8B8B")))
    fig.update_layout(height=max(260, 24 * len(dept)), margin=dict(t=10, b=10), title="Content volume by department")
    st.plotly_chart(fig, use_container_width=True)


with tabs[5]:
    import pandas as pd
    import demo_journey as dj
    st.markdown('<div class="efs-section-title">Sample document pack & demo journey</div>', unsafe_allow_html=True)
    st.caption("23 realistic, fully fictional documents (English and Arabic; typed and scanned; plus a duplicate and a corrupt file) are pushed through the real "
               "pipeline: scan-folder intake → OCR → classification → routing → numbering → approvals with e-signatures → inter-department routing → secure links → versioning → archive / legal hold.")
    files = dj.pack_files()
    st.dataframe(pd.DataFrame({"Sample file": files}), use_container_width=True, hide_index=True, height=220)
    c1, c2 = st.columns([1, 1])
    c1.download_button("⬇ Download the sample pack (.zip)", dj.pack_zip(), "sample_document_pack.zip", "application/zip", key="dj_zip")
    run_move = c2.checkbox("Also move documents through workflows (approve, reject, sign, release, archive…)", value=True, key="dj_move")
    if st.button("🚀 Load sample pack & run the demo journey", type="primary", disabled=not theme.is_admin(), key="dj_go"):
        with st.spinner("Scanning, OCR-ing, classifying and routing 23 files…"):
            res, jlog = dj.run(theme.current_user(), run_move)
        st.session_state["dj_res"] = (res, jlog)
    if not theme.is_admin():
        st.caption("Only an Administrator can load the pack.")
    got = st.session_state.get("dj_res")
    if got:
        res, jlog = got
        st.success(f"{sum(1 for r in res if r['status'] == 'Registered')} registered · "
                   f"{sum(1 for r in res if r['status'].startswith('Skipped'))} skipped as duplicates · "
                   f"{sum(1 for r in res if r['status'].startswith('Rejected'))} rejected as unreadable · {len(jlog)} workflow movements.")
        st.markdown("**Intake result**")
        st.dataframe(pd.DataFrame([{"File": r["file"], "Result": r["status"], "Reference": r.get("code", ""), "Routed to": r.get("routed", ""),
                                    "Text by": r.get("method", "")} for r in res]), use_container_width=True, hide_index=True)
        if jlog:
            st.markdown("**Movement log**")
            st.dataframe(pd.DataFrame(jlog, columns=["Document", "What happened"]), use_container_width=True, hide_index=True)
        st.caption("Now open Workflow & Approvals, Document Control, Secure Exchange, Records, Analytics and the Audit trail to follow each document.")
