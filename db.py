"""SQLite data layer for the EDMS demo.

Lessons carried over from the earlier prototype:
- Always commit + close the write connection BEFORE calling log_audit()
  (which opens its own connection) to avoid 'database is locked'.
- WAL journal mode + busy_timeout to tolerate concurrent Streamlit reruns.
"""
import sqlite3
import os
import random
import string
import datetime as dt

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "edms.db")

DEPARTMENTS = [
    "Medical Records", "Human Resources", "Finance", "Procurement",
    "Facilities", "Clinical Operations",
]
CLASSIFICATIONS = ["Internal", "External", "Regulatory"]
SECURITY_LEVELS = ["Public", "Internal", "Restricted", "Confidential"]
WORKFLOW_STAGES = ["Draft", "Department Review", "Approval", "Finance Sign-off", "Released"]
RETENTION_SCHEDULES = {
    "HR Records - 7 years": 7, "Finance Records - 10 years": 10,
    "Patient-Adjacent Admin - 10 years": 10, "Facility Records - 5 years": 5,
    "General Correspondence - 3 years": 3, "Procurement Records - 6 years": 6,
}


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 8000")
    return conn


def make_code(prefix="DOC"):
    yr = dt.datetime.now().year
    rand = "".join(random.choices(string.digits, k=4))
    return f"{prefix}-{yr}-{rand}"


def make_qr_token():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


