import streamlit as st
import db
import distribution as dist
import db_ext
import rfp_data
import numbering
import letter_templates as lt
import intake_ext as ix
import pandas as pd
import theme
from ocr_utils import extract_metadata, auto_name

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("1 · Correspondence & Document Intake Management",
             "Postal & email capture · registration · classification · QR verification")

tab1, tabD, tabU, tab2, tab3 = st.tabs(["📥 Register New Correspondence", "✍️ Draft from Template (Word)", "📂 Scan / Upload / Shared Folder",
                                          "📋 Incoming/Outgoing Register", "📤 Outgoing Dispatch Tracker"])

with tab1:
    st.markdown(f"{theme.tag_custom('Custom intake portal')} {theme.tag_ms('Outlook integration (simulated)')}",
                unsafe_allow_html=True)
    st.write("")
    with st.container(border=True, key="intake_form"):
        c1, c2 = st.columns(2)
        with c1:
            direction = st.selectbox("Direction", ["Incoming", "Outgoing", "Internal"])
            kind = st.selectbox("Kind", ["Letter", "Memo", "Email", "Circular", "Telegram / Transaction"])
            channel = st.selectbox("Channel", ["Postal Mail", "Email / Outlook"])
            sender = st.text_input("Sender", placeholder="e.g. Ministry of Public Health")
            recipient = st.text_input("Recipient", placeholder="e.g. Compliance Officer")
            subject = st.text_input("Subject", placeholder="e.g. Annual Facility License Renewal")
        with c2:
            department = st.selectbox("Assign to Department", db.DEPARTMENTS)
            classification = st.selectbox("Classification", db.CLASSIFICATIONS,
                                           help="Internal / External / Regulatory — per SOW §2.4")
            security_level = st.selectbox("Security Level", db.SECURITY_LEVELS)
            language = st.selectbox("Language", ["English", "Arabic"])
            copies = st.multiselect("Distribute copies to units", rfp_data.DEPARTMENTS)
        body = st.text_area("Content / Notes (captured text)", height=120,
                             placeholder="Paste or type the letter content — this becomes searchable full text.")
        auto = st.checkbox("📬 Route automatically by content (overrides the department above when a distribution rule matches)", value=True)
        _dtype = {"Memo": "Memo", "Circular": "Circular", "Email": "Memo"}.get(kind, "Regulatory Letter" if classification == "Regulatory" else "Letter")
        _num, _why = numbering.peek(department, _dtype, classification, security_level)
        st.markdown(f"""<div class="efs-card" style="display:flex;align-items:center;gap:14px;padding:10px 16px;margin:6px 0">
        <span style="font-size:1.4rem">🔢</span><div><div style="font-size:.72rem;color:#6B7280">REFERENCE NUMBER THAT WILL BE ISSUED</div>
        <div style="font-size:1.35rem;font-weight:800;color:#1F3864;letter-spacing:.04em">{_num}</div>
        <div style="font-size:.72rem;color:#6B7280">{_why}</div></div></div>""", unsafe_allow_html=True)
        submitted = st.button("Register Correspondence", type="primary")

    if submitted:
        if not subject:
            st.error("Subject is required.")
        else:
            meta = extract_metadata(body) if body else {}
            title = auto_name(meta, subject)
            doc_id, code = db.create_document(
                title=title or subject, department=department, classification=classification,
                security_level=security_level,
                doc_type={"Memo": "Memo", "Circular": "Circular", "Email": "Memo"}.get(kind, "Regulatory Letter" if classification == "Regulatory" else "Letter"),
                source="Postal" if channel.startswith("Postal") else "Email",
                language=language, body_text=body or subject,
                created_by=theme.current_user(), sender=sender, recipient=recipient,
            )
            db.log_correspondence(doc_id, direction, channel, sender, recipient, subject,
                                   theme.current_user())
            st.session_state["last_intake_doc"] = doc_id
            routed = None
            if auto:
                routed = dist.distribute(doc_id, theme.current_user(), apply_dept=True, notify=True)
            for n, p in rfp_data.ROLES.items():
                if not routed or not routed["hits"]:
                  if p["dept"] in copies or p["dept"] == department:
                      db_ext.notify(n, f"New {classification.lower()} {kind.lower()} registered: {code} — {subject}", doc_id, "info")
            if copies:
                db.log_audit(doc_id, theme.current_user(), "Copies Distributed", "Copies sent to: " + ", ".join(copies))
            if direction == "Outgoing":
                db_ext.create_dispatch(doc_id, classification, kind, recipient, ", ".join(copies), theme.current_user())
            if routed and routed["hits"]:
                st.success(f"✅ Registered as **{code}** — auto-routed to **{routed['primary']}**"
                           + (f", copies to {', '.join(routed['copies'])}" if routed["copies"] else "") + f" (rule: {routed['hits'][0]['rule']['name']}).")
            else:
                st.success(f"✅ Registered as **{code}** — routed to {department} for review." + (" No distribution rule matched, so it is in the triage queue." if auto else ""))
            if meta:
                st.caption("Auto-extracted metadata: " + ", ".join(f"**{k}**: {v}" for k, v in meta.items()))

    if "last_intake_doc" in st.session_state:
        doc = db.get_document(st.session_state["last_intake_doc"])
        if doc:
            st.markdown("---")
            st.markdown('<div class="efs-section-title">🔖 Document Number & QR Verification</div>',
                         unsafe_allow_html=True)
            cc1, cc2 = st.columns([2, 1])
            with cc1:
                st.markdown(f"""
                <div class="efs-card">
                <b>Document Code:</b> {doc['doc_code']}<br>
                <b>Status:</b> {theme.pill(doc['status'])}<br>
                <b>Department:</b> {doc['department']} &nbsp;|&nbsp; <b>Classification:</b> {doc['classification']}<br>
                <b>Registered by:</b> {doc['created_by']} on {doc['created_at']}
                </div>
                """, unsafe_allow_html=True)
                st.info("A QR verification code is generated automatically once the document is **released** "
                        "(see Workflow & Approvals, then Document Control). This proves the document is a "
                        "true copy at point of use.")
            with cc2:
                st.page_link("wg4_workflow.py", label="→ Continue to Workflow & Approvals")

