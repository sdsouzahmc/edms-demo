import pandas as pd
import streamlit as st
import accounts
import db
import icons
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("15 · Role Management", "What each role can do, which modules it sees, and the highest security level it may open")

me = theme.current_user()
admin = theme.is_admin()
rl = accounts.roles()
us = accounts.users()
cnt = {r["name"]: sum(1 for u in us if u["role"] == r["name"]) for r in rl}

st.markdown('<div class="efs-section-title">Roles</div>', unsafe_allow_html=True)
cols = st.columns(3)
for i, r in enumerate(rl):
    with cols[i % 3]:
        mods = " ".join(accounts.MODULES[m][1] for m in r["modules"] if m in accounts.MODULES)
        pm = "Full control" if "admin" in r["perms"] else ", ".join(accounts.PERM_LABEL[p] for p in r["perms"]) or "none"
        st.markdown(f"""<div class="efs-tl" style="--c:{r['color']};flex-direction:column;gap:6px">
        <div style="display:flex;gap:10px;align-items:center">{icons.chip('key' if 'admin' in r['perms'] else 'shield', r['color'], 38)}
        <div><div class="t">{r['name']}</div><div style="font-size:.74rem;color:#6B7280">{cnt[r['name']]} user(s) · clearance: {r['clearance']}</div></div></div>
        <div style="font-size:.82rem;color:#374151">{r['description']}</div>
        <div style="font-size:.76rem"><b>Can:</b> {pm}</div><div style="font-size:1rem" title="Modules in the menu">{mods}</div></div>""", unsafe_allow_html=True)

st.write("")
t1, t2, t3 = st.tabs(["🧮 Permission & module matrix", "➕ New role", "🔎 Who has access to what"])

with t1:
    st.caption("Tick what each role may do and which modules appear in its menu. Changes apply at the next page load and are written to the audit trail.")
    perm_df = pd.DataFrame([{"Role": r["name"], **{accounts.PERM_LABEL[p]: (p in r["perms"] or "admin" in r["perms"] and r["name"] == "Administrator") for p in accounts.PERMS}} for r in rl]).set_index("Role")
    mod_df = pd.DataFrame([{"Role": r["name"], **{f"{accounts.MODULES[m][1]} {m}": (m in r["modules"]) for m in accounts.ALL}} for r in rl]).set_index("Role")
    st.markdown("**Actions**")
    pe = st.data_editor(perm_df, use_container_width=True, disabled=not admin, key="perm_ed")
    st.markdown("**Menu modules** (🏠 home · 1 Intake · 2 OCR · 3 Control · 4 Workflow · 5 Security · 6 Search · 7 Audit · 8 Records · 9 Workspace · 10 Admin · 11 RFP · 12 Distribution · 13 Analytics · 14 Users · 15 Roles)")
    me_ = st.data_editor(mod_df, use_container_width=True, disabled=not admin, key="mod_ed")
    cl = {}
    cc = st.columns(4)
    for i, r in enumerate(rl):
        with cc[i % 4]:
            cl[r["name"]] = st.selectbox(f"{r['name']} — max security level", accounts.CLEARANCE, index=accounts.CLEARANCE.index(r["clearance"]) if r["clearance"] in accounts.CLEARANCE else 1, key=f"cl_{r['name']}", disabled=not admin)
    if admin and st.button("💾 Save role changes", type="primary"):
        inv = {f"{accounts.MODULES[m][1]} {m}": m for m in accounts.ALL}
        lab = {v: k for k, v in accounts.PERM_LABEL.items()}
        problems = []
        for r in rl:
            perms = [lab[c] for c in pe.columns if bool(pe.loc[r["name"], c])]
            mods = [inv[c] for c in me_.columns if bool(me_.loc[r["name"], c])]
            if r["name"] == "Administrator":
                perms, mods = accounts.PERMS, list(set(mods) | {"home", "14", "15"})
            if "home" not in mods:
                mods.append("home")
            if (perms, sorted(mods), cl[r["name"]]) != (r["perms"], sorted(r["modules"]), r["clearance"]):
                accounts.save_role(me, r["name"], r["description"], r["color"], perms, [m for m in accounts.ALL if m in mods], cl[r["name"]])
        st.success("Roles saved. Users signed in with an affected role see the new menu on their next page load.")
        st.rerun()
    if not admin:
        st.info("Read-only: only administrators can change roles.")

with t2:
    if not admin:
        st.info("Only administrators can create roles.")
    else:
        with st.form("new_role"):
            a, b = st.columns(2)
            with a:
                nm = st.text_input("Role name *")
                ds = st.text_input("Description")
                col = st.color_picker("Colour", "#2E8B8B")
            with b:
                base = st.selectbox("Start from", [r["name"] for r in rl], index=1)
                clr = st.selectbox("Max security level", accounts.CLEARANCE, index=1)
            if st.form_submit_button("Create role", type="primary"):
                b_ = next(r for r in rl if r["name"] == base)
                if not nm.strip() or any(r["name"].lower() == nm.strip().lower() for r in rl):
                    st.error("Give the role a unique name.")
                else:
                    perms = [p for p in b_["perms"] if p != "admin"]
                    accounts.save_role(me, nm.strip(), ds, col, perms, [m for m in b_["modules"] if m not in ("14", "15")], clr)
                    st.success("Role created — adjust its permissions in the matrix tab, then assign it in User Management.")
                    st.rerun()
        d1, d2 = st.columns([3, 1])
        with d1:
            dr = st.selectbox("Delete a role (only if unused and not built-in)", [r["name"] for r in rl], key="delrole")
        with d2:
            st.write("")
            if st.button("🗑 Delete role"):
                ok, msg = accounts.delete_role(me, dr)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

with t3:
    rows = []
    for u in us:
        r = next((x for x in rl if x["name"] == u["role"]), None)
        rows.append({"User": u["username"], "Role": u["role"], "Department": u["dept"], "Max security level": r["clearance"] if r else "—",
                     "Modules": " ".join(accounts.MODULES[m][1] for m in (r["modules"] if r else []) if m in accounts.MODULES),
                     "Actions": "Full control" if r and "admin" in r["perms"] else ", ".join(accounts.PERM_LABEL[p] for p in (r["perms"] if r else []))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