# ---------------------------------------------------------------- schema ---
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_code TEXT UNIQUE,
        title TEXT,
        department TEXT,
        classification TEXT,
        security_level TEXT,
        doc_type TEXT,
        status TEXT DEFAULT 'Draft',
        source TEXT,                    -- Postal / Email / Scan / Upload
        language TEXT DEFAULT 'English',
        body_text TEXT,                 -- extracted / OCR'd searchable text
        current_version TEXT DEFAULT '1.0',
        is_published INTEGER DEFAULT 0,
        qr_token TEXT,
        retention_schedule TEXT,
        retention_years INTEGER,
        effective_date TEXT,
        expiry_date TEXT,
        legal_hold INTEGER DEFAULT 0,
        created_by TEXT,
        created_at TEXT,
        modified_by TEXT,
        modified_at TEXT,
        released_at TEXT,
        archived_at TEXT,
        disposed_at TEXT,
        sender TEXT,
        recipient TEXT
    );

    CREATE TABLE IF NOT EXISTS correspondence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        direction TEXT,                 -- Incoming / Outgoing
        channel TEXT,                   -- Postal / Email
        sender TEXT,
        recipient TEXT,
        subject TEXT,
        logged_by TEXT,
        logged_at TEXT,
        FOREIGN KEY (document_id) REFERENCES documents(id)
    );

    CREATE TABLE IF NOT EXISTS versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        version_no TEXT,
        status TEXT,                    -- Draft / Published / Obsolete
        checked_out_by TEXT,
        notes TEXT,
        body_snapshot TEXT,
        created_by TEXT,
        created_at TEXT,
        FOREIGN KEY (document_id) REFERENCES documents(id)
    );

    CREATE TABLE IF NOT EXISTS workflow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        stage TEXT,
        stage_order INTEGER,
        status TEXT DEFAULT 'pending',  -- pending / active / done / rejected
        assignee TEXT,
        delegated_to TEXT,
        acted_by TEXT,
        acted_at TEXT,
        comment TEXT,
        due_at TEXT,
        FOREIGN KEY (document_id) REFERENCES documents(id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        actor TEXT,
        action TEXT,
        detail TEXT,
        result TEXT,
        ts TEXT
    );

    CREATE TABLE IF NOT EXISTS access_grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department TEXT,
        role TEXT,
        can_view INTEGER DEFAULT 1,
        can_edit INTEGER DEFAULT 0,
        can_approve INTEGER DEFAULT 0,
        can_release INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS disposal_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        requested_by TEXT,
        requested_at TEXT,
        reason TEXT,
        status TEXT DEFAULT 'Pending Approval',  -- Pending Approval / Approved / Rejected / Destroyed
        approved_by TEXT,
        approved_at TEXT,
        FOREIGN KEY (document_id) REFERENCES documents(id)
    );

    CREATE TABLE IF NOT EXISTS saved_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        name TEXT,
        query TEXT,
        dept_filter TEXT,
        class_filter TEXT,
        created_at TEXT
    );
    """)
    conn.commit()
    conn.close()
    _seed_access_grants()


def ensure_seeded():
    """Auto-seed sample data on first run (e.g. a fresh Streamlit Cloud deploy
    with an empty ephemeral filesystem) so the app is never shown empty."""
    conn = get_conn()
    existing = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
    conn.close()
    if existing == 0:
        import seed as _seed_module
        _seed_module.run()


def _seed_access_grants():
    conn = get_conn()
    cur = conn.cursor()
    existing = cur.execute("SELECT COUNT(*) c FROM access_grants").fetchone()["c"]
    if existing == 0:
        rows = []
        for dept in DEPARTMENTS:
            rows.append((dept, "department_user", 1, 1, 1, 0))
        rows.append(("ALL", "admin", 1, 1, 1, 1))
        cur.executemany(
            "INSERT INTO access_grants (department, role, can_view, can_edit, can_approve, can_release) "
            "VALUES (?,?,?,?,?,?)", rows)
        conn.commit()
    conn.close()


# ------------------------------------------------------------- audit log ---
def log_audit(document_id, actor, action, detail="", result="Success"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log (document_id, actor, action, detail, result, ts) VALUES (?,?,?,?,?,?)",
        (document_id, actor, action, detail, result, now()))
    conn.commit()
    conn.close()


def get_audit_log(document_id=None, limit=500):
    conn = get_conn()
    if document_id:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE document_id=? ORDER BY id DESC LIMIT ?",
            (document_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT a.*, d.title as doc_title, d.doc_code FROM audit_log a "
            "LEFT JOIN documents d ON d.id = a.document_id ORDER BY a.id DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return rows


# ------------------------------------------------------------- documents ---
def create_document(title, department, classification, security_level, doc_type,
                     source, language, body_text, created_by, sender="", recipient="",
                     retention_label=None):
    conn = get_conn()
    cur = conn.cursor()
    code = make_code("DOC")
    ts = now()
    retention_years = RETENTION_SCHEDULES.get(retention_label) if retention_label else None
    effective = dt.date.today().isoformat()
    expiry = (dt.date.today() + dt.timedelta(days=365 * retention_years)).isoformat() if retention_years else None
    cur.execute("""
        INSERT INTO documents (doc_code, title, department, classification, security_level, doc_type,
            status, source, language, body_text, current_version, is_published, qr_token,
            retention_schedule, retention_years, effective_date, expiry_date,
            created_by, created_at, modified_by, modified_at, sender, recipient)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (code, title, department, classification, security_level, doc_type,
          "Draft", source, language, body_text, "1.0", 0, None,
          retention_label, retention_years, effective, expiry,
          created_by, ts, created_by, ts, sender, recipient))
    doc_id = cur.lastrowid
    cur.execute("""
        INSERT INTO versions (document_id, version_no, status, notes, body_snapshot, created_by, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (doc_id, "1.0", "Draft", "Initial capture", body_text, created_by, ts))
    stages = WORKFLOW_STAGES
    for i, stage in enumerate(stages):
        status = "active" if i == 0 else "pending"
        assignee = department if i == 0 else None
        cur.execute("""
            INSERT INTO workflow (document_id, stage, stage_order, status, assignee)
            VALUES (?,?,?,?,?)
        """, (doc_id, stage, i, status, assignee))
    conn.commit()
    conn.close()
    log_audit(doc_id, created_by, "Created", f"{code} — {title}")
    return doc_id, code


def get_documents(department=None, status=None, classification=None, search=None,
                   include_disposed=False):
    conn = get_conn()
    q = "SELECT * FROM documents WHERE 1=1"
    params = []
    if department and department != "All":
        q += " AND department = ?"
        params.append(department)
    if status and status != "All":
        q += " AND status = ?"
        params.append(status)
    if classification and classification != "All":
        q += " AND classification = ?"
        params.append(classification)
    if not include_disposed:
        q += " AND status != 'Disposed'"
    if search:
        q += " AND (title LIKE ? OR body_text LIKE ? OR doc_code LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    q += " ORDER BY id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def get_document(doc_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    return row


def get_document_by_code(code):
    conn = get_conn()
    row = conn.execute("SELECT * FROM documents WHERE doc_code=?", (code,)).fetchone()
    conn.close()
    return row


def find_by_qr(token):
    conn = get_conn()
    row = conn.execute("SELECT * FROM documents WHERE qr_token=?", (token,)).fetchone()
    conn.close()
    return row


def update_document_text(doc_id, body_text, actor, note="OCR text updated"):
    conn = get_conn()
    conn.execute("UPDATE documents SET body_text=?, modified_by=?, modified_at=? WHERE id=?",
                 (body_text, actor, now(), doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Edited", note)


# --------------------------------------------------------------- versions --
def get_versions(doc_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM versions WHERE document_id=? ORDER BY id DESC", (doc_id,)).fetchall()
    conn.close()
    return rows


def checkout_document(doc_id, actor):
    conn = get_conn()
    row = conn.execute("SELECT checked_out_by FROM versions WHERE document_id=? ORDER BY id DESC LIMIT 1",
                        (doc_id,)).fetchone()
    conn.execute("UPDATE versions SET checked_out_by=? WHERE id = (SELECT id FROM versions WHERE document_id=? ORDER BY id DESC LIMIT 1)",
                 (actor, doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Checked Out", "Document locked for editing")
    return True


def checkin_new_version(doc_id, actor, new_text, notes, bump="minor"):
    conn = get_conn()
    cur = conn.cursor()
    last = cur.execute("SELECT version_no FROM versions WHERE document_id=? ORDER BY id DESC LIMIT 1",
                        (doc_id,)).fetchone()
    major, minor = (last["version_no"].split(".") + ["0"])[:2] if last else ("1", "0")
    if bump == "major":
        new_ver = f"{int(major) + 1}.0"
    else:
        new_ver = f"{major}.{int(minor) + 1}"
    ts = now()
    # clear checkout + mark previous obsolete relative status stays as historical record
    cur.execute("UPDATE versions SET checked_out_by=NULL WHERE document_id=?", (doc_id,))
    cur.execute("""
        INSERT INTO versions (document_id, version_no, status, notes, body_snapshot, created_by, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (doc_id, new_ver, "Draft", notes, new_text, actor, ts))
    cur.execute("UPDATE documents SET current_version=?, body_text=?, is_published=0, modified_by=?, modified_at=? WHERE id=?",
                (new_ver, new_text, actor, ts, doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "New Version Checked In", f"v{new_ver} — {notes}")
    return new_ver


def publish_version(doc_id, actor):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE versions SET status='Obsolete' WHERE document_id=? AND status='Published'", (doc_id,))
    cur.execute("UPDATE versions SET status='Published' WHERE id = (SELECT id FROM versions WHERE document_id=? ORDER BY id DESC LIMIT 1)",
                (doc_id,))
    cur.execute("UPDATE documents SET is_published=1, modified_by=?, modified_at=? WHERE id=?",
                (actor, now(), doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Version Published", "Marked as official released version")


def mark_version_obsolete(doc_id, version_id, actor):
    conn = get_conn()
    conn.execute("UPDATE versions SET status='Obsolete' WHERE id=?", (version_id,))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Version Marked Obsolete", f"version id {version_id}")


# -------------------------------------------------------------- workflow ---
def get_workflow(doc_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM workflow WHERE document_id=? ORDER BY stage_order", (doc_id,)).fetchall()
    conn.close()
    return rows


def get_pending_for_assignee(assignee_dept_or_all, is_admin_user=False):
    conn = get_conn()
    if is_admin_user:
        rows = conn.execute("""
            SELECT w.*, d.title, d.doc_code, d.department, d.classification
            FROM workflow w JOIN documents d ON d.id = w.document_id
            WHERE w.status='active' ORDER BY w.id DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT w.*, d.title, d.doc_code, d.department, d.classification
            FROM workflow w JOIN documents d ON d.id = w.document_id
            WHERE w.status='active' AND d.department=? ORDER BY w.id DESC
        """, (assignee_dept_or_all,)).fetchall()
    conn.close()
    return rows


def advance_workflow(doc_id, action, actor, comment=""):
    """action: 'approve' or 'reject'. Advances to next stage or finalizes release."""
    conn = get_conn()
    cur = conn.cursor()
    active = cur.execute("SELECT * FROM workflow WHERE document_id=? AND status='active'", (doc_id,)).fetchone()
    if not active:
        conn.close()
        return False
    ts = now()
    if action == "approve":
        cur.execute("UPDATE workflow SET status='done', acted_by=?, acted_at=?, comment=? WHERE id=?",
                    (actor, ts, comment, active["id"]))
        nxt = cur.execute("SELECT * FROM workflow WHERE document_id=? AND stage_order=?",
                           (doc_id, active["stage_order"] + 1)).fetchone()
        if nxt:
            cur.execute("UPDATE workflow SET status='active' WHERE id=?", (nxt["id"],))
            cur.execute("UPDATE documents SET status=?, modified_by=?, modified_at=? WHERE id=?",
                        (nxt["stage"], actor, ts, doc_id))
            if nxt["stage"] == "Released":
                # Released is the terminal stage: finalize immediately, no extra click
                qr = make_qr_token()
                cur.execute("UPDATE workflow SET status='done', acted_by=?, acted_at=? WHERE id=?",
                            (actor, ts, nxt["id"]))
                cur.execute("""UPDATE documents SET status='Released', is_published=1, qr_token=?,
                             released_at=?, modified_by=?, modified_at=? WHERE id=?""",
                            (qr, ts, actor, ts, doc_id))
                cur.execute("UPDATE versions SET status='Published' WHERE id = (SELECT id FROM versions WHERE document_id=? ORDER BY id DESC LIMIT 1)",
                            (doc_id,))
        log_msg = ("Approved", f"{active['stage']} stage approved")
    else:
        cur.execute("UPDATE workflow SET status='rejected', acted_by=?, acted_at=?, comment=? WHERE id=?",
                     (actor, ts, comment, active["id"]))
        cur.execute("UPDATE documents SET status='Rejected', modified_by=?, modified_at=? WHERE id=?",
                    (actor, ts, doc_id))
        log_msg = ("Rejected", f"{active['stage']} stage rejected — {comment}")
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, *log_msg)
    return True


def delegate_stage(doc_id, actor, delegate_to):
    conn = get_conn()
    conn.execute("UPDATE workflow SET delegated_to=? WHERE document_id=? AND status='active'",
                 (delegate_to, doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Delegated", f"Approval delegated to {delegate_to}")


# ---------------------------------------------------------- correspondence -
def log_correspondence(doc_id, direction, channel, sender, recipient, subject, logged_by):
    conn = get_conn()
    conn.execute("""
        INSERT INTO correspondence (document_id, direction, channel, sender, recipient, subject, logged_by, logged_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (doc_id, direction, channel, sender, recipient, subject, logged_by, now()))
    conn.commit()
    conn.close()


def get_correspondence(limit=200):
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.*, d.doc_code, d.title, d.status FROM correspondence c
        JOIN documents d ON d.id = c.document_id ORDER BY c.id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


# -------------------------------------------------------------- retention --
def archive_document(doc_id, actor):
    conn = get_conn()
    conn.execute("UPDATE documents SET status='Archived', archived_at=?, modified_by=?, modified_at=? WHERE id=?",
                 (now(), actor, now(), doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Archived", "Moved to archive library per retention schedule")


def toggle_legal_hold(doc_id, actor, hold: bool):
    conn = get_conn()
    conn.execute("UPDATE documents SET legal_hold=? WHERE id=?", (1 if hold else 0, doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Legal Hold " + ("Applied" if hold else "Released"))


def request_disposal(doc_id, actor, reason):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO disposal_requests (document_id, requested_by, requested_at, reason, status)
        VALUES (?,?,?,?,?)
    """, (doc_id, actor, now(), reason, "Pending Approval"))
    conn.commit()
    conn.close()
    log_audit(doc_id, actor, "Disposal Requested", reason)


def get_disposal_requests(status=None):
    conn = get_conn()
    q = """SELECT r.*, d.title, d.doc_code, d.department, d.legal_hold FROM disposal_requests r
           JOIN documents d ON d.id = r.document_id"""
    params = []
    if status:
        q += " WHERE r.status=?"
        params.append(status)
    q += " ORDER BY r.id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def decide_disposal(request_id, approver, approve: bool):
    conn = get_conn()
    cur = conn.cursor()
    req = cur.execute("SELECT * FROM disposal_requests WHERE id=?", (request_id,)).fetchone()
    if not req:
        conn.close()
        return False
    ts = now()
    new_status = "Approved" if approve else "Rejected"
    cur.execute("UPDATE disposal_requests SET status=?, approved_by=?, approved_at=? WHERE id=?",
                (new_status, approver, ts, request_id))
    doc_id = req["document_id"]
    if approve:
        cur.execute("UPDATE documents SET status='Disposed', disposed_at=?, modified_by=?, modified_at=? WHERE id=?",
                    (ts, approver, ts, doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, approver, f"Disposal {new_status}", f"Request #{request_id}")
    return True


def finalize_destruction(request_id, actor):
    conn = get_conn()
    cur = conn.cursor()
    req = cur.execute("SELECT * FROM disposal_requests WHERE id=?", (request_id,)).fetchone()
    cur.execute("UPDATE disposal_requests SET status='Destroyed' WHERE id=?", (request_id,))
    conn.commit()
    conn.close()
    if req:
        log_audit(req["document_id"], actor, "Destruction Evidence Logged",
                   "Secure disposal completed with audit evidence retained")


# ----------------------------------------------------------------- stats ---
def stats():
    conn = get_conn()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) n FROM documents").fetchone()["n"]
    released = c.execute("SELECT COUNT(*) n FROM documents WHERE status='Released'").fetchone()["n"]
    pending = c.execute("SELECT COUNT(*) n FROM workflow WHERE status='active'").fetchone()["n"]
    archived = c.execute("SELECT COUNT(*) n FROM documents WHERE status='Archived'").fetchone()["n"]
    rejected = c.execute("SELECT COUNT(*) n FROM documents WHERE status='Rejected'").fetchone()["n"]
    expiring = c.execute(
        "SELECT COUNT(*) n FROM documents WHERE expiry_date IS NOT NULL AND expiry_date <= date('now','+90 day') AND status NOT IN ('Disposed')"
    ).fetchone()["n"]
    by_dept = c.execute("SELECT department, COUNT(*) n FROM documents GROUP BY department").fetchall()
    by_status = c.execute("SELECT status, COUNT(*) n FROM documents GROUP BY status").fetchall()
    conn.close()
    return {
        "total": total, "released": released, "pending": pending, "archived": archived,
        "rejected": rejected, "expiring": expiring,
        "by_dept": by_dept, "by_status": by_status,
    }
