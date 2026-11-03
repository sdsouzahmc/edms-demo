import io
import re
import difflib
import zipfile
import streamlit as st
import pandas as pd
import db
import db_ext
import rfp_data
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("6 · Search & Information Retrieval Workgroup",
             "Full-text · Boolean · wildcard · fuzzy · natural language · classification trees · security-trimmed · e-discovery export")

profile = theme.current_profile()
user = theme.current_user()
is_admin = theme.is_admin()
shared_ids = db_ext.shared_with(profile["dept"])

SYNONYMS = {
    "money": ["invoice", "payment", "budget", "qar", "purchase"], "pay": ["invoice", "payment", "qar"],
    "staff": ["employee", "hr", "nursing", "contract", "leave", "appraisal"], "people": ["employee", "hr", "staff"],
    "safety": ["fire", "inspection", "security", "incident", "hvac"], "building": ["hvac", "floor", "plan", "electrical", "facility"],
    "licence": ["license", "certificate", "moph", "accreditation"], "license": ["licence", "certificate", "moph"],
    "patient": ["medical", "admission", "clinical", "intake", "discharge"], "rules": ["policy", "procedure", "sop"],
    "supplier": ["vendor", "tender", "purchase", "contract"], "accreditation": ["carf", "iso", "audit", "evidence"],
}
STOP = {"the", "a", "an", "of", "for", "to", "and", "about", "in", "on", "is", "are", "what", "which", "that", "with", "any", "me", "find", "show"}


def tokenize(q):
    return re.findall(r'"[^"]+"|\S+', q)


def term_match(term, text, words, fuzzy):
    t = term.lower()
    if t.startswith('"') and t.endswith('"'):
        return t.strip('"') in text
    if "*" in t or "?" in t:
        rx = re.compile("^" + re.escape(t).replace(r"\*", ".*").replace(r"\?", ".") + "$")
        return any(rx.match(w) for w in words)
    if t in text:
        return True
    if fuzzy and len(t) > 3:
        return bool(difflib.get_close_matches(t, words, n=1, cutoff=0.8))
    return False


def boolean_match(q, text, words, fuzzy):
    toks = tokenize(q)
    groups, cur = [], []
    for tk in toks:
        if tk == "OR":
            groups.append(cur)
            cur = []
        else:
            cur.append(tk)
    groups.append(cur)
    for g in groups:
        ok, neg = True, False
        for tk in g:
            if tk == "AND":
                continue
            if tk == "NOT":
                neg = True
                continue
            hit = term_match(tk, text, words, fuzzy)
            if neg:
                ok = ok and not hit
                neg = False
            else:
                ok = ok and hit
        if ok and g:
            return True
    return False


def nl_score(q, text):
    terms = [w for w in re.findall(r"\w+", q.lower()) if w not in STOP]
    expanded = set(terms)
    for t in terms:
        expanded.update(SYNONYMS.get(t, []))
    return sum(1 for e in expanded if e in text)


def haystack(d):
    return " ".join(str(d[k] or "") for k in ("doc_code", "title", "body_text", "doc_type", "department", "sender", "recipient", "classification")).lower()


tabs = st.tabs(["🔎 Search", "🌳 Browse Classification Tree", "🕘 History & Saved Searches"])

