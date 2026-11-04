"""User & role management (DB-backed). Keeps rfp_data.ROLES in sync so every existing page sees current users."""
import datetime as dt
import hashlib
import hmac
import json
import os
import db
import rfp_data

PERMS = ["view", "edit", "approve", "release", "delete", "export", "admin"]
PERM_LABEL = {"view": "View", "edit": "Edit", "approve": "Approve", "release": "Release", "delete": "Delete", "export": "Export", "admin": "Administer"}
CLEARANCE = ["Public", "Internal", "Restricted", "Confidential"]
DEMO_PASSWORD = "Demo@2026"

MODULES = {  # key -> (label, emoji, colour)
    "home": ("Home / Lifecycle Story", "🏠", "#1F3864"), "1": ("Correspondence & Intake", "📥", "#2E8B8B"), "2": ("OCR & Intelligent Capture", "🖨️", "#C0603C"),
    "3": ("Document Control & Versioning", "📚", "#6C4FA3"), "4": ("Workflow & Approvals", "🔀", "#B8860B"), "5": ("Security & Compliance", "🛡️", "#2E7D32"),
    "6": ("Search & Retrieval", "🔎", "#4A90C2"), "7": ("Audit, Governance & Reporting", "🧾", "#1F3864"), "8": ("Records, Archiving & Disposal", "🗄️", "#8D6E63"),
    "9": ("My Workspace", "💼", "#2E8B8B"), "10": ("Administration & Integrations", "⚙️", "#6B7280"), "11": ("RFP Coverage", "✅", "#2E7D32"),
    "12": ("Auto-Distribution", "📬", "#C0603C"), "13": ("Analytics & Insights", "📊", "#6C4FA3"), "14": ("User Management", "👥", "#1F6F78"),
    "15": ("Role Management", "🔐", "#B00020"), "16": ("Ask EDMS — Search Assistant", "🤖", "#2E8B8B"), "17": ("Workflow Designer", "🧩", "#6C4FA3"), "18": ("Numbering Rules", "🔢", "#B8860B"),
    "19": ("Approval Delegation", "🏖️", "#1F6F78"),
}
ALL = [m for m in MODULES if m not in ("16", "17", "18", "19")]   # 16 (assistant) is available to every signed-in role
OPS = ["home", "1", "2", "3", "4", "6", "7", "8", "9", "12", "13"]
MGR = ["home", "1", "3", "4", "6", "7", "9", "12", "13"]

ROLE_SEED = [  # name, level, description, colour, perms, modules, clearance
    ("Administrator", "admin", "Full control: users, roles, policies, integrations, backup & restore", "#B00020", PERMS, ALL, "Confidential"),
    ("Records Officer", "department_user", "Owns capture, registration, classification, retention and disposal", "#2E8B8B",
     ["view", "edit", "approve", "release", "export"], OPS, "Confidential"),
    ("HR Manager", "department_user", "Department manager — reviews and approves HR documents", "#6C4FA3", ["view", "edit", "approve", "export"], MGR, "Confidential"),
    ("Finance Controller", "department_user", "Department manager — finance sign-off stage", "#2E7D32", ["view", "edit", "approve", "export"], MGR, "Restricted"),
    ("Nursing Supervisor", "department_user", "Department manager — nursing documents", "#4A90C2", ["view", "edit", "approve", "export"], MGR, "Confidential"),
    ("QRI Officer", "department_user", "Quality, risk & improvement — accreditation evidence", "#B8860B", ["view", "edit", "approve", "export"], MGR + ["8"], "Restricted"),
    ("Legal Counsel", "department_user", "Legal review stage, legal holds and contracts", "#1F3864", ["view", "edit", "approve", "export"], MGR + ["8"], "Confidential"),
    ("Internal Auditor", "department_user", "Read-only: audit trail, records and compliance evidence", "#C0603C", ["view", "export"], ["home", "6", "7", "8", "11", "13"], "Restricted"),
    ("Scanning Operator", "department_user", "Capture station: scan, OCR, correct and file documents", "#8D6E63", ["view", "edit"], ["home", "1", "2", "6", "12"], "Internal"),
    ("Executive", "department_user", "Leadership view: dashboards, approvals and search", "#1F6F78", ["view", "approve", "export"], ["home", "6", "7", "9", "13"], "Confidential"),
]
USER_SEED = [  # extra people (the original seven come from rfp_data.ROLES)
    ("Khalid Al-Mannai", "Internal Auditor", "QRI", "khalid.almannai@demo.local"),
    ("Mariam Al-Hajri", "Scanning Operator", "Medical Records", "mariam.alhajri@demo.local"),
    ("Abdulla Al-Thani", "Executive", "Executive Offices", "abdulla.althani@demo.local"),
]
_ORIGINAL = {
    "Sara Al-Ansari": {"role": "Records Officer", "dept": "Medical Records"}, "Omar Al-Kaabi": {"role": "HR Manager", "dept": "HR"},
    "Fatima Al-Sulaiti": {"role": "Finance Controller", "dept": "Finance"}, "Hassan Al-Naimi": {"role": "Nursing Supervisor", "dept": "Nursing"},
    "Layla Al-Marri": {"role": "QRI Officer", "dept": "QRI"}, "Noor Al-Kuwari": {"role": "Legal Counsel", "dept": "Legal"},
    "Yusuf Al-Marri": {"role": "Administrator", "dept": "IT"},
}


