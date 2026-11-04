"""Unlimited nested folder hierarchy with per-folder access restriction (inherited down the tree)."""
import json

import db
import rfp_data

STANDARD = ["Policies & Procedures", "Contracts & Agreements", "Correspondence", "Forms & Templates", "Reports & Records"]
SUBS = {"Correspondence": ["Incoming", "Outgoing"]}
# restricted sub-folders seeded as examples: (department, folder path under it) -> allowed departments
SEED_RESTRICT = {
    ("HR", "Contracts & Agreements"): ["HR", "Legal", "Executive Offices"],
    ("Legal", "Contracts & Agreements"): ["Legal", "Finance", "Executive Offices"],
    ("Finance", "Reports & Records"): ["Finance", "Executive Offices", "Audit & Compliance"],
    ("Medical Records", "Reports & Records"): ["Medical Records", "Nursing", "QRI"],
}
TYPE_MAP = {
    "Policies & Procedures": ["Policy", "Procedure", "SOP", "Circular", "Memo", "Research Protocol"],
    "Contracts & Agreements": ["Employee Contract", "Vendor Agreement", "Service Contract", "SLA", "Tender", "Purchase Order", "Supplier Record"],
    "Correspondence": ["Letter", "Regulatory Letter"],
    "Forms & Templates": ["Certificate", "Compliance Certificate", "Branding Asset", "Marketing Material", "Campaign Document", "Event Plan"],
}


def _c():
    return db.get_conn()


def init():
    conn = _c()
    conn.execute("""CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER, name TEXT NOT NULL,
        restricted_depts TEXT, created_by TEXT, created_at TEXT)""")
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(documents)").fetchall()]
    if "folder_id" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN folder_id INTEGER")
    n = conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
    conn.commit()
    conn.close()
    if n == 0:
        _seed()
    backfill()


def _add(parent, name, actor="System", restricted=None):
    conn = _c()
    r = conn.execute("SELECT id FROM folders WHERE COALESCE(parent_id,0)=? AND name=?", (parent or 0, name)).fetchone()
    if r:
        conn.close()
        return r["id"]
    cur = conn.execute("INSERT INTO folders (parent_id, name, restricted_depts, created_by, created_at) VALUES (?,?,?,?,?)",
                       (parent, name, json.dumps(restricted) if restricted else None, actor, db.now()))
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def _seed():
    for dept in rfp_data.DEPARTMENTS:
        root = _add(None, dept)
        for s in STANDARD:
            fid = _add(root, s, restricted=SEED_RESTRICT.get((dept, s)))
            for sub in SUBS.get(s, []):
                _add(fid, sub)


# ------------------------------------------------------------------ reading --
def all_folders():
    conn = _c()
    rows = [dict(r) for r in conn.execute("SELECT * FROM folders ORDER BY name").fetchall()]
    conn.close()
    for r in rows:
        r["restricted"] = json.loads(r["restricted_depts"]) if r["restricted_depts"] else None
    return rows


def index():
    fs = all_folders()
    by = {f["id"]: f for f in fs}
    kids = {}
    for f in fs:
        kids.setdefault(f["parent_id"], []).append(f["id"])
    return by, kids


def path_ids(fid, by=None):
    by = by or index()[0]
    out = []
    while fid and fid in by:
        out.append(fid)
        fid = by[fid]["parent_id"]
    return out[::-1]


def path(fid, by=None):
    by = by or index()[0]
    return " / ".join(by[i]["name"] for i in path_ids(fid, by))


def root_dept(fid, by=None):
    p = path_ids(fid, by)
    return (by or index()[0])[p[0]]["name"] if p else None


def descendants(fid, kids=None):
    kids = kids or index()[1]
    out, st = [], [fid]
    while st:
        x = st.pop()
        for k in kids.get(x, []):
            out.append(k)
            st.append(k)
    return out


def ordered(by=None, kids=None):
    """Depth-first list of (id, depth)."""
    if by is None:
        by, kids = index()
    res = []

    def walk(pid, d):
        for k in sorted(kids.get(pid, []), key=lambda i: by[i]["name"]):
            res.append((k, d))
            walk(k, d + 1)
    walk(None, 0)
    return res


