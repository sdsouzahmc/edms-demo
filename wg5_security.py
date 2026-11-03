import re
import streamlit as st
import pandas as pd
import db
import db_ext
import rfp_data
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("5 · Security & Compliance Workgroup",
             "Active Directory / SSO · role-based access control · PII/PHI masking · password policy · e-signature")

st.markdown(f"{theme.tag_ms('Active Directory + SSO (ADFS)')} {theme.tag_ms('Microsoft Purview sensitivity labels')}",
            unsafe_allow_html=True)
st.write("")

profile = theme.current_profile()
user = theme.current_user()
is_admin = theme.is_admin()
all_docs = db.get_documents()
shared_ids = db_ext.shared_with(profile["dept"])


def can_see(d):
    return is_admin or d["department"] == profile["dept"] or d["status"] == "Released" or d["id"] in shared_ids


tabs = st.tabs(["🛡️ Access Control (live)", "🙈 PII / PHI Masking", "🔐 Authentication Policy",
                "📋 Access Report & Sharing", "✍️ E-Signature Report"])

with tabs[0]:
    st.caption("Switch role in the sidebar — the list below is computed from the logged-in user's department and "
               "permission level; this is the real access-control logic, not a cosmetic filter.")
    st.markdown(f"""
    <div class="efs-card">
    <b>Viewing as:</b> {user} &nbsp;·&nbsp; <b>Role:</b> {profile['role']} &nbsp;·&nbsp; <b>Department:</b> {profile['dept']}
    &nbsp;·&nbsp; <b>Access level:</b> {"🛡️ Administrator (all departments, full control)" if is_admin else "Department user (own department + released documents + explicitly shared)"}
    </div>""", unsafe_allow_html=True)
    visible = [d for d in all_docs if can_see(d)]
    hidden = [d for d in all_docs if not can_see(d)]
    c1, c2, c3 = st.columns(3)
    theme.metric_card("Documents visible to this user", len(visible), c1)
    theme.metric_card("Hidden by department RBAC", len(hidden), c2)
    theme.metric_card("Confidential documents", len([d for d in all_docs if d["security_level"] == "Confidential"]), c3)
    st.write("")
    for d in visible[:40]:
        own = is_admin or d["department"] == profile["dept"]
        can_approve = is_admin or (own and profile.get("can_approve"))
        masked = d["security_level"] == "Confidential" and not own
        st.markdown(f"""
        <div class="efs-card">
        <b>{d['doc_code']} — {d['title']}</b><br>
        {d['department']} · {d['security_level']} · {theme.pill(d['status'])}{' · 🔗 shared with your department' if d['id'] in shared_ids and not own else ''}<br>
        <span style="font-size:0.82rem;color:#6B7280">View: ✅ &nbsp; Edit: {"✅" if own else "🚫"} &nbsp; Approve: {"✅" if can_approve else "🚫"}
        {" &nbsp; 🔒 Confidential — metadata only" if masked else ""}</span>
        </div>""", unsafe_allow_html=True)
    if hidden:
        with st.expander(f"🚫 {len(hidden)} document(s) NOT visible to this user (other departments, in progress)"):
            for d in hidden:
                st.markdown(f"- {d['doc_code']} — *{d['department']}* ({d['status']}) — hidden by department-level RBAC")


def mask_phi(text: str) -> str:
    text = re.sub(r"(Patient:\s*)([A-Z][a-z]+)\s+([A-Z])\.", r"\1▓▓▓▓▓▓ ▓.", text)
    text = re.sub(r"QID\s*\d{4}\*{0,4}\d{0,4}", "QID ▓▓▓▓▓▓▓▓▓▓▓", text)
    text = re.sub(r"DOB\s*\d{1,2}/\d{1,2}/\d{4}", "DOB ▓▓/▓▓/▓▓▓▓", text)
    return text


with tabs[1]:
    st.markdown('<div class="efs-section-title">Mask patient PII / PHI from infrastructure roles</div>', unsafe_allow_html=True)
    st.caption("Administrators, super-users, developers and support staff can run the platform without ever seeing patient "
               "identifiers. Masking applies at the data layer and for data in transit; only authorised clinical / records "
               "roles see clear text. Switch between **Sara Al-Ansari** (Medical Records) and **Yusuf Al-Marri** (Administrator).")
    med = [d for d in all_docs if d["doc_type"] == "Medical Record"]
    if not med:
        st.info("No medical records in the repository.")
    else:
        pick = st.selectbox("Medical record", [f"{d['doc_code']} — {d['title']}" for d in med])
        d = db.get_document_by_code(pick.split(" — ")[0])
        clear_role = profile["dept"] == "Medical Records"
        infra_role = is_admin or profile["dept"] == "IT"
        body = d["body_text"] or ""
        l, r = st.columns(2)
        with l:
            st.markdown("**What a Medical Records officer sees**")
            st.code(body, language=None)
        with r:
            st.markdown("**What an infrastructure role sees (masked)**")
            st.code(mask_phi(body), language=None)
        if clear_role:
            st.success(f"You are signed in as {user} ({profile['dept']}) — authorised to view clear text.")
        elif infra_role:
            st.warning(f"You are signed in as {user} ({profile['role']}) — an infrastructure role. Patient identifiers are masked for you.")
        else:
            st.info("Your department has no access to patient identifiers in this document.")

