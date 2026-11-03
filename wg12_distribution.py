import os
import streamlit as st
import pandas as pd
from PIL import Image
import db
import db_ext
import distribution as dist
import rfp_data
import theme
from ocr_utils import run_ocr, extract_metadata, auto_name
from sample_docs import generate_samples, ASSETS_DIR

db.init_db()
dist.init_dist()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("12 · Automatic Distribution",
             "OCR text → content rules → routed to the right department, copies sent, acknowledged within SLA")

user = theme.current_user()
profile = theme.current_profile()
is_admin = theme.is_admin()

s = dist.stats()
c1, c2, c3, c4, c5 = st.columns(5)
theme.metric_card("Auto-distributed", s["total"], c1)
theme.metric_card("Straight-through", f"{round(100 * s['routed'] / s['total']) if s['total'] else 0}%", c2)
theme.metric_card("In triage", s["triage"], c3)
theme.metric_card("Acknowledged", f"{s['acked']}/{s['primary']}", c4)
theme.metric_card("Past SLA", s["overdue"], c5)
st.write("")

tabs = st.tabs(["🧪 Simulate: scan → route", "📥 My Distribution Inbox", "⚙️ Routing Rules", "📋 Distribution Log",
                "🚧 Triage Queue", "📊 Analytics"])


def show_decision(res):
    if not res["hits"]:
        st.warning("No rule matched — this item would go to the **Triage Queue** for a records officer to assign.")
        return
    st.success(f"**Primary:** {res['primary']}  ·  **Copies:** {', '.join(res['copies']) or '—'}  ·  "
               f"**Type:** {res['doc_type']}  ·  **Classification:** {res['classification']}")
    rows = [{"Rule": h["rule"]["name"], "Matched terms": ", ".join(h["matched"]), "Score": round(h["score"], 1),
             "Priority": h["rule"]["priority"], "→ Department": h["rule"]["primary_dept"], "SLA (h)": h["rule"]["sla_hours"]}
            for h in res["hits"]]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    people = []
    for d in [res["primary"]] + res["copies"]:
        people += dist._users(d) or [f"{d} inbox"]
    st.caption("Notified: " + ", ".join(people))


with tabs[0]:
    st.markdown('<div class="efs-section-title">Capture once — the system reads it and routes it</div>', unsafe_allow_html=True)
    st.caption("Pick a scanned letter (or paste text). The real OCR engine reads the page, the rules decide who must act, "
               "and nothing is typed by hand. Arabic keywords work too.")
    a, b = st.columns([1, 1])
    with a:
        if st.button("🖨️ Generate / refresh sample scans"):
            generate_samples()
        files = sorted(f for f in os.listdir(ASSETS_DIR) if f.endswith(".png")) if os.path.isdir(ASSETS_DIR) else []
        if not files:
            generate_samples()
            files = sorted(f for f in os.listdir(ASSETS_DIR) if f.endswith(".png"))
        mode = st.radio("Input", ["Sample scanned letter (OCR)", "Paste text"], horizontal=True)
        text, title, sender, src_name = "", "", "", ""
        if mode.startswith("Sample"):
            pick = st.selectbox("Scanned letter", files)
            st.image(os.path.join(ASSETS_DIR, pick), use_container_width=True)
            cache = st.session_state.setdefault("dist_ocr", {})
            if st.button("▶ Run OCR and route", type="primary"):
                with st.spinner("OCR…"):
                    cache[pick] = run_ocr(Image.open(os.path.join(ASSETS_DIR, pick)).convert("RGB"), lang="eng")
            text = cache.get(pick, "")
            src_name = pick
        else:
            text = st.text_area("Text", height=200, placeholder="e.g. Invoice INV-100 for QAR 5,000. Payment due in 30 days.  /  عقد خدمات جديد")
            src_name = "pasted text"
        meta = extract_metadata(text) if text else {}
        title = auto_name(meta, src_name) if text else ""
        sender = meta.get("Sender", "") if meta else ""
    with b:
        if text.strip():
            st.markdown("**OCR / input text**")
            st.code(text.strip()[:900], language=None)
            res = dist.analyse(text, title, sender)
            st.markdown("**Automatic routing decision**")
            show_decision(res)
            if st.button("✅ Create the document and distribute it now"):
                dept = res["primary"] or "Medical Records"
                doc_id, code = db.create_document(
                    title=title or src_name, department=dept, classification=res["classification"] or "External",
                    security_level="Internal", doc_type=res["doc_type"] or "Letter", source="Scan",
                    language="English", body_text=text.strip(), created_by=user, sender=sender, recipient="")
                db.log_audit(doc_id, user, "OCR Capture", f"Captured and auto-distributed from {src_name}")
                dist.distribute(doc_id, user, apply_dept=True, notify=True, text=text)
                st.success(f"Created **{code}** and distributed. Open *My Distribution Inbox* as a user of the target department, "
                           "or find it in Search (it is indexed automatically).")
        else:
            st.info("Run OCR (or paste text) to see the routing decision.")

