"""Automatic distribution engine.

Content rules read the (OCR'd) text of a document and decide, with no manual step:
  * which department owns it (primary) and who receives copies,
  * what the document type / classification should be,
  * who is notified, with an SLA to acknowledge,
and anything that matches no rule is parked in a triage queue.
"""
import difflib
import json
import re
import db
import rfp_data

DEFAULT_RULES = [
    # name, keywords, primary, copies, doc_type, classification, priority, sla_hours
    ("Supplier invoices & payments", "invoice; tax invoice; payment due; remit; فاتورة; accounts payable", "Finance", "Procurement", "Invoice", "External", 9, 24),
    ("Purchase orders & tenders", "purchase order; tender; rfq; quotation; supplier; po-20", "Procurement", "Finance", "Purchase Order", "External", 8, 24),
    ("Contracts & legal review", "contract; agreement; indemnity; liability; counsel; litigation; عقد; اتفاقية", "Legal", "Executive Offices", "Service Contract", "External", 7, 48),
    ("Regulatory & ministry correspondence", "ministry; moph; licen; accreditation; regulatory; وزارة; ترخيص", "QRI", "Executive Offices; Legal", "Regulatory Letter", "Regulatory", 10, 8),
    ("Patient records & referrals", "patient; discharge; admission; medical record; referral; qid; clinical notes", "Medical Records", "Nursing; Physicians, Dental & Pharmacy", "Medical Record", "Internal", 9, 4),
    ("HR, leave & staffing", "leave policy; employee; recruitment; payroll; appraisal; staff leave; إجازات; موظف", "HR", "Talent Management", "Circular", "Internal", 6, 48),
    ("IT incidents & systems", "server; network; firewall; outage; switch failure; system configuration; patch", "IT", "Security", "System Configuration", "Internal", 6, 8),
    ("Security & safety", "fire safety; fire drill; cctv; access card; evacuation; security incident", "Security", "Hospitality, Facility & Vendors", "Inspection Report", "Internal", 7, 24),
    ("Facilities & maintenance", "hvac; maintenance; cleaning; electrical; facility; vendor; calibration", "Hospitality, Facility & Vendors", "Procurement", "Maintenance Log", "Internal", 5, 48),
    ("Research & ethics", "research protocol; irb; ethics committee; clinical trial; study", "Research", "Legal", "Research Protocol", "Internal", 5, 72),
    ("Marketing & communications", "campaign; event plan; brand; press release; media", "Marketing", "Executive Offices", "Campaign Document", "Internal", 4, 72),
]


def _c():
    c = db.get_conn()
    return c


