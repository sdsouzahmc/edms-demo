"""Automatic document permissions.

Every new document (uploaded, scanned, created, e-mailed, imported, received through a secure link) is run through an ordered set of
permission rules the moment it is registered. The rules decide:
  * the security level (only ever raised, never lowered),
  * whether visibility is Standard (own department + released + shared) or Restricted (only the listed people),
  * who is granted which access: View < Edit < Approve < Manage — to a department, a role, a named user or everyone,
  * optional expiry of a grant, and whether the grantees are notified.
Folder restrictions are inherited automatically. Manual grants added by an owner/administrator are never overwritten by a re-apply.
"""
import json

import db

LEVELS = ["View", "Edit", "Approve", "Manage"]
RANK = {l: i for i, l in enumerate(LEVELS)}
SEC_RANK = {"Public": 0, "Internal": 1, "Restricted": 2, "Confidential": 3}
EVERYONE = "*"


def _c():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS perm_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, enabled INTEGER DEFAULT 1, priority INTEGER DEFAULT 100,
        conditions TEXT, actions TEXT, created_by TEXT, created_at TEXT, hits INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS doc_permissions (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, ptype TEXT, principal TEXT, access TEXT,
        source TEXT, granted_by TEXT, granted_at TEXT, expires_at TEXT);
    CREATE INDEX IF NOT EXISTS ix_perm_doc ON doc_permissions(document_id);
    """)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(documents)")]
    if "access_mode" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN access_mode TEXT")
    conn.commit()
    return conn


G = lambda t, n, a, exp=None: {"type": t, "name": n, "access": a, **({"expires_days": exp} if exp else {})}

DEFAULT_RULES = [
    ("Patient & clinical records — restricted to the care team", 10,
     {"doc_types": ["Medical Record"], "keywords": ["patient", "discharge", "referral", "admission"]},
     {"security": "Confidential", "mode": "restricted", "notify": True,
      "grants": [G("dept", "Medical Records", "Manage"), G("dept", "Nursing", "View"), G("dept", "Physicians, Dental & Pharmacy", "View"),
                 G("dept", "QRI", "View")]}),
    ("HR files — HR and Executive Offices only", 20,
     {"doc_types": ["Employee Contract", "Appraisal"], "keywords": ["salary", "disciplinary", "appraisal", "employee contract"]},
     {"security": "Restricted", "mode": "restricted", "notify": False,
      "grants": [G("dept", "HR", "Manage"), G("dept", "Talent Management", "Edit"), G("dept", "Executive Offices", "View")]}),
    ("Contracts & agreements — Legal manages, Finance and Executive view", 30,
     {"doc_types": ["Service Contract", "Vendor Agreement", "SLA"], "keywords": ["agreement", "contract"]},
     {"security": "Restricted", "mode": "standard", "notify": False,
      "grants": [G("dept", "Legal", "Manage"), G("dept", "Finance", "View"), G("dept", "Executive Offices", "View"), G("dept", "Procurement", "View")]}),
    ("Finance documents — Finance edits, Procurement and Executive view", 40,
     {"doc_types": ["Invoice", "Purchase Order", "Payment Approval", "Tender"], "keywords": ["invoice", "purchase order"]},
     {"security": "Internal", "mode": "standard", "notify": False,
      "grants": [G("dept", "Finance", "Manage"), G("dept", "Procurement", "Edit"), G("dept", "Executive Offices", "View")]}),
    ("Regulatory & accreditation — QRI manages, Executive and Legal view", 50,
     {"classifications": ["Regulatory"]},
     {"security": "Internal", "mode": "standard", "notify": True,
      "grants": [G("dept", "QRI", "Manage"), G("dept", "Executive Offices", "View"), G("dept", "Legal", "View")]}),
    ("Accreditation & compliance evidence — QRI manages", 55,
     {"doc_types": ["Compliance Certificate", "Audit Document"], "keywords": ["accreditation", "quality audit"]},
     {"security": "Internal", "mode": "standard", "notify": False, "grants": [G("dept", "QRI", "Manage"), G("dept", "Executive Offices", "View")]}),
    ("Board & executive papers — Executive Offices only", 15,
     {"keywords": ["board meeting", "board minutes", "executive committee", "minutes of the meeting", "management meeting"]},
     {"security": "Confidential", "mode": "restricted", "notify": False, "grants": [G("dept", "Executive Offices", "Manage")]}),
    ("Incident & security reports — IT, Security and QRI", 60,
     {"keywords": ["incident report", "fire drill", "evacuation", "core switch"], "doc_types": ["Inspection Report"]},
     {"security": "Restricted", "mode": "standard", "notify": True,
      "grants": [G("dept", "IT", "Edit"), G("dept", "Security", "Edit"), G("dept", "QRI", "View")]}),
    ("Marketing & public material — visible to everyone", 70,
     {"doc_types": ["Marketing Material", "Campaign Document", "Event Plan", "Branding Asset"], "keywords": ["press release", "awareness campaign"]},
     {"security": "Public", "mode": "standard", "notify": False, "grants": [G("dept", "Marketing", "Manage"), G("all", EVERYONE, "View")]}),
    ("External submissions — hold for Records review", 80,
     {"sources": ["Upload"], "classifications": ["External"]},
     {"security": "Internal", "mode": "standard", "notify": False, "grants": [G("dept", "Medical Records", "Edit")]}),
]


def init():
    conn = _c()
    if not conn.execute("SELECT 1 FROM perm_rules LIMIT 1").fetchone():
        for name, pr, cond, act in DEFAULT_RULES:
            conn.execute("INSERT INTO perm_rules (name, enabled, priority, conditions, actions, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
                         (name, 1, pr, json.dumps(cond), json.dumps(act), "System", db.now()))
        conn.commit()
    conn.close()


# ------------------------------------------------------------------ rules ---
def rules(only_enabled=False):
    conn = _c()
    rows = conn.execute("SELECT * FROM perm_rules" + (" WHERE enabled=1" if only_enabled else "") + " ORDER BY priority, id").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["cond"] = json.loads(r["conditions"] or "{}")
        d["act"] = json.loads(r["actions"] or "{}")
        out.append(d)
    return out


def save_rule(rid, name, priority, cond, act, enabled, actor):
    conn = _c()
    if rid:
        conn.execute("UPDATE perm_rules SET name=?, priority=?, conditions=?, actions=?, enabled=? WHERE id=?",
                     (name, priority, json.dumps(cond), json.dumps(act), 1 if enabled else 0, rid))
    else:
        conn.execute("INSERT INTO perm_rules (name, enabled, priority, conditions, actions, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
                     (name, 1 if enabled else 0, priority, json.dumps(cond), json.dumps(act), actor, db.now()))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Permission Rule " + ("Updated" if rid else "Created"), name)


def set_enabled(rid, on, actor):
    conn = _c()
    conn.execute("UPDATE perm_rules SET enabled=? WHERE id=?", (1 if on else 0, rid))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Permission Rule " + ("Enabled" if on else "Disabled"), f"rule #{rid}")


def delete_rule(rid, actor):
    conn = _c()
    conn.execute("DELETE FROM perm_rules WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Permission Rule Deleted", f"rule #{rid}")


def _matches(cond, a):
    """All condition groups must hold; inside a group any value matches. 'keywords' is checked in title and body."""
    for key, field in (("doc_types", "doc_type"), ("departments", "department"), ("classifications", "classification"),
                       ("security_levels", "security_level"), ("sources", "source"), ("languages", "language")):
        vals = cond.get(key)
        if vals and key != "doc_types" and (a.get(field) or "") not in vals:
            return False
    # doc types and keywords are alternatives of one another: a document of the right type OR mentioning the right words
    types, kws = cond.get("doc_types") or [], [k.lower() for k in (cond.get("keywords") or [])]
    if types or kws:
        text = f"{a.get('title') or ''} {a.get('body_text') or ''}".lower()
        if not ((types and (a.get("doc_type") in types)) or (kws and any(k in text for k in kws))):
            return False
    return True


def evaluate(a):
    """Pure function: attributes of a document -> merged outcome (used by the live preview and by apply())."""
    matched, grants, sec, restricted, notify = [], {}, a.get("security_level") or "Internal", False, False
    for r in rules(only_enabled=True):
        if not _matches(r["cond"], a):
            continue
        matched.append(r)
        act = r["act"]
        if act.get("security") and SEC_RANK.get(act["security"], 0) > SEC_RANK.get(sec, 0):
            sec = act["security"]
        restricted = restricted or act.get("mode") == "restricted"
        notify = notify or bool(act.get("notify"))
        for g in act.get("grants", []):
            k = (g["type"], g["name"])
            cur = grants.get(k)
            if not cur or RANK[g["access"]] > RANK[cur["access"]]:
                grants[k] = {**g, "source": "rule: " + r["name"]}
    # the owning department always keeps Edit, the creator keeps View at least
    own = a.get("department")
    if own and ("dept", own) not in grants:
        grants[("dept", own)] = {"type": "dept", "name": own, "access": "Edit", "source": "baseline: owning department"}
    return {"matched": matched, "grants": list(grants.values()), "security": sec, "restricted": restricted, "notify": notify}


# ------------------------------------------------------------------ apply ---
def apply(doc_id, trigger="Created", actor="System"):
    """Run the rules for one document and store the resulting permissions (automatic grants are replaced; manual ones are kept)."""
    conn = _c()
    d = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not d:
        conn.close()
        return None
    a = dict(d)
    res = evaluate(a)
    # folder inheritance: a restricted folder restricts its documents to the folder's departments
    try:
        import folders
        by, _k = folders.index()
        fid = a.get("folder_id")
        if fid and fid in by:
            deps, _src = folders.restriction(fid, by)
            if deps:
                res["restricted"] = True
                have = {(g["type"], g["name"]) for g in res["grants"]}
                for dep in deps:
                    if ("dept", dep) not in have:
                        res["grants"].append({"type": "dept", "name": dep, "access": "Edit", "source": "folder: inherited restriction"})
    except Exception:
        pass
    ts = db.now()
    conn.execute("DELETE FROM doc_permissions WHERE document_id=? AND (source LIKE 'rule:%' OR source LIKE 'baseline:%' OR source LIKE 'folder:%')", (doc_id,))
    import datetime as dt
    for g in res["grants"]:
        exp = (dt.date.today() + dt.timedelta(days=int(g["expires_days"]))).isoformat() if g.get("expires_days") else None
        conn.execute("INSERT INTO doc_permissions (document_id, ptype, principal, access, source, granted_by, granted_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                     (doc_id, g["type"], g["name"], g["access"], g["source"], "System", ts, exp))
    old_sec = a.get("security_level")
    conn.execute("UPDATE documents SET security_level=?, access_mode=? WHERE id=?", (res["security"], "restricted" if res["restricted"] else "standard", doc_id))
    for r in res["matched"]:
        conn.execute("UPDATE perm_rules SET hits=hits+1 WHERE id=?", (r["id"],))
    conn.commit()
    conn.close()
    names = "; ".join(r["name"].split(" — ")[0] for r in res["matched"]) or "baseline only"
    db.log_audit(doc_id, actor, "Permissions Auto-Applied",
                 f"{trigger}: {len(res['grants'])} grant(s), {'RESTRICTED' if res['restricted'] else 'standard'} visibility · rules: {names}",
                 field="security_level" if res["security"] != old_sec else None, old=old_sec if res["security"] != old_sec else None,
                 new=res["security"] if res["security"] != old_sec else None)
    if res["notify"] and res["restricted"] is not None:
        _notify(doc_id, a, res)
    return res


def _notify(doc_id, a, res):
    try:
        import db_ext
        import rfp_data
        depts = {g["name"] for g in res["grants"] if g["type"] == "dept" and g["name"] != a.get("department")}
        for u, p in rfp_data.ROLES.items():
            if p["dept"] in depts:
                db_ext.notify(u, f"Access granted: {a['doc_code']} — {a['title']} is now available to {p['dept']} (automatic permission rule)", doc_id, "access")
    except Exception:
        pass


def reapply_all(actor):
    conn = _c()
    ids = [r["id"] for r in conn.execute("SELECT id FROM documents")]
    conn.close()
    for i in ids:
        apply(i, "Re-applied", actor)
    return len(ids)


# --------------------------------------------------------------- manual -----
def grant(doc_id, ptype, principal, access, actor, expires_days=None):
    import datetime as dt
    conn = _c()
    exp = (dt.date.today() + dt.timedelta(days=int(expires_days))).isoformat() if expires_days else None
    conn.execute("INSERT INTO doc_permissions (document_id, ptype, principal, access, source, granted_by, granted_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                 (doc_id, ptype, principal, access, "manual", actor, db.now(), exp))
    conn.commit()
    conn.close()
    db.log_audit(doc_id, actor, "Permission Granted", f"{access} to {ptype} '{principal}'" + (f" until {exp}" if exp else ""))


def revoke(perm_id, actor):
    conn = _c()
    r = conn.execute("SELECT * FROM doc_permissions WHERE id=?", (perm_id,)).fetchone()
    conn.execute("DELETE FROM doc_permissions WHERE id=?", (perm_id,))
    conn.commit()
    conn.close()
    if r:
        db.log_audit(r["document_id"], actor, "Permission Revoked", f"{r['access']} from {r['ptype']} '{r['principal']}'")


def permissions(doc_id):
    conn = _c()
    rows = conn.execute("SELECT * FROM doc_permissions WHERE document_id=? ORDER BY id", (doc_id,)).fetchall()
    conn.close()
    return rows


def recent_applications(limit=60):
    conn = _c()
    rows = conn.execute("""SELECT a.ts, a.detail, a.document_id, d.doc_code, d.title, d.department, d.security_level, d.access_mode, d.source
                           FROM audit_log a JOIN documents d ON d.id=a.document_id WHERE a.action='Permissions Auto-Applied' ORDER BY a.id DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return rows