def restriction(fid, by=None):
    """(allowed_departments, folder_id_that_defines_it) or (None, None) when unrestricted."""
    by = by or index()[0]
    for i in reversed(path_ids(fid, by)):
        if by[i]["restricted"]:
            return by[i]["restricted"], i
    return None, None


def can_access(fid, dept, admin, by=None):
    if admin:
        return True
    allowed, _ = restriction(fid, by)
    return allowed is None or dept in allowed


def counts():
    conn = _c()
    rows = conn.execute("SELECT folder_id, COUNT(*) n FROM documents WHERE folder_id IS NOT NULL GROUP BY folder_id").fetchall()
    conn.close()
    return {r["folder_id"]: r["n"] for r in rows}


def docs_in(fids):
    if not fids:
        return []
    conn = _c()
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM documents WHERE folder_id IN ({','.join('?' * len(fids))}) ORDER BY doc_code", list(fids)).fetchall()]
    conn.close()
    return rows


# ------------------------------------------------------------------ writing --
def create(parent, name, actor):
    name = name.strip().replace("/", "-")
    if not name:
        return None, "Enter a folder name."
    by, kids = index()
    if any(by[k]["name"].lower() == name.lower() for k in kids.get(parent, [])):
        return None, "A folder with this name already exists here."
    fid = _add(parent, name, actor)
    db.log_audit(None, actor, "Folder Created", f"{path(fid)}")
    return fid, ""


def rename(fid, name, actor):
    by = index()[0]
    old = path(fid, by)
    conn = _c()
    conn.execute("UPDATE folders SET name=? WHERE id=?", (name.strip().replace("/", "-"), fid))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Folder Renamed", f"{old} → {name}")


def move_folder(fid, new_parent, actor):
    by, kids = index()
    if new_parent == fid or new_parent in descendants(fid, kids):
        return "A folder cannot be moved into itself or its own sub-folder."
    if new_parent and any(by[k]["name"].lower() == by[fid]["name"].lower() for k in kids.get(new_parent, [])):
        return "The destination already has a folder with this name."
    old = path(fid, by)
    conn = _c()
    conn.execute("UPDATE folders SET parent_id=? WHERE id=?", (new_parent, fid))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Folder Moved", f"{old} → {path(fid)}")
    return ""


def delete(fid, actor):
    by, kids = index()
    if kids.get(fid):
        return "Folder has sub-folders — move or delete them first."
    if counts().get(fid):
        return "Folder contains documents — move them first."
    p = path(fid, by)
    conn = _c()
    conn.execute("DELETE FROM folders WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Folder Deleted", p)
    return ""


def set_restriction(fid, depts, actor):
    conn = _c()
    conn.execute("UPDATE folders SET restricted_depts=? WHERE id=?", (json.dumps(depts) if depts else None, fid))
    conn.commit()
    conn.close()
    db.log_audit(None, actor, "Folder Access Changed", f"{path(fid)} → " + (", ".join(depts) if depts else "inherits from parent"))


def move_docs(doc_ids, fid, actor):
    by = index()[0]
    conn = _c()
    for d in doc_ids:
        conn.execute("UPDATE documents SET folder_id=? WHERE id=?", (fid, d))
    conn.commit()
    conn.close()
    for d in doc_ids:
        db.log_audit(d, actor, "Filed in Folder", path(fid, by))


def ensure_path(dept, *names):
    fid = _add(None, dept)
    for n in names:
        fid = _add(fid, n)
    return fid


def target_folder(dept, doc_type, direction="Incoming"):
    sub = next((k for k, v in TYPE_MAP.items() if doc_type in v), "Reports & Records")
    if sub == "Correspondence":
        return ensure_path(dept, sub, direction)
    return ensure_path(dept, sub)


def autofile(doc_id, direction="Incoming"):
    conn = _c()
    d = conn.execute("SELECT department, doc_type, folder_id FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not d or d["folder_id"]:
        return
    fid = target_folder(d["department"] or "Medical Records", d["doc_type"], direction)
    conn = _c()
    conn.execute("UPDATE documents SET folder_id=? WHERE id=?", (fid, doc_id))
    conn.commit()
    conn.close()


def backfill():
    conn = _c()
    ids = [r["id"] for r in conn.execute("SELECT id FROM documents WHERE folder_id IS NULL").fetchall()]
    conn.close()
    for i in ids:
        autofile(i)
