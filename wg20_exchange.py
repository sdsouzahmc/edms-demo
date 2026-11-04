from datetime import date, timedelta

import pandas as pd
import streamlit as st
import db
import db_ext
import exchange as ex
import rfp_data
import theme

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("20 · Secure Exchange", "Department-to-department routing · secure share links for external bodies · secure upload requests")

user = theme.current_user()
prof = theme.current_profile()
admin = theme.is_admin()
dept = prof["dept"]
st.markdown(f"{theme.tag_custom('Inter-department & external workflows — every link expiring, code-protected, logged and revocable')}",
            unsafe_allow_html=True)

docs = [dict(d) for d in db.get_documents()]
_by = {d["id"]: d for d in docs}
doc_label = lambda i: f"{_by[i]['doc_code']} — {_by[i]['title']}"
all_links = ex.links()
m1, m2, m3, m4 = st.columns(4)
theme.metric_card("Inter-dept requests for me", ex.inbox_count(dept, admin), m1)
theme.metric_card("Active secure links", len([x for x in all_links if x["state"] == "Active"]), m2)
theme.metric_card("External uploads received", sum(x["uploads"] or 0 for x in all_links), m3)
theme.metric_card("Downloads by externals", sum(x["downloads"] or 0 for x in all_links), m4)
st.write("")


def _show_link(token, code, who, kind="link"):
    url = ex.link_url(token)
    st.success(f"Secure link created for **{who}**. Copy it now — for security it is shown only once.")
    st.code(url, language=None)
    if code:
        st.markdown(f"🔑 **Access code: `{code}`** — send it through a *different* channel (SMS / phone), never in the same message as the link.")
    st.caption("In production the portal sends the link by e-mail and the code by SMS automatically; this demo shows both here.")
    st.link_button("🌐 Open as the external recipient (new tab)", url)


tabs = st.tabs(["🏢 Send to Department(s)", "📥 My Department Inbox", "🌍 Send to External Body", "📤 Request Upload from External",
                "🛡 Links & Access Log", "ℹ️ How it is secured"])

# ================================================== send to departments ======
with tabs[0]:
    st.markdown('<div class="efs-section-title">Route a document to other departments for review / approval</div>', unsafe_allow_html=True)
    st.caption("Parallel = all departments receive it now. Sequential = one after another; a department only receives it after the previous one approves.")
    with st.container(border=True, key="tx_form"):
        sel = _by.get(st.selectbox("Document", list(_by), format_func=doc_label, key="tx_doc")) if docs else None
        c1, c2 = st.columns([2, 1])
        to = c1.multiselect("To department(s) — order matters for Sequential", [x for x in rfp_data.DEPARTMENTS if x != dept], key="tx_to")
        mode = c2.radio("Routing", ["Parallel", "Sequential"], horizontal=True, key="tx_mode")
        c3, c4 = st.columns([1, 1])
        act = c3.selectbox("Action required", ex.ACTIONS, key="tx_act")
        due = c4.date_input("Due date", value=date.today() + timedelta(days=5), key="tx_due")
        also_ext = st.checkbox("Also include an external party in this request", key="tx_ext")
        ext = None
        if also_ext:
            e1, e2, e3 = st.columns(3)
            en = e1.text_input("External contact name", key="tx_en")
            eo = e2.text_input("Organisation", key="tx_eo")
            ee = e3.text_input("E-mail", key="tx_ee")
            ext = {"name": en.strip(), "org": eo.strip(), "email": ee.strip(), "days": 7, "use_code": True}
        ins = st.text_area("Instructions", key="tx_ins", height=70, placeholder="e.g. Please confirm the contract terms are acceptable to your department.")
        ready = sel and (to or (also_ext and ext and ext["name"]))
        if st.button("📨 Send", type="primary", disabled=not ready, key="tx_send"):
            batch, einfo = ex.send_transmittal(sel["id"], user, to, act, due, ins, mode, ext if also_ext and ext and ext["name"] else None)
            st.session_state["tx_done"] = (batch, einfo, ext["name"] if einfo else "")
            st.rerun()
    done = st.session_state.get("tx_done")
    if done:
        st.success(f"Sent. Tracking reference **{done[0]}**.")
        if done[1]:
            _show_link(done[1]["token"], done[1]["code"], done[2])
        if st.button("Dismiss", key="tx_dismiss"):
            st.session_state.pop("tx_done")
            st.rerun()

    st.markdown('<div class="efs-section-title">Requests sent by my department</div>', unsafe_allow_html=True)
    sent = ex.transmittals(sent_by_dept=None if admin else dept)
    if not sent:
        st.info("Nothing sent yet.")
    else:
        icon = {"Pending": "🟡", "Waiting": "⏳", "Approved": "✅", "Reviewed": "✅", "Acknowledged": "✅", "Returned": "↩️", "Rejected": "❌", "Cancelled": "⚪"}
        df = pd.DataFrame([{"Ref": t["batch"], "Document": t["doc_code"], "From": t["from_dept"], "To": t["to_dept"] or f"{t['to_external']} (external)",
                            "Action": t["action"], "Routing": t["mode"], "Due": t["due_date"] or "",
                            "Status": f"{icon.get(t['status'], '')} {t['status']}", "Response": t["response"] or ""} for t in sent])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ================================================== inbox ====================