with tabs[0]:
    TEMPLATES = {"(none)": "", "Contracts expiring (all depts)": 'contract OR agreement OR sla',
                 "Regulatory correspondence": "moph OR ministry OR regulatory NOT circular",
                 "Finance approvals": "invoice OR payment OR purchase", "Patient-related (clinical)": "patient AND (record OR admission)".replace("(", "").replace(")", ""),
                 "Accreditation evidence": "carf OR iso OR accreditation"}
    tpl = st.selectbox("Search template (editable)", list(TEMPLATES.keys()))
    c1, c2 = st.columns([3, 1])
    with c1:
        query = st.text_input("Query", value=TEMPLATES[tpl],
                              placeholder='e.g.  invoice AND qar   |   moph OR ministry   |   contract NOT expired   |   maint*   |   "fire safety"',
                              help="Supports AND / OR / NOT, wildcards (* ?), quoted phrases, and fuzzy matching.")
    with c2:
        mode = st.radio("Mode", ["Boolean", "Natural language"], horizontal=False)
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        dept_filter = st.selectbox("Department", ["All"] + rfp_data.DEPARTMENTS)
    with f2:
        type_filter = st.selectbox("Document type", ["All"] + rfp_data.DOC_TYPES)
    with f3:
        class_filter = st.selectbox("Classification", ["All"] + db.CLASSIFICATIONS)
    with f4:
        status_filter = st.selectbox("Status", ["All"] + db.WORKFLOW_STAGES + ["Rejected", "Archived"])
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        fuzzy = st.checkbox("Fuzzy / homonyms (Jeri ≈ Jerry)", value=True)
    with g2:
        date_from = st.date_input("Created from", value=None)
    with g3:
        date_to = st.date_input("Created to", value=None)
    with g4:
        min_ver = st.number_input("Version ≥", 0.0, 99.0, 0.0, step=0.1)
    sort = st.selectbox("Sort by", ["Relevance / newest", "Title", "Department", "Created (oldest)"])

    results = db.get_documents(department=dept_filter, status=status_filter if status_filter != "All" else None,
                               classification=class_filter, include_disposed=False)
    if type_filter != "All":
        results = [r for r in results if r["doc_type"] == type_filter]
    # security trimming: only what this user is allowed to find
    if not is_admin:
        results = [r for r in results if r["department"] == profile["dept"] or r["status"] in ("Released", "Archived")
                   or r["id"] in shared_ids]
    if date_from:
        results = [r for r in results if (r["created_at"] or "")[:10] >= date_from.isoformat()]
    if date_to:
        results = [r for r in results if (r["created_at"] or "")[:10] <= date_to.isoformat()]
    if min_ver > 0:
        def _v(r):
            try:
                return float(r["current_version"])
            except Exception:
                return 0.0
        results = [r for r in results if _v(r) >= min_ver]
    scored = []
    if query.strip():
        for r in results:
            hs = haystack(r)
            words = set(re.findall(r"\w+", hs))
            if mode == "Boolean":
                if boolean_match(query, hs, words, fuzzy):
                    scored.append((1, r))
            else:
                sc = nl_score(query, hs)
                if sc:
                    scored.append((sc, r))
        if mode != "Boolean":
            scored.sort(key=lambda x: -x[0])
        results = [r for _, r in scored]
    if sort == "Title":
        results = sorted(results, key=lambda r: r["title"].lower())
    elif sort == "Department":
        results = sorted(results, key=lambda r: r["department"])
    elif sort == "Created (oldest)":
        results = sorted(results, key=lambda r: r["created_at"])

    st.markdown(f"**{len(results)}** result(s)" + ("" if is_admin else " — security-trimmed to your access level"))
    if query.strip() and st.session_state.get("last_logged") != (user, query, len(results)):
        db_ext.log_search(user, query, len(results))
        st.session_state["last_logged"] = (user, query, len(results))

    a1, a2, a3 = st.columns([1, 1, 2])
    with a1:
        if results:
            df = pd.DataFrame([{"Code": r["doc_code"], "Title": r["title"], "Department": r["department"], "Type": r["doc_type"],
                                "Status": r["status"], "Classification": r["classification"], "Version": r["current_version"],
                                "Created": r["created_at"]} for r in results])
            st.download_button("⬇ Export results (CSV, e-discovery)", df.to_csv(index=False).encode("utf-8-sig"),
                               "search_results.csv")
    with a2:
        if results:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for r in results[:50]:
                    z.writestr(f"{r['doc_code']}.txt", f"{r['title']}\n{r['department']} · v{r['current_version']}\n\n{r['body_text'] or ''}")
            st.download_button("🗜 Download results (ZIP)", buf.getvalue(), "search_results.zip")
    with a3:
        save_name = st.text_input("Save query as…", placeholder="e.g. My open Finance approvals", label_visibility="collapsed")
        if st.button("💾 Save query") and save_name:
            conn = db.get_conn()
            conn.execute("INSERT INTO saved_searches (user, name, query, dept_filter, class_filter, created_at) VALUES (?,?,?,?,?,?)",
                         (user, save_name, query, dept_filter, class_filter, db.now()))
            conn.commit()
            conn.close()
            st.success("Query saved.")

    for r in results[:40]:
        snippet = (r["body_text"] or "")[:170]
        bm = r["id"] in {b["id"] for b in db_ext.get_bookmarks(user)}
        st.markdown(f"""
        <div class="efs-card">
        <b>{r['doc_code']} — {r['title']}</b> &nbsp; {theme.pill(r['status'])}<br>
        <span style="font-size:0.82rem;color:#6B7280">{r['department']} · {r['doc_type']} · {r['classification']} · {r['language']} ·
        v{r['current_version']} · created {r['created_at']}</span><br>
        <span style="font-size:0.85rem">{snippet}{"…" if len(r["body_text"] or "") > 170 else ""}</span>
        </div>""", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("👁 View / Log Access", key=f"view_{r['id']}"):
                db.log_audit(r["id"], user, "Viewed", "Opened via Search & Retrieval")
                db_ext.log_view(user, r["id"])
                st.toast(f"Access logged for {r['doc_code']}")
        with c2:
            if st.button("⬇ Download", key=f"dl_{r['id']}"):
                db.log_audit(r["id"], user, "Downloaded", "Downloaded via Search & Retrieval")
                st.toast(f"Download logged for {r['doc_code']}")
        with c3:
            if st.button("⭐ Bookmark" if not bm else "★ Remove bookmark", key=f"bm_{r['id']}"):
                db_ext.toggle_bookmark(user, r["id"])
                st.rerun()
    if not results:
        st.info("No matches. Try clearing filters, using a wildcard (e.g. contr*), or Natural language mode.")

with tabs[1]:
    st.markdown('<div class="efs-section-title">Alternative taxonomy — browse without folders</div>', unsafe_allow_html=True)
    st.caption("Documents are classified against a multi-level classification tree and can be browsed independently of the "
               "folder hierarchy, with no duplication of the underlying document.")
    docs = [d for d in db.get_documents() if is_admin or d["department"] == profile["dept"] or d["status"] in ("Released", "Archived")
            or d["id"] in shared_ids]
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