with tabD:
    prof = theme.current_profile()
    me = theme.current_user()
    st.markdown(f"{theme.tag_custom('Draft on the fly')} {theme.tag_ms('Exports a real Word (.docx) file')}", unsafe_allow_html=True)
    st.caption("Pick a template, fill in a few fields and the letter writes itself — with the next reference number, date and signature block. "
               "Edit the wording if needed, download it as Word, or register it straight away so it enters approval and the dispatch tracker.")
    tpls = lt.templates()
    labels = {t["id"]: f"{t['name']}  ·  {t['language']}  ·  {t['category']}" for t in tpls}
    d1, d2 = st.columns([2, 1])
    tid = d1.selectbox("Template", [t["id"] for t in tpls], format_func=lambda x: labels[x], key="dr_tpl")
    T = next(t for t in tpls if t["id"] == tid)
    rtl = T["language"] == "Arabic"
    kx = f"dr_{tid}_"
    f1, f2, f3 = st.columns(3)
    recipient_name = f1.text_input("Recipient name / title", key=kx + "rn", placeholder="e.g. Director of Licensing")
    recipient_org = f2.text_input("Recipient organisation", key=kx + "ro", placeholder="e.g. Ministry of Public Health")
    subject = f3.text_input("Subject", key=kx + "sj", value=None, placeholder=lt.render(T["subject_default"], {}).replace("[", "").replace("]", ""))
    g1, g2, g3, g4 = st.columns(4)
    d_dept = g1.selectbox("Department (letterhead & ownership)", db.DEPARTMENTS, index=db.DEPARTMENTS.index(prof["dept"]) if prof["dept"] in db.DEPARTMENTS else 0, key=kx + "dp")
    d_class = g2.selectbox("Classification", db.CLASSIFICATIONS, index=(2 if T["category"] == "Regulatory" else (1 if "External" in T["category"] else 0)), key=kx + "cl")
    d_sec = g3.selectbox("Security level", db.SECURITY_LEVELS, index=1, key=kx + "sc")
    d_sign = g4.text_input("Signatory", me, key=kx + "sg")
    extra = lt.custom_fields(T["body"], T["subject_default"])
    vals = {"recipient_name": recipient_name, "recipient_org": recipient_org, "department": d_dept, "sender_name": d_sign, "sender_title": prof["role"],
            "date": __import__("datetime").date.today().strftime("%d %B %Y")}
    if extra:
        st.markdown("**Template fields**")
        cols = st.columns(min(3, len(extra)))
        for i, f_ in enumerate(extra):
            if f_ in ("main_message",):
                continue
            vals[f_] = cols[i % len(cols)].text_input(lt.label(f_), key=kx + f_)
        if "main_message" in extra:
            vals["main_message"] = st.text_area("Main message", key=kx + "main_message", height=100, placeholder="Write the key paragraph — the rest of the letter is already drafted.")
    vals["subject"] = lt.render(subject or T["subject_default"], vals)
    _dt = "Regulatory Letter" if T["category"] == "Regulatory" else {"Internal memo": "Memo", "Circular": "Circular"}.get(T["category"], "Letter")
    ref_prev, ref_why = numbering.peek(d_dept, _dt, d_class, d_sec)
    vals["ref_no"] = ref_prev
    rendered = lt.render(T["body"], vals)
    ed_key = kx + "edit_" + str(abs(hash(rendered)) % 10**8)
    p1, p2 = st.columns([1.15, 1])
    with p1:
        st.markdown('<div class="efs-section-title">Live preview</div>', unsafe_allow_html=True)
        final_text = st.session_state.get(ed_key, rendered)
        st.markdown(lt.preview_html(T["heading"], vals, final_text, rtl), unsafe_allow_html=True)
    with p2:
        st.markdown('<div class="efs-section-title">Edit & issue</div>', unsafe_allow_html=True)
        st.text_area("Edit the final wording (optional)", rendered, height=300, key=ed_key)
        st.caption(f"🔢 Reference **{ref_prev}** will be issued on registration · {ref_why}")
        missing = [f_ for f_ in extra if not (vals.get(f_) or "").strip()]
        if missing:
            st.info("Still blank: " + ", ".join(lt.label(m) for m in missing) + " (shown as [placeholders] in the draft).")
        st.download_button("⬇ Download draft as Word (.docx)", lt.build_docx(T["heading"], dict(vals, ref_no=ref_prev + " (draft)"), st.session_state.get(ed_key, rendered), rtl),
                           file_name="Draft_" + (T["name"].split(" ")[0] or "letter") + ".docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        if st.button("💾 Register & issue reference number", type="primary", use_container_width=True, key=kx + "reg"):
            if not (vals["recipient_name"] and vals["subject"] and not vals["subject"].startswith("[")):
                st.error("Recipient and subject are required before registering.")
            else:
                direction = "Internal" if T["category"] in ("Internal memo", "Circular") else "Outgoing"
                body_now = st.session_state.get(ed_key, rendered)
                doc_id, code = db.create_document(vals["subject"], d_dept, d_class, d_sec, _dt, "Drafted", T["language"], body_now, me,
                                                  sender=d_sign, recipient=f"{recipient_name} — {recipient_org}".strip(" —"))
                vals["ref_no"] = code
                final_body = body_now.replace(ref_prev, code)
                db.update_document_text(doc_id, final_body, me, "Final reference number applied to drafted letter")
                docx_bytes = lt.build_docx(T["heading"], vals, final_body, rtl)
                ix.store_file(doc_id, f"{code.replace('/', '-')}.docx", docx_bytes, "Drafted from template", me)
                db.log_correspondence(doc_id, direction, "Drafted in EDMS", d_sign, vals["recipient_name"], vals["subject"], me)
                db.log_audit(doc_id, me, "Drafted from Template", f"Template: {T['name']}")
                if direction == "Outgoing":
                    db_ext.create_dispatch(doc_id, d_class, "Letter", vals["recipient_name"], "", me)
                st.session_state["draft_done"] = (doc_id, code, docx_bytes, direction)
                st.rerun()
    if st.session_state.get("draft_done"):
        did_, code_, bytes_, dir_ = st.session_state["draft_done"]
        st.success(f"✅ Registered as **{code_}** ({dir_.lower()}). It is now in the approval workflow" + (" and the Outgoing Dispatch Tracker." if dir_ == "Outgoing" else "."))
        st.download_button("⬇ Download the registered Word letter", bytes_, file_name=f"{code_.replace('/', '-')}.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_done")

    with st.expander("🧩 Manage templates — create your own, or upload a Word file as a template"):
        st.caption("Use {{placeholders}} anywhere in the text, e.g. {{recipient_name}}, {{deadline}}, {{contract_ref}}. Automatic ones: "
                   "{{ref_no}}, {{date}}, {{sender_name}}, {{sender_title}}, {{department}}, {{subject}}. Any other name becomes a form field.")
        allt = lt.templates(active_only=False)
        pick = st.selectbox("Edit template", [None] + [t["id"] for t in allt], format_func=lambda x: "➕ New template" if x is None else
                            f"{next(t for t in allt if t['id'] == x)['name']}" + ("" if next(t for t in allt if t['id'] == x)["active"] else "  (disabled)"), key="tm_pick")
        C = next((t for t in allt if t["id"] == pick), None)
        km = f"tm_{pick}_"
        up = st.file_uploader("…or start from a Word file (.docx) — its text and {{placeholders}} are imported", type=["docx"], key=km + "up")
        if up is not None and st.session_state.get(km + "up_done") != up.file_id:
            st.session_state[km + "body"] = lt.parse_docx(up.getvalue())
            st.session_state[km + "name"] = up.name.rsplit(".", 1)[0]
            st.session_state[km + "up_done"] = up.file_id
        m1, m2, m3 = st.columns(3)
        t_name = m1.text_input("Template name", C["name"] if C else "", key=km + "name")
        cats = ["External letter", "Regulatory", "Internal memo", "Circular"]
        t_cat = m2.selectbox("Category", cats, index=cats.index(C["category"]) if C and C["category"] in cats else 0, key=km + "cat")
        t_lang = m3.selectbox("Language", ["English", "Arabic"], index=(1 if C and C["language"] == "Arabic" else 0), key=km + "lang")
        m4, m5 = st.columns(2)
        t_head = m4.text_input("Document heading", C["heading"] if C else "OFFICIAL LETTER", key=km + "head")
        t_subj = m5.text_input("Default subject", C["subject_default"] if C else "{{topic}}", key=km + "subj")
        t_body = st.text_area("Template text", C["body"] if C else "Dear {{recipient_name}},\n\n{{main_message}}\n\nYours sincerely,", height=200, key=km + "body")
        st.caption("Fields detected: " + (", ".join(lt.label(x) for x in lt.custom_fields(t_body, t_subj)) or "none"))
        b1, b2, _ = st.columns([1, 1, 2])
        if b1.button("💾 Save template", disabled=not t_name.strip() or not t_body.strip(), key=km + "save"):
            lt.save_template(pick, t_name.strip(), t_cat, t_lang, t_head, t_subj, t_body, "Word upload" if up is not None else (C["source"] if C else "Custom"), theme.current_user())
            st.success("Template saved.")
            st.rerun()
        if C and b2.button("⏸ Disable" if C["active"] else "▶ Enable", key=km + "tog"):
            lt.set_active(pick, not C["active"], theme.current_user())
            st.rerun()

with tabU:
    me = theme.current_user()
    st.markdown(f"{theme.tag_custom('Bulk intake')} {theme.tag_ms('OCR English + Arabic · PDF · Word')}", unsafe_allow_html=True)
    st.caption("Scanned or electronic correspondence can be added from your own computer, or picked up automatically from a shared scan folder where the "
               "scanner / MFP saves its files. Each file is read (OCR for images and scanned PDFs), named, classified, routed by the distribution rules and "
               "numbered — and the original file is kept with the record.")
    u1, u2, u3 = st.columns([1.3, 1, 1])
    u_dir = u1.selectbox("Register as", ["Incoming", "Internal"], key="up_dir")
    u_auto = u2.checkbox("📬 Route automatically by content", value=True, key="up_auto")
    u_dept = u3.selectbox("Default department", db.DEPARTMENTS, key="up_dept", help="Used when no distribution rule matches.")
    st.markdown('<div class="efs-section-title">📤 From your computer</div>', unsafe_allow_html=True)
    ups = st.file_uploader("Choose scanned letters, PDFs or Word files (several at once)", type=["png", "jpg", "jpeg", "pdf", "docx", "txt"],
                           accept_multiple_files=True, key="up_files")
    if ups and st.button(f"📥 Register {len(ups)} file(s)", type="primary", key="up_go"):
        with st.spinner("Reading and registering…"):
            st.session_state["up_results"] = [ix.register_file(f.name, f.getvalue(), me, "Upload from user's computer", u_dir, u_auto, u_dept) for f in ups]
    st.markdown('<div class="efs-section-title">🗄️ From the shared scan folder (network share / watch folder)</div>', unsafe_allow_html=True)
    fcol1, fcol2 = st.columns([3, 1])
    path_in = fcol1.text_input("Folder path on the server", ix.folder(), disabled=not theme.is_admin(),
                               help="Production example: a mounted network share such as /mnt/scans or \\\\fileserver\\scans. Only Administrators can change it.")
    if theme.is_admin() and path_in != ix.folder() and fcol2.button("Save path", key="fold_save"):
        ix.set_folder(path_in, me)
        st.rerun()
    fl = ix.list_folder()
    ac1, ac2 = st.columns([1, 3])
    if ac1.button("🖨 Simulate scanner → folder (demo)", key="fold_demo"):
        n_ = ix.drop_samples()
        st.toast(f"{n_} scanned page(s) saved to the shared folder")
        st.rerun()
    ac2.caption("In the demo this copies sample scanned letters into the folder, as if the office scanner had just saved them there.")
    if fl:
        st.dataframe(pd.DataFrame([{"File": f_["name"], "Size (KB)": round(f_["size"] / 1024, 1),
                                    "Saved": __import__("datetime").datetime.fromtimestamp(f_["mtime"]).strftime("%Y-%m-%d %H:%M")} for f_ in fl]),
                     hide_index=True, use_container_width=True)
        chosen = st.multiselect("Import only these (leave empty = all)", [f_["name"] for f_ in fl], key="fold_sel")
        if st.button(f"📥 Import {len(chosen) or len(fl)} file(s) from the folder", type="primary", key="fold_go"):
            with st.spinner("Reading, routing and registering…"):
                st.session_state["up_results"] = ix.import_folder(me, chosen or None, u_auto)
            st.rerun()
    else:
        st.info(f"The folder `{ix.folder()}` has no new files. Use ‘Simulate scanner → folder’ to see it work.")
    if st.session_state.get("up_results"):
        st.markdown("**Result**")
        st.dataframe(pd.DataFrame(st.session_state["up_results"]).rename(columns={"file": "File", "status": "Status", "code": "Reference", "routed": "Routed to",
                                                                                 "method": "Text read by", "words": "Words"}), hide_index=True, use_container_width=True)
        st.caption("Registered files appear in the Register tab (with the original file attached), in Search & Retrieval, and in the routing log of Auto-Distribution.")

with tab2:
    corr = db.get_correspondence(limit=1000)
    files_map = ix.files_by_doc()
    conn_ = db.get_conn()
    dept_of = {r["id"]: r["department"] for r in conn_.execute("SELECT id, department FROM documents").fetchall()}
    conn_.close()
    st.markdown('<div class="efs-section-title">🔎 Search the register</div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([2.4, 1, 1.3, 1])
    q = f1.text_input("Search", placeholder="Reference number (any style, e.g. FIN/2611, REG/2026, MRN-01), subject, sender or recipient",
                      key="reg_q", label_visibility="collapsed")
    fdir = f2.selectbox("Direction", ["All", "Incoming", "Outgoing", "Internal"], key="reg_dir")
    fdep = f3.selectbox("Department", ["All"] + rfp_data.DEPARTMENTS, key="reg_dep")
    fst = f4.selectbox("Status", ["All"] + sorted({r["status"] for r in corr if r["status"]}), key="reg_st")

    def _norm(x):
        return "".join(ch for ch in (x or "").lower() if ch.isalnum())
    terms = [t for t in (q or "").lower().split() if t]
    def _hit(r):
        hay = " ".join(str(r[k] or "") for k in ("doc_code", "subject", "sender", "recipient", "channel", "logged_by")).lower()
        hay_n = _norm(hay)
        return all(t in hay or _norm(t) in hay_n for t in terms)
    corr = [r for r in corr if _hit(r) and (fdir == "All" or r["direction"] == fdir) and (fst == "All" or r["status"] == fst)
            and (fdep == "All" or dept_of.get(r["document_id"]) == fdep)]
    st.markdown(f"**{len(corr)}** correspondence entries" + (f" matching “{q}”" if q else " logged"))
    if corr:
        for r in corr[:50]:
            c1, c2, c3 = st.columns([0.5, 3, 1])
            with c1:
                icon = "📨" if r["direction"] == "Incoming" else "📤"
                st.markdown(f"<div style='font-size:1.4rem'>{icon}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{r['subject']}** — `{r['doc_code']}`  \n"
                             f"<span style='color:#6B7280;font-size:0.85rem'>"
                             f"{r['direction']} · {r['channel']} · {r['sender']} → {r['recipient']} · "
                             f"{dept_of.get(r['document_id'], '')} · logged by {r['logged_by']} at {r['logged_at']}</span>",
                             unsafe_allow_html=True)
            with c3:
                st.markdown(theme.pill(r["status"]), unsafe_allow_html=True)
                for fx in files_map.get(r["document_id"], [])[:2]:
                    fr = ix.get_file(fx["id"])
                    st.download_button(f"📎 {fx['filename'][:22]}", fr["data"], file_name=fx["filename"], mime=fr["mime"], key=f"fl_{fx['id']}")
            st.divider()
    else:
        st.info("No correspondence matches." if (q or fdir != "All" or fdep != "All" or fst != "All") else "No correspondence registered yet. Use the form above to log one.")

with tab3:
    st.markdown('<div class="efs-section-title">Controlled dispatch — approval → release → recipient</div>', unsafe_allow_html=True)
    st.caption("Outgoing items are tracked through Drafted → Approved → Released → Dispatched, with who approved and "
               "released each one, by category (internal / external / regulatory).")
    rows = db_ext.list_dispatch()
    cats = st.multiselect("Category", ["Internal", "External", "Regulatory"], default=["Internal", "External", "Regulatory"])
    for x in [r for r in rows if r["category"] in cats]:
        steps = db_ext.DISPATCH_STEPS
        idx = steps.index(x["status"])
        html = '<div class="efs-stepper">' + '<span class="efs-arrow">→</span>'.join(
            f'<span class="efs-step {"done" if i < idx or x["status"] == "Dispatched" else ("active" if i == idx else "")}">{s_}</span>'
            for i, s_ in enumerate(steps)) + "</div>"
        st.markdown(f"""<div class="efs-card"><b>{x['doc_code']} — {x['title']}</b><br>
        {x['category']} · {x['kind']} → <b>{x['recipient']}</b>{' · cc: ' + x['copies_to'] if x['copies_to'] else ''}<br>
        <span style="font-size:0.8rem;color:#6B7280">approved by {x['approved_by'] or '—'} · released by {x['released_by'] or '—'} ·
        dispatched {x['dispatched_at'] or '—'}</span>{html}</div>""", unsafe_allow_html=True)
        if x["status"] != "Dispatched":
            nxt = steps[idx + 1]
            if st.button(f"Mark as {nxt}", key=f"disp_{x['id']}"):
                db_ext.advance_dispatch(x["id"], theme.current_user())
                st.rerun()
    if not rows:
        st.info("No outgoing items yet — register one with Direction = Outgoing.")