with tabs[1]:
    st.markdown(f'<div class="efs-section-title">Items delivered to {profile["dept"]}</div>', unsafe_allow_html=True)
    rows = dist.log_rows(dept=profile["dept"])
    if is_admin:
        rows = dist.log_rows(status="Delivered")
        st.caption("Administrator view: all unacknowledged deliveries.")
    if not rows:
        st.info("Nothing has been routed to your department yet. Use the Simulate tab, then switch to a user of the target department.")
    for r in rows[:30]:
        late = r["status"] == "Delivered" and r["sla_due"] and r["sla_due"] < db.now()
        flag = "🔴 SLA breached" if late else ("✅ Acknowledged" if r["status"] == "Acknowledged" else "🟡 Awaiting acknowledgement")
        st.markdown(f"""<div class="efs-card"><b>{r['doc_code']} — {r['title']}</b> &nbsp; {flag}<br>
        <span style="font-size:0.82rem;color:#6B7280">{r['role']} · rule: {r['rule_name']} · matched: {r['matched'] or '—'} · due {r['sla_due'] or '—'}</span></div>""",
                    unsafe_allow_html=True)
        if r["status"] == "Delivered" and (is_admin or r["target_dept"] == profile["dept"]):
            if st.button("✔ Acknowledge receipt", key=f"ack_{r['id']}"):
                dist.acknowledge(r["id"], user)
                st.rerun()

with tabs[2]:
    st.markdown('<div class="efs-section-title">Routing rules — editable without code</div>', unsafe_allow_html=True)
    st.caption("Keywords are separated by semicolons; phrases and Arabic terms are supported; a stem such as ‘licen’ matches licence/license. "
               "Higher priority wins when several rules match. OCR slips on longer words are tolerated.")
    rules = dist.list_rules()
    df = pd.DataFrame([{"ID": r["id"], "Active": bool(r["active"]), "Rule": r["name"], "Keywords": r["keywords"], "Primary": r["primary_dept"],
                        "Copies": r["copy_depts"], "Type": r["doc_type"], "Class": r["classification"], "Priority": r["priority"],
                        "SLA h": r["sla_hours"]} for r in rules])
    st.dataframe(df, use_container_width=True, hide_index=True, height=300)
    if not is_admin:
        st.caption("Only Administrators can change routing rules (switch to Yusuf Al-Marri).")
    with st.form("rule_form"):
        st.markdown("**Add or edit a rule**")
        edit = st.selectbox("Edit existing (or leave as New)", ["(New rule)"] + [f"{r['id']} — {r['name']}" for r in rules])
        cur = next((r for r in rules if edit.startswith(f"{r['id']} —")), None)
        f1, f2 = st.columns(2)
        with f1:
            name = st.text_input("Rule name", value=cur["name"] if cur else "")
            kws = st.text_area("Keywords (; separated)", value=cur["keywords"] if cur else "", height=90)
            primary = st.selectbox("Primary department", rfp_data.DEPARTMENTS,
                                   index=rfp_data.DEPARTMENTS.index(cur["primary_dept"]) if cur and cur["primary_dept"] in rfp_data.DEPARTMENTS else 0)
        with f2:
            copies = st.multiselect("Copy to", rfp_data.DEPARTMENTS,
                                    default=[d for d in dist._terms(cur["copy_depts"]) if d in rfp_data.DEPARTMENTS] if cur else [])
            dtype = st.selectbox("Set document type", rfp_data.DOC_TYPES,
                                 index=rfp_data.DOC_TYPES.index(cur["doc_type"]) if cur and cur["doc_type"] in rfp_data.DOC_TYPES else 0)
            cls = st.selectbox("Set classification", db.CLASSIFICATIONS,
                               index=db.CLASSIFICATIONS.index(cur["classification"]) if cur and cur["classification"] in db.CLASSIFICATIONS else 0)
            pr = st.number_input("Priority (1-10)", 1, 10, int(cur["priority"]) if cur else 5)
            sla = st.number_input("Acknowledge within (hours)", 1, 240, int(cur["sla_hours"]) if cur else 24)
        active = st.checkbox("Active", value=bool(cur["active"]) if cur else True)
        if st.form_submit_button("Save rule", disabled=not is_admin):
            if name and kws:
                dist.save_rule(name, kws, primary, copies, dtype, cls, int(pr), int(sla), user, rule_id=cur["id"] if cur else None, active=active)
                st.success("Rule saved.")
                st.rerun()
            else:
                st.error("Name and keywords are required.")
    if is_admin and rules:
        d1, d2 = st.columns([3, 1])
        with d1:
            rid = st.selectbox("Delete a rule", [f"{r['id']} — {r['name']}" for r in rules], key="del_rule")
        with d2:
            st.write("")
            if st.button("🗑 Delete rule"):
                dist.delete_rule(int(rid.split(" — ")[0]))
                st.rerun()

