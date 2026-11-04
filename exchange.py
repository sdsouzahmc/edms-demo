"""Inter-department transmittals + secure external exchange (share / review / upload links)."""
import hashlib
import io
import json
import os
import re
import secrets
from datetime import datetime, timedelta

import db
import db_ext
import intake_ext as ix
import rfp_data

DEFAULT_BASE = "https://edms-de-vckcrpenutzb6xr5xn74aq.streamlit.app"
ACTIONS = ["Review & comment", "Approve", "Acknowledge receipt", "For information"]
EXPIRY_CHOICES = {"1 day": 1, "3 days": 3, "7 days": 7, "14 days": 14, "30 days": 30}
ALLOWED_EXT = ["pdf", "docx", "doc", "xlsx", "png", "jpg", "jpeg", "txt", "csv"]
MAX_ATTEMPTS = 5
LOCK_MIN = 15
MAGIC = {"pdf": [b"%PDF"], "png": [b"\x89PNG"], "jpg": [b"\xff\xd8"], "jpeg": [b"\xff\xd8"],
         "docx": [b"PK"], "xlsx": [b"PK"], "doc": [b"\xd0\xcf\x11\xe0"]}


def _c():
    return db.get_conn()


def _now():
    return db.now()


def init():
    conn = _c()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS share_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT UNIQUE, token_hint TEXT,
        kind TEXT,                       -- download | review | upload
        document_id INTEGER, transmittal_id INTEGER,
        recipient_name TEXT, recipient_org TEXT, recipient_email TEXT, purpose TEXT,
        created_by TEXT, created_at TEXT, expires_at TEXT,
        max_downloads INTEGER, downloads INTEGER DEFAULT 0,
        code_salt TEXT, code_hash TEXT,
        watermark INTEGER DEFAULT 1,
        upload_dept TEXT, upload_note TEXT, max_mb INTEGER DEFAULT 10, uploads INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',    -- active | revoked
        failed INTEGER DEFAULT 0, locked_until TEXT
    );
    CREATE TABLE IF NOT EXISTS share_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, link_id INTEGER, ts TEXT, event TEXT, detail TEXT
    );
    CREATE TABLE IF NOT EXISTS transmittals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch TEXT, seq INTEGER DEFAULT 0, mode TEXT,
        document_id INTEGER, from_dept TEXT, from_user TEXT,
        to_dept TEXT, to_external TEXT, link_id INTEGER,
        action TEXT, instructions TEXT, due_date TEXT,
        status TEXT,                     -- Waiting | Pending | Approved | Reviewed | Acknowledged | Returned | Rejected | Cancelled
        response TEXT, responded_by TEXT, responded_at TEXT, created_at TEXT
    );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- settings --
def base_url():
    conn = _c()
    r = conn.execute("SELECT value FROM settings WHERE key='public_base_url'").fetchone()
    conn.close()
    return (r["value"] if r else DEFAULT_BASE).rstrip("/")


def set_base_url(url, actor):
    conn = _c()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('public_base_url',?)", (url.strip(),))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Setting Changed", f"Public base URL for secure links: {url}")


def link_url(token):
    return f"{base_url()}/?x={token}"


# ------------------------------------------------------------------- links --
def _hash(s, salt=""):
    return hashlib.sha256((salt + s).encode()).hexdigest()


