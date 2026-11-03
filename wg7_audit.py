import streamlit as st
import json
import pandas as pd
import db
import db_ext
import rfp_data
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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📜 Document Audit Trail", "📊 Compliance Dashboard", "👥 User Activity Report",
                                         "🧭 Audit Readiness", "📑 My Report Templates"])

with tab1:
    import html as _h
    import icons
    import audit_ext
    docs = db.get_documents(include_disposed=True)
    doc_map = {f"{d['doc_code']} — {d['title']}": d["id"] for d in docs}
    choice = st.selectbox("Select a document to inspect", list(doc_map.keys()))
    doc_id = doc_map[choice]
    doc = db.get_document(doc_id)
    log = [dict(r) for r in db.get_audit_log(doc_id)]
    hashes = audit_ext.chain(log)
    st.markdown(f"""
    <div class="efs-card" style="display:flex;gap:14px;align-items:center">
    {icons.chip('document', '#1F3864', 46)}
    <div><b style="font-size:1.05rem">{_h.escape(doc['title'])}</b> <span style="color:#6B7280">({doc['doc_code']})</span> &nbsp; {theme.pill(doc['status'])}<br>
    <span style="font-size:.82rem;color:#6B7280">Created by <b>{doc['created_by']}</b> on {doc['created_at']} &nbsp;·&nbsp;
    last modified by <b>{doc['modified_by']}</b> on {doc['modified_at']}</span></div>
    </div>""", unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns([1.3, 1.3, 1.2, 1])
    with f1:
        who = st.multiselect("Who", sorted({e["actor"] for e in log}), placeholder="Everyone")
    with f2:
        what = st.multiselect("What", sorted({e["action"] for e in log}), placeholder="All actions")
    with f3:
        only_changes = st.checkbox("Only value changes", value=False)
    with f4:
        newest_first = st.checkbox("Newest first", value=True)
    view = [e for e in log if (not who or e["actor"] in who) and (not what or e["action"] in what)
            and (not only_changes or e["field"])]
    view.sort(key=lambda e: (e["ts"], e["id"]), reverse=newest_first)

    changes = [e for e in log if e["field"]]
    c1, c2, c3, c4 = st.columns(4)
    theme.metric_card("Audit events", len(log), c1)
    theme.metric_card("People involved", len({e["actor"] for e in log}), c2)
    theme.metric_card("Value changes", len(changes), c3)
    theme.metric_card("Last activity", (log[0]["ts"][:10] if log else "—"), c4)
    st.write("")
    t_time, t_chg, t_who = st.tabs(["🕑 Timeline", "🔁 Changes — old → new", "👥 Who did what"])

    def role_of(n):
        return rfp_data.ROLES.get(n, {}).get("role", "System")

    with t_time:
        if not view:
            st.info("No events match the filters.")
        for e in view:
            ic, col = icons.for_action(e["action"])
            val = ""
            if e["field"] and e["field"] not in ("body_text",):
                val = (f'<div style="margin-top:6px"><span class="efs-hash" style="background:#F3F4F6">{_h.escape(e["field"])}</span> '
                       f'<span class="efs-old">{_h.escape(str(e["old_value"] if e["old_value"] is not None else "—"))}</span> '
                       f'→ <span class="efs-new">{_h.escape(str(e["new_value"] if e["new_value"] is not None else "—"))}</span></div>')
            elif e["field"] == "body_text":
                val = '<div style="margin-top:6px"><span class="efs-hash" style="background:#F3F4F6">body_text</span> text changed — see the diff below</div>'
            res = "" if e["result"] == "Success" else f' <span class="efs-pill pill-rejected">{_h.escape(e["result"])}</span>'
            st.markdown(f"""<div class="efs-tl" style="--c:{col}">
            {icons.chip(ic, col, 40)}
            <div style="flex:1;min-width:0">
              <div class="t">{_h.escape(e['action'])}{res}</div>
              <div style="font-size:.86rem;color:#374151">{_h.escape(e['detail'] or '')}</div>{val}
              <div class="m">
                <span style="display:inline-flex;align-items:center;gap:6px">{icons.avatar(e['actor'], 22)}<b>{_h.escape(e['actor'] or '')}</b> · {_h.escape(role_of(e['actor']))}</span>
                <span>🕑 {e['ts']}</span><span>🌐 {e['ip'] or '—'} · {e['channel'] or '—'}</span>
                <span title="Hash chained to the previous event — any edit breaks the chain">🔗 <span class="efs-hash">{hashes.get(e['id'], '')}</span></span>
              </div>
            </div></div>""", unsafe_allow_html=True)
            if e["field"] == "body_text" and e["old_value"] != e["new_value"]:
                with st.expander("View text difference"):
                    st.markdown(audit_ext.word_diff(e["old_value"], e["new_value"]), unsafe_allow_html=True)

    with t_chg:
        if changes:
            df = pd.DataFrame([{"When": e["ts"], "Who": e["actor"], "Role": role_of(e["actor"]), "What": e["action"], "Field": e["field"],
                                "Old value": (e["old_value"] or "")[:80], "New value": (e["new_value"] or "")[:80]} for e in sorted(changes, key=lambda x: x["ts"], reverse=True)])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No field-level changes recorded for this document.")

    with t_who:
        if log:
            import plotly.express as px
            df = pd.DataFrame(log)
            m = df.groupby(["actor", "action"]).size().reset_index(name="n")
            fig = px.bar(m, x="n", y="actor", color="action", orientation="h", color_discrete_sequence=px.colors.qualitative.Safe)
            fig.update_layout(height=max(260, 46 * df["actor"].nunique() + 90), margin=dict(l=4, r=4, t=10, b=4), legend=dict(orientation="h", y=-0.2, title=None),
                              template="plotly_white", yaxis_title=None, xaxis_title="Events")
            st.plotly_chart(fig, use_container_width=True)

    out = pd.DataFrame([{"Event ID": e["id"], "When": e["ts"], "Who": e["actor"], "What": e["action"], "Detail": e["detail"], "Field": e["field"],
                         "Old value": e["old_value"], "New value": e["new_value"], "IP": e["ip"], "Channel": e["channel"], "Result": e["result"],
                         "Chain hash": hashes.get(e["id"])} for e in log])
    d1, d2 = st.columns([1, 3])
    with d1:
        st.download_button("⬇ Export audit trail (CSV)", out.to_csv(index=False).encode("utf-8-sig"), f"audit_{doc['doc_code'].replace('/', '-')}.csv")
    with d2:
        st.markdown(
            f'<div style="font-size:.78rem;color:#6B7280;display:flex;gap:6px;align-items:center">{icons.svg("shield", 16, "#2E7D32")} Append-only log — the database rejects updates and deletes. Every event carries a chained hash, so a missing or altered row is detectable.</div>',
            unsafe_allow_html=True)

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


with tab4:
    comp = db_ext.department_compliance()
    scored = [c for c in comp if c["score"] is not None]
    overall = round(sum(c["score"] for c in scored) / len(scored)) if scored else 0
    od = db_ext.overdue_approvals()
    ex = db_ext.expiry_report()
    expired = [e for e in ex if e["days_left"] is not None and e["days_left"] < 0]
    expiring = [e for e in ex if e["days_left"] is not None and 0 <= e["days_left"] <= 90]
    c1, c2, c3, c4 = st.columns(4)
    theme.metric_card("Audit-readiness score", f"{overall}%", c1)
    theme.metric_card("Overdue approvals (SLA 3d)", len(od), c2)
    theme.metric_card("Expired documents", len(expired), c3)
    theme.metric_card("Expiring ≤ 90 days", len(expiring), c4)
    st.write("")
    st.markdown('<div class="efs-section-title">Department compliance status</div>', unsafe_allow_html=True)
    df = pd.DataFrame([{"Department": c["department"], "Documents": c["docs"],
                        "Released/Archived %": c["released_pct"], "Overdue approvals": c["overdue"],
                        "No retention schedule": c["no_retention"], "Compliance score": c["score"]} for c in comp])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇ Export (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "department_compliance.csv")
    l, r = st.columns(2)
    with l:
        st.markdown('<div class="efs-section-title">⏰ Overdue approvals</div>', unsafe_allow_html=True)
        for o in od:
            st.markdown(f"- 🔴 **{o['doc_code']}** {o['title']} — {o['status']} · **{o['days']} days** ({o['department']})")
        if not od:
            st.caption("None — all approvals within SLA.")
    with r:
        st.markdown('<div class="efs-section-title">📅 Expired / expiring documents</div>', unsafe_allow_html=True)
        for e in expired + expiring:
            tag = "🔴 expired" if e["days_left"] < 0 else f"🟠 {e['days_left']}d"
            st.markdown(f"- {tag} — **{e['doc_code']}** {e['title']} ({e['department']})")
        if not (expired or expiring):
            st.caption("Nothing expired or expiring within 90 days.")
    st.markdown('<div class="efs-section-title">🔒 Immutability check</div>', unsafe_allow_html=True)
    st.caption("The audit log is protected at the database level — updates and deletes are rejected, even for administrators.")
    if st.button("Attempt to tamper with the audit log"):
        import sqlite3
        conn = db.get_conn()
        try:
            conn.execute("UPDATE audit_log SET actor='Someone Else' WHERE id=(SELECT MIN(id) FROM audit_log)")
            conn.commit()
            st.error("Tampering succeeded (unexpected).")
        except sqlite3.DatabaseError as e:
            st.success(f"Blocked: {e}")
        finally:
            conn.close()

with tab5:
    st.markdown('<div class="efs-section-title">Save & reuse your own report templates</div>', unsafe_allow_html=True)
    user = theme.current_user()
    c1, c2, c3 = st.columns(3)
    with c1:
        rtype = st.selectbox("Report", ["Documents by status", "Overdue approvals", "Expiring documents",
                                         "Audit events by user", "E-signature usage"])
    with c2:
        rdept = st.selectbox("Department", ["All"] + rfp_data.DEPARTMENTS, key="rt_dept")
    with c3:
        rname = st.text_input("Template name", placeholder="e.g. Monthly Finance overdue")
    if st.button("💾 Save template") and rname:
        conn = db.get_conn()
        conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (f"report:{user}:{rname}", json.dumps({"type": rtype, "dept": rdept})))
        conn.commit()
        conn.close()
        st.success("Template saved.")
        st.rerun()
    conn = db.get_conn()
    tpls = conn.execute("SELECT key, value FROM settings WHERE key LIKE ?", (f"report:{user}:%",)).fetchall()
    conn.close()
    for t in tpls:
        name = t["key"].split(":", 2)[2]
        cfg = json.loads(t["value"])
        if st.button(f"▶ Run “{name}” ({cfg['type']} · {cfg['dept']})", key=t["key"]):
            st.session_state["run_report"] = cfg
    cfg = st.session_state.get("run_report")
    if cfg:
        st.markdown(f"**{cfg['type']}** — {cfg['dept']}")
        dept_ok = lambda d: cfg["dept"] == "All" or d == cfg["dept"]
        if cfg["type"] == "Documents by status":
            rows = [d for d in db.get_documents() if dept_ok(d["department"])]
            st.dataframe(pd.DataFrame([{"Code": d["doc_code"], "Title": d["title"], "Status": d["status"], "Dept": d["department"]} for d in rows]),
                         use_container_width=True, hide_index=True)
        elif cfg["type"] == "Overdue approvals":
            st.dataframe(pd.DataFrame([dict(o) for o in db_ext.overdue_approvals() if dept_ok(o["department"])]), use_container_width=True, hide_index=True)
        elif cfg["type"] == "Expiring documents":
            st.dataframe(pd.DataFrame([dict(o) for o in db_ext.expiry_report() if dept_ok(o["department"])]), use_container_width=True, hide_index=True)
        elif cfg["type"] == "Audit events by user":
            log = db.get_audit_log(limit=500)
            st.dataframe(pd.DataFrame([dict(l) for l in log]).groupby("actor").size().reset_index(name="events"), use_container_width=True, hide_index=True)
        else:
            st.dataframe(pd.DataFrame([dict(e) for e in db_ext.esign_report()]), use_container_width=True, hide_index=True)
    if not tpls:
        st.caption("No templates yet.")