with tabs[1]:
    inbox = ex.transmittals(None if admin else dept, status=["Pending"])
    inbox = [t for t in inbox if t["to_dept"]]
    st.markdown(f"**{len(inbox)}** request(s) from other departments" + (" (all departments)" if admin else f" waiting for **{dept}**"))
    if not inbox:
        st.info("Nothing waiting. Send one from the first tab, then switch to a user in the receiving department.")
    for t in inbox:
        od = t["due_date"] and t["due_date"] < str(date.today())
        st.markdown(f"""<div class="efs-card"><b>{t['title']}</b> — {t['doc_code']}<br>
        From <b>{t['from_dept']}</b> ({t['from_user']}) → <b>{t['to_dept']}</b> · {t['action']} · {t['mode']}
        {(' · ⏰ due ' + t['due_date']) if t['due_date'] else ''}{' <b style="color:#B00020">· OVERDUE</b>' if od else ''}<br>
        <span style="color:#6B7280">{t['instructions'] or ''}</span></div>""", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 2])
        opts = ["Acknowledge"] if t["action"] == "Acknowledge receipt" else ["Approve", "Reviewed — no objection", "Return for changes", "Reject"]
        dec = c1.selectbox("Decision", opts, key=f"ib_dec_{t['id']}", label_visibility="collapsed")
        com = c2.text_input("Comment", key=f"ib_com_{t['id']}", placeholder="Comment (required when returning or rejecting)", label_visibility="collapsed")
        need = dec in ("Return for changes", "Reject") and not com.strip()
        if st.button("✍ Submit response", key=f"ib_go_{t['id']}", type="primary", disabled=need):
            sig = db_ext.log_esign(t["document_id"], user, f"Inter-dept: {dec}")
            ex.respond(t["id"], user, dec, (com or "").strip())
            st.toast(f"Response recorded · e-signature {sig}")
            st.rerun()
        st.divider()

