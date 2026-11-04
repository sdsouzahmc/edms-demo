"""Public secure-exchange portal. Opened with ?x=<token>; no EDMS login. Reached from app.py before any page runs."""
import streamlit as st
import db
import db_ext
import exchange as ex
import theme


def _fmt_exp(l):
    return l["expires_at"][:16]


def _msg(title, body, icon="🔒"):
    st.markdown(f"""<div class="xp-card" style="text-align:center"><div style="font-size:2.4rem">{icon}</div>
    <h3 style="margin:.3rem 0">{theme.tr(title)}</h3><div style="color:#6B7280">{theme.tr(body)}</div></div>""", unsafe_allow_html=True)


def render(token):
    theme.inject_css()
    st.markdown("""<style>
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {display:none !important}
    .block-container {max-width: 760px; padding-top: 1.2rem}
    .xp-head {background:linear-gradient(120deg,#1F3864,#2E8B8B); color:#fff; border-radius:16px; padding:18px 22px; margin-bottom:16px}
    .xp-head h2 {margin:0; color:#fff; font-size:1.3rem}
    .xp-head div {opacity:.85; font-size:.85rem}
    .xp-card {background:#fff; border:1px solid #E2E6EC; border-radius:14px; padding:18px 20px; margin:10px 0; box-shadow:0 1px 6px rgba(31,56,100,.06)}
    .xp-kv {display:flex; gap:8px; flex-wrap:wrap; margin-top:8px}
    .xp-kv span {background:#EEF3F8; border-radius:10px; padding:3px 10px; font-size:.78rem; color:#1F3864}
    </style>""", unsafe_allow_html=True)
    c1, c2 = st.columns([4, 1])
    c2.selectbox("Language", ["English", "العربية"], index=1 if theme.lang() == "ar" else 0, key="xp_lang", label_visibility="collapsed",
                 on_change=lambda: st.session_state.update(lang="ar" if st.session_state["xp_lang"] == "العربية" else "en"))
    st.markdown(f"""<div class="xp-head"><h2>🔐 {theme.tr('Secure Document Exchange')}</h2>
    <div>{theme.tr('Encrypted in transit · access is logged · links expire automatically')}</div></div>""", unsafe_allow_html=True)

    l = ex.by_token(token)
    if not l:
        _msg("This link is not valid", "Check that you copied the whole link, or ask the sender to issue a new one.", "⚠️")
        return
    s = ex.state(l)
    if s in ("Revoked", "Expired", "Used up"):
        ex.log(l["id"], "Blocked", f"link is {s.lower()}")
        _msg({"Revoked": "This link has been withdrawn", "Expired": "This link has expired", "Used up": "The download limit has been reached"}[s],
             "Please contact the sender to request a new link.", "⛔")
        return
    if s == "Locked":
        _msg("Link temporarily locked", f"Too many wrong access codes. Try again after {l['locked_until'][11:16]}.")
        return

    okkey = f"x_ok_{l['id']}"
    if l["code_hash"] and not st.session_state.get(okkey):
        st.markdown(f"<div class='xp-card'><b>{theme.tr('Enter the access code')}</b><br><span style='color:#6B7280;font-size:.85rem'>"
                    f"{theme.tr('The sender gave you a 6-digit code separately (SMS, phone or a second e-mail).')}</span></div>", unsafe_allow_html=True)
        code = st.text_input("Access code", type="password", max_chars=6, key="xp_code", label_visibility="collapsed", placeholder="••••••")
        if st.button("Unlock", type="primary", key="xp_unlock"):
            ok, msg = ex.check_code(l, code)
            if ok:
                st.session_state[okkey] = True
                st.rerun()
            else:
                st.error(theme.tr(msg))
        return
    if not st.session_state.get(f"x_open_{l['id']}"):
        ex.log(l["id"], "Opened", "")
        st.session_state[f"x_open_{l['id']}"] = True
        db.log_audit(l["document_id"], f"External: {l['recipient_name']}", "Secure Link Opened", f"link …{l['token_hint']}")

    st.markdown(f"""<div class="xp-card">{theme.tr('Prepared for')} <b>{l['recipient_name']}</b>{(' · ' + l['recipient_org']) if l['recipient_org'] else ''}
    <div class="xp-kv"><span>⏳ {theme.tr('Valid until')} {_fmt_exp(l)}</span><span>🔒 {theme.tr('Confidential')}</span></div></div>""", unsafe_allow_html=True)

    if l["kind"] in ("download", "review"):
        _download_view(l)
    if l["kind"] == "review":
        _review_view(l)
    if l["kind"] == "upload":
        _upload_view(l)


