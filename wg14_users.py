import html
import pandas as pd
import streamlit as st
import accounts
import db
import db_ext
import icons
import rfp_data
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("14 · User Management", "People, roles, status, passwords, lock-outs and sign-in history")

me = theme.current_user()
rmap = {r["name"]: r for r in accounts.roles()}
us = accounts.users()
now_day = pd.Timestamp.now().normalize()
recent = sum(1 for u in us if u["last_login"] and pd.Timestamp(u["last_login"]) >= now_day - pd.Timedelta(days=1))
c = st.columns(5)
theme.metric_card("Users", len(us), c[0])
theme.metric_card("Active", sum(1 for u in us if u["active"]), c[1])
theme.metric_card("Locked", sum(1 for u in us if u["locked"]), c[2])
theme.metric_card("Administrators", sum(1 for u in us if "admin" in rmap.get(u["role"], {"perms": []})["perms"]), c[3])
theme.metric_card("Signed in (24 h)", recent, c[4])
st.write("")
t1, t2, t3, t4 = st.tabs(["👥 Directory", "➕ Add user", "✏️ Edit / reset / unlock", "🕑 Sign-in history"])

with t1:
    f1, f2, f3 = st.columns([2, 1.3, 1.3])
    with f1:
        q = st.text_input("Search", placeholder="Name, e-mail, department…", label_visibility="collapsed")
    with f2:
        rf = st.multiselect("Role", list(rmap), placeholder="All roles", label_visibility="collapsed")
    with f3:
        sf = st.selectbox("Status", ["All", "Active", "Locked", "Disabled"], label_visibility="collapsed")
    shown = [u for u in us if (not q or q.lower() in (u["username"] + u["email"] + u["dept"] + u["role"]).lower())
             and (not rf or u["role"] in rf)
             and (sf == "All" or (sf == "Active" and u["active"] and not u["locked"]) or (sf == "Locked" and u["locked"]) or (sf == "Disabled" and not u["active"]))]
    cols = st.columns(2)
    for i, u in enumerate(shown):
        r = rmap.get(u["role"], {"color": "#6B7280", "perms": [], "modules": []})
        status = ("Disabled", "#6B7280") if not u["active"] else (("Locked", "#B00020") if u["locked"] else ("Active", "#2E7D32"))
        perms = " ".join(f'<span class="efs-hash">{accounts.PERM_LABEL[p]}</span>' for p in r["perms"][:7]) if "admin" not in r["perms"] else '<span class="efs-hash">Full control</span>'
        with cols[i % 2]:
            st.markdown(f"""<div class="efs-tl" style="--c:{r['color']}">{icons.avatar(u['username'], 46, r['color'])}
            <div style="flex:1;min-width:0"><div class="t">{html.escape(u['username'])} <span class="efs-pill" style="background:{status[1]}1A;color:{status[1]};margin-left:6px">{status[0]}</span></div>
            <div style="font-size:.84rem;color:#374151">{u['role']} · {u['dept']}</div>
            <div class="m"><span>✉️ {html.escape(u['email'] or '—')}</span><span>🕑 {u['last_login'] or 'never signed in'}</span></div>
            <div style="margin-top:6px">{perms}</div></div></div>""", unsafe_allow_html=True)
    if not shown:
        st.info("No users match.")
    df = pd.DataFrame([{"User": u["username"], "Role": u["role"], "Department": u["dept"], "E-mail": u["email"], "Active": bool(u["active"]),
                        "Locked": bool(u["locked"]), "Last sign-in": u["last_login"], "Created": u["created_at"], "Created by": u["created_by"]} for u in us])
    st.download_button("⬇ Export users (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "users.csv")

admin = theme.is_admin()
if not admin:
    for t in (t2, t3):
        with t:
            st.info("Only administrators can add or change users. You are viewing as a read-only role.")
else:
    with t2:
        with st.form("add_user"):
            a, b = st.columns(2)
            with a:
                nm = st.text_input("Full name *")
                em = st.text_input("E-mail")
                pw = st.text_input("Temporary password * (min 8 characters)", type="password")
            with b:
                rl = st.selectbox("Role *", list(rmap))
                dp = st.selectbox("Department *", rfp_data.DEPARTMENTS)
                st.caption("The user must change the temporary password at first sign-in (policy).")
            if st.form_submit_button("Create user", type="primary"):
                if not nm.strip() or len(pw) < 8:
                    st.error("Name and a password of at least 8 characters are required.")
                else:
                    ok, msg = accounts.add_user(me, nm, rl, dp, em, pw)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
    with t3:
        who = st.selectbox("User", [u["username"] for u in us])
        u = next(x for x in us if x["username"] == who)
        a, b = st.columns(2)
        with a:
            rl = st.selectbox("Role", list(rmap), index=list(rmap).index(u["role"]) if u["role"] in rmap else 0, key="eu_role")
            dp = st.selectbox("Department", rfp_data.DEPARTMENTS, index=rfp_data.DEPARTMENTS.index(u["dept"]) if u["dept"] in rfp_data.DEPARTMENTS else 0, key="eu_dept")
        with b:
            em = st.text_input("E-mail", value=u["email"] or "", key="eu_mail")
            act = st.checkbox("Account active", value=bool(u["active"]), key="eu_act")
        if st.button("💾 Save changes", type="primary"):
            if who == me and not act:
                st.error("You cannot disable your own account.")
            else:
                accounts.update_user(me, who, rl, dp, em, act)
                st.success("Saved — the change is recorded in the audit trail with old and new values.")
                st.rerun()
        st.divider()
        x1, x2 = st.columns(2)
        with x1:
            npw = st.text_input("New temporary password", type="password", key="rp")
            if st.button("🔑 Reset password"):
                if len(npw) < 8:
                    st.error("Minimum 8 characters.")
                else:
                    accounts.reset_password(me, who, npw)
                    st.success("Password reset; the user must change it at next sign-in.")
        with x2:
            fails, locked = db_ext.get_lock_state(who)
            st.write(f"Failed attempts: **{fails}** · Locked: **{'yes' if locked else 'no'}**")
            if st.button("🔓 Unlock account", disabled=not (locked or fails)):
                db_ext.unlock(who, me)
                st.rerun()

with t4:
    conn = db.get_conn()
    rows = conn.execute("SELECT ts, actor, action, detail, result, ip, channel FROM audit_log WHERE action IN ('Login','Login Failed','Logout','Password Reset',"
                        "'User Created','User Role Changed','User Updated','User Status Changed','Account Unlocked','Access Denied') ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    if rows:
        st.dataframe(pd.DataFrame([dict(r) for r in rows]).rename(columns={"ts": "When", "actor": "Who", "action": "What", "detail": "Detail", "result": "Result",
                                                                           "ip": "IP", "channel": "Channel"}), use_container_width=True, hide_index=True, height=420)
    else:
        st.info("No sign-in events yet.")