def init_dist():
    conn = _c()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS dist_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, keywords TEXT, primary_dept TEXT, copy_depts TEXT,
        doc_type TEXT, classification TEXT, priority INTEGER DEFAULT 5, sla_hours INTEGER DEFAULT 24,
        active INTEGER DEFAULT 1, created_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS dist_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, rule_name TEXT, matched TEXT, target_dept TEXT,
        role TEXT, delivered_to TEXT, ts TEXT, sla_due TEXT, status TEXT, ack_by TEXT, ack_at TEXT, score REAL);
    """)
    if conn.execute("SELECT COUNT(*) FROM dist_rules").fetchone()[0] == 0:
        for n, kw, p, cp, dt_, cl, pr, sla in DEFAULT_RULES:
            conn.execute("INSERT INTO dist_rules (name, keywords, primary_dept, copy_depts, doc_type, classification, priority, "
                         "sla_hours, active, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,1,'System',?)",
                         (n, kw, p, cp, dt_, cl, pr, sla, db.now()))
    conn.commit()
    conn.close()


def list_rules():
    conn = _c()
    rows = conn.execute("SELECT * FROM dist_rules ORDER BY priority DESC, id").fetchall()
    conn.close()
    return rows


def save_rule(name, keywords, primary, copies, doc_type, classification, priority, sla, user, rule_id=None, active=1):
    conn = _c()
    if rule_id:
        conn.execute("UPDATE dist_rules SET name=?, keywords=?, primary_dept=?, copy_depts=?, doc_type=?, classification=?, "
                     "priority=?, sla_hours=?, active=? WHERE id=?",
                     (name, keywords, primary, "; ".join(copies), doc_type, classification, priority, sla, int(active), rule_id))
    else:
        conn.execute("INSERT INTO dist_rules (name, keywords, primary_dept, copy_depts, doc_type, classification, priority, "
                     "sla_hours, active, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,1,?,?)",
                     (name, keywords, primary, "; ".join(copies), doc_type, classification, priority, sla, user, db.now()))
    conn.commit()
    conn.close()


def set_active(rule_id, active):
    conn = _c()
    conn.execute("UPDATE dist_rules SET active=? WHERE id=?", (int(active), rule_id))
    conn.commit()
    conn.close()


def delete_rule(rule_id):
    conn = _c()
    conn.execute("DELETE FROM dist_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


def _terms(kw):
    return [t.strip() for t in re.split(r"[;\n]", kw or "") if t.strip()]


def _count(term, text, words):
    """Count occurrences of a keyword/phrase; tolerant of OCR slips for longer single words."""
    t = term.lower()
    if re.search(r"[^\x00-\x7f]", t):               # Arabic / non-latin -> plain substring
        return text.count(t)
    n = len(re.findall(r"(?<![a-z0-9])" + re.escape(t), text))   # prefix-aware: 'licen' hits licence/license
    if n:
        return n
    if " " not in t and len(t) >= 6:                  # OCR-tolerant fuzzy match
        m = difflib.get_close_matches(t, words, n=1, cutoff=0.86)
        if m:
            return 1
    return 0


def analyse(text, title="", sender="", rules=None):
    """Return the routing decision for a piece of text without touching the database."""
    hay = " ".join([title or "", sender or "", text or ""]).lower()
    words = set(re.findall(r"\w+", hay))
    hits = []
    for r in (rules if rules is not None else list_rules()):
        if not r["active"]:
            continue
        matched, score = [], 0.0
        for t in _terms(r["keywords"]):
            n = _count(t, hay, words)
            if n:
                matched.append(t)
                score += min(n, 3)
        if matched:
            hits.append({"rule": r, "matched": matched, "score": score + r["priority"] * 10})
    hits.sort(key=lambda h: -h["score"])
    if not hits:
        return {"hits": [], "primary": None, "copies": [], "doc_type": None, "classification": None}
    top = hits[0]["rule"]
    copies = []
    cand = _terms(top["copy_depts"]) + ([hits[1]["rule"]["primary_dept"]] if len(hits) > 1 else [])
    for d in cand:
        if d != top["primary_dept"] and d in rfp_data.DEPARTMENTS and d not in copies:
            copies.append(d)
    return {"hits": hits, "primary": top["primary_dept"], "copies": copies[:3], "doc_type": top["doc_type"],
            "classification": top["classification"]}


def _users(dept):
    return [n for n, p in rfp_data.ROLES.items() if p["dept"] == dept]


def distribute(doc_id, actor="System", apply_dept=True, notify=True, text=None):
    """Apply the rules to a stored document: route, classify, notify, log. Returns the decision."""
    import db_ext
    d = db.get_document(doc_id)
    res = analyse(text if text is not None else (d["body_text"] or ""), d["title"], d["sender"] or "")
    conn = _c()
    ts = db.now()
    if not res["hits"]:
        conn.execute("INSERT INTO dist_log (document_id, rule_name, matched, target_dept, role, delivered_to, ts, sla_due, status, score) "
                     "VALUES (?,?,?,?,?,?,?,?,?,0)", (doc_id, "— no rule matched —", "", "Unrouted", "Triage", "Records triage queue",
                                                      ts, None, "Needs triage"))
        conn.commit()
        conn.close()
        db.log_audit(doc_id, actor, "Auto-distribution", "No rule matched — sent to triage queue")
        return res
    top = res["hits"][0]
    sla = top["rule"]["sla_hours"] or 24
    due = f"datetime('now', '+{int(sla)} hour')"
    targets = [(res["primary"], "Primary")] + [(c, "Copy") for c in res["copies"]]
    for dept, role in targets:
        users = _users(dept)
        who = ", ".join(users) if users else f"{dept} inbox"
        conn.execute(f"INSERT INTO dist_log (document_id, rule_name, matched, target_dept, role, delivered_to, ts, sla_due, status, score) "
                     f"VALUES (?,?,?,?,?,?,?,{due},?,?)",
                     (doc_id, top["rule"]["name"], ", ".join(top["matched"][:6]), dept, role, who, ts, "Delivered", top["score"]))
    sets, params = [], []
    if apply_dept and d["department"] != res["primary"]:
        sets.append("department=?")
        params.append(res["primary"])
        conn.execute("UPDATE workflow SET assignee=? WHERE document_id=? AND status='active'", (res["primary"], doc_id))
    if apply_dept and res["doc_type"] and d["doc_type"] in ("Scanned Correspondence", "Letter", None, ""):
        sets.append("doc_type=?")
        params.append(res["doc_type"])
    if apply_dept and res["classification"] and d["source"] == "Scan":
        sets.append("classification=?")
        params.append(res["classification"])
    if sets:
        conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE id=?", params + [doc_id])
    conn.commit()
    conn.close()
    db.log_audit(doc_id, actor, "Auto-distribution",
                 f"Rule '{top['rule']['name']}' matched [{', '.join(top['matched'][:5])}] → {res['primary']}"
                 + (f"; copies: {', '.join(res['copies'])}" if res["copies"] else ""))
    if notify:
        for dept, role in targets:
            for u in _users(dept):
                db_ext.notify(u, f"{'Action required' if role == 'Primary' else 'Copy'}: {d['doc_code']} — {d['title']} "
                                 f"auto-routed by rule “{top['rule']['name']}” (acknowledge within {sla}h)", doc_id,
                              "action" if role == "Primary" else "info")
    return res


def acknowledge(log_id, user):
    conn = _c()
    conn.execute("UPDATE dist_log SET status='Acknowledged', ack_by=?, ack_at=? WHERE id=?", (user, db.now(), log_id))
    row = conn.execute("SELECT document_id, target_dept FROM dist_log WHERE id=?", (log_id,)).fetchone()
    conn.commit()
    conn.close()
    if row:
        db.log_audit(row["document_id"], user, "Distribution acknowledged", f"{row['target_dept']} acknowledged receipt")


def triage_assign(doc_id, dept, user):
    import db_ext
    conn = _c()
    d = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.execute("UPDATE documents SET department=? WHERE id=?", (dept, doc_id))
    conn.execute("UPDATE workflow SET assignee=? WHERE document_id=? AND status='active'", (dept, doc_id))
    conn.execute("UPDATE dist_log SET status='Triaged', ack_by=?, ack_at=? WHERE document_id=? AND target_dept='Unrouted'",
                 (user, db.now(), doc_id))
    conn.execute("INSERT INTO dist_log (document_id, rule_name, matched, target_dept, role, delivered_to, ts, sla_due, status, score) "
                 "VALUES (?,?,?,?,?,?,?,datetime('now','+24 hour'),'Delivered',0)",
                 (doc_id, "Manual triage", "", dept, "Primary", ", ".join(_users(dept)) or f"{dept} inbox", db.now()))
    conn.commit()
    conn.close()
    db.log_audit(doc_id, user, "Manual triage", f"Assigned to {dept}")
    for u in _users(dept):
        db_ext.notify(u, f"Action required: {d['doc_code']} — {d['title']} assigned to you from triage", doc_id, "action")


def log_rows(status=None, dept=None, doc_id=None, limit=300):
    conn = _c()
    q = ("SELECT l.*, d.doc_code, d.title, d.source FROM dist_log l JOIN documents d ON d.id=l.document_id WHERE 1=1")
    p = []
    if status and status != "All":
        q += " AND l.status=?"
        p.append(status)
    if dept and dept != "All":
        q += " AND l.target_dept=?"
        p.append(dept)
    if doc_id:
        q += " AND l.document_id=?"
        p.append(doc_id)
    q += " ORDER BY l.id DESC LIMIT ?"
    p.append(limit)
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return rows


def triage_queue():
    conn = _c()
    rows = conn.execute("SELECT l.*, d.doc_code, d.title, d.body_text FROM dist_log l JOIN documents d ON d.id=l.document_id "
                        "WHERE l.target_dept='Unrouted' AND l.status='Needs triage' ORDER BY l.id DESC").fetchall()
    conn.close()
    return rows


def stats():
    conn = _c()
    s = {
        "total": conn.execute("SELECT COUNT(DISTINCT document_id) FROM dist_log").fetchone()[0],
        "routed": conn.execute("SELECT COUNT(DISTINCT document_id) FROM dist_log WHERE target_dept!='Unrouted'").fetchone()[0],
        "triage": conn.execute("SELECT COUNT(*) FROM dist_log WHERE status='Needs triage'").fetchone()[0],
        "acked": conn.execute("SELECT COUNT(*) FROM dist_log WHERE status='Acknowledged' AND role='Primary'").fetchone()[0],
        "primary": conn.execute("SELECT COUNT(*) FROM dist_log WHERE role='Primary'").fetchone()[0],
        "overdue": conn.execute("SELECT COUNT(*) FROM dist_log WHERE status='Delivered' AND sla_due < datetime('now')").fetchone()[0],
        "by_rule": conn.execute("SELECT rule_name, COUNT(DISTINCT document_id) n FROM dist_log WHERE target_dept!='Unrouted' "
                                "GROUP BY rule_name ORDER BY n DESC").fetchall(),
        "by_dept": conn.execute("SELECT target_dept, COUNT(*) n FROM dist_log WHERE target_dept!='Unrouted' "
                                "GROUP BY target_dept ORDER BY n DESC").fetchall(),
    }
    conn.close()
    return s