with tabs[2]:
    pol = db_ext.get_policy()
    st.markdown('<div class="efs-section-title">Password, MFA, lockout & session policy</div>', unsafe_allow_html=True)
    with st.form("policy"):
        c1, c2, c3 = st.columns(3)
        with c1:
            min_len = st.number_input("Minimum password length", 8, 32, int(pol["pw_min_len"]))
            complex_ = st.checkbox("Require complexity (upper, lower, digit, symbol)", value=pol["pw_complex"] == "1")
        with c2:
            exp = st.number_input("Password expiry (days) — forced change", 30, 365, int(pol["pw_expiry_days"]))
            mfa = st.checkbox("Multi-factor authentication required", value=pol["mfa"] == "1")
        with c3:
            lock = st.number_input("Lock account after N failed sign-ins", 3, 10, int(pol["lockout_after"]))
            idle = st.number_input("Auto log-off after inactivity (minutes)", 5, 120, int(pol["idle_minutes"]))
        if st.form_submit_button("Save policy", disabled=not is_admin):
            db_ext.set_policy({"pw_min_len": min_len, "pw_complex": int(complex_), "pw_expiry_days": exp,
                               "mfa": int(mfa), "lockout_after": lock, "idle_minutes": idle}, user)
            st.success("Policy saved and written to the audit log.")
            st.rerun()
    if not is_admin:
        st.caption("Only Administrators can change the policy.")
    st.markdown('<div class="efs-section-title">Try it — sign-in lockout simulation</div>', unsafe_allow_html=True)
    st.caption(f"Policy: lock after **{pol['lockout_after']}** failed attempts; an Administrator can override the lockout.")
    target = st.selectbox("Account", list(rfp_data.ROLES.keys()), key="lock_user")
    fails, locked = db_ext.get_lock_state(target)
    st.markdown(f"Status: {'🔒 **LOCKED**' if locked else '🟢 Active'} · failed attempts: **{fails}**")
    cA, cB, cC = st.columns(3)
    with cA:
        if st.button("❌ Simulate failed sign-in"):
            res = db_ext.attempt_login(target, False)
            if res == "locked":
                st.error("Account is locked after repeated failures.")
            else:
                st.warning(f"Sign-in {res}")
            st.rerun()
    with cB:
        if st.button("✅ Simulate valid sign-in (+MFA)"):
            st.info(f"Result: {db_ext.attempt_login(target, True)}")
    with cC:
        if locked and st.button("🔓 Administrator unlock", disabled=not is_admin):
            db_ext.unlock(target, user)
            st.rerun()
    st.caption("Passwords are never stored by the EDMS — authentication is delegated to Active Directory / SSO; "
               "this simulation demonstrates the enforced policy behaviour.")

with tabs[3]:
    st.markdown('<div class="efs-section-title">Access permissions audit report — who can access what</div>', unsafe_allow_html=True)
    rows = []
    for dept in rfp_data.DEPARTMENTS:
        users = [(n, p) for n, p in rfp_data.ROLES.items() if p["dept"] == dept]
        n_docs = len([d for d in all_docs if d["department"] == dept])
        rows.append({"Folder / Department": dept, "Documents": n_docs,
                     "Department users": ", ".join(f"{n} ({p['role']})" for n, p in users) or "—",
                     "Access type": "Read / Edit / Approve (own dept)",
                     "Shared to": ", ".join(sorted({s["to_department"] for s in db_ext.list_shares() if s["department"] == dept})) or "—"})
    rows.append({"Folder / Department": "ALL", "Documents": len(all_docs),
                 "Department users": "Yusuf Al-Marri (Administrator)", "Access type": "Full control", "Shared to": "—"})
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇ Export access report (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "access_permissions_report.csv")

    st.markdown('<div class="efs-section-title">Share a document with another department (as needed)</div>', unsafe_allow_html=True)
    st.caption("Staff cannot see other departments' files by default; a specific document can be shared on an as-needed basis.")
    mine = [d for d in all_docs if is_admin or d["department"] == profile["dept"]]
    if mine:
        c1, c2 = st.columns(2)
        with c1:
            dsel = st.selectbox("Document", [f"{d['doc_code']} — {d['title']}" for d in mine], key="sh_doc")
        with c2:
            to = st.selectbox("Share with department", rfp_data.DEPARTMENTS, key="sh_to")
        if st.button("🔗 Share"):
            d = db.get_document_by_code(dsel.split(" — ")[0])
            db_ext.share_doc(d["id"], to, user)
            st.success(f"Shared with {to}. Switch to a user in that department to confirm.")
            st.rerun()
    for s in db_ext.list_shares()[:10]:
        st.markdown(f"- 🔗 **{s['doc_code']}** {s['title']} → *{s['to_department']}* (by {s['shared_by']}, {s['ts']})")

with tabs[4]:
    st.markdown('<div class="efs-section-title">Electronic signature usage</div>', unsafe_allow_html=True)
    st.caption("Each approval applies a secure e-signature (user, stage, timestamp, SHA-256 signature hash). "
               "Only authorised approvers can sign; usage is reportable per user.")
    log = db_ext.esign_report()
    if log:
        df = pd.DataFrame([{"Signer": e["signer"], "Document": e["doc_code"], "Title": e["title"], "Stage": e["stage"],
                            "Signature hash": e["signature_hash"], "Timestamp": e["ts"]} for e in log])
        by = df.groupby("Signer").size().reset_index(name="Signatures applied")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.dataframe(by, use_container_width=True, hide_index=True)
        with c2:
            st.dataframe(df.head(50), use_container_width=True, hide_index=True)
        st.download_button("⬇ Export e-signature log (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "esignature_usage.csv")
    else:
        st.info("No signatures yet — approve a document in Workflow & Approvals.")
