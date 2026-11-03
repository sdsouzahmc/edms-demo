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
    "Parallel review (Legal ‖ Quality ‖ Clinical → Approval)": [("Review", "Department Review", 24, False, "Always", ""),
        ("Legal", "Legal Review", 48, False, "Always", "", "Sequential", "All must approve"),
        ("Quality", "Quality Review", 48, False, "Always", "", "Parallel with previous", "All must approve"),
        ("Clinical", "Clinical Review", 48, False, "Always", "", "Parallel with previous", "All must approve"),
        ("Approval", "Approval", 24, True, "Always", "")],
    "Parallel — any one approves (two approvers race)": [("Approval", "Approval — Head of Dept", 24, True, "Always", "", "Sequential", "Any one approves"),
        ("Approval", "Approval — Deputy", 24, True, "Always", "", "Parallel with previous", "Any one approves")],
    "Fast-track (single approval)": [("Approval", "Approval", 12, True, "Always", "")],
    "Conditional (extra step if Confidential)": [("Review", "Department Review", 24, False, "Always", ""), ("Executive", "Executive Approval", 72, True, "Security level at least", "Confidential"),
                                                 ("Approval", "Approval", 48, True, "Always", "")],
}


def init():
    conn = db.get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_designs (id INTEGER PRIMARY KEY AUTOINCREMENT, department TEXT, doc_type TEXT,
        name TEXT, version INTEGER, status TEXT, steps TEXT, note TEXT, updated_by TEXT, updated_at TEXT)""")
    for col in ("sla_hours INTEGER", "esign_required INTEGER", "par_group INTEGER", "join_rule TEXT"):
        try:
            conn.execute(f"ALTER TABLE workflow ADD COLUMN {col}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def new_step(kind="Review", name=None, sla=24, esign=False, cond="Always", cval="", assignee="(owner department)", mode="Sequential", join="All must approve"):
    return {"id": uuid.uuid4().hex[:6], "kind": kind, "name": name or KINDS[kind][2], "assignee": assignee, "role": "Any approver",
            "sla_h": sla, "esign": esign, "cond": cond, "cval": cval, "on_reject": "Return to Draft",
            "mode": mode, "join": join}


def from_template(key):
    return [new_step(k, n, s, e, c, v, mode=(rest[0] if rest else "Sequential"), join=(rest[1] if len(rest) > 1 else "All must approve"))
            for k, n, s, e, c, v, *rest in TEMPLATES[key]]


def grouped(steps):
    """Split an ordered list of (already condition-filtered) steps into execution groups.
    A step in mode 'Parallel with previous' runs at the same time as the step before it."""
    groups = []
    for s in steps:
        if s.get("mode") == "Parallel with previous" and groups:
            groups[-1].append(s)
        else:
            groups.append([s])
    return groups


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
    if steps and steps[0].get("mode") == "Parallel with previous":
        msgs.append(("error", "The first step cannot be ‘parallel with previous’ — there is nothing before it."))
    for g in grouped(steps):
        if len(g) > 1 and len({s["assignee"] for s in g}) == 1 and g[0]["assignee"] != "(owner department)":
            msgs.append(("warn", f"Parallel steps ‘{' ‖ '.join(s['name'] for s in g)}’ are all assigned to {g[0]['assignee']} — consider different departments."))
    if not msgs:
        msgs.append(("ok", "Design is valid and ready to publish."))
    return msgs


def _t(s, n):
    s = str(s)
    return html.escape(s if len(s) <= n else s[: n - 1] + "…")


def svg(steps, selected=None, active=None, per_row=4):
    """Flowchart Draft → (sequential steps / parallel groups) → Released. Parallel branches are stacked in one column
    between a fork and a join. Steps whose condition is false in a simulation (not in `active`) are faded."""
    W, H, GX, GY, PAD, VG = 176, 92, 44, 40, 14, 14
    cols = [[{"kind": "Start", "name": "Draft", "sub": "Document created", "col": "#6B7280", "em": "📝", "id": "start"}]]
    for g in grouped(steps):
        col = []
        for s in g:
            sub = f"{s['assignee'] if s['assignee'] != '(owner department)' else 'Owner dept'} · SLA {s['sla_h']}h"
            col.append({"kind": s["kind"], "name": s["name"], "sub": sub, "col": KINDS[s["kind"]][0], "em": KINDS[s["kind"]][1], "id": s["id"], "s": s,
                        "par": len(g) > 1, "join": g[0].get("join", "All must approve")})
        cols.append(col)
    cols.append([{"kind": "End", "name": "Released", "sub": "Published · QR issued", "col": "#2E7D32", "em": "🚀", "id": "end"}])
    nrows = (len(cols) + per_row - 1) // per_row
    row_h = []
    for r in range(nrows):
        mx = max(len(c) for c in cols[r * per_row:(r + 1) * per_row])
        row_h.append(mx * H + (mx - 1) * VG)
    width = PAD * 2 + per_row * W + (per_row - 1) * GX
    height = PAD * 2 + sum(row_h) + (nrows - 1) * GY + 40
    ys = [PAD + 18]
    for r in range(1, nrows):
        ys.append(ys[-1] + row_h[r - 1] + GY)
    placed = []     # per column: list of (node, x, y)
    for ci, col in enumerate(cols):
        r, c = divmod(ci, per_row)
        if r % 2:
            c = per_row - 1 - c
        x = PAD + c * (W + GX)
        total = len(col) * H + (len(col) - 1) * VG
        y0 = ys[r] + (row_h[r] - total) / 2
        placed.append([(n, x, y0 + k * (H + VG), r) for k, n in enumerate(col)])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px;font-family:Source Sans Pro,Segoe UI,sans-serif">',
           '<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#8896AB"/></marker></defs>']
    for ci in range(len(placed) - 1):
        for (n1, x1, y1, r1) in placed[ci]:
            for (n2, x2, y2, r2) in placed[ci + 1]:
                if r1 == r2:
                    xa, xb = (x1 + W, x2) if x2 > x1 else (x1, x2 + W)
                    ya, yb = y1 + H / 2, y2 + H / 2
                    mid = (xa + xb) / 2
                    d = f"M{xa},{ya} C{mid},{ya} {mid},{yb} {xb},{yb}" if ya != yb else f"M{xa},{ya} L{xb},{yb}"
                    out.append(f'<path d="{d}" stroke="#8896AB" stroke-width="2.2" fill="none" marker-end="url(#ar)"/>')
                elif n1 is placed[ci][0][0] and n2 is placed[ci + 1][0][0]:
                    out.append(f'<path d="M{x1 + W / 2},{y1 + H} L{x2 + W / 2},{y2}" stroke="#8896AB" stroke-width="2.2" fill="none" marker-end="url(#ar)"/>')
    for col in placed:
        if len(col) > 1:
            n0, x, y, _ = col[0]
            top, bot = col[0][2] - 8, col[-1][2] + H + 8
            out.append(f'<rect x="{x - 6}" y="{top}" width="{W + 12}" height="{bot - top}" rx="16" fill="#6C4FA3" fill-opacity="0.06" stroke="#6C4FA3" stroke-dasharray="3 4" stroke-width="1.2"/>')
            lab = "⫴ PARALLEL · ANY ONE" if n0["join"] == "Any one approves" else "⫴ PARALLEL · ALL MUST APPROVE"
            out.append(f'<text x="{x + W / 2}" y="{top - 3}" fill="#6C4FA3" font-size="10.5" font-weight="700" text-anchor="middle">{lab}</text>')
    for col in placed:
        for n, x, y, _r in col:
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
    out.append(f'<text x="{PAD}" y="{height - 6}" fill="#B00020" font-size="11">↩ A rejection at any approval stage returns the document to the author (status “Rejected”); in a parallel group it cancels the other branches.</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------ sample designs --
SAMPLES = [  # dept, doc_type, name, note, steps: (kind, name, assignee, sla, esign, cond, cval)
    ("Finance", "Invoice", "Supplier invoice approval", "Three-way check, approval, finance sign-off",
     [("Review", "Department Review", "(owner department)", 24, False, "Always", ""), ("Approval", "Approval", "(owner department)", 24, True, "Always", ""),
      ("Sign-off", "Finance Sign-off", "Finance", 48, True, "Always", "")]),
    ("Procurement", "Purchase Order", "Purchase order with budget control", "Finance sign-off added automatically for POs",
     [("Review", "Department Review", "(owner department)", 24, False, "Always", ""), ("Approval", "Approval", "(owner department)", 24, True, "Always", ""),
      ("Sign-off", "Finance Sign-off", "Finance", 48, True, "Document type is finance-related", "")]),
    ("Legal", "Vendor Agreement", "Contract legal review", "Legal and quality checks, executive approval if confidential",
     [("Legal", "Legal Review", "Legal", 48, False, "Always", ""), ("Quality", "Quality Review", "QRI", 48, False, "Always", "", "Parallel with previous", "All must approve"),
      ("Executive", "Executive Approval", "Executive Offices", 72, True, "Security level at least", "Confidential"),
      ("Approval", "Approval", "(owner department)", 24, True, "Always", "")]),
    ("HR", "Employee Contract", "Employment contract", "HR review, legal review for external, head of HR signature",
     [("Review", "Department Review", "(owner department)", 24, False, "Always", ""), ("Legal", "Legal Review", "Legal", 48, False, "Classification is", "External"),
      ("Approval", "Approval", "(owner department)", 24, True, "Always", "")]),
    ("Medical Records", "Medical Record", "Patient record release", "Clinical review then medical records approval; confidential adds executive sign-off",
     [("Clinical", "Clinical Review", "Clinical Operations", 12, False, "Always", ""), ("Approval", "Approval", "(owner department)", 12, True, "Always", ""),
      ("Executive", "Executive Approval", "Executive Offices", 48, True, "Security level at least", "Confidential")]),
    ("Research", "Research Protocol", "Research protocol & ethics", "Quality and legal review before executive approval",
     [("Review", "Department Review", "(owner department)", 48, False, "Always", ""), ("Quality", "Quality Review", "QRI", 72, False, "Always", "", "Sequential", "All must approve"),
      ("Legal", "Legal Review", "Legal", 72, False, "Always", "", "Parallel with previous", "All must approve"), ("Executive", "Executive Approval", "Executive Offices", 72, True, "Always", "")]),
    ("IT", "System Configuration", "Change approval (CAB)", "Security review and approval for production changes",
     [("Review", "Department Review", "(owner department)", 8, False, "Always", ""), ("Review", "Security Review", "Security", 24, False, "Always", ""),
      ("Approval", "Approval", "(owner department)", 24, True, "Always", "")]),
    ("Clinical Operations", "SOP", "Clinical SOP publication", "Clinical and quality review, acknowledgment by staff",
     [("Clinical", "Clinical Review", "(owner department)", 48, False, "Always", ""), ("Quality", "Quality Review", "QRI", 48, False, "Always", "", "Parallel with previous", "All must approve"),
      ("Approval", "Approval", "(owner department)", 24, True, "Always", ""), ("Acknowledge", "Acknowledgment", "Nursing", 72, False, "Always", "")]),
    ("Finance", "Payment Approval", "Sequential 5-level payment approval", "Strictly one after another: review, head of department, finance, executive, final approval",
     [("Review", "Department Review", "(owner department)", 12, False, "Always", ""), ("Approval", "Head of Dept Approval", "(owner department)", 24, True, "Always", ""),
      ("Sign-off", "Finance Sign-off", "Finance", 24, True, "Always", ""), ("Executive", "Executive Approval", "Executive Offices", 48, True, "Always", ""),
      ("Approval", "Final Approval", "Finance", 12, True, "Always", "")]),
    ("Procurement", "Tender", "Sequential tender evaluation", "Procurement → Legal → Finance → Executive, each level waits for the previous",
     [("Review", "Procurement Review", "(owner department)", 48, False, "Always", ""), ("Legal", "Legal Review", "Legal", 48, False, "Always", ""),
      ("Sign-off", "Finance Sign-off", "Finance", 48, True, "Always", ""), ("Executive", "Executive Approval", "Executive Offices", 72, True, "Always", "")]),
    ("Security", "Inspection Report", "Two-level inspection approval", "Sequential: security review then approval",
     [("Review", "Department Review", "(owner department)", 24, False, "Always", ""), ("Approval", "Approval", "(owner department)", 24, True, "Always", "")]),
    ("HR", "Appraisal", "Performance appraisal chain", "Line review, HR approval, executive acknowledgment — in order",
     [("Review", "Line Manager Review", "(owner department)", 72, False, "Always", ""), ("Approval", "HR Approval", "(owner department)", 48, True, "Always", ""),
      ("Acknowledge", "Acknowledgment", "Executive Offices", 72, False, "Always", "")]),
    ("Marketing", "Campaign Document", "Marketing material approval", "Fast-track with executive approval for external material",
     [("Approval", "Approval", "(owner department)", 12, True, "Always", ""), ("Executive", "Executive Approval", "Executive Offices", 48, True, "Classification is", "External")]),
]


def flow_kind(steps):
    gs = grouped(steps)
    if any(len(g) > 1 for g in gs):
        return "⫴ Hybrid (sequential + parallel)" if any(len(g) == 1 for g in gs) else "⫴ Parallel"
    return "➡ Sequential"


def seed_samples():
    """Publish any sample design whose scope has no live design yet (safe to run on every start)."""
    for dept, dtype, name, note, st_ in SAMPLES:
        if latest(dept, dtype, "Published"):
            continue
        steps = []
        for kind, sname, assignee, sla, esign, cond, cval, *rest in st_:
            steps.append(new_step(kind, sname, sla, esign, cond, cval, assignee, *(rest or [])))
        save(dept, dtype, name, steps, "Yusuf Al-Marri", True, note)