# ================================================== external download ========
with tabs[2]:
    st.markdown('<div class="efs-section-title">Share a document with someone outside the organisation</div>', unsafe_allow_html=True)
    st.caption("They need no account. The link expires, is protected by a separate access code, delivers a watermarked PDF copy and every action is logged.")
    with st.container(border=True, key="ext_form"):
        sel2 = _by.get(st.selectbox("Document", list(_by), format_func=doc_label, key="ex_doc")) if docs else None
        a1, a2, a3 = st.columns(3)
        rn = a1.text_input("Recipient name", key="ex_rn")
        ro = a2.text_input("Organisation / authority", key="ex_ro")
        re_ = a3.text_input("Recipient e-mail", key="ex_re")
        b1, b2, b3 = st.columns(3)
        exp = b1.selectbox("Link expires after", list(ex.EXPIRY_CHOICES), index=2, key="ex_exp")
        mx = b2.number_input("Max downloads", 1, 20, 3, key="ex_mx")
        mode2 = b3.radio("Type", ["View / download only", "Needs their approval / response"], key="ex_mode")
        c1, c2 = st.columns(2)
        use_code = c1.checkbox("Require access code (recommended)", value=True, key="ex_code")
        wm = c2.checkbox("Watermark the copy with recipient name & date", value=True, key="ex_wm")
        purpose = st.text_input("Message shown to the recipient", key="ex_purpose", placeholder="e.g. Final licence documents for your review")
        ack = False
        if sel2 and sel2["classification"] in ("Confidential", "Restricted"):
            st.warning(f"⚠️ {sel2['doc_code']} is classified **{sel2['classification']}**. External sharing is recorded and should be authorised by the owner.")
            ack = st.checkbox("I have authority to share this document externally", key="ex_ack")
        ok = bool(sel2 and rn.strip()) and (ack or not (sel2 and sel2["classification"] in ("Confidential", "Restricted")))
        if st.button("🔗 Create secure link", type="primary", disabled=not ok, key="ex_go"):
            if mode2.startswith("Needs"):
                batch, info = ex.send_transmittal(sel2["id"], user, [], "Review & comment", date.today() + timedelta(days=ex.EXPIRY_CHOICES[exp]),
                                                  purpose, "Parallel", {"name": rn.strip(), "org": ro.strip(), "email": re_.strip(),
                                                                       "days": ex.EXPIRY_CHOICES[exp], "use_code": use_code})
                st.session_state["ex_done"] = (info["token"], info["code"], rn.strip())
            else:
                tok, code, _ = ex.create_link("download", user, rn.strip(), re_.strip(), ro.strip(), purpose, sel2["id"],
                                              ex.EXPIRY_CHOICES[exp], int(mx), use_code, wm)
                st.session_state["ex_done"] = (tok, code, rn.strip())
            st.rerun()
    d2 = st.session_state.get("ex_done")
    if d2:
        _show_link(*d2)
        if st.button("Done", key="ex_dismiss"):
            st.session_state.pop("ex_done")
            st.rerun()

# ================================================== upload request ===========
with tabs[3]:
    st.markdown('<div class="efs-section-title">Ask an external party to upload documents to us</div>', unsafe_allow_html=True)
    st.caption("They upload through a private link — no e-mail attachments. Files are type- and size-checked, registered as incoming correspondence "
               "in the department you choose, and a receipt number is returned.")
    with st.container(border=True, key="up_form"):
        u1, u2, u3 = st.columns(3)
        un = u1.text_input("Who will upload (name)", key="up_n")
        uo = u2.text_input("Organisation", key="up_o")
        ue = u3.text_input("E-mail", key="up_e")
        v1, v2, v3 = st.columns(3)
        ud = v1.selectbox("Deliver into department", rfp_data.DEPARTMENTS, index=rfp_data.DEPARTMENTS.index(dept) if dept in rfp_data.DEPARTMENTS else 0, key="up_d")
        uexp = v2.selectbox("Link expires after", list(ex.EXPIRY_CHOICES), index=2, key="up_exp")
        umb = v3.number_input("Max size per file (MB)", 1, 10, 10, key="up_mb")
        ucode = st.checkbox("Require access code (recommended)", value=True, key="up_code")
        unote = st.text_area("What should they upload?", key="up_note", height=70,
                             placeholder="e.g. Signed contract, trade licence copy and insurance certificate.")
        if st.button("🔗 Create upload link", type="primary", disabled=not un.strip(), key="up_go"):
            tok, code, _ = ex.create_link("upload", user, un.strip(), ue.strip(), uo.strip(), "Upload request", None,
                                          ex.EXPIRY_CHOICES[uexp], None, ucode, False, ud, unote, int(umb))
            st.session_state["up_done"] = (tok, code, un.strip())
            st.rerun()
    d3 = st.session_state.get("up_done")
    if d3:
        _show_link(*d3)
        if st.button("Done", key="up_dismiss"):
            st.session_state.pop("up_done")
            st.rerun()

