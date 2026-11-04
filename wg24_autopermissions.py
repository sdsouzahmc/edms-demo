import pandas as pd
import streamlit as st
import access
import db
import db_ext
import rfp_data
import theme

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("24 · Access Automation", "Permissions are applied automatically the moment a document is uploaded, scanned, created or received")

user = theme.current_user()
prof = theme.current_profile()
admin = theme.is_admin()
st.markdown(f"{theme.tag_custom('Rule-based document permissions — applied on upload · scan · e-mail · import · secure upload · manual creation')}", unsafe_allow_html=True)

S = access.stats()
m = st.columns(5)
theme.metric_card("Documents", S["docs"], m[0])
theme.metric_card("Permissions set by rules", S["auto"], m[1])
theme.metric_card("Restricted visibility", S["restricted"], m[2])
theme.metric_card("Active rules", S["rules"], m[3])
theme.metric_card("Manual grants", S["manual"], m[4])
st.write("")

DEPTS = rfp_data.DEPARTMENTS
TYPES = rfp_data.DOC_TYPES
ROLE_NAMES = sorted({p["role"] for p in rfp_data.ROLES.values()})
ACC_ICON = {"View": "👁️ View", "Edit": "✏️ Edit", "Approve": "✅ Approve", "Manage": "🛡️ Manage"}


def summarize(cond):
    bits = []
    for k, lab in (("doc_types", "type"), ("departments", "dept"), ("classifications", "class"), ("security_levels", "level"),
                   ("sources", "source"), ("languages", "language"), ("keywords", "words")):
        if cond.get(k):
            bits.append(f"{lab}: {', '.join(cond[k])}")
    if cond.get("doc_types") and cond.get("keywords"):
        bits = [b for b in bits if not b.startswith(("type", "words"))] + [f"type: {', '.join(cond['doc_types'])} <b>or</b> words: {', '.join(cond['keywords'])}"]
    return " · ".join(bits) or "every document"


def grants_text(act):
    gs = act.get("grants", [])
    return " · ".join(f"{g['name'] if g['type'] != 'all' else 'Everyone'} ({g['access']})" for g in gs) or "—"


t1, t2, t3, t4, t5 = st.tabs(["📜 Rules", "🧪 Try it — live preview", "📄 Document permissions", "🕘 Applied automatically", "ℹ️ How it works"])

