import streamlit as st
import db
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("5 · Security & Compliance Workgroup",
             "Active Directory / SSO · role-based access control · department-level permissions")

st.markdown(f"{theme.tag_ms('Active Directory + SSO (ADFS)')}", unsafe_allow_html=True)
st.write("")

st.markdown('<div class="efs-section-title">👤 Log in as a different role to see access control in action</div>',
             unsafe_allow_html=True)
st.caption("Use the role switcher in the left sidebar. The document list below updates live based on the "
           "logged-in user's department and permission level — this is the actual access-control logic, "
           "not a cosmetic filter.")

profile = theme.current_profile()
st.markdown(f"""
<div class="efs-card">
<b>Currently viewing as:</b> {theme.current_user()} &nbsp;·&nbsp; <b>Role:</b> {profile['role']}
&nbsp;·&nbsp; <b>Department:</b> {profile['dept']} &nbsp;·&nbsp;
<b>Access level:</b> {"🛡️ Administrator (all departments, full control)" if profile['level']=='admin' else "Department user (own department + published releases)"}
</div>
""", unsafe_allow_html=True)

all_docs = db.get_documents()
is_admin = theme.is_admin()

if is_admin:
    visible = all_docs
else:
    visible = [d for d in all_docs if d["department"] == profile["dept"] or d["status"] == "Released"]
hidden_count = len(all_docs) - len(visible)

c1, c2, c3 = st.columns(3)
theme.metric_card("Documents visible to this user", len(visible), c1)
theme.metric_card("Documents hidden by RBAC", hidden_count, c2)
theme.metric_card("Confidential-tier documents", len([d for d in all_docs if d["security_level"] == "Confidential"]), c3)

st.markdown('<div class="efs-section-title">📂 What this user can see right now</div>', unsafe_allow_html=True)
for d in visible:
    can_edit = is_admin or d["department"] == profile["dept"]
    can_approve = is_admin or (d["department"] == profile["dept"] and profile.get("can_approve"))
    confidential_block = (d["security_level"] == "Confidential" and not is_admin
                           and d["department"] != profile["dept"])
    st.markdown(f"""
    <div class="efs-card">
    <b>{d['doc_code']} — {d['title']}</b><br>
    {d['department']} &nbsp;·&nbsp; {d['security_level']} &nbsp;·&nbsp; {theme.pill(d['status'])}<br>
    <span style="font-size:0.82rem;color:#6B7280">
    View: ✅ &nbsp; Edit: {"✅" if can_edit else "🚫"} &nbsp; Approve: {"✅" if can_approve else "🚫"}
    {" &nbsp; 🔒 Confidential — content masked, metadata only" if confidential_block else ""}
    </span>
    </div>
    """, unsafe_allow_html=True)

if hidden_count:
    with st.expander(f"🚫 {hidden_count} document(s) NOT visible to this user (other departments, in-progress)"):
        hidden = [d for d in all_docs if d not in visible]
        for d in hidden:
            st.markdown(f"- {d['doc_code']} — *{d['department']}* ({d['status']}) — hidden by department-level RBAC")

st.markdown("---")
st.markdown('<div class="efs-section-title">🔑 Access Control Model</div>', unsafe_allow_html=True)
grid = {
    "Records Officer / HR User / Finance User (Department User)": [
        "View & edit documents within own department",
        "Approve workflow stages assigned to their department",
        "View any document once it reaches Released status",
        "Cannot view in-progress documents from other departments",
        "Confidential documents outside their department show metadata only",
    ],
    "Administrator": [
        "View, edit, approve all documents across all departments",
        "Override check-out locks",
        "Manage disposal approvals and legal holds",
        "Full audit log and compliance dashboard access",
    ],
}
for role, perms in grid.items():
    st.markdown(f"**{role}**")
    for p in perms:
        st.markdown(f"- {p}")
    st.write("")

st.info("Encryption & authentication: data in transit is TLS/HTTPS-encrypted; data at rest is encrypted "
        "at the storage layer; authentication is delegated to Active Directory via SSO — no passwords are "
        "stored by the DMS itself.")
