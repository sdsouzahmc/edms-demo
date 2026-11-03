"""Visual workflow designer — data model, validation, simulation and SVG rendering."""
import html
import json
import uuid
import db
import db_ext
import rfp_data

KINDS = {  # kind -> (colour, emoji, default step name)
    "Review": ("#2E8B8B", "🔍", "Department Review"), "Approval": ("#1F3864", "✅", "Approval"),
    "Sign-off": ("#B8860B", "💰", "Finance Sign-off"), "Legal": ("#6C4FA3", "⚖️", "Legal Review"),
    "Quality": ("#2E7D32", "🏅", "Quality Review"), "Clinical": ("#C0603C", "🩺", "Clinical Review"),
    "Executive": ("#B00020", "🏛️", "Executive Approval"), "Acknowledge": ("#4A90C2", "👁️", "Acknowledgment"),
    "Notify": ("#6B7280", "🔔", "Notify stakeholders"),
}
COND_FIELDS = ["Always", "Classification is", "Security level at least", "Document type is finance-related", "Document type is"]
LEVELS = ["Public", "Internal", "Restricted", "Confidential"]
TEMPLATES = {
    "Standard (Review → Approval)": [("Review", "Department Review", 24, False, "Always", ""), ("Approval", "Approval", 48, True, "Always", "")],
    "Finance (adds Finance Sign-off)": [("Review", "Department Review", 24, False, "Always", ""), ("Approval", "Approval", 48, True, "Always", ""),
                                        ("Sign-off", "Finance Sign-off", 48, True, "Always", "")],
    "Regulated (Legal + Quality + Executive)": [("Review", "Department Review", 24, False, "Always", ""), ("Legal", "Legal Review", 48, False, "Always", ""),
                                               ("Quality", "Quality Review", 48, False, "Always", ""), ("Executive", "Executive Approval", 72, True, "Always", "")],
    "Fast-track (single approval)": [("Approval", "Approval", 12, True, "Always", "")],
    "Conditional (extra step if Confidential)": [("Review", "Department Review", 24, False, "Always", ""), ("Executive", "Executive Approval", 72, True, "Security level at least", "Confidential"),
                                                 ("Approval", "Approval", 48, True, "Always", "")],
}


def init():
    conn = db.get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_designs (id INTEGER PRIMARY KEY AUTOINCREMENT, department TEXT, doc_type TEXT,
        name TEXT, version INTEGER, status TEXT, steps TEXT, note TEXT, updated_by TEXT, updated_at TEXT)""")
    for col in ("sla_hours INTEGER", "esign_required INTEGER"):
        try:
            conn.execute(f"ALTER TABLE workflow ADD COLUMN {col}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def new_step(kind="Review", name=None, sla=24, esign=False, cond="Always", cval="", assignee="(owner department)"):
    return {"id": uuid.uuid4().hex[:6], "kind": kind, "name": name or KINDS[kind][2], "assignee": assignee, "role": "Any approver",
            "sla_h": sla, "esign": esign, "cond": cond, "cval": cval, "on_reject": "Return to Draft"}


def from_template(key):
    return [new_step(k, n, s, e, c, v) for k, n, s, e, c, v in TEMPLATES[key]]


def current_steps(dept, dtype):
    """Steps behind today's behaviour for this scope (published design, else legacy template / default)."""
    d = latest(dept, dtype, "Published")
    if d:
        return json.loads(d["steps"])
    names = [n for n in db_ext.stages_for(dept, dtype) if n not in ("Draft", "Released")]
    out = []
    for n in names:
        kind = next((k for k, v in KINDS.items() if v[2] == n), "Review")
        out.append(new_step(kind, n, 24, kind in ("Approval", "Sign-off", "Executive")))
    return out


def latest(dept, dtype, status=None):
    conn = db.get_conn()
    q = "SELECT * FROM workflow_designs WHERE department=? AND COALESCE(doc_type,'')=?" + (" AND status=?" if status else "") + " ORDER BY version DESC LIMIT 1"
    row = conn.execute(q, (dept, dtype or "") + ((status,) if status else ())).fetchone()
    conn.close()
    return row