def create_link(kind, created_by, recipient_name, recipient_email="", recipient_org="", purpose="", doc_id=None,
                days=7, max_downloads=5, use_code=True, watermark=True, upload_dept=None, upload_note="",
                max_mb=10, transmittal_id=None):
    token = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(1000000):06d}" if use_code else None
    salt = secrets.token_hex(8)
    exp = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _c()
    cur = conn.execute("""INSERT INTO share_links (token_hash, token_hint, kind, document_id, transmittal_id, recipient_name,
        recipient_org, recipient_email, purpose, created_by, created_at, expires_at, max_downloads, code_salt, code_hash,
        watermark, upload_dept, upload_note, max_mb) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (_hash(token), token[-4:], kind, doc_id, transmittal_id, recipient_name, recipient_org, recipient_email,
                        purpose, created_by, _now(), exp, max_downloads if kind != "upload" else None, salt,
                        _hash(code, salt) if code else None, 1 if watermark else 0, upload_dept, upload_note, max_mb))
    lid = cur.lastrowid
    conn.commit()
    conn.close()
    label = {"download": "Secure share link", "review": "External review link", "upload": "Secure upload link"}[kind]
    log(lid, "Created", f"by {created_by} for {recipient_name} · expires {exp[:16]}" + (" · access code required" if code else ""))
    db.log_audit(doc_id, created_by, f"{label} Created",
                 f"{recipient_name} {('<' + recipient_email + '>') if recipient_email else ''} · expires {exp[:16]} · "
                 f"{'code-protected' if code else 'NO access code'}")
    return token, code, lid


def log(link_id, event, detail=""):
    conn = _c()
    conn.execute("INSERT INTO share_events (link_id, ts, event, detail) VALUES (?,?,?,?)", (link_id, _now(), event, detail))
    conn.commit()
    conn.close()


def by_token(token):
    if not token or len(token) < 20:
        return None
    conn = _c()
    r = conn.execute("SELECT * FROM share_links WHERE token_hash=?", (_hash(token),)).fetchone()
    conn.close()
    return dict(r) if r else None


def get(lid):
    conn = _c()
    r = conn.execute("SELECT * FROM share_links WHERE id=?", (lid,)).fetchone()
    conn.close()
    return dict(r) if r else None


def state(l):
    if l["status"] == "revoked":
        return "Revoked"
    if _now() > l["expires_at"]:
        return "Expired"
    if l["locked_until"] and _now() < l["locked_until"]:
        return "Locked"
    if l["kind"] != "upload" and l["max_downloads"] is not None and l["kind"] == "download" and l["downloads"] >= l["max_downloads"]:
        return "Used up"
    return "Active"


def links():
    conn = _c()
    rows = [dict(r) for r in conn.execute("""SELECT s.*, d.doc_code, d.title FROM share_links s
                LEFT JOIN documents d ON d.id=s.document_id ORDER BY s.id DESC""").fetchall()]
    conn.close()
    for r in rows:
        r["state"] = state(r)
    return rows


def events(link_id=None, limit=300):
    conn = _c()
    q = "SELECT e.*, s.recipient_name, s.kind, s.token_hint FROM share_events e JOIN share_links s ON s.id=e.link_id"
    rows = conn.execute(q + (" WHERE e.link_id=?" if link_id else "") + " ORDER BY e.id DESC LIMIT ?",
                        ((link_id, limit) if link_id else (limit,))).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def revoke(lid, actor):
    conn = _c()
    conn.execute("UPDATE share_links SET status='revoked' WHERE id=?", (lid,))
    conn.commit()
    l = conn.execute("SELECT * FROM share_links WHERE id=?", (lid,)).fetchone()
    conn.close()
    log(lid, "Revoked", f"by {actor}")
    db.log_audit(l["document_id"] if l else None, actor, "Secure Link Revoked", f"{l['recipient_name']} (…{l['token_hint']})")


def check_code(l, code):
    """Returns (ok, message). Locks the link after too many wrong attempts."""
    if state(l) == "Locked":
        return False, f"Too many wrong attempts. Try again after {l['locked_until'][11:16]}."
    if not l["code_hash"]:
        return True, ""
    if _hash((code or "").strip(), l["code_salt"]) == l["code_hash"]:
        conn = _c()
        conn.execute("UPDATE share_links SET failed=0 WHERE id=?", (l["id"],))
        conn.commit()
        conn.close()
        log(l["id"], "Access code accepted")
        return True, ""
    conn = _c()
    n = (l["failed"] or 0) + 1
    lock = None
    if n >= MAX_ATTEMPTS:
        lock = (datetime.now() + timedelta(minutes=LOCK_MIN)).strftime("%Y-%m-%d %H:%M:%S")
        n = 0
    conn.execute("UPDATE share_links SET failed=?, locked_until=? WHERE id=?", (n, lock, l["id"]))
    conn.commit()
    conn.close()
    log(l["id"], "Wrong access code", f"attempt {n if not lock else MAX_ATTEMPTS}" + (" — link locked" if lock else ""))
    if lock:
        db.log_audit(l["document_id"], "External", "Secure Link Locked", f"{l['recipient_name']} (…{l['token_hint']}) after {MAX_ATTEMPTS} wrong codes", "Denied")
        return False, f"Too many wrong attempts. The link is locked for {LOCK_MIN} minutes."
    return False, f"Incorrect access code ({MAX_ATTEMPTS - n} attempts left)."


# ----------------------------------------------------------- controlled copy --
def _latin(s):
    return (s or "").encode("latin-1", "replace").decode("latin-1")


def controlled_copy(doc_id, l):
    """Return (bytes, filename): a PDF copy, watermarked with who it was shared with, when and under which link."""
    import fitz
    d = db.get_document(doc_id)
    mark = f"Shared with {l['recipient_name']} - {datetime.now():%Y-%m-%d %H:%M} - link ...{l['token_hint']} - CONTROLLED COPY"
    fname = re.sub(r"[^A-Za-z0-9._-]+", "_", d["doc_code"]) + ".pdf"
    src = None
    files = [f for f in (ix.files_by_doc().get(doc_id) or [])]
    if files:
        fr = ix.get_file(files[0]["id"])
        src = (fr["filename"], fr["data"])
    pdf = fitz.open()
    if src and src[0].lower().endswith(".pdf"):
        pdf = fitz.open(stream=src[1], filetype="pdf")
    elif src and src[0].lower().endswith((".png", ".jpg", ".jpeg")):
        pg = pdf.new_page()
        pg.insert_image(fitz.Rect(30, 60, 565, 800), stream=src[1], keep_proportion=True)
    else:
        import textwrap
        text = d["body_text"] or ""
        head = f"{d['title']}\n{d['doc_code']}  |  {d['department']}  |  {d['classification']}\n" + "-" * 80 + "\n"
        lines = []
        for para in _latin(head + text).splitlines():
            lines += textwrap.wrap(para, 100) or [""]
        per = 62
        for i in range(0, max(len(lines), 1), per):
            pg = pdf.new_page()
            y = 60
            for ln in lines[i:i + per]:
                pg.insert_text((50, y), ln, fontsize=9.5, fontname="helv")
                y += 12
    if l["watermark"]:
        for pg in pdf:
            r = pg.rect
            pg.insert_text((24, r.height - 14), _latin(mark), fontsize=7.5, color=(0.6, 0.1, 0.1))
            pg.insert_text((r.width * 0.12, r.height * 0.55), "CONTROLLED COPY", fontsize=54, color=(0.85, 0.85, 0.85),
                           rotate=0, fill_opacity=0.35, overlay=False)
    buf = pdf.tobytes(garbage=3, deflate=True)
    pdf.close()
    return buf, fname


def count_download(l):
    conn = _c()
    conn.execute("UPDATE share_links SET downloads=downloads+1 WHERE id=?", (l["id"],))
    conn.commit()
    conn.close()
    log(l["id"], "Downloaded", f"{l['recipient_name']}")
    db.log_audit(l["document_id"], f"External: {l['recipient_name']}", "Document Downloaded (secure link)", f"link …{l['token_hint']}")
    creator = l["created_by"]
    if creator in rfp_data.ROLES:
        d = db.get_document(l["document_id"])
        db_ext.notify(creator, f"{l['recipient_name']} downloaded {d['doc_code']} via your secure link.", l["document_id"], "info")


# ------------------------------------------------------------------ uploads --
def validate_upload(name, data, max_mb):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        return f"File type .{ext or '?'} is not accepted. Allowed: {', '.join(ALLOWED_EXT)}."
    if len(data) > max_mb * 1024 * 1024:
        return f"Larger than the {max_mb} MB limit."
    if len(data) == 0:
        return "The file is empty."
    sigs = MAGIC.get(ext)
    if sigs and not any(data.startswith(s) for s in sigs):
        return "The file content does not match its extension (rejected by content check)."
    return None


def receive_upload(l, name, data, sender_name, sender_org, note):
    err = validate_upload(name, data, l["max_mb"] or 10)
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", os.path.basename(name))
    if err:
        log(l["id"], "Upload rejected", f"{safe}: {err}")
        return {"file": safe, "status": "Rejected — " + err, "code": ""}
    r = ix.register_file(safe, data, f"External: {sender_name}", "Secure upload link", "Incoming", auto_route=False,
                         dept=l["upload_dept"] or "Medical Records")
    if r["status"] == "Registered":
        conn = _c()
        conn.execute("UPDATE share_links SET uploads=uploads+1 WHERE id=?", (l["id"],))
        d = conn.execute("SELECT id FROM documents WHERE doc_code=?", (r["code"],)).fetchone()
        if d:
            conn.execute("UPDATE documents SET sender=? WHERE id=?", (f"{sender_name}{(' — ' + sender_org) if sender_org else ''}", d["id"]))
        conn.commit()
        conn.close()
        log(l["id"], "Uploaded", f"{safe} → {r['code']} ({sender_name}{', ' + sender_org if sender_org else ''})" + (f" · note: {note}" if note else ""))
        did = d["id"] if d else None
        db.log_audit(did, f"External: {sender_name}", "External Upload Received", f"{safe} via secure upload link …{l['token_hint']}; "
                     f"AV/type check passed (simulated)" + (f"; note: {note}" if note else ""))
        for u, p in rfp_data.ROLES.items():
            if p["dept"] == (l["upload_dept"] or "Medical Records") or u == l["created_by"]:
                db_ext.notify(u, f"New external upload {r['code']} from {sender_name} ({safe}).", did, "info")
    else:
        log(l["id"], "Upload skipped", f"{safe}: {r['status']}")
    return r


# ------------------------------------------------------------ transmittals ---
def _users_in(dept):
    return [u for u, p in rfp_data.ROLES.items() if p["dept"] == dept]


def send_transmittal(doc_id, from_user, to_depts, action, due, instructions, mode="Parallel", external=None):
    """to_depts: list of departments. external: dict(name, email, org, days, use_code) -> adds an external recipient with a review link.
    Returns (batch, external_link_info or None)."""
    prof = rfp_data.ROLES[from_user]
    d = db.get_document(doc_id)
    batch = secrets.token_hex(3).upper()
    conn = _c()
    ids = []
    for i, dept in enumerate(to_depts):
        st_ = "Pending" if (mode == "Parallel" or i == 0) else "Waiting"
        cur = conn.execute("""INSERT INTO transmittals (batch, seq, mode, document_id, from_dept, from_user, to_dept, action, instructions,
                     due_date, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (batch, i, mode, doc_id, prof["dept"], from_user, dept, action, instructions, str(due) if due else None, st_, _now()))
        ids.append((cur.lastrowid, dept, st_))
    conn.commit()
    conn.close()
    ext_info = None
    if external:
        cur_seq = len(to_depts)
        conn = _c()
        cur = conn.execute("""INSERT INTO transmittals (batch, seq, mode, document_id, from_dept, from_user, to_external, action, instructions,
                     due_date, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (batch, cur_seq, mode, doc_id, prof["dept"], from_user, external["name"], action, instructions,
                            str(due) if due else None, "Pending" if (mode == "Parallel" or not to_depts) else "Waiting", _now()))
        tid = cur.lastrowid
        conn.commit()
        conn.close()
        token, code, lid = create_link("review", from_user, external["name"], external.get("email", ""), external.get("org", ""),
                                       f"{action}: {instructions}"[:200], doc_id, external.get("days", 7), 5,
                                       external.get("use_code", True), True, transmittal_id=tid)
        conn = _c()
        conn.execute("UPDATE transmittals SET link_id=? WHERE id=?", (lid, tid))
        conn.commit()
        conn.close()
        ext_info = {"token": token, "code": code, "url": link_url(token), "tid": tid}
    names = ", ".join(to_depts + ([f"{external['name']} (external)"] if external else []))
    db.log_audit(doc_id, from_user, "Transmittal Sent", f"{prof['dept']} → {names} · {action} · {mode}" + (f" · due {due}" if due else ""))
    for tid, dept, st_ in ids:
        if st_ == "Pending":
            _notify_dept(dept, f"{prof['dept']} sent you {d['doc_code']} — {action}" + (f" (due {due})" if due else ""), doc_id)
    return batch, ext_info


def _notify_dept(dept, msg, doc_id):
    for u in _users_in(dept):
        db_ext.notify(u, msg, doc_id, "approval")


def transmittals(dept=None, sent_by_dept=None, status=None, limit=300):
    conn = _c()
    q = ("SELECT t.*, d.doc_code, d.title, d.classification FROM transmittals t JOIN documents d ON d.id=t.document_id WHERE 1=1")
    p = []
    if dept:
        q += " AND t.to_dept=?"
        p.append(dept)
    if sent_by_dept:
        q += " AND t.from_dept=?"
        p.append(sent_by_dept)
    if status:
        q += f" AND t.status IN ({','.join('?' * len(status))})"
        p += status
    rows = conn.execute(q + " ORDER BY t.id DESC LIMIT ?", p + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def inbox_count(dept, admin=False):
    return len([t for t in transmittals(None if admin else dept, status=["Pending"]) if t["to_dept"]])


DECISIONS = {"Approve": "Approved", "Reviewed — no objection": "Reviewed", "Acknowledge": "Acknowledged",
             "Return for changes": "Returned", "Reject": "Rejected"}


def respond(tid, who, decision, comment, external=False):
    """decision is a label from DECISIONS. Advances sequential batches and notifies the sender."""
    conn = _c()
    t = conn.execute("SELECT * FROM transmittals WHERE id=?", (tid,)).fetchone()
    if not t or t["status"] != "Pending":
        conn.close()
        return False
    status = DECISIONS[decision]
    conn.execute("UPDATE transmittals SET status=?, response=?, responded_by=?, responded_at=? WHERE id=?",
                 (status, comment, who, _now(), tid))
    stop = status in ("Returned", "Rejected")
    msg_next = ""
    if t["mode"] == "Sequential":
        rest = conn.execute("SELECT * FROM transmittals WHERE batch=? AND seq>? AND status='Waiting' ORDER BY seq", (t["batch"], t["seq"])).fetchall()
        if stop:
            conn.execute("UPDATE transmittals SET status='Cancelled' WHERE batch=? AND status='Waiting'", (t["batch"],))
        elif rest:
            conn.execute("UPDATE transmittals SET status='Pending' WHERE id=?", (rest[0]["id"],))
            msg_next = rest[0]["to_dept"] or rest[0]["to_external"]
    conn.commit()
    conn.close()
    d = db.get_document(t["document_id"])
    who_t = f"{who} (external)" if external else who
    recip = t["to_dept"] or f"{t['to_external']} (external)"
    db.log_audit(t["document_id"], who_t, f"Transmittal {status}", f"{recip}: {decision}" + (f" — {comment}" if comment else ""))
    if msg_next and rfp_data.ROLES:
        nd = msg_next if msg_next in rfp_data.DEPARTMENTS else None
        if nd:
            _notify_dept(nd, f"{t['from_dept']} → you: {d['doc_code']} — {t['action']} (previous department approved)", t["document_id"])
    if t["from_user"] in rfp_data.ROLES:
        db_ext.notify(t["from_user"], f"{recip} {status.lower()} {d['doc_code']}" + (f": “{comment[:80]}”" if comment else ""),
                      t["document_id"], "approval")
    return True


def batch_summary(batch):
    conn = _c()
    rows = [dict(r) for r in conn.execute("SELECT * FROM transmittals WHERE batch=? ORDER BY seq", (batch,)).fetchall()]
    conn.close()
    return rows