# ================================================== links & log ==============
with tabs[4]:
    st.markdown('<div class="efs-section-title">All secure links</div>', unsafe_allow_html=True)
    flt = st.multiselect("Show", ["Active", "Expired", "Revoked", "Locked", "Used up"], default=["Active", "Locked"], key="lk_flt")
    rows = [x for x in all_links if x["state"] in flt and (admin or x["created_by"] == user)]
    if not rows:
        st.info("No links match.")
    for x in rows:
        col = {"Active": "#2E7D32", "Expired": "#6B7280", "Revoked": "#B00020", "Locked": "#B8860B", "Used up": "#6B7280"}[x["state"]]
        kind = {"download": "⬇ Share", "review": "✍ Review", "upload": "⬆ Upload request"}[x["kind"]]
        what = x["doc_code"] if x["doc_code"] else f"→ {x['upload_dept']}"
        use = f"{x['uploads']} upload(s)" if x["kind"] == "upload" else f"{x['downloads']}/{x['max_downloads']} downloads"
        st.markdown(f"""<div class="efs-card" style="border-left:5px solid {col}"><b>{kind}</b> · {what} · <b>{x['recipient_name']}</b>
        {(' — ' + x['recipient_org']) if x['recipient_org'] else ''}
        <span style="background:{col};color:#fff;border-radius:10px;padding:1px 9px;font-size:.75rem;margin-inline-start:8px">{x['state']}</span><br>
        <span style="color:#6B7280;font-size:.8rem">by {x['created_by']} · expires {x['expires_at'][:16]} · {use} · link …{x['token_hint']}
        {' · 🔑 code' if x['code_hash'] else ' · ⚠ no code'}</span></div>""", unsafe_allow_html=True)
        if x["state"] in ("Active", "Locked") and (admin or x["created_by"] == user):
            if st.button("⛔ Revoke now", key=f"rv_{x['id']}"):
                ex.revoke(x["id"], user)
                st.rerun()
    st.markdown('<div class="efs-section-title">Access log (every open, wrong code, download, upload, response)</div>', unsafe_allow_html=True)
    ev = ex.events()
    if admin or True:
        mine = {x["id"] for x in all_links if admin or x["created_by"] == user}
        ev = [e for e in ev if e["link_id"] in mine]
    if ev:
        st.dataframe(pd.DataFrame([{"Time": e["ts"], "Link": f"{e['kind']} · {e['recipient_name']} …{e['token_hint']}", "Event": e["event"], "Detail": e["detail"]} for e in ev]),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("No external activity yet.")
    if admin:
        with st.expander("Settings — public address used in links"):
            nb = st.text_input("Public base URL", value=ex.base_url(), key="st_base")
            if st.button("Save address", key="st_base_go"):
                ex.set_base_url(nb, user)
                st.success("Saved.")

# ================================================== security =================
with tabs[5]:
    st.markdown("""
**How an external link is protected**

| Control | What it does |
|---|---|
| Unguessable token | 192-bit random link; only a hash is stored, so a database leak cannot reveal live links |
| Expiry | 1–30 days, then the link stops working by itself |
| Separate access code | 6-digit code delivered on another channel; 5 wrong tries lock the link for 15 minutes |
| Download limit | Maximum number of downloads, then the link is “used up” |
| Controlled copy | The recipient gets a PDF watermarked with their name, date and link ID — leaks can be traced |
| Revoke | The owner or Administrator can withdraw a link instantly |
| Upload checks | Allowed file types only, size limit, file content must match its extension, names sanitised |
| Full audit | Every open, failed code, download, upload and response is logged against the link and the document |
| Sensitive documents | Confidential / Restricted documents need an explicit “I have authority” confirmation |

**Demo notes:** the access code is displayed to the sender instead of being sent by SMS, and the file check is a type/size/content check — a production deployment
adds an SMTP/SMS gateway and an anti-virus engine (e.g. ClamAV) in front of the upload.
    """)