with tabs[3]:
    f1, f2 = st.columns(2)
    with f1:
        sf = st.selectbox("Status", ["All", "Delivered", "Acknowledged", "Needs triage", "Triaged"])
    with f2:
        df_ = st.selectbox("Department", ["All"] + rfp_data.DEPARTMENTS + ["Unrouted"])
    logs = dist.log_rows(status=sf, dept=df_)
    if logs:
        out = pd.DataFrame([{"When": r["ts"], "Document": r["doc_code"], "Title": r["title"], "Rule": r["rule_name"],
                             "Matched": r["matched"], "To": r["target_dept"], "Role": r["role"], "Delivered to": r["delivered_to"],
                             "Status": r["status"], "SLA due": r["sla_due"], "Ack by": r["ack_by"]} for r in logs])
        st.dataframe(out, use_container_width=True, hide_index=True, height=420)
        st.download_button("⬇ Export distribution log (CSV)", out.to_csv(index=False).encode("utf-8-sig"), "distribution_log.csv")
    else:
        st.info("No entries.")

with tabs[4]:
    q = dist.triage_queue()
    st.markdown('<div class="efs-section-title">Items no rule could place</div>', unsafe_allow_html=True)
    if not q:
        st.success("Triage queue is empty — everything was routed automatically.")
    for r in q:
        with st.container(border=True):
            st.markdown(f"**{r['doc_code']} — {r['title']}**")
            st.caption((r["body_text"] or "")[:240])
            t1, t2 = st.columns([3, 1])
            with t1:
                to = st.selectbox("Assign to department", rfp_data.DEPARTMENTS, key=f"tri_{r['id']}")
            with t2:
                st.write("")
                if st.button("Assign", key=f"trib_{r['id']}"):
                    dist.triage_assign(r["document_id"], to, user)
                    st.rerun()
    st.caption("Tip: add or widen a keyword rule in ‘Routing Rules’ so the next similar item routes itself.")

with tabs[5]:
    l, r = st.columns(2)
    with l:
        st.markdown("**Documents routed per rule**")
        if s["by_rule"]:
            st.bar_chart(pd.DataFrame(s["by_rule"], columns=["Rule", "Documents"]).set_index("Rule"), color="#2E8B8B")
    with r:
        st.markdown("**Deliveries per department**")
        if s["by_dept"]:
            st.bar_chart(pd.DataFrame(s["by_dept"], columns=["Department", "Deliveries"]).set_index("Department"), color="#C0603C")
