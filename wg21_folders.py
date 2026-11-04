import pandas as pd
import streamlit as st
import db
import db_ext
import folders as fo
import theme

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("21 · Folders & Classification", "Unlimited nested folders · per-folder access with inheritance · move & file documents")

user = theme.current_user()
dept = theme.current_profile()["dept"]
admin = theme.is_admin()
st.markdown(f"{theme.tag_custom('Folder hierarchy — unlimited depth, access inherited down the tree')}", unsafe_allow_html=True)

by, kids = fo.index()
cnt = fo.counts()
order = fo.ordered(by, kids)
total_in = {fid: cnt.get(fid, 0) + sum(cnt.get(x, 0) for x in fo.descendants(fid, kids)) for fid in by}
restricted_n = len([f for f in by.values() if f["restricted"]])
depth = max((len(fo.path_ids(i, by)) for i in by), default=0)
m1, m2, m3, m4 = st.columns(4)
theme.metric_card("Folders", len(by), m1)
theme.metric_card("Documents filed", sum(cnt.values()), m2)
theme.metric_card("Restricted folders", restricted_n, m3)
theme.metric_card("Deepest level", depth, m4)
st.write("")

ids = [i for i, _ in order]
if "fo_next" in st.session_state:
    st.session_state["fo_sel"] = st.session_state.pop("fo_next")
depth_of = dict(order)
if "fo_sel" not in st.session_state or st.session_state["fo_sel"] not in by:
    mine = next((i for i in ids if by[i]["parent_id"] is None and by[i]["name"] == dept), ids[0])
    st.session_state["fo_sel"] = mine


def _goto(fid):
    st.session_state["fo_sel"] = fid


def _label(i):
    lock = "🔒 " if by[i]["restricted"] else ""
    return " " * depth_of[i] + ("📁 " if depth_of[i] == 0 else "└ ") + lock + by[i]["name"] + f"  ({total_in[i]})"


left, right = st.columns([1.1, 2.2])
with left:
    st.markdown('<div class="efs-section-title">Folder tree</div>', unsafe_allow_html=True)
    q = st.text_input("Find folder", key="fo_find", placeholder="type part of a folder name…", label_visibility="collapsed")
    show = [i for i in ids if not q or q.lower() in fo.path(i, by).lower()]
    if show:
        if st.session_state["fo_sel"] not in show:
            st.session_state["fo_sel"] = show[0]
        st.selectbox("Folder", show, format_func=_label, key="fo_sel", label_visibility="collapsed")
    else:
        st.info("No folder matches.")
    sel = st.session_state["fo_sel"]
    st.caption("Tip: the number in brackets counts documents in the folder and everything below it.")
    # compact visual tree of the current department
    top = fo.path_ids(sel, by)[0]
    rows = []

    def walk(pid, d):
        for k in sorted(kids.get(pid, []), key=lambda i: by[i]["name"]):
            cur = " style='background:#E8F3F3;border-radius:6px;font-weight:700'" if k == sel else ""
            lock = "🔒" if by[k]["restricted"] else ""
            rows.append(f"<div{cur}><span style='margin-inline-start:{d * 16}px'>{'📂' if k == sel else '📁'} {by[k]['name']} {lock}"
                        f"<span style='color:#6B7280;font-size:.75rem'> ({total_in[k]})</span></span></div>")
            walk(k, d + 1)
    rows.append(f"<div><b>🗄️ {by[top]['name']}</b> <span style='color:#6B7280;font-size:.75rem'>({total_in[top]})</span></div>")
    walk(top, 1)
    st.markdown("<div class='efs-card' style='padding:10px 14px;line-height:1.7'>" + "".join(rows) + "</div>", unsafe_allow_html=True)