def _hash(pw, salt=None):
    salt = salt or os.urandom(8).hex()
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 60000).hex()
    return f"{salt}${h}"


def _check(pw, stored):
    try:
        salt, _ = stored.split("$")
    except Exception:
        return False
    return hmac.compare_digest(_hash(pw, salt), stored)


def _now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_accounts():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS app_roles (name TEXT PRIMARY KEY, level TEXT, description TEXT, color TEXT, perms TEXT, modules TEXT,
        clearance TEXT, system_role INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS app_users (username TEXT PRIMARY KEY, role TEXT, dept TEXT, email TEXT, phone TEXT, active INTEGER DEFAULT 1,
        pw_hash TEXT, must_change INTEGER DEFAULT 0, mfa INTEGER DEFAULT 1, last_login TEXT, created_at TEXT, created_by TEXT);
    """)
    if not conn.execute("SELECT COUNT(*) FROM app_roles").fetchone()[0]:
        for n, lv, ds, col, pm, md, cl in ROLE_SEED:
            conn.execute("INSERT INTO app_roles VALUES (?,?,?,?,?,?,?,?)", (n, lv, ds, col, json.dumps(pm), json.dumps(md), cl, 1 if n == "Administrator" else 0))
    if not conn.execute("SELECT COUNT(*) FROM app_users").fetchone()[0]:
        ph = _hash(DEMO_PASSWORD)
        for n, p in _ORIGINAL.items():
            em = n.lower().replace(" ", ".").replace("-", "") + "@demo.local"
            conn.execute("INSERT INTO app_users (username, role, dept, email, active, pw_hash, created_at, created_by) VALUES (?,?,?,?,1,?,?,?)",
                         (n, p["role"], p["dept"], em, ph, _now(), "System"))
        for n, r, d, em in USER_SEED:
            conn.execute("INSERT INTO app_users (username, role, dept, email, active, pw_hash, created_at, created_by) VALUES (?,?,?,?,1,?,?,?)",
                         (n, r, d, em, ph, _now(), "System"))
    conn.commit()
    conn.close()
    sync_roles()


def roles():
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM app_roles ORDER BY system_role DESC, name")]
    conn.close()
    for r in rows:
        r["perms"] = json.loads(r["perms"] or "[]")
        r["modules"] = json.loads(r["modules"] or "[]")
    return rows


def role(name):
    return next((r for r in roles() if r["name"] == name), None)


def users():
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM app_users ORDER BY username")]
    conn.close()
    for r in rows:
        r["failures"], r["locked"] = _lock(r["username"])
    return rows


def _lock(u):
    import db_ext
    return db_ext.get_lock_state(u)


def sync_roles():
    """Rebuild rfp_data.ROLES in place from active users so the rest of the app sees the current directory."""
    conn = db.get_conn()
    rs = {r["name"]: r for r in conn.execute("SELECT * FROM app_roles")}
    us = conn.execute("SELECT * FROM app_users WHERE active=1 ORDER BY rowid").fetchall()
    conn.close()
    keep = {}
    for u in us:
        r = rs.get(u["role"])
        pm = json.loads(r["perms"]) if r else []
        keep[u["username"]] = {"role": u["role"], "dept": u["dept"], "level": "admin" if "admin" in pm else "department_user",
                               "can_approve": "approve" in pm or "admin" in pm, "email": u["email"]}
    rfp_data.ROLES.clear()
    rfp_data.ROLES.update(keep)


def allowed_modules(user):
    conn = db.get_conn()
    u = conn.execute("SELECT role FROM app_users WHERE username=?", (user,)).fetchone()
    conn.close()
    r = role(u["role"]) if u else None
    if not r:
        return {"home", "16", "19"}
    return set(r["modules"]) | {"16", "19"} | ({"17", "18"} if r.get("level") == "admin" else set())


def has_perm(user, perm):
    conn = db.get_conn()
    u = conn.execute("SELECT role FROM app_users WHERE username=?", (user,)).fetchone()
    conn.close()
    r = role(u["role"]) if u else None
    return bool(r and (perm in r["perms"] or "admin" in r["perms"]))


def authenticate(username, password):
    """Returns (ok, message). Uses the policy lock-out from the security module."""
    import db_ext
    conn = db.get_conn()
    u = conn.execute("SELECT * FROM app_users WHERE lower(username)=lower(?)", (username.strip(),)).fetchone()
    conn.close()
    if not u:
        return False, "Unknown user name."
    name = u["username"]
    if not u["active"]:
        db.log_audit(None, name, "Login Failed", "Account disabled", "Denied")
        return False, "This account is disabled. Contact an administrator."
    ok = bool(u["pw_hash"]) and _check(password, u["pw_hash"])
    st_ = db_ext.attempt_login(name, ok)
    if st_ == "locked":
        db.log_audit(None, name, "Login Failed", "Account locked", "Denied")
        return False, "Account locked after repeated failures. An administrator must unlock it."
    if not ok:
        db.log_audit(None, name, "Login Failed", "Wrong password " + st_.replace("failed ", ""), "Denied")
        return False, f"Incorrect password — {st_.replace('failed ', 'attempt ')}."
    return True, name


def record_login(name, method="Password"):
    conn = db.get_conn()
    conn.execute("UPDATE app_users SET last_login=? WHERE username=?", (_now(), name))
    conn.commit()
    conn.close()
    db.log_audit(None, name, "Login", f"Signed in ({method})")


def record_logout(name):
    db.log_audit(None, name, "Logout", "Signed out")


# --------------------------------------------------------------- admin ops
def _chg(actor, target, field, old, new, action):
    if str(old) != str(new):
        db.log_audit(None, actor, action, f"{target}", field=field, old=old, new=new)


def add_user(actor, username, role_name, dept, email, password):
    conn = db.get_conn()
    if conn.execute("SELECT 1 FROM app_users WHERE lower(username)=lower(?)", (username.strip(),)).fetchone():
        conn.close()
        return False, "A user with that name already exists."
    conn.execute("INSERT INTO app_users (username, role, dept, email, active, pw_hash, must_change, created_at, created_by) VALUES (?,?,?,?,1,?,1,?,?)",
                 (username.strip(), role_name, dept, email, _hash(password), _now(), actor))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "User Created", username.strip(), field="role", old="—", new=role_name)
    sync_roles()
    return True, "User created."


def update_user(actor, username, role_name, dept, email, active):
    conn = db.get_conn()
    o = conn.execute("SELECT * FROM app_users WHERE username=?", (username,)).fetchone()
    conn.execute("UPDATE app_users SET role=?, dept=?, email=?, active=? WHERE username=?", (role_name, dept, email, 1 if active else 0, username))
    conn.commit()
    conn.close()
    _chg(actor, username, "role", o["role"], role_name, "User Role Changed")
    _chg(actor, username, "department", o["dept"], dept, "User Updated")
    _chg(actor, username, "email", o["email"], email, "User Updated")
    _chg(actor, username, "status", "Active" if o["active"] else "Disabled", "Active" if active else "Disabled", "User Status Changed")
    sync_roles()


def reset_password(actor, username, password):
    conn = db.get_conn()
    conn.execute("UPDATE app_users SET pw_hash=?, must_change=1 WHERE username=?", (_hash(password), username))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Password Reset", username)


def save_role(actor, name, description, color, perms, modules, clearance, level=None):
    conn = db.get_conn()
    o = conn.execute("SELECT * FROM app_roles WHERE name=?", (name,)).fetchone()
    lv = "admin" if "admin" in perms else "department_user"
    if o:
        conn.execute("UPDATE app_roles SET description=?, color=?, perms=?, modules=?, clearance=?, level=? WHERE name=?",
                     (description, color, json.dumps(perms), json.dumps(modules), clearance, lv, name))
    else:
        conn.execute("INSERT INTO app_roles VALUES (?,?,?,?,?,?,?,0)", (name, lv, description, color, json.dumps(perms), json.dumps(modules), clearance))
    conn.commit()
    conn.close()
    if o:
        _chg(actor, name, "permissions", ", ".join(json.loads(o["perms"])) or "none", ", ".join(perms) or "none", "Role Permissions Changed")
        _chg(actor, name, "modules", ", ".join(json.loads(o["modules"])), ", ".join(modules), "Role Access Changed")
        _chg(actor, name, "clearance", o["clearance"], clearance, "Role Updated")
    else:
        db.log_audit(None, actor, "Role Created", name, field="permissions", old="—", new=", ".join(perms))
    sync_roles()


def delete_role(actor, name):
    conn = db.get_conn()
    n = conn.execute("SELECT COUNT(*) FROM app_users WHERE role=?", (name,)).fetchone()[0]
    sysr = conn.execute("SELECT system_role FROM app_roles WHERE name=?", (name,)).fetchone()
    if n or (sysr and sysr[0]):
        conn.close()
        return False, "Role is built-in or still assigned to users."
    conn.execute("DELETE FROM app_roles WHERE name=?", (name,))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Role Deleted", name)
    return True, "Role deleted."
