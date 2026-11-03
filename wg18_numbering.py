import pandas as pd
import streamlit as st
import db
import db_ext
import numbering as nm
import rfp_data
import theme

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("18 · Numbering Rules", "Choose a fixed standard or dynamic rule-based document numbers · per department, type and classification · live preview")

user = theme.current_user()
can_edit = theme.is_admin()
mode = nm.mode()
st.markdown(f"{theme.tag_custom('Configurable numbering — applies to every new document, existing numbers never change')}", unsafe_allow_html=True)

# ------------------------------------------------------------------ switch ---
with st.container(border=True):
    c1, c2 = st.columns([1, 3])
    dyn = c1.toggle("Dynamic numbering", value=(mode == "dynamic"), disabled=not can_edit, key="num_toggle",
                    help="Off = one fixed standard style. On = numbers follow the rules below.")
    if dyn != (mode == "dynamic") and can_edit:
        nm.set_mode("dynamic" if dyn else "fixed", user)
        st.rerun()
    if mode == "fixed":
        c2.markdown("🔒 **Fixed standard** — every document is numbered `DEPT-TYPE-YEAR-NNNN`, e.g. **FIN-INV-2026-0001**. Simple and identical for all departments.")
    else:
        c2.markdown("⚙️ **Dynamic** — numbers follow the most specific matching rule (department + type + classification). "
                    "Anything not covered falls back to the default rule. Each rule has its own counter and reset period.")
    if not can_edit:
        st.caption("Only Administrators can change numbering.")

tabs = st.tabs(["🧮 Preview", "📐 Rules", "🔢 Counters & history", "ℹ️ Where this is used"])

with tabs[0]:
    st.caption("See the next number that would be issued — nothing is consumed by previewing.")
    p1, p2, p3, p4 = st.columns(4)
    d = p1.selectbox("Department", rfp_data.DEPARTMENTS, key="pv_d")
    t = p2.selectbox("Document type", rfp_data.DOC_TYPES, key="pv_t")
    cl = p3.selectbox("Classification", db.CLASSIFICATIONS, key="pv_c")
    sl = p4.selectbox("Security level", db.SECURITY_LEVELS, key="pv_s")
    code, why = nm.peek(d, t, cl, sl)
    st.markdown(f"""<div class="efs-card" style="text-align:center"><div style="color:#6B7280;font-size:.8rem">NEXT NUMBER ({'DYNAMIC' if mode == 'dynamic' else 'FIXED'})</div>
    <div style="font-size:2rem;font-weight:800;color:#1F3864;letter-spacing:.04em">{code}</div><div style="color:#6B7280;font-size:.8rem">{why}</div></div>""", unsafe_allow_html=True)
    if mode == "fixed":
        dc, _ = nm.next_number(d, t, cl, sl, consume=False)
        st.info(f"If dynamic numbering were switched on, this document would be numbered **{dc}**.")
    st.markdown("**Examples across the organisation**")
    ex = [("Finance", "Invoice", "Internal", "Internal"), ("Legal", "Vendor Agreement", "External", "Restricted"), ("HR", "Appraisal", "Internal", "Internal"),
          ("Executive Offices", "Regulatory Letter", "Regulatory", "Restricted"), ("Medical Records", "Medical Record", "Internal", "Confidential"), ("IT", "Memo", "Internal", "Internal")]
    st.dataframe(pd.DataFrame([{"Department": a, "Type": b, "Classification": c, "Fixed": db_ext.next_code_fixed(a, b),
                                "Dynamic": nm.next_number(a, b, c, e, consume=False)[0]} for a, b, c, e in ex]), hide_index=True, use_container_width=True)