def history(dept, dtype):
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM workflow_designs WHERE department=? AND COALESCE(doc_type,'')=? ORDER BY version DESC", (dept, dtype or "")).fetchall()
    conn.close()
    return rows


def all_published():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM workflow_designs WHERE status='Published' ORDER BY department, doc_type").fetchall()
    conn.close()
    return rows


def save(dept, dtype, name, steps, user, publish, note=""):
    conn = db.get_conn()
    v = (conn.execute("SELECT COALESCE(MAX(version),0) FROM workflow_designs WHERE department=? AND COALESCE(doc_type,'')=?", (dept, dtype or "")).fetchone()[0]) + 1
    if publish:
        conn.execute("UPDATE workflow_designs SET status='Superseded' WHERE department=? AND COALESCE(doc_type,'')=? AND status='Published'", (dept, dtype or ""))
    conn.execute("INSERT INTO workflow_designs (department, doc_type, name, version, status, steps, note, updated_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (dept, dtype or "", name, v, "Published" if publish else "Draft", json.dumps(steps), note, user, db.now()))
    conn.commit()
    conn.close()
    if publish:
        db_ext.save_template(dept, dtype, ["Draft"] + [s["name"] for s in steps if s["cond"] == "Always"] + ["Released"], user)
    db.log_audit(None, user, "Workflow Published" if publish else "Workflow Draft Saved",
                 f"{dept} / {dtype or 'default'} v{v}: " + " → ".join(s["name"] for s in steps), field="workflow", new=f"v{v}")
    return v


def restore(design_id, user):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM workflow_designs WHERE id=?", (design_id,)).fetchone()
    conn.close()
    return save(r["department"], r["doc_type"], r["name"], json.loads(r["steps"]), user, True, f"Restored from v{r['version']}")


def matches(step, classification, security_level, doc_type):
    c, v = step.get("cond", "Always"), step.get("cval", "")
    if c == "Always":
        return True
    if c == "Classification is":
        return classification == v
    if c == "Security level at least":
        return LEVELS.index(security_level) >= LEVELS.index(v) if security_level in LEVELS and v in LEVELS else False
    if c == "Document type is finance-related":
        return doc_type in rfp_data.FINANCE_TYPES
    if c == "Document type is":
        return doc_type == v
    return True


def resolve(dept, doc_type, classification, security_level):
    """Published design applicable to a new document → list of steps (conditions applied) or None."""
    d = latest(dept, doc_type, "Published") or latest(dept, "", "Published")
    if not d:
        return None
    return [s for s in json.loads(d["steps"]) if matches(s, classification, security_level, doc_type)]


def validate(steps):
    msgs = []
    names = [s["name"].strip() for s in steps]
    if not steps:
        msgs.append(("error", "Add at least one step between Draft and Released."))
    if any(not n for n in names):
        msgs.append(("error", "Every step needs a name."))
    if len(set(n.lower() for n in names)) != len(names):
        msgs.append(("error", "Step names must be unique (they become the document status)."))
    if any(n in ("Draft", "Released", "Rejected", "Archived") for n in names):
        msgs.append(("error", "‘Draft’, ‘Released’, ‘Rejected’ and ‘Archived’ are reserved names."))
    if steps and not any(s["kind"] in ("Approval", "Sign-off", "Executive") and s["cond"] == "Always" for s in steps):
        msgs.append(("warn", "No unconditional approval step — some documents could be released without approval."))
    if steps and not any(s["esign"] for s in steps):
        msgs.append(("warn", "No step requires an e-signature."))
    if any(s["sla_h"] <= 0 for s in steps):
        msgs.append(("error", "SLA hours must be greater than zero."))
    if not msgs:
        msgs.append(("ok", "Design is valid and ready to publish."))
    return msgs


def _t(s, n):
    s = str(s)
    return html.escape(s if len(s) <= n else s[: n - 1] + "…")


def svg(steps, selected=None, active=None, per_row=4):
    """Flowchart of Draft → steps → Released; skipped steps (condition false in simulation) are faded."""
    W, H, GX, GY, PAD = 176, 92, 44, 50, 14
    nodes = [{"kind": "Start", "name": "Draft", "sub": "Document created", "col": "#6B7280", "em": "📝", "id": "start"}]
    for s in steps:
        sub = f"{s['assignee'] if s['assignee'] != '(owner department)' else 'Owner dept'} · SLA {s['sla_h']}h"
        nodes.append({"kind": s["kind"], "name": s["name"], "sub": sub, "col": KINDS[s["kind"]][0], "em": KINDS[s["kind"]][1], "id": s["id"], "s": s})
    nodes.append({"kind": "End", "name": "Released", "sub": "Published · QR issued", "col": "#2E7D32", "em": "🚀", "id": "end"})
    rows = (len(nodes) + per_row - 1) // per_row
    width = PAD * 2 + per_row * W + (per_row - 1) * GX
    height = PAD * 2 + rows * H + (rows - 1) * GY + 22
    pos = []
    for i in range(len(nodes)):
        r, c = divmod(i, per_row)
        if r % 2:
            c = per_row - 1 - c           # snake layout
        pos.append((PAD + c * (W + GX), PAD + r * (H + GY)))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px;font-family:Source Sans Pro,Segoe UI,sans-serif">',
           '<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#8896AB"/></marker></defs>']
    for i in range(len(nodes) - 1):
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if y1 == y2:
            xa, xb = (x1 + W, x2) if x2 > x1 else (x1, x2 + W)
            out.append(f'<line x1="{xa}" y1="{y1 + H / 2}" x2="{xb}" y2="{y2 + H / 2}" stroke="#8896AB" stroke-width="2.2" marker-end="url(#ar)"/>')
        else:
            out.append(f'<path d="M{x1 + W / 2},{y1 + H} L{x2 + W / 2},{y2}" stroke="#8896AB" stroke-width="2.2" fill="none" marker-end="url(#ar)"/>')
    for n, (x, y) in zip(nodes, pos):
        s = n.get("s")
        op = 0.32 if (active is not None and s and s["id"] not in active) else 1
        sel = selected == n["id"]
        dash = ' stroke-dasharray="6 4"' if s and s["cond"] != "Always" else ""
        stroke = "#C0603C" if sel else n["col"]
        out.append(f'<g opacity="{op}">'
                   f'<rect x="{x}" y="{y}" width="{W}" height="{H}" rx="14" fill="#fff" stroke="{stroke}" stroke-width="{4 if sel else 2.4}"{dash}/>'
                   f'<rect x="{x}" y="{y}" width="{W}" height="26" rx="14" fill="{n["col"]}"/><rect x="{x}" y="{y + 14}" width="{W}" height="12" fill="{n["col"]}"/>'
                   f'<text x="{x + 10}" y="{y + 18}" fill="#fff" font-size="12.5" font-weight="700">{n["em"]} {html.escape(n["kind"].upper())}</text>'
                   f'<text x="{x + 10}" y="{y + 49}" fill="#1F3864" font-size="14" font-weight="700">{_t(n["name"], 21)}</text>'
                   f'<text x="{x + 10}" y="{y + 67}" fill="#6B7280" font-size="11">{_t(n["sub"], 29)}</text>')
        if s:
            tags = []
            if s["esign"]:
                tags.append(("✍ e-sign", "#B8860B"))
            if s["cond"] != "Always":
                tags.append(("IF " + (s["cval"] or s["cond"].replace("Document type is ", "")).replace("finance-related", "finance"), "#C0603C"))
            for k, (tx, cl) in enumerate(tags[:2]):
                out.append(f'<text x="{x + 10 + k * 70}" y="{y + 84}" fill="{cl}" font-size="10.5" font-weight="700">{html.escape(tx)}</text>')
        out.append("</g>")
    out.append(f'<text x="{PAD}" y="{height - 6}" fill="#B00020" font-size="11">↩ A rejection at any approval stage returns the document to the author (status “Rejected”).</text>')
    out.append("</svg>")
    return "".join(out)
