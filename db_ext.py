"""Extended schema + helpers for RFP-driven features (workspace, redaction, backup, dispatch,
physical records, workflow templates, e-signature log, policy settings)."""
import json
import os
import shutil
import sqlite3
import datetime as dt
import hashlib
import db
import rfp_data


def _c():
    return db.get_conn()


def init_ext():
    conn = _c()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, document_id INTEGER, created_at TEXT);
    CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, message TEXT,
        document_id INTEGER, kind TEXT, is_read INTEGER DEFAULT 0, ts TEXT);
    CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, topic TEXT);
    CREATE TABLE IF NOT EXISTS recent_views (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, document_id INTEGER, ts TEXT);
    CREATE TABLE IF NOT EXISTS search_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, query TEXT, hits INTEGER, ts TEXT);
    CREATE TABLE IF NOT EXISTS annotations (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, user TEXT,
        kind TEXT, text TEXT, target TEXT, reason TEXT, restricted INTEGER DEFAULT 0, ts TEXT);
    CREATE TABLE IF NOT EXISTS dispatch (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, category TEXT, kind TEXT,
        recipient TEXT, status TEXT DEFAULT 'Drafted', approved_by TEXT, released_by TEXT, dispatched_at TEXT,
        copies_to TEXT, created_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS physical_records (id INTEGER PRIMARY KEY AUTOINCREMENT, box_code TEXT, description TEXT,
        department TEXT, site TEXT, location TEXT, custodian TEXT, status TEXT, retention_until TEXT, document_id INTEGER);
    CREATE TABLE IF NOT EXISTS workflow_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, department TEXT, doc_type TEXT,
        stages TEXT, updated_by TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS esign_log (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, signer TEXT,
        stage TEXT, signature_hash TEXT, ts TEXT);
    CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, path TEXT, created_by TEXT,
        created_at TEXT, size_kb INTEGER, kind TEXT);
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS ad_users (username TEXT PRIMARY KEY, display TEXT, department TEXT, groups TEXT,
        status TEXT, last_sync TEXT);
    CREATE TABLE IF NOT EXISTS login_attempts (user TEXT PRIMARY KEY, failures INTEGER DEFAULT 0, locked INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS shares (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, to_department TEXT,
        shared_by TEXT, ts TEXT);
    """)
    for tbl, col, ddl in [("documents", "deleted_from", "TEXT"), ("documents", "deleted_at", "TEXT"),
                           ("documents", "deleted_by", "TEXT"), ("documents", "site", "TEXT"),
                           ("documents", "classification_path", "TEXT")]:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if col not in cols:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ddl}")
    conn.executescript("""
    CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
    BEGIN SELECT RAISE(ABORT, 'audit_log is immutable: records cannot be altered'); END;
    CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
    BEGIN SELECT RAISE(ABORT, 'audit_log is immutable: records cannot be deleted'); END;
    """)
    conn.commit()
    conn.close()
    import distribution
    distribution.init_dist()
    import wfdesign
    wfdesign.init()
    import numbering
    numbering.init()
    import delegation
    delegation.init()
    import exchange
    exchange.init()
    import letter_templates
    letter_templates.init()
    import accounts
    accounts.init_accounts()
    import audit_ext
    audit_ext.seed_history()


# ------------------------------------------------------------- numbering ---
def next_code_fixed(department, doc_type):
    """Fixed standard DEPT-TYPE-YYYY-NNNN (SOW 2.2.10.5)."""
    d = rfp_data.DEPT_CODE.get(department, "GEN")
    t = rfp_data.TYPE_CODE.get(doc_type, "DOC")
    yr = dt.datetime.now().year
    conn = _c()
    pref = f"{d}-{t}-{yr}-"
    n = conn.execute("SELECT COUNT(*) c FROM documents WHERE doc_code LIKE ?", (pref + "%",)).fetchone()["c"]
    conn.close()
    return f"{pref}{n + 1:04d}"


def next_code(department, doc_type, classification=None, security_level=None):
    """Issue the next document number — fixed standard or rule-based, per the Numbering Rules switch."""
    import numbering
    if numbering.mode() == "dynamic":
        return numbering.next_number(department, doc_type, classification, security_level)[0]
    return next_code_fixed(department, doc_type)


# ------------------------------------------------------ workflow templates --
DEFAULT_STAGES = ["Draft", "Department Review", "Approval", "Released"]
FINANCE_STAGES = ["Draft", "Department Review", "Approval", "Finance Sign-off", "Released"]


def stages_for(department, doc_type):
    conn = _c()
    row = conn.execute("SELECT stages FROM workflow_templates WHERE department=? AND doc_type=?",
                        (department, doc_type)).fetchone()
    if not row:
        row = conn.execute("SELECT stages FROM workflow_templates WHERE department=? AND (doc_type IS NULL OR doc_type='')",
                            (department,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["stages"])
    return FINANCE_STAGES if doc_type in rfp_data.FINANCE_TYPES else DEFAULT_STAGES


def save_template(department, doc_type, stages, user):
    conn = _c()
    conn.execute("DELETE FROM workflow_templates WHERE department=? AND COALESCE(doc_type,'')=?", (department, doc_type or ""))
    conn.execute("INSERT INTO workflow_templates (department, doc_type, stages, updated_by, updated_at) VALUES (?,?,?,?,?)",
                 (department, doc_type or "", json.dumps(stages), user, db.now()))
    conn.commit()
    conn.close()


def list_templates():
    conn = _c()
    rows = conn.execute("SELECT * FROM workflow_templates ORDER BY department, doc_type").fetchall()
    conn.close()
    return rows


# ------------------------------------------------------------- e-signature --
def log_esign(document_id, signer, stage):
    h = hashlib.sha256(f"{document_id}|{signer}|{stage}|{db.now()}".encode()).hexdigest()[:20].upper()
    conn = _c()
    conn.execute("INSERT INTO esign_log (document_id, signer, stage, signature_hash, ts) VALUES (?,?,?,?,?)",
                 (document_id, signer, stage, h, db.now()))
    conn.commit()
    conn.close()
    return h


def esign_report():
    conn = _c()
    rows = conn.execute("""SELECT e.*, d.doc_code, d.title FROM esign_log e LEFT JOIN documents d ON d.id=e.document_id
                           ORDER BY e.id DESC""").fetchall()
    conn.close()
    return rows


# ------------------------------------------------------------ notifications --
def notify(user, message, document_id=None, kind="info"):
    conn = _c()
    conn.execute("INSERT INTO notifications (user, message, document_id, kind, ts) VALUES (?,?,?,?,?)",
                 (user, message, document_id, kind, db.now()))
    conn.commit()
    conn.close()


def get_notifications(user, only_unread=False):
    conn = _c()
    q = "SELECT * FROM notifications WHERE user=?" + (" AND is_read=0" if only_unread else "") + " ORDER BY id DESC LIMIT 100"
    rows = conn.execute(q, (user,)).fetchall()
    conn.close()
    return rows


def mark_all_read(user):
    conn = _c()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user=?", (user,))
    conn.commit()
    conn.close()


def subscribers_of(document_id, topic=None):
    conn = _c()
    rows = conn.execute("SELECT user FROM subscriptions WHERE topic=? OR topic=?",
                        (f"doc:{document_id}", f"topic:{topic}")).fetchall()
    conn.close()
    return [r["user"] for r in rows]


def toggle_subscription(user, topic):
    conn = _c()
    ex = conn.execute("SELECT id FROM subscriptions WHERE user=? AND topic=?", (user, topic)).fetchone()
    if ex:
        conn.execute("DELETE FROM subscriptions WHERE id=?", (ex["id"],))
    else:
        conn.execute("INSERT INTO subscriptions (user, topic) VALUES (?,?)", (user, topic))
    conn.commit()
    conn.close()
    return not ex


def my_subscriptions(user):
    conn = _c()
    rows = conn.execute("SELECT topic FROM subscriptions WHERE user=?", (user,)).fetchall()
    conn.close()
    return [r["topic"] for r in rows]


# ---------------------------------------------------------------- bookmarks --
def toggle_bookmark(user, document_id):
    conn = _c()
    ex = conn.execute("SELECT id FROM bookmarks WHERE user=? AND document_id=?", (user, document_id)).fetchone()
    if ex:
        conn.execute("DELETE FROM bookmarks WHERE id=?", (ex["id"],))
    else:
        conn.execute("INSERT INTO bookmarks (user, document_id, created_at) VALUES (?,?,?)", (user, document_id, db.now()))
    conn.commit()
    conn.close()


def get_bookmarks(user):
    conn = _c()
    rows = conn.execute("""SELECT d.* FROM bookmarks b JOIN documents d ON d.id=b.document_id
                           WHERE b.user=? AND d.status NOT IN ('Deleted','Disposed') ORDER BY b.id DESC""", (user,)).fetchall()
    conn.close()
    return rows


def log_view(user, document_id):
    conn = _c()
    conn.execute("INSERT INTO recent_views (user, document_id, ts) VALUES (?,?,?)", (user, document_id, db.now()))
    conn.commit()
    conn.close()


def recent_views(user, n=8):
    conn = _c()
    rows = conn.execute("""SELECT d.*, MAX(v.ts) last_ts FROM recent_views v JOIN documents d ON d.id=v.document_id
                           WHERE v.user=? AND d.status NOT IN ('Deleted','Disposed') GROUP BY d.id
                           ORDER BY last_ts DESC LIMIT ?""", (user, n)).fetchall()
    conn.close()
    return rows


# ----------------------------------------------------------- recycle bin ----
def soft_delete(document_id, user):
    d = db.get_document(document_id)
    if not d or d["status"] in ("Deleted", "Disposed") or d["legal_hold"]:
        return False
    conn = _c()
    conn.execute("UPDATE documents SET deleted_from=?, status='Deleted', deleted_at=?, deleted_by=? WHERE id=?",
                 (d["status"], db.now(), user, document_id))
    conn.commit()
    conn.close()
    db.log_audit(document_id, user, "Moved to Recycle Bin", "Soft delete — restorable")
    return True


def restore(document_id, user):
    d = db.get_document(document_id)
    if not d or d["status"] != "Deleted":
        return False
    conn = _c()
    conn.execute("UPDATE documents SET status=COALESCE(deleted_from,'Draft'), deleted_at=NULL, deleted_by=NULL WHERE id=?",
                 (document_id,))
    conn.commit()
    conn.close()
    db.log_audit(document_id, user, "Restored from Recycle Bin", "Restored to previous state")
    return True


def recycle_bin():
    conn = _c()
    rows = conn.execute("SELECT * FROM documents WHERE status='Deleted' ORDER BY deleted_at DESC").fetchall()
    conn.close()
    return rows


# --------------------------------------------------------- search history ---
def log_search(user, query, hits):
    if not query:
        return
    conn = _c()
    conn.execute("INSERT INTO search_history (user, query, hits, ts) VALUES (?,?,?,?)", (user, query, hits, db.now()))
    conn.commit()
    conn.close()


def get_search_history(user, n=15):
    conn = _c()
    rows = conn.execute("SELECT * FROM search_history WHERE user=? ORDER BY id DESC LIMIT ?", (user, n)).fetchall()
    conn.close()
    return rows


# ----------------------------------------------------------- annotations ----
def add_annotation(document_id, user, kind, text, target, reason="", restricted=0):
    conn = _c()
    conn.execute("""INSERT INTO annotations (document_id, user, kind, text, target, reason, restricted, ts)
                    VALUES (?,?,?,?,?,?,?,?)""", (document_id, user, kind, text, target, reason, restricted, db.now()))
    conn.commit()
    conn.close()
    db.log_audit(document_id, user, "Annotated", f"{kind}: {target[:60]}" + (f" (reason: {reason})" if reason else ""))


def get_annotations(document_id):
    conn = _c()
    rows = conn.execute("SELECT * FROM annotations WHERE document_id=? ORDER BY id", (document_id,)).fetchall()
    conn.close()
    return rows


def delete_annotation(ann_id):
    conn = _c()
    conn.execute("DELETE FROM annotations WHERE id=?", (ann_id,))
    conn.commit()
    conn.close()


# ----------------------------------------------------------- dispatch -------
DISPATCH_STEPS = ["Drafted", "Approved", "Released", "Dispatched"]


def create_dispatch(document_id, category, kind, recipient, copies_to, user):
    conn = _c()
    conn.execute("""INSERT INTO dispatch (document_id, category, kind, recipient, status, copies_to, created_by, created_at)
                    VALUES (?,?,?,?,?,?,?,?)""", (document_id, category, kind, recipient, "Drafted", copies_to, user, db.now()))
    conn.commit()
    conn.close()


def advance_dispatch(dispatch_id, user):
    conn = _c()
    r = conn.execute("SELECT * FROM dispatch WHERE id=?", (dispatch_id,)).fetchone()
    if not r or r["status"] == "Dispatched":
        conn.close()
        return
    nxt = DISPATCH_STEPS[DISPATCH_STEPS.index(r["status"]) + 1]
    if nxt == "Approved":
        conn.execute("UPDATE dispatch SET status=?, approved_by=? WHERE id=?", (nxt, user, dispatch_id))
    elif nxt == "Released":
        conn.execute("UPDATE dispatch SET status=?, released_by=? WHERE id=?", (nxt, user, dispatch_id))
    else:
        conn.execute("UPDATE dispatch SET status=?, dispatched_at=? WHERE id=?", (nxt, db.now(), dispatch_id))
    conn.commit()
    conn.close()
    db.log_audit(r["document_id"], user, f"Outgoing {nxt}", f"{r['kind']} to {r['recipient']}")


def list_dispatch():
    conn = _c()
    rows = conn.execute("""SELECT x.*, d.doc_code, d.title FROM dispatch x LEFT JOIN documents d ON d.id=x.document_id
                           ORDER BY x.id DESC""").fetchall()
    conn.close()
    return rows


# ------------------------------------------------------- physical records ---
def add_physical(box_code, description, department, site, location, custodian, retention_until):
    conn = _c()
    conn.execute("""INSERT INTO physical_records (box_code, description, department, site, location, custodian, status,
                    retention_until) VALUES (?,?,?,?,?,?,?,?)""",
                 (box_code, description, department, site, location, custodian, "In Storage", retention_until))
    conn.commit()
    conn.close()


def list_physical():
    conn = _c()
    rows = conn.execute("SELECT * FROM physical_records ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def set_physical_status(rec_id, status, custodian=None):
    conn = _c()
    if custodian:
        conn.execute("UPDATE physical_records SET status=?, custodian=? WHERE id=?", (status, custodian, rec_id))
    else:
        conn.execute("UPDATE physical_records SET status=? WHERE id=?", (status, rec_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- backup ----
BACKUP_DIR = os.path.join(db.DB_DIR, "backups")


def make_backup(label, user, kind="Manual"):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(BACKUP_DIR, f"edms_{stamp}.db")
    src = _c()
    dst = sqlite3.connect(path)
    src.backup(dst)
    dst.close()
    src.close()
    size = max(1, os.path.getsize(path) // 1024)
    conn = _c()
    conn.execute("INSERT INTO backups (label, path, created_by, created_at, size_kb, kind) VALUES (?,?,?,?,?,?)",
                 (label, path, user, db.now(), size, kind))
    conn.commit()
    conn.close()
    return path


def list_backups():
    conn = _c()
    rows = conn.execute("SELECT * FROM backups ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def restore_backup(backup_id, user):
    conn = _c()
    b = conn.execute("SELECT * FROM backups WHERE id=?", (backup_id,)).fetchone()
    conn.close()
    if not b or not os.path.exists(b["path"]):
        return False
    make_backup(f"Auto pre-restore snapshot (before restoring '{b['label']}')", user, kind="Auto")
    kc = _c()
    keep = [tuple(r) for r in kc.execute("SELECT label, path, created_by, created_at, size_kb, kind FROM backups ORDER BY id").fetchall()]
    kc.close()
    src = sqlite3.connect(b["path"])
    dst = _c()
    src.backup(dst)
    src.close()
    dst.execute("CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, path TEXT, created_by TEXT, created_at TEXT, size_kb INTEGER, kind TEXT)")
    dst.execute("DELETE FROM backups")
    dst.executemany("INSERT INTO backups (label, path, created_by, created_at, size_kb, kind) VALUES (?,?,?,?,?,?)", keep)
    dst.commit()
    dst.close()
    init_ext()
    db.log_audit(None, user, "System Restored", f"Restored to recovery point '{b['label']}' ({b['created_at']})")
    return True


# -------------------------------------------------------------- settings ----
DEFAULT_POLICY = {"pw_min_len": "12", "pw_complex": "1", "pw_expiry_days": "90", "mfa": "1",
                  "lockout_after": "5", "idle_minutes": "15"}


def get_policy():
    conn = _c()
    rows = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings").fetchall()}
    conn.close()
    p = dict(DEFAULT_POLICY)
    p.update({k: v for k, v in rows.items() if k in DEFAULT_POLICY})
    return p


def set_policy(values, user):
    conn = _c()
    for k, v in values.items():
        conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Security Policy Updated", ", ".join(f"{k}={v}" for k, v in values.items()))


def attempt_login(user, ok):
    pol = get_policy()
    conn = _c()
    row = conn.execute("SELECT * FROM login_attempts WHERE user=?", (user,)).fetchone()
    fails = row["failures"] if row else 0
    locked = row["locked"] if row else 0
    if locked:
        conn.close()
        return "locked"
    if ok:
        fails = 0
    else:
        fails += 1
        if fails >= int(pol["lockout_after"]):
            locked = 1
    conn.execute("INSERT INTO login_attempts (user, failures, locked) VALUES (?,?,?) "
                 "ON CONFLICT(user) DO UPDATE SET failures=excluded.failures, locked=excluded.locked", (user, fails, locked))
    conn.commit()
    conn.close()
    return "locked" if locked else ("ok" if ok else f"failed ({fails}/{pol['lockout_after']})")


def unlock(user, admin):
    conn = _c()
    conn.execute("UPDATE login_attempts SET failures=0, locked=0 WHERE user=?", (user,))
    conn.commit()
    conn.close()
    db.log_audit(None, admin, "Account Unlocked", f"Administrator override for {user}")


def get_lock_state(user):
    conn = _c()
    r = conn.execute("SELECT * FROM login_attempts WHERE user=?", (user,)).fetchone()
    conn.close()
    return (r["failures"], r["locked"]) if r else (0, 0)


# ------------------------------------------------------------ AD directory --
def sync_ad():
    conn = _c()
    ts = db.now()
    n = 0
    for name, p in rfp_data.ROLES.items():
        user = name.lower().replace(" ", ".").replace("-", "")
        grp = f"EDMS-{rfp_data.DEPT_CODE.get(p['dept'], 'IT')}-Users" + (";EDMS-Admins" if p["level"] == "admin" else "")
        conn.execute("""INSERT INTO ad_users (username, display, department, groups, status, last_sync) VALUES (?,?,?,?,?,?)
                        ON CONFLICT(username) DO UPDATE SET display=excluded.display, department=excluded.department,
                        groups=excluded.groups, status='Active', last_sync=excluded.last_sync""",
                     (user, name, p["dept"], grp, "Active", ts))
        n += 1
    conn.commit()
    conn.close()
    return n


def list_ad():
    conn = _c()
    rows = conn.execute("SELECT * FROM ad_users ORDER BY department").fetchall()
    conn.close()
    return rows


def deprovision(username, admin):
    conn = _c()
    conn.execute("UPDATE ad_users SET status='Disabled (de-provisioned)', last_sync=? WHERE username=?", (db.now(), username))
    conn.commit()
    conn.close()
    db.log_audit(None, admin, "User De-provisioned", f"{username} disabled via AD sync")


# ----------------------------------------------------------------- shares ---
def share_doc(document_id, to_department, user):
    conn = _c()
    conn.execute("INSERT INTO shares (document_id, to_department, shared_by, ts) VALUES (?,?,?,?)",
                 (document_id, to_department, user, db.now()))
    conn.commit()
    conn.close()
    db.log_audit(document_id, user, "Shared", f"Shared with {to_department} as-needed")


def shared_with(department):
    conn = _c()
    rows = conn.execute("SELECT document_id FROM shares WHERE to_department=?", (department,)).fetchall()
    conn.close()
    return {r["document_id"] for r in rows}


def list_shares():
    conn = _c()
    rows = conn.execute("""SELECT s.*, d.doc_code, d.title, d.department FROM shares s JOIN documents d ON d.id=s.document_id
                           ORDER BY s.id DESC""").fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------- reports ---
def overdue_approvals(sla_days=3):
    conn = _c()
    rows = conn.execute("""SELECT d.id, d.doc_code, d.title, d.department, d.status, d.modified_at,
                           CAST(julianday('now') - julianday(d.modified_at) AS INTEGER) days
                           FROM documents d WHERE d.status IN ('Department Review','Approval','Finance Sign-off')
                           AND julianday('now') - julianday(d.modified_at) > ? ORDER BY days DESC""", (sla_days,)).fetchall()
    conn.close()
    return rows


def expiry_report():
    conn = _c()
    rows = conn.execute("""SELECT id, doc_code, title, department, expiry_date, legal_hold,
                           CAST(julianday(expiry_date) - julianday('now') AS INTEGER) days_left
                           FROM documents WHERE expiry_date IS NOT NULL AND status NOT IN ('Deleted','Disposed')
                           ORDER BY expiry_date""").fetchall()
    conn.close()
    return rows


def department_compliance():
    """Per-department compliance posture used by the audit-readiness dashboard."""
    conn = _c()
    out = []
    for dept in rfp_data.DEPARTMENTS:
        docs = conn.execute("SELECT * FROM documents WHERE department=? AND status NOT IN ('Deleted','Disposed')", (dept,)).fetchall()
        n = len(docs)
        if not n:
            out.append({"department": dept, "docs": 0, "released_pct": None, "overdue": 0, "no_retention": 0, "score": None})
            continue
        rel = sum(1 for d in docs if d["status"] in ("Released", "Archived"))
        od = sum(1 for d in docs if d["status"] in ("Department Review", "Approval", "Finance Sign-off") and
                 conn.execute("SELECT julianday('now')-julianday(?)", (d["modified_at"],)).fetchone()[0] > 3)
        nr = sum(1 for d in docs if not d["retention_schedule"])
        score = max(0, round(100 * (0.5 * rel / n + 0.3 * (1 - od / n) + 0.2 * (1 - nr / n))))
        out.append({"department": dept, "docs": n, "released_pct": round(100 * rel / n), "overdue": od,
                    "no_retention": nr, "score": score})
    conn.close()
    return out


def storage_usage():
    conn = _c()
    docs = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
    vers = conn.execute("SELECT COUNT(*) c FROM versions").fetchone()["c"]
    logs = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    conn.close()
    size = os.path.getsize(db.DB_PATH) // 1024 if os.path.exists(db.DB_PATH) else 0
    return {"documents": docs, "versions": vers, "audit_events": logs, "db_kb": size}


# ------------------------------------------------------ declared records ----
def declare_record(document_id, user):
    conn = _c()
    conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (f"declared:{document_id}", f"{user}|{db.now()}"))
    conn.commit()
    conn.close()
    db.log_audit(document_id, user, "Record Declared", "Registered and declared as an official record — immutable")


def is_declared(document_id):
    conn = _c()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (f"declared:{document_id}",)).fetchone()
    conn.close()
    return r["value"] if r else None
