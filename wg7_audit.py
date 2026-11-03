import streamlit as st
import db
import theme
import plotly.graph_objects as go
import datetime as dt

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("7 · Audit, Governance & Reporting Workgroup",
             "Immutable audit trail · compliance dashboards · overdue & expiring documents")

st.markdown(f"{theme.tag_custom('Immutable audit log (append-only)')} {theme.tag_ms('Power BI dashboards')}",
            unsafe_allow_html=True)
st.write("")

tab1, tab2, tab3 = st.tabs(["📜 Document Audit Trail", "📊 Compliance Dashboard", "👥 User Activity Report"])

with tab1:
    docs = db.get_documents(include_disposed=True)
    doc_map = {f"{d['doc_code']} — {d['title']}": d["id"] for d in docs}
    choice = st.selectbox("Select a document to inspect", list(doc_map.keys()))
    doc_id = doc_map[choice]
    doc = db.get_document(doc_id)

    st.markdown(f"""
    <div class="efs-card">
    <b>{doc['title']}</b> ({doc['doc_code']}) &nbsp; {theme.pill(doc['status'])}<br>
    Created by <b>{doc['created_by']}</b> on {doc['created_at']} &nbsp;·&nbsp;
    Last modified by <b>{doc['modified_by']}</b> on {doc['modified_at']}
    </div>
    """, unsafe_allow_html=True)

    log = db.get_audit_log(doc_id)
    st.markdown(f"**{len(log)}** audit events — immutable, timestamped, cannot be altered or deleted")
    action_icons = {
        "Created": "🆕", "Edited": "✏️", "Checked Out": "🔒", "New Version Checked In": "📥",
        "Version Published": "📣", "Approved": "✅", "Rejected": "❌", "Delegated": "↪️",
        "Viewed": "👁", "Downloaded": "⬇️", "Archived": "🗄️", "Disposal Requested": "🗑️",
        "OCR Capture": "🔎",
    }
    for entry in log:
        icon = next((v for k, v in action_icons.items() if k in entry["action"]), "📌")
        st.markdown(f"""
        <div style="padding:8px 0;border-bottom:1px solid #E2E6EC;">
        {icon} <b>{entry['action']}</b> — {entry['detail'] or ''}<br>
        <span style="font-size:0.8rem;color:#6B7280">by {entry['actor']} · {entry['ts']} · {entry['result']}</span>
        </div>
        """, unsafe_allow_html=True)
    if not log:
        st.info("No audit events recorded for this document yet.")

with tab2:
    s = db.stats()
    c1, c2, c3, c4 = st.columns(4)
    theme.metric_card("Total Documents", s["total"], c1)
    theme.metric_card("Pending Approvals", s["pending"], c2)
    theme.metric_card("Expiring ≤ 90 days", s["expiring"], c3)
    theme.metric_card("Rejected", s["rejected"], c4)

    st.write("")
    colL, colR = st.columns(2)
    with colL:
        st.markdown('<div class="efs-section-title">Overdue approvals by department</div>', unsafe_allow_html=True)
        conn = db.get_conn()
        rows = conn.execute("""
            SELECT d.department, COUNT(*) n FROM workflow w
            JOIN documents d ON d.id = w.document_id
            WHERE w.status='active' GROUP BY d.department
        """).fetchall()
        conn.close()
        if rows:
            fig = go.Figure(data=[go.Bar(x=[r["department"] for r in rows], y=[r["n"] for r in rows],
                                          marker=dict(color="#C0603C"))])
            fig.update_layout(height=280, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No items currently pending approval.")

    with colR:
        st.markdown('<div class="efs-section-title">Documents nearing retention expiry</div>', unsafe_allow_html=True)
        conn = db.get_conn()
        expiring = conn.execute("""
            SELECT doc_code, title, department, expiry_date FROM documents
            WHERE expiry_date IS NOT NULL AND expiry_date <= date('now', '+365 day')
            AND status != 'Disposed' ORDER BY expiry_date ASC LIMIT 10
        """).fetchall()
        conn.close()
        if expiring:
            for e in expiring:
                st.markdown(f"- **{e['doc_code']}** {e['title']} ({e['department']}) — expires {e['expiry_date']}")
        else:
            st.caption("Nothing expiring within the next year.")

    st.write("")
    st.markdown('<div class="efs-section-title">Regulatory & accreditation compliance posture</div>',
                 unsafe_allow_html=True)
    comp_cols = st.columns(4)
    badges = [
        ("ISO 9001/27001", "Governance embedded via document control & audit trail"),
        ("HIPAA / GDPR / PDPPL", "Access control, encryption, audit logging in place"),
        ("CARF", "Policy & SOP version control supports accreditation evidence"),
        ("MOPH / MOF", "Regulatory correspondence tracked end-to-end"),
    ]
    for col, (name, desc) in zip(comp_cols, badges):
        with col:
            st.markdown(f"""<div class="efs-metric"><div class="val">✅</div>
            <div class="lbl">{name}</div></div>
            <div style="font-size:0.75rem;color:#6B7280;margin-top:4px">{desc}</div>""",
                        unsafe_allow_html=True)

with tab3:
    log = db.get_audit_log(limit=300)
    actors = sorted(set(l["actor"] for l in log))
    pick = st.selectbox("Filter by user", ["All"] + actors)
    filtered = log if pick == "All" else [l for l in log if l["actor"] == pick]
    st.markdown(f"**{len(filtered)}** system-wide events")
    for entry in filtered[:100]:
        st.markdown(f"""
        <div style="padding:6px 0;border-bottom:1px solid #E2E6EC;font-size:0.88rem;">
        <b>{entry['actor']}</b> — {entry['action']} — {entry['doc_title'] or ''} ({entry['doc_code'] or ''})
        <span style="color:#6B7280;float:right">{entry['ts']}</span>
        </div>
        """, unsafe_allow_html=True)