# ================================================================= RULES
with t1:
    if not admin:
        st.info("Everyone can read the rules; only an Administrator can change them.")
    rs = access.rules()
    for r in rs:
        act = r["act"]
        mode = "🔒 Restricted — only the people listed" if act.get("mode") == "restricted" else "Standard visibility + grants"
        c1, c2 = st.columns([5, 1.3])
        c1.markdown(f"""<div class="efs-card" style="border-left:5px solid {'#2E7D32' if r['enabled'] else '#9CA3AF'};{'' if r['enabled'] else 'opacity:.6'}">
        <b>{r['name']}</b> <span style="color:#6B7280;font-size:.78rem">· priority {r['priority']} · applied {r['hits']}×</span><br>
        <span style="font-size:.84rem"><b>When:</b> {summarize(r['cond'])}</span><br>
        <span style="font-size:.84rem"><b>Then:</b> security → <b>{act.get('security') or 'unchanged'}</b> · {mode}{' · 🔔 notify grantees' if act.get('notify') else ''}</span><br>
        <span style="font-size:.84rem"><b>Access:</b> {grants_text(act)}</span></div>""", unsafe_allow_html=True)
        if admin:
            with c2:
                st.toggle("Active", value=bool(r["enabled"]), key=f"ap_on_{r['id']}", on_change=lambda rid=r["id"]: access.set_enabled(rid, st.session_state[f"ap_on_{rid}"], user))
                if st.button("✏️ Edit", key=f"ap_ed_{r['id']}", use_container_width=True):
                    st.session_state["ap_edit"] = r["id"]
                    st.rerun()
    if admin:
        st.write("")
        a1, a2 = st.columns([1, 1])
        if a1.button("➕ New rule", key="ap_new", use_container_width=True):
            st.session_state["ap_edit"] = 0
            st.rerun()
        if a2.button("♻️ Re-apply all rules to existing documents", key="ap_reapply", use_container_width=True,
                     help="Replaces automatic permissions on every document. Manual grants are kept."):
            n = access.reapply_all(user)
            st.success(f"Rules re-applied to {n} documents.")
        if "ap_edit" in st.session_state:
            rid = st.session_state["ap_edit"]
            cur = next((x for x in rs if x["id"] == rid), None) if rid else None
            cond, act = (cur["cond"], cur["act"]) if cur else ({}, {"mode": "standard", "grants": []})
            st.markdown(f'<div class="efs-section-title">{"Edit rule" if cur else "New rule"}</div>', unsafe_allow_html=True)
            with st.form("ap_form"):
                name = st.text_input("Rule name", value=cur["name"] if cur else "")
                p1, p2 = st.columns(2)
                prio = p1.number_input("Priority (lower runs first)", 1, 999, int(cur["priority"]) if cur else 100)
                enabled = p2.checkbox("Active", value=bool(cur["enabled"]) if cur else True)
                st.markdown("**When a document…**  (leave a box empty = any)")
                c1, c2, c3 = st.columns(3)
                f_types = c1.multiselect("…is of type", TYPES, default=[x for x in cond.get("doc_types", []) if x in TYPES])
                f_depts = c2.multiselect("…belongs to department", DEPTS, default=[x for x in cond.get("departments", []) if x in DEPTS])
                f_cls = c3.multiselect("…is classified", db.CLASSIFICATIONS, default=cond.get("classifications", []))
                c4, c5, c6 = st.columns(3)
                f_src = c4.multiselect("…arrived by", ["Upload", "Scan", "Email", "Postal"], default=cond.get("sources", []))
                f_lang = c5.multiselect("…is in language", ["English", "Arabic"], default=cond.get("languages", []))
                f_kw = c6.text_input("…mentions any of these words (comma-separated)", value=", ".join(cond.get("keywords", [])),
                                     help="Looked up in the title and the full text (including OCR). If you also pick types, either the type or the words may match.")
                st.markdown("**…then automatically**")
                d1, d2, d3 = st.columns(3)
                sec_opts = ["(leave unchanged)"] + db.SECURITY_LEVELS
                f_sec = d1.selectbox("Raise security level to", sec_opts, index=sec_opts.index(act["security"]) if act.get("security") in sec_opts else 0,
                                     help="Levels are only ever raised, never lowered.")
                f_mode = d2.radio("Visibility", ["Standard", "Restricted"], index=1 if act.get("mode") == "restricted" else 0,
                                  help="Restricted: invisible to everyone not listed below (administrators always see it).")
                f_notify = d3.checkbox("Notify the people who gain access", value=bool(act.get("notify")))
                cur_g = act.get("grants", [])
                gl = lambda lv: [g["name"] for g in cur_g if g["type"] == "dept" and g["access"] == lv and g["name"] in DEPTS]
                g1, g2 = st.columns(2)
                g_view = g1.multiselect("👁️ View — departments", DEPTS, default=gl("View"))
                g_edit = g2.multiselect("✏️ Edit — departments", DEPTS, default=gl("Edit"))
                g3, g4 = st.columns(2)
                g_appr = g3.multiselect("✅ Approve — departments", DEPTS, default=gl("Approve"))
                g_mng = g4.multiselect("🛡️ Manage — departments", DEPTS, default=gl("Manage"))
                g5, g6 = st.columns(2)
                g_role = g5.multiselect("View — also these roles", ROLE_NAMES, default=[g["name"] for g in cur_g if g["type"] == "role"])
                g_all = g6.checkbox("Everyone can view", value=any(g["type"] == "all" for g in cur_g))
                exp = st.number_input("Grants expire after (days) — 0 = never", 0, 3650, int(max([g.get("expires_days", 0) for g in cur_g] or [0])))
                s1, s2, s3 = st.columns([1, 1, 3])
                save = s1.form_submit_button("💾 Save", type="primary")
                cancel = s2.form_submit_button("Cancel")
            if cancel:
                st.session_state.pop("ap_edit", None)
                st.rerun()
            if save:
                if not name.strip():
                    st.error("Give the rule a name.")
                else:
                    grants = []
                    for lv, lst in (("View", g_view), ("Edit", g_edit), ("Approve", g_appr), ("Manage", g_mng)):
                        grants += [{"type": "dept", "name": d_, "access": lv, **({"expires_days": int(exp)} if exp else {})} for d_ in lst]
                    grants += [{"type": "role", "name": r_, "access": "View", **({"expires_days": int(exp)} if exp else {})} for r_ in g_role]
                    if g_all:
                        grants.append({"type": "all", "name": access.EVERYONE, "access": "View"})
                    cond_new = {k: v for k, v in {"doc_types": f_types, "departments": f_depts, "classifications": f_cls, "sources": f_src, "languages": f_lang,
                                                  "keywords": [x.strip() for x in f_kw.split(",") if x.strip()]}.items() if v}
                    act_new = {"security": None if f_sec.startswith("(") else f_sec, "mode": f_mode.lower(), "notify": f_notify, "grants": grants}
                    access.save_rule(rid or None, name.strip(), int(prio), cond_new, act_new, enabled, user)
                    st.session_state.pop("ap_edit", None)
                    st.success("Rule saved. It applies to every document registered from now on; use “Re-apply” for existing ones.")
                    st.rerun()
            if cur and st.button("🗑 Delete this rule", key="ap_del"):
                access.delete_rule(rid, user)
                st.session_state.pop("ap_edit", None)
                st.rerun()

