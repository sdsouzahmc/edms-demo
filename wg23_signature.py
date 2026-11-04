import pandas as pd
import streamlit as st
import db
import db_ext
import signing as sg
import theme

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("23 · My Signature & Certificate", "Upload your handwritten signature · PIN-protected e-signature · digital certificate · verify signed documents")

user = theme.current_user()
st.markdown(f"{theme.tag_custom('E-signature + digital signature — RSA-2048 / SHA-256, certificate issued per user')}", unsafe_allow_html=True)
p = sg.ensure(user)
mine = sg.signatures(user=user)
a, b, c, d = st.columns(4)
theme.metric_card("Documents I signed", len(mine), a)
theme.metric_card("Signature type", p["kind"].title(), b)
theme.metric_card("Certificate valid until", p["valid_to"], c)
theme.metric_card("All signatures in EDMS", len(sg.signatures()), d)
st.write("")

t1, t2, t3, t4 = st.tabs(["✍️ My signature", "🔐 PIN & certificate", "📜 Documents I signed", "✅ Verify a document"])

# ------------------------------------------------------------------ signature --
with t1:
    if p["is_demo"]:
        st.info("You are using the **demo signature** (your name in script) and demo PIN **1234**. Upload your own handwritten signature below and set your own PIN.")
    c1, c2 = st.columns([1, 1.6])
    with c1:
        st.markdown('<div class="efs-section-title">Current signature</div>', unsafe_allow_html=True)
        st.markdown("<div class='efs-card' style='background:#fff;text-align:center'>", unsafe_allow_html=True)
        st.image(p["image"], width=260)
        st.markdown(f"<div style='color:#6B7280;font-size:.8rem'>{p['kind'].title()} · updated {p['updated_at'][:16]}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="efs-section-title">Change it</div>', unsafe_allow_html=True)
        how = st.radio("Method", ["Upload an image of my signature", "Generate from my typed name"], horizontal=True, key="sg_how")
        if how.startswith("Upload"):
            st.caption("Sign on white paper, take a photo or scan it, and upload (PNG or JPG). The white background is removed automatically.")
            up = st.file_uploader("Signature image", type=["png", "jpg", "jpeg"], key="sg_up")
            if up is not None:
                clean = sg.clean_signature_image(up.getvalue())
                st.image(clean, caption="Preview — as it will appear on documents", width=260)
                pin_ok = st.text_input("Confirm with your signature PIN", type="password", key="sg_up_pin")
                if st.button("💾 Use this signature", type="primary", key="sg_up_go"):
                    if sg.check_pin(user, pin_ok):
                        sg.replace_image(user, clean, "uploaded")
                        st.success("Signature updated.")
                        st.rerun()
                    else:
                        st.error("Incorrect PIN.")
        else:
            nm = st.text_input("Name to render", value=user, key="sg_typed")
            st.image(sg.typed_signature_png(nm), width=260)
            pin_ok = st.text_input("Confirm with your signature PIN", type="password", key="sg_ty_pin")
            if st.button("💾 Use this signature", type="primary", key="sg_ty_go"):
                if sg.check_pin(user, pin_ok):
                    sg.replace_image(user, sg.typed_signature_png(nm), "typed")
                    st.success("Signature updated.")
                    st.rerun()
                else:
                    st.error("Incorrect PIN.")
        st.caption("A pad for drawing the signature with a finger or mouse is a standard add-on for the production build.")

# ------------------------------------------------------------------ PIN / cert --
with t2:
    ci = sg.certificate_info(user)
    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown('<div class="efs-section-title">My digital certificate</div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="efs-card" style="line-height:1.8">
        <b>Subject</b> {ci['subject']}<br><b>Issuer</b> {ci['issuer']}<br><b>Serial</b> <code>{ci['serial']}</code><br>
        <b>Valid</b> {ci['from']} → {ci['to']}<br><b>Key</b> {ci['key']} · {ci['alg']}<br><b>Fingerprint (SHA-256)</b> <code>{ci['fingerprint']}…</code></div>""",
                    unsafe_allow_html=True)
        st.download_button("⬇ Download certificate (.pem)", ci["pem"], file_name=f"{user.replace(' ', '_')}_certificate.pem", mime="application/x-pem-file", key="sg_cert")
        st.caption("The private key never leaves the server in clear text: it is stored encrypted with your PIN, so a signature can only be made by someone who knows it.")
    with c2:
        st.markdown('<div class="efs-section-title">Change PIN</div>', unsafe_allow_html=True)
        old = st.text_input("Current PIN", type="password", key="sg_old")
        n1 = st.text_input("New PIN (4–12 characters)", type="password", key="sg_n1", max_chars=12)
        n2 = st.text_input("Repeat new PIN", type="password", key="sg_n2", max_chars=12)
        if st.button("🔐 Change PIN", key="sg_pin_go", disabled=not (old and n1 and n1 == n2 and len(n1) >= 4)):
            if sg.check_pin(user, old):
                sg.change_pin(user, old, n1)
                st.success("PIN changed.")
            else:
                st.error("Current PIN is incorrect.")

# ------------------------------------------------------------------ my signatures --
with t3:
    if not mine:
        st.info("You have not signed anything yet. Open Workflow & Approvals and use “Sign & Approve”.")
    else:
        rows = []
        for s in mine:
            stt, det = sg.verify(s)
            rows.append({"Document": s["doc_code"], "Title": s["title"], "Stage": s["stage"], "Meaning": s["meaning"], "On behalf of": s["on_behalf_of"] or "",
                         "Signed at": s["signed_at"], "Verification": {"Valid": "✅ Valid", "Document changed": "⚠ Document changed since", "Invalid": "❌ Invalid"}[stt]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ verify -------
with t4:
    allsig = sg.signatures()
    ids = sorted({s["document_id"] for s in allsig})
    if not ids:
        st.info("No signed documents yet.")
    else:
        lab = {s["document_id"]: f"{s['doc_code']} — {s['title']}" for s in allsig}
        did = st.selectbox("Signed document", ids, format_func=lambda i: lab[i], key="sg_vdoc")
        sigs = list(reversed(sg.signatures(did)))
        allok = True
        for s in sigs:
            stt, det = sg.verify(s)
            allok &= stt == "Valid"
            col = {"Valid": "#2E7D32", "Document changed": "#B8860B", "Invalid": "#B00020"}[stt]
            ic = {"Valid": "✅", "Document changed": "⚠️", "Invalid": "❌"}[stt]
            c1, c2 = st.columns([1, 3])
            c1.image(s["image"], width=170)
            c2.markdown(f"""<div class="efs-card" style="border-left:5px solid {col}"><b>{s['meaning']} — {s['stage']}</b> · {s['signer']} ({s['role']})
            {(' · on behalf of ' + s['on_behalf_of']) if s['on_behalf_of'] else ''}<br>
            <span style="color:#6B7280;font-size:.82rem">{s['signed_at']} · certificate {s['cert_serial']} · hash {s['content_hash'][:16]}…</span><br>
            <b style="color:{col}">{ic} {stt}</b> — {det}</div>""", unsafe_allow_html=True)
        (st.success if allok else st.warning)("All signatures verified against the current document." if allok else
                                              "At least one signature no longer matches the document — it was changed after signing.")
        st.download_button("⬇ Download signed PDF (with signature page)", sg.signed_pdf(did), file_name=f"{lab[did].split(' — ')[0].replace('/', '_')}_signed.pdf",
                           mime="application/pdf", key="sg_pdf")
        st.caption("Each signature is an RSA-2048 signature over the SHA-256 of the document content, made with the signer's certificate. "
                   "If the content or version changes later, verification reports it.")