def stats():
    conn = _c()
    out = {"docs": conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
           "restricted": conn.execute("SELECT COUNT(*) FROM documents WHERE access_mode='restricted'").fetchone()[0],
           "auto": conn.execute("SELECT COUNT(DISTINCT document_id) FROM doc_permissions WHERE source LIKE 'rule:%'").fetchone()[0],
           "manual": conn.execute("SELECT COUNT(*) FROM doc_permissions WHERE source='manual'").fetchone()[0],
           "rules": conn.execute("SELECT COUNT(*) FROM perm_rules WHERE enabled=1").fetchone()[0]}
    conn.close()
    return out


# ------------------------------------------------------------- enforcement --
def _active_grants(doc_id):
    import datetime as dt
    today = dt.date.today().isoformat()
    return [g for g in permissions(doc_id) if not g["expires_at"] or g["expires_at"] >= today]


def level(d, user, dept, role, admin=False):
    """Highest explicit access level this person holds on the document (or None)."""
    if admin:
        return "Manage"
    best = None
    for g in _active_grants(d["id"]):
        if g["ptype"] == "all" or (g["ptype"] == "dept" and g["principal"] == dept) or (g["ptype"] == "role" and g["principal"] == role) \
                or (g["ptype"] == "user" and g["principal"] == user):
            if best is None or RANK[g["access"]] > RANK[best]:
                best = g["access"]
    if d["created_by"] == user and best is None:
        best = "View"
    return best


def visible(d, user, dept, role, admin, shared_ids=()):
    """The one visibility rule used by Search, Ask EDMS and Security: explicit grant, else (unless restricted) the standard department rule."""
    if admin:
        return True
    if level(d, user, dept, role) is not None:
        return True
    try:
        mode = d["access_mode"]
    except (KeyError, IndexError):
        mode = None
    if mode == "restricted":
        return False
    return d["department"] == dept or d["status"] in ("Released", "Archived") or d["id"] in shared_ids


def backfill(actor="System"):
    """Give every document that pre-dates this feature its automatic permissions (runs once; cheap when nothing is pending)."""
    conn = _c()
    ids = [r["id"] for r in conn.execute("SELECT id FROM documents WHERE access_mode IS NULL")]
    conn.close()
    for i in ids:
        apply(i, "Initial back-fill", actor)
    return len(ids)