# ================================================================= PREVIEW
with t2:
    st.caption("Describe a document and see — before anything is uploaded — which rules fire and who ends up able to see it.")
    c1, c2, c3 = st.columns(3)
    p_title = c1.text_input("Title / first line", value="Supplier invoice INV-2026-0912 — infusion pumps", key="pv_title")
    p_dept = c2.selectbox("Department it is filed under", DEPTS, index=DEPTS.index("Finance"), key="pv_dept")
    p_type = c3.selectbox("Document type", TYPES, index=TYPES.index("Invoice"), key="pv_type")
    c4, c5, c6 = st.columns(3)
    p_cls = c4.selectbox("Classification", db.CLASSIFICATIONS, index=1, key="pv_cls")
    p_src = c5.selectbox("Arrives by", ["Upload", "Scan", "Email", "Postal"], key="pv_src")
    p_body = c6.text_input("Words in the text (optional)", key="pv_body")
    res = access.evaluate({"title": p_title, "department": p_dept, "doc_type": p_type, "classification": p_cls, "source": p_src,
                           "body_text": p_body, "security_level": "Internal", "language": "English"})
    k1, k2, k3 = st.columns(3)
    theme.metric_card("Rules that fire", len(res["matched"]), k1)
    theme.metric_card("Security level", res["security"], k2)
    theme.metric_card("Visibility", "Restricted" if res["restricted"] else "Standard", k3)
    if res["matched"]:
        st.markdown("**Rules that fire (in order):** " + " → ".join(f"{r['name'].split(' — ')[0]}" for r in res["matched"]))
    else:
        st.info("No rule matches — only the baseline applies (the owning department).")
    rows = []
    for u, pf in rfp_data.ROLES.items():
        lvl = None
        for g in res["grants"]:
            if g["type"] == "all" or (g["type"] == "dept" and g["name"] == pf["dept"]) or (g["type"] == "role" and g["name"] == pf["role"]):
                if lvl is None or access.RANK[g["access"]] > access.RANK[lvl]:
                    lvl = g["access"]
        adm = pf["level"] == "admin"
        sees = adm or lvl is not None or (not res["restricted"] and pf["dept"] == p_dept)
        rows.append({"Person": u, "Role": pf["role"], "Department": pf["dept"], "Can open?": "✅ yes" if sees else "🚫 no",
                     "Access": "Manage (administrator)" if adm else (lvl or ("Edit (own dept)" if sees else "—"))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with st.expander("Grants that would be written"):
        st.dataframe(pd.DataFrame([{"Who": (g["name"] if g["type"] != "all" else "Everyone"), "Kind": g["type"], "Access": g["access"], "Why": g["source"]} for g in res["grants"]]),
                     use_container_width=True, hide_index=True)

# ================================================================= PER-DOCUMENT
with t3:
    docs = [d for d in db.get_documents() if access.visible(d, user, prof["dept"], prof["role"], admin, db_ext.shared_with(prof["dept"]))]
    if not docs:
        st.info("No documents available.")
    else:
        lab = {d["id"]: f"{d['doc_code']} — {d['title'][:70]}" for d in docs}
        did = st.selectbox("Document", list(lab), format_func=lambda i: lab[i], key="ap_doc")
        d = db.get_document(did)
        lvl = access.level(d, user, prof["dept"], prof["role"], admin)
        c1, c2, c3 = st.columns(3)
        theme.metric_card("Security level", d["security_level"], c1)
        theme.metric_card("Visibility", "Restricted" if d["access_mode"] == "restricted" else "Standard", c2)
        theme.metric_card("Your access", lvl or "Own department", c3)
        perms = access.permissions(did)
        if perms:
            for p in perms:
                a1, a2, a3 = st.columns([4, 3, 1])
                who = "Everyone" if p["ptype"] == "all" else f"{p['principal']} ({p['ptype']})"
                a1.markdown(f"**{who}** — {ACC_ICON[p['access']]}" + (f" · until {p['expires_at']}" if p["expires_at"] else ""))
                a2.caption(p["source"])
                if (admin or lvl == "Manage") and p["source"] == "manual":
                    a3.button("Revoke", key=f"ap_rv_{p['id']}", on_click=access.revoke, args=(p["id"], user))
        else:
            st.caption("No explicit permissions recorded.")
        if admin or lvl == "Manage":
            st.markdown('<div class="efs-section-title">Add a manual grant</div>', unsafe_allow_html=True)
            with st.form("ap_manual", clear_on_submit=True):
                g1, g2, g3, g4 = st.columns(4)
                kind = g1.selectbox("Grant to", ["Department", "Role", "Person"])
                target = g2.selectbox("Who", DEPTS + ROLE_NAMES + list(rfp_data.ROLES))
                lvl_new = g3.selectbox("Access", access.LEVELS)
                days = g4.number_input("Expires in days (0 = never)", 0, 3650, 0)
                if st.form_submit_button("➕ Grant access"):
                    access.grant(did, {"Department": "dept", "Role": "role", "Person": "user"}[kind], target, lvl_new, user, days or None)
                    st.rerun()
            if st.button("♻️ Re-apply the rules to this document", key="ap_one"):
                access.apply(did, "Re-applied", user)
                st.rerun()

# ================================================================= LOG
with t4:
    rows = access.recent_applications()
    st.caption("Every automatic decision is written to the immutable audit trail.")
    if rows:
        st.dataframe(pd.DataFrame([{"When": r["ts"][:16], "Document": r["doc_code"], "Title": r["title"][:50], "Arrived by": r["source"],
                                    "Security": r["security_level"], "Visibility": r["access_mode"], "What happened": r["detail"]} for r in rows]),
                     use_container_width=True, hide_index=True)
    else:
        st.info("Nothing has been applied yet.")

# ================================================================= HOW
with t5:
    st.markdown("""
**When it runs** — automatically, for every new document, whichever way it arrives: uploaded, scanned/OCR'd, e-mailed, received through a secure upload link,
imported by the migration wizard, or created by hand.

**What it does, in order**
1. Reads the document's type, department, classification, language, source, title and full text.
2. Runs every *active* rule, lowest priority number first. All matching rules combine: the **highest** access per person wins and the security level can only go **up**.
3. Applies the folder's inherited restrictions.
4. Always keeps the owning department's access and the creator's access.
5. Writes the permissions, sets **Standard** or **Restricted** visibility, optionally notifies the people who gained access, and records it in the audit trail.

**Access levels** — 👁️ View → ✏️ Edit → ✅ Approve → 🛡️ Manage. Grants can be time-limited. Administrators can always see everything.

**Restricted visibility** hides the document from Search, Ask EDMS and the security views for everyone who is not listed — even once it is Released.

**Manual changes** — owners with *Manage* access and administrators can add or revoke individual grants; re-applying the rules never removes a manual grant.
""")