with tabs[1]:
    st.markdown('<div class="efs-section-title">Pattern tokens</div>', unsafe_allow_html=True)
    st.markdown(" ".join(f'<span class="efs-tag-ms" title="{v}">{k}</span>' for k, v in nm.TOKENS.items()), unsafe_allow_html=True)
    st.caption("Example: `FIN/{YY}{MM}/{TYPE}-{SEQ:4}` → FIN/2611/INV-0001 · allowed characters around tokens: letters, digits, / _ - .")
    rl = nm.rules()
    st.markdown(f"**{len(rl)}** rule(s) — most specific match wins (department › type › classification); inactive rules are ignored.")
    if rl:
        st.dataframe(pd.DataFrame([{"#": r["id"], "On": bool(r["active"]), "Department": r["dept"] or "any", "Doc type": r["doc_type"] or "any",
                                    "Classification": r["classification"] or "any", "Pattern": r["pattern"], "Resets": r["reset"], "Starts at": r["start_at"],
                                    "Example": nm.next_number(r["dept"] or "Finance", r["doc_type"] or "Invoice", r["classification"] or "Internal", "Internal", consume=False)[0], "Note": r["note"]} for r in rl]), hide_index=True, use_container_width=True)
    st.markdown('<div class="efs-section-title">Add or edit a rule</div>', unsafe_allow_html=True)
    ids = [None] + [r["id"] for r in rl]
    pick = st.selectbox("Rule", ids, format_func=lambda x: "➕ New rule" if x is None else f"#{x} — " + next(f"{r['dept'] or 'any'} / {r['doc_type'] or 'any'} / {r['classification'] or 'any'}: {r['pattern']}" for r in rl if r["id"] == x), key="rl_pick")
    cur = next((r for r in rl if r["id"] == pick), None)
    k = f"rl_{pick}"
    a1, a2, a3 = st.columns(3)
    r_dept = a1.selectbox("Department", [""] + rfp_data.DEPARTMENTS, index=([""] + rfp_data.DEPARTMENTS).index(cur["dept"]) if cur and cur["dept"] in rfp_data.DEPARTMENTS else 0,
                          format_func=lambda x: x or "(any department)", key=k + "d")
    r_type = a2.selectbox("Document type", [""] + rfp_data.DOC_TYPES, index=([""] + rfp_data.DOC_TYPES).index(cur["doc_type"]) if cur and cur["doc_type"] in rfp_data.DOC_TYPES else 0,
                          format_func=lambda x: x or "(any type)", key=k + "t")
    r_cls = a3.selectbox("Classification", [""] + db.CLASSIFICATIONS, index=([""] + db.CLASSIFICATIONS).index(cur["classification"]) if cur and cur["classification"] in db.CLASSIFICATIONS else 0,
                         format_func=lambda x: x or "(any classification)", key=k + "c")
    b1, b2, b3 = st.columns([2, 1, 1])
    r_pat = b1.text_input("Pattern", cur["pattern"] if cur else "{DEPT}/{TYPE}/{YYYY}/{SEQ:4}", key=k + "p")
    r_reset = b2.selectbox("Counter resets", nm.RESETS, index=nm.RESETS.index(cur["reset"]) if cur else 0, key=k + "r")
    r_start = b3.number_input("First number", 0, 10_000_000, int(cur["start_at"] or 1) if cur else 1, key=k + "s")
    r_note = st.text_input("Description", cur["note"] if cur else "", key=k + "n")
    r_on = st.checkbox("Rule is active", bool(cur["active"]) if cur else True, key=k + "a")
    err = nm.validate_pattern(r_pat)
    if err:
        st.error(err)
    else:
        sample = nm._render(r_pat, r_dept or "Finance", r_type or "Invoice", r_cls or "Internal", "Internal", __import__("datetime").date.today(), int(r_start))
        st.success(f"Preview of the first number this rule issues: **{sample}**")
    s1, s2, _ = st.columns([1, 1, 3])
    if s1.button("💾 Save rule", type="primary", disabled=bool(err) or not can_edit):
        e = nm.save_rule(user, pick, r_dept, r_type, r_cls, r_pat, r_reset, r_start, r_on, r_note)
        if e:
            st.error(e)
        else:
            st.success("Rule saved.")
            st.rerun()
    if s2.button("🗑 Delete rule", disabled=pick is None or not can_edit):
        nm.delete_rule(user, pick)
        st.rerun()
    if mode == "fixed":
        st.warning("Dynamic numbering is switched **off** — these rules are ready but new documents still use the fixed standard.")

with tabs[2]:
    conn = db.get_conn()
    cnt = conn.execute("SELECT ckey, last FROM numbering_counters ORDER BY ckey").fetchall()
    n_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    recent = conn.execute("SELECT doc_code, title, department, doc_type, created_at FROM documents ORDER BY id DESC LIMIT 15").fetchall()
    changes = conn.execute("SELECT ts, actor, action, detail FROM audit_log WHERE action LIKE 'Numbering%' ORDER BY id DESC LIMIT 15").fetchall()
    conn.close()
    st.markdown(f"**{n_docs}** documents numbered so far. Dynamic counters (one per pattern + period):")
    if cnt:
        st.dataframe(pd.DataFrame([{"Series (pattern|period)": r["ckey"].replace("\u0000", "#"), "Last issued": r["last"]} for r in cnt]), hide_index=True, use_container_width=True)
    else:
        st.caption("No dynamic counters yet — they appear after the first document is numbered in dynamic mode.")
    st.markdown("**Most recently issued numbers**")
    st.dataframe(pd.DataFrame([dict(r) for r in recent]), hide_index=True, use_container_width=True)
    st.markdown("**Configuration changes (audit trail)**")
    st.dataframe(pd.DataFrame([dict(r) for r in changes]) if changes else pd.DataFrame({"Info": ["No changes yet"]}), hide_index=True, use_container_width=True)

with tabs[3]:
    st.markdown("""
- **Where it runs:** every new document — correspondence intake, OCR capture, upload, workflow-generated — gets its number at creation.
- **Never reused:** a counter only moves forward and every number is checked against existing documents, so a number cannot repeat even if a document is deleted.
- **Existing documents** keep the number they were given; changing the rules affects new documents only.
- **Searchable:** any number, in any style, is found by Search & Retrieval, the Ask EDMS assistant and the Correspondence register search.
- **Fixed vs dynamic:** switching modes is instant and reversible; it is recorded in the immutable audit trail with who and when.
""")
