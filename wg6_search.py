import streamlit as st
import db
import theme
import datetime as dt

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("6 · Search & Information Retrieval Workgroup",
             "Full-text · metadata · OCR content · security-trimmed results")

profile = theme.current_profile()
is_admin = theme.is_admin()

st.markdown('<div class="efs-section-title">🔎 Search</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
with c1:
    query = st.text_input("Search by document number, title, or full text (incl. OCR content)",
                           placeholder="e.g. MOPH, PO-2026, leave policy…")
with c2:
    dept_filter = st.selectbox("Department", ["All"] + db.DEPARTMENTS)
with c3:
    class_filter = st.selectbox("Classification", ["All"] + db.CLASSIFICATIONS)
with c4:
    status_filter = st.selectbox("Status", ["All"] + db.WORKFLOW_STAGES + ["Rejected", "Archived"])

date_range = st.date_input("Date range (created)", value=(), help="Optional — leave empty to search all dates")

cc1, cc2 = st.columns([1, 3])
with cc1:
    search_clicked = st.button("🔍 Search", type="primary")
with cc2:
    save_name = st.text_input("Save this search as…", placeholder="e.g. 'My open Finance approvals'",
                               label_visibility="collapsed")
    if st.button("💾 Save search") and save_name:
        conn = db.get_conn()
        conn.execute("INSERT INTO saved_searches (user, name, query, dept_filter, class_filter, created_at) "
                      "VALUES (?,?,?,?,?,?)",
                      (theme.current_user(), save_name, query, dept_filter, class_filter, db.now()))
        conn.commit()
        conn.close()
        st.success("Search saved.")

conn = db.get_conn()
saved = conn.execute("SELECT * FROM saved_searches WHERE user=? ORDER BY id DESC",
                      (theme.current_user(),)).fetchall()
conn.close()
if saved:
    with st.expander(f"⭐ My saved searches ({len(saved)})"):
        for sv in saved:
            st.markdown(f"- **{sv['name']}** — query: `{sv['query'] or '(none)'}`, "
                         f"dept: {sv['dept_filter']}, class: {sv['class_filter']}")

results = db.get_documents(department=dept_filter, status=status_filter if status_filter != "All" else None,
                            classification=class_filter, search=query or None, include_disposed=True)

if date_range and len(date_range) == 2:
    start, end = date_range
    results = [r for r in results if r["created_at"] and
               start.isoformat() <= r["created_at"][:10] <= end.isoformat()]

# security trimming — department users only see their own dept + released docs
if not is_admin:
    results = [r for r in results if r["department"] == profile["dept"] or r["status"] in ("Released", "Archived")]

st.markdown(f"**{len(results)}** result(s)" + (" — security-trimmed to your access level" if not is_admin else ""))
st.write("")

for r in results:
    with st.container():
        snippet = (r["body_text"] or "")[:180]
        st.markdown(f"""
        <div class="efs-card">
        <b>{r['doc_code']} — {r['title']}</b> &nbsp; {theme.pill(r['status'])}<br>
        <span style="font-size:0.82rem;color:#6B7280">
        {r['department']} · {r['classification']} · {r['language']} · v{r['current_version']} ·
        created {r['created_at']}
        </span><br>
        <span style="font-size:0.85rem">{snippet}{"…" if len(r["body_text"] or "") > 180 else ""}</span>
        </div>
        """, unsafe_allow_html=True)
        cc1, cc2, cc3 = st.columns([1, 1, 4])
        with cc1:
            if st.button("👁 View / Log Access", key=f"view_{r['id']}"):
                db.log_audit(r["id"], theme.current_user(), "Viewed", "Opened via Search & Retrieval")
                st.toast(f"Access logged for {r['doc_code']}")
        with cc2:
            if st.button("⬇ Download", key=f"dl_{r['id']}"):
                db.log_audit(r["id"], theme.current_user(), "Downloaded", "Downloaded via Search & Retrieval")
                st.toast(f"Download logged for {r['doc_code']}")

if not results:
    st.info("No matches. Try clearing filters, or register/OCR a document first.")