with right:
    sel = st.session_state["fo_sel"]
    f = by[sel]
    allowed, defined_in = fo.restriction(sel, by)
    ok = fo.can_access(sel, dept, admin, by)
    can_manage = admin or fo.root_dept(sel, by) == dept
    crumbs = " › ".join(f"<b>{by[i]['name']}</b>" if i == sel else by[i]["name"] for i in fo.path_ids(sel, by))
    st.markdown(f"<div class='efs-card'>📍 {crumbs}<br><span style='color:#6B7280;font-size:.82rem'>"
                f"{total_in[sel]} document(s) in total · {len(kids.get(sel, []))} sub-folder(s) · "
                + (f"🔒 access limited to <b>{', '.join(allowed)}</b>" + ("" if defined_in == sel else f" (inherited from {by[defined_in]['name']})")
                   if allowed else "🔓 open to everyone with module access") + "</span></div>", unsafe_allow_html=True)
    if not ok:
        st.error(f"🔒 Your department ({dept}) is not allowed to open this folder. Ask the owning department or an Administrator.")
        db.log_audit(None, user, "Folder Access Denied", fo.path(sel, by), "Denied") if st.session_state.get("fo_denied") != sel else None
        st.session_state["fo_denied"] = sel
        st.stop()

    t1, t2, t3, t4 = st.tabs(["📄 Contents", "➕ Manage folder", "🔐 Access", "📥 File documents here"])

    with t1:
        subs = sorted(kids.get(sel, []), key=lambda i: by[i]["name"])
        if subs:
            st.markdown("**Sub-folders**")
            cols = st.columns(3)
            for n, k in enumerate(subs):
                cols[n % 3].button(f"{'🔒 ' if by[k]['restricted'] else '📁 '}{by[k]['name']} ({total_in[k]})", key=f"sub_{k}",
                                   on_click=_goto, args=(k,), use_container_width=True)
        rec = st.checkbox("Include documents from all sub-folders", key="fo_rec")
        fids = [sel] + (fo.descendants(sel, kids) if rec else [])
        docs = fo.docs_in([i for i in fids if fo.can_access(i, dept, admin, by)])
        if not docs:
            st.info("No documents in this folder.")
        else:
            st.dataframe(pd.DataFrame([{"Document": d["doc_code"], "Title": d["title"], "Type": d["doc_type"], "Status": d["status"],
                                        "Classification": d["classification"], "Folder": fo.path(d["folder_id"], by) if rec else ""} for d in docs]
                                      ).drop(columns=[] if rec else ["Folder"]), use_container_width=True, hide_index=True)

    with t2:
        if not can_manage:
            st.info("Only the owning department or an Administrator can change this folder structure.")
        c1, c2 = st.columns([3, 1])
        nn = c1.text_input("New sub-folder name", key="fo_new", disabled=not can_manage, placeholder="e.g. 2026 Audits")
        if c2.button("➕ Create", key="fo_new_go", disabled=not can_manage or not nn.strip()):
            nid, err = fo.create(sel, nn, user)
            if err:
                st.error(err)
            else:
                st.session_state["fo_next"] = nid
                st.rerun()
        r1, r2 = st.columns([3, 1])
        rn = r1.text_input("Rename this folder", value=f["name"], key=f"fo_ren_{sel}", disabled=not can_manage)
        if r2.button("✏ Rename", key="fo_ren_go", disabled=not can_manage or not rn.strip() or rn.strip() == f["name"]):
            fo.rename(sel, rn, user)
            st.rerun()
        bad = {sel, *fo.descendants(sel, kids)}
        dest_opts = [None] + [i for i in ids if i not in bad]
        m1_, m2_ = st.columns([3, 1])
        dest = m1_.selectbox("Move this folder under…", dest_opts, key=f"fo_mv_{sel}", disabled=not can_manage,
                             format_func=lambda i: "(top level)" if i is None else fo.path(i, by))
        if m2_.button("↦ Move", key="fo_mv_go", disabled=not can_manage):
            err = fo.move_folder(sel, dest, user)
            st.error(err) if err else st.rerun()
        if st.button("🗑 Delete this folder (must be empty)", key="fo_del", disabled=not can_manage):
            err = fo.delete(sel, user)
            if err:
                st.error(err)
            else:
                st.session_state["fo_next"] = f["parent_id"] or ids[0]
                st.rerun()

    with t3:
        st.markdown(f"**Effective access:** " + (f"limited to {', '.join(allowed)}" if allowed else "open to all departments"))
        st.caption("A restriction applies to this folder and everything below it, unless a sub-folder sets its own.")
        inherit = st.checkbox("Inherit access from the parent folder", value=not f["restricted"], key=f"fo_inh_{sel}", disabled=not can_manage)
        import rfp_data
        pick = st.multiselect("Departments allowed", rfp_data.DEPARTMENTS, default=f["restricted"] or [], key=f"fo_acc_{sel}",
                              disabled=inherit or not can_manage)
        if st.button("💾 Save access", key="fo_acc_go", disabled=not can_manage or (not inherit and not pick)):
            fo.set_restriction(sel, None if inherit else pick, user)
            st.success("Saved.")
            st.rerun()

    with t4:
        st.caption("Select documents from anywhere and file them into this folder (the document itself is never copied).")
        pool = [d for d in db.get_documents() if d["folder_id"] != sel]
        qd = st.text_input("Search documents", key="fo_dq", placeholder="code or title…")
        pool = [d for d in pool if not qd or qd.lower() in (d["doc_code"] + d["title"]).lower()][:60]
        pick_d = st.multiselect("Documents", [d["id"] for d in pool], key=f"fo_pick_{st.session_state.get('fo_pk', 0)}",
                                format_func=lambda i: next(f"{d['doc_code']} — {d['title']}" for d in pool if d["id"] == i))
        if st.button(f"📥 File {len(pick_d)} document(s) here", key="fo_file_go", disabled=not pick_d):
            fo.move_docs(pick_d, sel, user)
            st.session_state["fo_pk"] = st.session_state.get("fo_pk", 0) + 1
            st.success("Filed.")
            st.rerun()
