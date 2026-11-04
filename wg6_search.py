import io
import zipfile
import streamlit as st
import pandas as pd
import db
import db_ext
import distribution as dist
import rfp_data
import search_engine as se
import access
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("6 · Search & Information Retrieval Workgroup",
             "Full-text index over documents and OCR'd scans · ranked · Boolean · phrase · wildcard · typo-tolerant · security-trimmed")

profile = theme.current_profile()
user = theme.current_user()
is_admin = theme.is_admin()
shared_ids = db_ext.shared_with(profile["dept"])
idx = se.ensure_index()


def allowed(d):
    return access.visible(d, user, profile["dept"], profile["role"], is_admin, shared_ids)


tabs = st.tabs(["🔎 Search", "🌳 Browse Classification Tree", "🕘 History & Saved Searches"])

with tabs[0]:
    if st.session_state.get("global_q") is not None:          # arrived from the sidebar quick-search
        st.session_state["s_query"] = st.session_state.pop("global_q")
    st.caption(f"Index: **{idx['docs']}** documents · **{idx['terms']}** distinct terms · **{idx['ocr_docs']}** OCR-scanned documents "
               f"· auto-updated whenever a document is captured, versioned or archived.")
    TEMPLATES = {"(none)": "", "Contracts & agreements": 'contract OR agreement OR sla',
                 "Regulatory correspondence": "moph OR ministry OR regulatory NOT circular",
                 "Finance approvals": "invoice OR payment OR purchase",
                 "Patient-related (clinical)": "patient AND (admission OR discharge OR referral)",
                 "Accreditation evidence": "carf OR iso OR accreditation",
                 "Text found by OCR (scans)": "amount OR payment OR contract OR fire"}
    t1, t2 = st.columns([3, 1])
    with t2:
        tpl = st.selectbox("Search template", list(TEMPLATES.keys()))
        if tpl != "(none)" and st.session_state.get("last_tpl") != tpl:
            st.session_state["s_query"] = TEMPLATES[tpl]
            st.session_state["last_tpl"] = tpl
    with t1:
        query = st.text_input("Query", key="s_query",
                              placeholder='invoice AND qar   ·   "fire safety"   ·   maint*   ·   contr?ct   ·   patient (admission OR discharge)   ·   فاتورة',
                              help="Type words, \"exact phrases\", AND / OR / NOT, wildcards (* ?) and brackets. Misspellings are corrected automatically.")
    m1, m2, m3 = st.columns([2, 1.3, 1.3])
    with m1:
        mode = st.radio("Mode", ["Smart (Boolean · phrase · wildcard)", "Natural language"], horizontal=True)
    with m2:
        ocr_only = st.checkbox("📠 Scanned / OCR documents only", value=False)
    with m3:
        sort = st.selectbox("Sort", ["Relevance", "Newest", "Title", "Department"], label_visibility="collapsed")
    with st.expander("Advanced filters"):
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            class_filter = st.selectbox("Classification", ["All"] + db.CLASSIFICATIONS)
        with g2:
            date_from = st.date_input("Created from", value=None)
        with g3:
            date_to = st.date_input("Created to", value=None)
        with g4:
            min_ver = st.number_input("Version ≥", 0.0, 99.0, 0.0, step=0.1)

    info = se.search(query, "nl" if mode.startswith("Natural") else "smart", allow=allowed,
                     filters={"classification": class_filter})
    res = info["results"]
    if ocr_only:
        res = [o for o in res if o["doc"]["source"] == "Scan"]
    if date_from:
        res = [o for o in res if (o["doc"]["created_at"] or "")[:10] >= date_from.isoformat()]
    if date_to:
        res = [o for o in res if (o["doc"]["created_at"] or "")[:10] <= date_to.isoformat()]
    if min_ver > 0:
        def _v(o):
            try:
                return float(o["doc"]["current_version"])
            except Exception:
                return 0.0
        res = [o for o in res if _v(o) >= min_ver]

    if info["error"]:
        st.error(info["error"])
    if info["corrected"]:
        st.info(f"No results for **{query}** — showing results for **{info['corrected']}** (typo corrected).")
    if info["expanded"]:
        st.caption("Concepts searched: " + ", ".join(info["expanded"]))
    if query.strip():
        st.caption(f"Index query: `{info['expr']}`")

    fac = se.facets(res)
    fl, fr = st.columns([1, 3])
    with fl:
        st.markdown("**Refine results**")
        chosen = {}
        for name, vals in fac.items():
            if len(vals) > 1 or name in ("Source",):
                opts = [f"{k} ({v})" for k, v in vals.items()]
                sel = st.multiselect(name, opts, key=f"fac_{name}")
                chosen[name] = [o.rsplit(" (", 1)[0] for o in sel]

    def keep(o):
        d = o["doc"]
        vals = {"Department": d["department"], "Document type": d["doc_type"], "Status": d["status"],
                "Source": se.source_label(d["source"]), "Language": d["language"]}
        return all(not c or vals[k] in c for k, c in chosen.items())

    res = [o for o in res if keep(o)]
    if sort == "Newest":
        res = sorted(res, key=lambda o: o["doc"]["created_at"], reverse=True)
    elif sort == "Title":
        res = sorted(res, key=lambda o: o["doc"]["title"].lower())
    elif sort == "Department":
        res = sorted(res, key=lambda o: o["doc"]["department"])

    with fr:
        st.markdown(f"**{len(res)}** result(s)" + ("" if is_admin else " — security-trimmed to your access level"))
        if query.strip() and st.session_state.get("last_logged") != (user, query, len(res)):
            db_ext.log_search(user, query, len(res))
            st.session_state["last_logged"] = (user, query, len(res))
        a1, a2, a3 = st.columns([1, 1, 2])
        with a1:
            if res:
                df = pd.DataFrame([{"Code": o["doc"]["doc_code"], "Title": o["doc"]["title"], "Department": o["doc"]["department"],
                                    "Type": o["doc"]["doc_type"], "Status": o["doc"]["status"], "Source": se.source_label(o["doc"]["source"]),
                                    "Relevance": round(o["rel"], 2), "Created": o["doc"]["created_at"]} for o in res])
                st.download_button("⬇ Export results (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "search_results.csv")
        with a2:
            if res:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as z:
                    for o in res[:50]:
                        d = o["doc"]
                        z.writestr(f"{d['doc_code'].replace('/', '-')}.txt", f"{d['title']}\n{d['department']} · v{d['current_version']}\n\n{d['body_text'] or ''}")
                st.download_button("🗜 Download results (ZIP)", buf.getvalue(), "search_results.zip")
        with a3:
            save_name = st.text_input("Save query as…", placeholder="e.g. My open Finance approvals", label_visibility="collapsed")
            if st.button("💾 Save query") and save_name:
                conn = db.get_conn()
                conn.execute("INSERT INTO saved_searches (user, name, query, dept_filter, class_filter, created_at) VALUES (?,?,?,?,?,?)",
                             (user, save_name, query, "All", class_filter, db.now()))
                conn.commit()
                conn.close()
                st.success("Query saved.")

        bm_ids = {b["id"] for b in db_ext.get_bookmarks(user)}
        for o in res[:40]:
            d = o["doc"]
            routed = [r for r in dist.log_rows(doc_id=d["id"], limit=6) if r["target_dept"] != "Unrouted"]
            route_txt = (" · 📬 routed → " + ", ".join(f"{r['target_dept']}{'' if r['role'] == 'Primary' else ' (cc)'}" for r in routed[:4])) if routed else ""
            where = " · ".join(x for x, f in (("title", o["in_title"]), ("content", o["in_body"])) if f)
            badge = "📠 OCR scan" if d["source"] == "Scan" else se.source_label(d["source"])
            bar = f'<div style="height:4px;background:#E2E6EC;border-radius:2px;width:90px;display:inline-block;vertical-align:middle"><div style="height:4px;width:{int(o["rel"] * 90)}px;background:#2E8B8B;border-radius:2px"></div></div>' if query.strip() else ""
            st.markdown(f"""
            <div class="efs-card">
            <b>{o['code_html']} — {o['title_html']}</b> &nbsp; {theme.pill(d['status'])} &nbsp; <span style="font-size:0.75rem;background:#eef2f7;padding:1px 7px;border-radius:9px">{badge}</span><br>
            <span style="font-size:0.82rem;color:#6B7280">{d['department']} · {d['doc_type']} · {d['classification']} · {d['language']} · v{d['current_version']}
            · {bar} {'matched in ' + where if where else ''}{route_txt}</span><br>
            <span style="font-size:0.88rem">{o['snippet']}</span>
            </div>""", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("👁 View / Log Access", key=f"view_{d['id']}"):
                    db.log_audit(d["id"], user, "Viewed", "Opened via Search & Retrieval")
                    db_ext.log_view(user, d["id"])
                    st.toast(f"Access logged for {d['doc_code']}")
            with c2:
                if st.button("⬇ Download", key=f"dl_{d['id']}"):
                    db.log_audit(d["id"], user, "Downloaded", "Downloaded via Search & Retrieval")
                    st.toast(f"Download logged for {d['doc_code']}")
            with c3:
                if st.button("⭐ Bookmark" if d["id"] not in bm_ids else "★ Remove bookmark", key=f"bm_{d['id']}"):
                    db_ext.toggle_bookmark(user, d["id"])
                    st.rerun()
        if not res:
            st.info("No matches. Try fewer words, a wildcard (e.g. contr*), Natural-language mode, or clear the refine filters.")

with tabs[1]:
    st.markdown('<div class="efs-section-title">Alternative taxonomy — browse without folders</div>', unsafe_allow_html=True)
    st.caption("Documents are classified against a multi-level classification tree and can be browsed independently of the "
               "folder hierarchy, with no duplication of the underlying document.")
    docs = [d for d in db.get_documents() if allowed(d)]
    by_type = {}
    for d in docs:
        by_type.setdefault(d["doc_type"], []).append(d)
    for l1, l2s in rfp_data.CLASS_TREE.items():
        n1 = sum(len(by_type.get(t, [])) for ts in l2s.values() for t in ts)
        with st.expander(f"📁 {l1}  ({n1})"):
            for l2, types in l2s.items():
                n2 = sum(len(by_type.get(t, [])) for t in types)
                st.markdown(f"**└ {l2}** ({n2})")
                for t in types:
                    for d in by_type.get(t, []):
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ *{t}* — **{d['doc_code']}** {d['title']} ({d['department']})",
                                    unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="efs-section-title">Search history</div>', unsafe_allow_html=True)
    for h in db_ext.get_search_history(user):
        st.markdown(f"🕘 `{h['query']}` — {h['hits']} hit(s) · {h['ts']}")
    if not db_ext.get_search_history(user):
        st.caption("No searches yet.")
    st.markdown('<div class="efs-section-title">Saved searches</div>', unsafe_allow_html=True)
    conn = db.get_conn()
    saved = conn.execute("SELECT * FROM saved_searches WHERE user=? ORDER BY id DESC", (user,)).fetchall()
    conn.close()
    for sv in saved:
        st.markdown(f"⭐ **{sv['name']}** — `{sv['query'] or '(none)'}` · dept: {sv['dept_filter']} · class: {sv['class_filter']}")
    if not saved:
        st.caption("No saved searches.")