def _download_view(l):
    d = db.get_document(l["document_id"])
    left = (l["max_downloads"] - l["downloads"]) if l["max_downloads"] is not None else None
    st.markdown(f"""<div class="xp-card"><b>{d['title']}</b><br><span style="color:#6B7280">{d['doc_code']}</span>
    <div class="xp-kv"><span>🏢 {d['department']}</span><span>📄 PDF</span>{('<span>⬇ ' + str(left) + ' ' + theme.tr('download(s) left') + '</span>') if left is not None else ''}
    {('<span>💧 ' + theme.tr('Watermarked with your name') + '</span>') if l['watermark'] else ''}</div>
    {('<p style="margin:10px 0 0;color:#374151">' + l['purpose'] + '</p>') if l['purpose'] else ''}</div>""", unsafe_allow_html=True)
    if left is not None and left <= 0:
        st.warning(theme.tr("The download limit has been reached."))
        return
    data, fname = ex.controlled_copy(l["document_id"], l)
    st.download_button("⬇ " + theme.tr("Download document"), data, file_name=fname, mime="application/pdf", type="primary",
                       key=f"xp_dl_{l['id']}", on_click=ex.count_download, args=(l,))


def _review_view(l):
    import sqlite3
    conn = db.get_conn()
    t = conn.execute("SELECT * FROM transmittals WHERE id=?", (l["transmittal_id"],)).fetchone()
    conn.close()
    if not t:
        return
    st.markdown(f"<div class='xp-card'><b>{theme.tr('Your response is requested')}</b> — {theme.tr(t['action'])}"
                f"{(' · ' + theme.tr('due') + ' ' + t['due_date']) if t['due_date'] else ''}<br>"
                f"<span style='color:#374151'>{t['instructions'] or ''}</span></div>", unsafe_allow_html=True)
    if t["status"] == "Waiting":
        st.info(theme.tr("Your turn has not started yet — the previous reviewer is still working on it."))
        return
    if t["status"] != "Pending":
        st.success(f"{theme.tr('Response recorded')}: **{theme.tr(t['status'])}** · {t['responded_at']}")
        return
    opts = ["Approve", "Reviewed — no objection", "Return for changes", "Reject"] if t["action"] != "Acknowledge receipt" else ["Acknowledge"]
    dec = st.radio(theme.tr("Your decision"), opts, key="xp_dec", horizontal=True)
    com = st.text_area(theme.tr("Comments"), key="xp_com", height=90)
    nm = st.text_input(theme.tr("Type your full name to sign"), key="xp_sign")
    ok = st.checkbox(theme.tr("I confirm I am authorised to respond on behalf of my organisation."), key="xp_auth")
    if st.button(theme.tr("Submit response"), type="primary", key="xp_submit", disabled=not (nm.strip() and ok)):
        ex.respond(t["id"], f"{nm.strip()} ({l['recipient_name']})", dec, com, external=True)
        ex.log(l["id"], "Responded", f"{dec} by {nm.strip()}")
        st.rerun()


def _upload_view(l):
    st.markdown(f"""<div class="xp-card"><b>{theme.tr('Upload documents securely')}</b><br>
    <span style="color:#374151">{l['upload_note'] or theme.tr('Please upload the requested documents below.')}</span>
    <div class="xp-kv"><span>📎 {', '.join(ex.ALLOWED_EXT)}</span><span>📏 ≤ {l['max_mb']} MB</span></div></div>""", unsafe_allow_html=True)
    done = st.session_state.get(f"x_up_{l['id']}")
    if done:
        st.success(theme.tr("Thank you — your documents were received."))
        for r in done:
            ok = r["status"] == "Registered"
            st.markdown(f"{'✅' if ok else '⚠️'} **{r['file']}** — " + (f"{theme.tr('Receipt number')} `{r['code']}`" if ok else r["status"]))
        if st.button(theme.tr("Upload more"), key="xp_more"):
            st.session_state.pop(f"x_up_{l['id']}")
            st.rerun()
        return
    c1, c2 = st.columns(2)
    nm = c1.text_input(theme.tr("Your name"), value=l["recipient_name"] or "", key="xp_n")
    org = c2.text_input(theme.tr("Organisation"), value=l["recipient_org"] or "", key="xp_o")
    note = st.text_input(theme.tr("Note (optional)"), key="xp_note")
    files = st.file_uploader(theme.tr("Choose files"), accept_multiple_files=True, key="xp_files")
    st.caption(theme.tr("Files are scanned for type and size, stored encrypted and logged. You will get a receipt number for each file."))
    if st.button(theme.tr("Send securely"), type="primary", disabled=not (files and nm.strip()), key="xp_send"):
        res = [ex.receive_upload(l, f.name, f.getvalue(), nm.strip(), org.strip(), note.strip()) for f in files]
        st.session_state[f"x_up_{l['id']}"] = res
        st.rerun()
