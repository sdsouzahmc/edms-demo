"""Letter / memo templates with {{placeholders}}, Word (.docx) generation and Word-template import."""
import io
import re
import html
import datetime as dt
import db

BUILTIN = ["ref_no", "date", "sender_name", "sender_title", "department", "recipient_name", "recipient_org", "subject"]
_PH = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
LABELS = {"recipient_name": "Recipient name / title", "recipient_org": "Recipient organisation", "subject": "Subject"}


def init():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS letter_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT, language TEXT, heading TEXT,
        subject_default TEXT, body TEXT, active INTEGER DEFAULT 1, source TEXT, created_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS correspondence_files (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, filename TEXT, mime TEXT,
        data BLOB, sha TEXT, origin TEXT, uploaded_by TEXT, ts TEXT);
    """)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM letter_templates").fetchone()[0]
    conn.close()
    if not n:
        for name, cat, lang, head, subj, body in SEED:
            save_template(None, name, cat, lang, head, subj, body, "Built-in", "System")


SEED = [
    ("Official letter to an authority", "External letter", "English", "OFFICIAL LETTER", "{{topic}}",
     "Dear {{recipient_name}},\n\nWe write to you on behalf of the {{department}} department regarding {{topic}}.\n\n{{main_message}}\n\n"
     "We would appreciate your response by {{deadline}}. Please do not hesitate to contact us should you require any further information.\n\nYours sincerely,"),
    ("Reply to a regulatory request", "Regulatory", "English", "RESPONSE TO REGULATORY REQUEST", "Response to your letter {{request_ref}}",
     "Dear {{recipient_name}},\n\nReference is made to your letter {{request_ref}} dated {{request_date}} concerning {{topic}}.\n\n"
     "In response, we confirm that {{main_message}}\n\nSupporting documents are enclosed ({{enclosures}}). We remain at your disposal for any clarification.\n\nYours faithfully,"),
    ("Internal memorandum", "Internal memo", "English", "INTERNAL MEMORANDUM", "{{topic}}",
     "To: {{recipient_name}} ({{recipient_org}})\nFrom: {{sender_name}}, {{sender_title}}\n\nPlease note the following regarding {{topic}}:\n\n{{main_message}}\n\n"
     "Action required by {{deadline}}. Kindly acknowledge receipt.\n\nRegards,"),
    ("Staff circular", "Circular", "English", "STAFF CIRCULAR", "{{topic}}",
     "To: All staff — {{recipient_org}}\n\nThis circular is issued to inform all concerned of {{topic}}, effective {{effective_date}}.\n\n{{main_message}}\n\n"
     "Heads of departments are requested to cascade this circular to their teams.\n\nThank you for your cooperation,"),
    ("Vendor notice / award letter", "External letter", "English", "NOTICE TO VENDOR", "Notice regarding {{contract_ref}}",
     "Dear {{recipient_name}},\n\nWith reference to {{contract_ref}}, we hereby notify {{recipient_org}} that {{main_message}}\n\n"
     "Please confirm acceptance in writing within {{days}} days of receipt of this letter.\n\nYours sincerely,"),
    ("Acknowledgement of receipt", "External letter", "English", "ACKNOWLEDGEMENT OF RECEIPT", "Acknowledgement of your letter {{request_ref}}",
     "Dear {{recipient_name}},\n\nWe acknowledge receipt of your letter {{request_ref}} dated {{request_date}}. It has been registered and forwarded to "
     "{{forwarded_to}} for action. You will receive a response by {{deadline}}.\n\nYours sincerely,"),
    ("خطاب رسمي (عربي)", "External letter", "Arabic", "خطاب رسمي", "{{topic}}",
     "السيد/ة {{recipient_name}} المحترم/ة،\n\nتحية طيبة وبعد،\n\nنكتب إليكم بخصوص {{topic}}.\n\n{{main_message}}\n\n"
     "نأمل التكرم بالرد قبل تاريخ {{deadline}}.\n\nوتفضلوا بقبول فائق الاحترام والتقدير،"),
]


def templates(active_only=True):
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM letter_templates" + (" WHERE active=1" if active_only else "") + " ORDER BY id").fetchall()
    conn.close()
    return rows


def save_template(tid, name, category, language, heading, subject_default, body, source, user):
    conn = db.get_conn()
    if tid:
        conn.execute("UPDATE letter_templates SET name=?, category=?, language=?, heading=?, subject_default=?, body=? WHERE id=?",
                     (name, category, language, heading, subject_default, body, tid))
    else:
        conn.execute("INSERT INTO letter_templates (name, category, language, heading, subject_default, body, active, source, created_by, created_at) VALUES (?,?,?,?,?,?,1,?,?,?)",
                     (name, category, language, heading, subject_default, body, source, user, db.now()))
    conn.commit()
    conn.close()
    if user and user != "System":
        db.log_audit(None, user, "Letter Template Saved", f"{name} ({language}, {source})")


def set_active(tid, active, user):
    conn = db.get_conn()
    conn.execute("UPDATE letter_templates SET active=? WHERE id=?", (1 if active else 0, tid))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Letter Template " + ("Enabled" if active else "Disabled"), f"template #{tid}")


def custom_fields(*texts):
    seen = []
    for t in texts:
        for m in _PH.findall(t or ""):
            if m not in BUILTIN and m not in seen:
                seen.append(m)
    return seen


def label(key):
    return LABELS.get(key, key.replace("_", " ").capitalize())


def render(text, values):
    return _PH.sub(lambda m: str(values.get(m.group(1)) or f"[{m.group(1)}]"), text or "")


def preview_html(heading, values, body, rtl=False):
    d = "rtl" if rtl else "ltr"
    paras = "".join(f"<p style='margin:0 0 10px 0'>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in body.split("\n\n"))
    return f"""<div dir="{d}" style="background:#fff;border:1px solid #D5DBE5;border-radius:6px;box-shadow:0 4px 14px rgba(31,56,100,.12);padding:30px 38px;
    font-family:Georgia,'Times New Roman',serif;font-size:.92rem;color:#1b2333;line-height:1.5;max-width:720px;margin:auto">
    <div style="text-align:center;border-bottom:3px double #1F3864;padding-bottom:8px;margin-bottom:12px"><div style="font-weight:700;color:#1F3864;letter-spacing:.06em">HOSPITAL ADMINISTRATION</div>
    <div style="font-size:.78rem;color:#6B7280">{html.escape(values.get('department') or '')}</div></div>
    <div style="text-align:center;font-weight:700;letter-spacing:.08em;margin:6px 0 10px">{html.escape(heading or '')}</div>
    <div style="display:flex;justify-content:space-between;font-size:.82rem;color:#374151;margin-bottom:10px"><span><b>Ref:</b> {html.escape(str(values.get('ref_no') or ''))}</span><span><b>Date:</b> {html.escape(str(values.get('date') or ''))}</span></div>
    <div style="font-size:.86rem;margin-bottom:8px"><b>To:</b> {html.escape(str(values.get('recipient_name') or ''))}{(' — ' + html.escape(str(values.get('recipient_org')))) if values.get('recipient_org') else ''}</div>
    <div style="font-weight:700;margin:6px 0 12px">Subject: {html.escape(str(values.get('subject') or ''))}</div>
    {paras}
    <div style="margin-top:26px"><div style="border-top:1px solid #999;width:200px;padding-top:4px"><b>{html.escape(str(values.get('sender_name') or ''))}</b><br>
    <span style="font-size:.82rem;color:#6B7280">{html.escape(str(values.get('sender_title') or ''))} · {html.escape(str(values.get('department') or ''))}</span></div></div></div>"""


def build_docx(heading, values, body, rtl=False):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor, Cm
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.4)
        s.top_margin, s.bottom_margin = Cm(2), Cm(2)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)

    def para(text="", bold=False, size=None, color=None, align=None, after=6):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.bold = bold
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
        p.paragraph_format.space_after = Pt(after)
        if rtl:
            ppr = p._p.get_or_add_pPr()
            ppr.append(OxmlElement("w:bidi"))
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if align is None else align
            r.font.rtl = True
        elif align is not None:
            p.alignment = align
        return p
    C = WD_ALIGN_PARAGRAPH.CENTER
    para("HOSPITAL ADMINISTRATION", True, 15, "1F3864", C, 0)
    para(values.get("department") or "", False, 10, "6B7280", C, 10)
    para(heading or "", True, 12, None, C, 10)
    para(f"Ref: {values.get('ref_no') or ''}        Date: {values.get('date') or ''}", False, 10, None, None, 8)
    to = str(values.get("recipient_name") or "") + (f" — {values.get('recipient_org')}" if values.get("recipient_org") else "")
    para(f"To: {to}", False, 11, None, None, 4)
    para(f"Subject: {values.get('subject') or ''}", True, 11, None, None, 10)
    for blk in body.split("\n\n"):
        para(blk, after=8)
    para("", after=14)
    para(str(values.get("sender_name") or ""), True, 11, None, None, 0)
    para(f"{values.get('sender_title') or ''} · {values.get('department') or ''}", False, 10, "6B7280", None, 0)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def parse_docx(data):
    """Read a Word file → text with its {{placeholders}} preserved (paragraphs separated by blank lines)."""
    from docx import Document
    d = Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in d.paragraphs if p.text.strip())
