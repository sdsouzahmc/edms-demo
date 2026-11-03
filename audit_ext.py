"""Rich, backdated audit history for the demo documents + helpers for the audit-trail UI.

The audit table is append-only (triggers block UPDATE/DELETE). At first start the demo needs a believable
history, so the seed step lifts the guard once, back-dates the seeded 'Created' rows and appends the
life-cycle events (with old -> new values). Afterwards the guard is restored and the log is immutable again.
"""
import datetime as dt
import difflib
import hashlib
import random
import db
import rfp_data

FLOW = ["Draft", "Department Review", "Approval", "Finance Sign-off", "Released"]
CLASS = ["Internal", "External", "Regulatory"]
SEC = ["Public", "Internal", "Restricted", "Confidential"]
IPS = ["10.20.4.37", "10.20.4.52", "10.20.6.11", "10.20.7.84", "10.30.1.9", "172.16.8.23"]
CH = ["Web", "Web", "Web", "Mobile", "Outlook add-in", "Scan station"]


def _fmt(t):
    return t.strftime("%Y-%m-%d %H:%M:%S")


def seed_history():
    conn = db.get_conn()
    done = conn.execute("SELECT value FROM settings WHERE key='audit_history_v1'").fetchone()
    if done:
        conn.close()
        return
    docs = conn.execute("SELECT * FROM documents ORDER BY id").fetchall()
    if not docs:
        conn.close()
        return
    users = list(rfp_data.ROLES.keys())
    by_dept = {}
    for n, p in rfp_data.ROLES.items():
        by_dept.setdefault(p["dept"], []).append(n)
    r = random.Random(77)
    now = dt.datetime.now()
    rows = []
    updates = []
    for d in docs:
        owner = d["created_by"]
        t0 = now - dt.timedelta(days=r.randint(25, 330), hours=r.randint(0, 9))
        updates.append((_fmt(t0), d["id"]))
        t = t0
        pool = by_dept.get(d["department"]) or users

        def ev(actor, action, detail, field=None, old=None, new=None, gap=(1, 40)):
            nonlocal t
            t = t + dt.timedelta(hours=r.randint(*gap), minutes=r.randint(0, 59))
            if t > now - dt.timedelta(minutes=5):
                t = now - dt.timedelta(minutes=r.randint(6, 90))
            rows.append((d["id"], actor, action, detail, "Success", _fmt(t), field, None if old is None else str(old),
                         None if new is None else str(new), r.choice(IPS), r.choice(CH)))

        # initial metadata capture / correction
        if r.random() < 0.8:
            cls = r.choice([c for c in CLASS if c != d["classification"]])
            ev(owner, "Metadata Edited", "Classification corrected after review", "classification", cls, d["classification"], (1, 6))
        if r.random() < 0.7:
            sec = r.choice([c for c in SEC if c != d["security_level"]])
            ev(r.choice(pool), "Metadata Edited", "Security level re-assessed", "security_level", sec, d["security_level"], (1, 20))
        if d["source"] == "Scan":
            ev(owner, "OCR Text Corrected", "Operator fixed low-confidence words", "body_text",
               (d["body_text"] or "")[:60].replace("e", "c", 1), (d["body_text"] or "")[:60], (1, 5))
        if r.random() < 0.6:
            ev(r.choice(pool), "Edited", "Title standardised to naming convention", "title", (d["title"] or "").lower()[:70], d["title"], (2, 30))
        ev(r.choice(pool), "New Version Checked In", "v1.0 → v1.1 review comments incorporated", "version", "1.0", "1.1", (3, 40))
        # workflow path up to current status
        st = d["status"]
        path = FLOW[:FLOW.index(st) + 1] if st in FLOW else (FLOW if st in ("Archived", "Disposed") else FLOW[:2])
        for a, b in zip(path, path[1:]):
            ev(r.choice(pool + ["Yusuf Al-Marri"]), "Approved" if b != "Released" else "Version Published", f"{a} stage approved", "status", a, b, (4, 60))
        if st == "Rejected":
            ev(r.choice(pool), "Rejected", "Returned to author — missing annexure", "status", "Approval", "Rejected", (4, 40))
        if st in ("Archived", "Disposed"):
            ev("Yusuf Al-Marri", "Archived", "Moved to archive library per retention schedule", "status", "Released", "Archived", (24, 120))
        if d["legal_hold"]:
            ev("Yusuf Al-Marri", "Legal Hold Applied", "Litigation hold requested by Legal", "legal_hold", 0, 1, (2, 60))
        for _ in range(r.randint(2, 6)):
            u = r.choice(users)
            act = r.choice(["Viewed", "Viewed", "Viewed", "Downloaded", "Printed", "Shared"])
            ev(u, act, {"Viewed": "Opened in viewer", "Downloaded": "Downloaded with watermark", "Printed": "Printed — controlled copy",
                        "Shared": "Shared with another department"}[act], gap=(2, 60))
        if r.random() < 0.15:
            rows.append((d["id"], r.choice(users), "Access Denied", "Attempted to open a restricted document", "Denied",
                         _fmt(now - dt.timedelta(days=r.randint(1, 20))), None, None, None, r.choice(IPS), "Web"))
    conn.execute("DROP TRIGGER IF EXISTS audit_no_update")
    conn.execute("DROP TRIGGER IF EXISTS audit_no_delete")
    conn.execute("DELETE FROM audit_log WHERE action IN ('Approved','Rejected','Edited','Checked Out',"
                 "'New Version Checked In','Version Published','Delegated','Archived','Legal Hold Applied')")
    for ts, did in updates:
        conn.execute("UPDATE documents SET created_at=? WHERE id=?", (ts, did))
        conn.execute("UPDATE audit_log SET ts=? WHERE document_id=? AND action='Created'", (ts, did))
        conn.execute("UPDATE audit_log SET ts=datetime(?, '+3 minutes') WHERE document_id=? AND action IN ('OCR Capture','Outlook Capture','EMR Upload')", (ts, did))
        conn.execute("UPDATE audit_log SET ts=datetime(?, '+6 minutes') WHERE document_id=? AND action IN ('Auto-distribution')", (ts, did))
    conn.executemany("INSERT INTO audit_log (document_id, actor, action, detail, result, ts, field, old_value, new_value, ip, channel) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("""CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'audit_log is immutable: records cannot be altered'); END;""")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'audit_log is immutable: records cannot be deleted'); END;""")
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('audit_history_v1','1')")
    conn.commit()
    conn.close()


def chain(rows):
    """Tamper-evident hash chain over the events (oldest first). Returns {id: short_hash}."""
    out, prev = {}, "GENESIS"
    for e in sorted(rows, key=lambda x: x["id"]):
        h = hashlib.sha256(f"{prev}|{e['id']}|{e['actor']}|{e['action']}|{e['ts']}|{e['old_value']}|{e['new_value']}".encode()).hexdigest()
        out[e["id"]] = h[:10]
        prev = h
    return out


def word_diff(old, new):
    """HTML diff of two texts: deletions red/struck, insertions green."""
    import html
    a, b = (old or "").split(), (new or "").split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            out.append(html.escape(" ".join(a[i1:i2])))
        else:
            if i2 > i1:
                out.append(f'<span class="efs-del">{html.escape(" ".join(a[i1:i2]))}</span>')
            if j2 > j1:
                out.append(f'<span class="efs-ins">{html.escape(" ".join(b[j1:j2]))}</span>')
    return " ".join(out)
