"""Configurable document numbering.

Two modes (switch on the Numbering Rules page):
  fixed   – one standard style for everything:  DEPT-TYPE-YYYY-NNNN   (legacy behaviour, unchanged)
  dynamic – rule based: a pattern per department / document type / classification, with its own counter reset.
"""
import datetime as dt
import re
import db
import rfp_data

TOKENS = {
    "{DEPT}": "Department code (FIN, HR, LEG …)", "{TYPE}": "Document-type code (INV, PO, CTR …)", "{CLASS}": "INT / EXT / REG",
    "{SEC}": "PUB / INT / RES / CON (security level)", "{YYYY}": "Year, 4 digits", "{YY}": "Year, 2 digits", "{MM}": "Month 01-12",
    "{DD}": "Day 01-31", "{SEQ:n}": "Running number with n digits, e.g. {SEQ:5} → 00042",
}
CLASS_CODE = {"Internal": "INT", "External": "EXT", "Regulatory": "REG"}
SEC_CODE = {"Public": "PUB", "Internal": "INT", "Restricted": "RES", "Confidential": "CON"}
RESETS = ["Yearly", "Monthly", "Never"]
DEFAULT_PATTERN = "{DEPT}-{TYPE}-{YYYY}-{SEQ:4}"
_TOK = re.compile(r"\{(DEPT|TYPE|CLASS|SEC|YYYY|YY|MM|DD|SEQ)(?::(\d{1,2}))?\}")


def init():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS numbering_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, dept TEXT, doc_type TEXT, classification TEXT,
        pattern TEXT, reset TEXT, start_at INTEGER, active INTEGER DEFAULT 1, note TEXT, updated_by TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS numbering_counters (ckey TEXT PRIMARY KEY, last INTEGER);
    """)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM numbering_rules").fetchone()[0]
    conn.close()
    if not n:
        for dept, dtype, cl, pat, reset, start, note in SAMPLE_RULES:
            conn = db.get_conn()
            conn.execute("INSERT INTO numbering_rules (dept, doc_type, classification, pattern, reset, start_at, active, note, updated_by, updated_at) VALUES (?,?,?,?,?,?,1,?,?,?)",
                         (dept, dtype, cl, pat, reset, start, note, "Yusuf Al-Marri", db.now()))
            conn.commit()
            conn.close()


SAMPLE_RULES = [  # dept, type, classification ('' = any)
    ("", "", "", DEFAULT_PATTERN, "Yearly", 1, "Global default — same as the fixed standard"),
    ("Finance", "", "", "FIN/{YY}{MM}/{TYPE}-{SEQ:4}", "Monthly", 1, "Finance: month-based, restarts every month"),
    ("Legal", "Vendor Agreement", "", "LEG-CON-{YYYY}-{SEQ:3}", "Yearly", 1, "Contracts: short three-digit series"),
    ("HR", "", "", "HR-{TYPE}-{YY}-{SEQ:5}", "Yearly", 1, "HR: two-digit year, five-digit sequence"),
    ("", "", "Regulatory", "REG/{YYYY}/{DEPT}/{SEQ:5}", "Yearly", 1, "All regulatory correspondence in one controlled series"),
    ("Medical Records", "Medical Record", "", "MRN-{SEQ:7}", "Never", 100000, "Medical records: continuous 7-digit number, never resets"),
]


# ------------------------------------------------------------------ settings --
def _get(key, default=None):
    conn = db.get_conn()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else default


def _set(key, value):
    conn = db.get_conn()
    conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()


def mode():
    return _get("num_mode", "fixed")


def set_mode(m, user):
    old = mode()
    _set("num_mode", m)
    if old != m:
        db.log_audit(None, user, "Numbering Mode Changed", f"Document numbering switched to {m}", field="numbering_mode", old=old, new=m)


# --------------------------------------------------------------------- rules --
def rules(active_only=False):
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM numbering_rules" + (" WHERE active=1" if active_only else "") + " ORDER BY id").fetchall()
    conn.close()
    return rows


def validate_pattern(p):
    p = (p or "").strip()
    if not p:
        return "Pattern is required."
    if len(p) > 48:
        return "Pattern is too long (max 48 characters)."
    if "{SEQ" not in p:
        return "Pattern must contain a running number, e.g. {SEQ:4}."
    if len(re.findall(r"\{SEQ(?::\d{1,2})?\}", p)) != 1:
        return "Use {SEQ:n} exactly once."
    leftover = _TOK.sub("", p)
    if re.search(r"[{}]", leftover):
        return "Unknown token — use only: " + ", ".join(TOKENS)
    if not re.fullmatch(r"[A-Za-z0-9/_\-. ]*", leftover.replace(" ", "")):
        return "Only letters, digits and / _ - . are allowed around tokens."
    return None


def save_rule(user, rule_id, dept, doc_type, classification, pattern, reset, start_at, active, note):
    err = validate_pattern(pattern)
    if err:
        return err
    conn = db.get_conn()
    if rule_id:
        conn.execute("UPDATE numbering_rules SET dept=?, doc_type=?, classification=?, pattern=?, reset=?, start_at=?, active=?, note=?, updated_by=?, updated_at=? WHERE id=?",
                     (dept, doc_type, classification, pattern, reset, int(start_at), 1 if active else 0, note, user, db.now(), rule_id))
    else:
        conn.execute("INSERT INTO numbering_rules (dept, doc_type, classification, pattern, reset, start_at, active, note, updated_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (dept, doc_type, classification, pattern, reset, int(start_at), 1 if active else 0, note, user, db.now()))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Numbering Rule Saved", f"{dept or 'any dept'} / {doc_type or 'any type'} / {classification or 'any class'}: {pattern} ({reset})",
                 field="numbering_rule", new=pattern)
    return None


def delete_rule(user, rule_id):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM numbering_rules WHERE id=?", (rule_id,)).fetchone()
    conn.execute("DELETE FROM numbering_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()
    if r:
        db.log_audit(None, user, "Numbering Rule Deleted", f"{r['dept'] or 'any'} / {r['doc_type'] or 'any'}: {r['pattern']}", field="numbering_rule", old=r["pattern"])


def match_rule(dept, doc_type, classification):
    """Most specific active rule wins (dept 4, type 2, classification 1); ties → newest id."""
    best, best_score = None, -1
    for r in rules(active_only=True):
        if r["dept"] and r["dept"] != dept:
            continue
        if r["doc_type"] and r["doc_type"] != doc_type:
            continue
        if r["classification"] and r["classification"] != classification:
            continue
        score = (4 if r["dept"] else 0) + (2 if r["doc_type"] else 0) + (1 if r["classification"] else 0)
        if score >= best_score:
            best, best_score = r, score
    return best


# ------------------------------------------------------------------ rendering --
def _render(pattern, dept, doc_type, classification, security_level, today, seq=None):
    vals = {"DEPT": rfp_data.DEPT_CODE.get(dept, "GEN"), "TYPE": rfp_data.TYPE_CODE.get(doc_type, "DOC"),
            "CLASS": CLASS_CODE.get(classification, "GEN"), "SEC": SEC_CODE.get(security_level, "GEN"),
            "YYYY": f"{today.year:04d}", "YY": f"{today.year % 100:02d}", "MM": f"{today.month:02d}", "DD": f"{today.day:02d}"}

    def sub(m):
        t, n = m.group(1), m.group(2)
        if t == "SEQ":
            return "\u0000" if seq is None else str(seq).zfill(int(n or 4))
        return vals[t]
    return _TOK.sub(sub, pattern)


def _period(reset, today):
    return {"Yearly": f"{today.year}", "Monthly": f"{today.year}-{today.month:02d}"}.get(reset, "all")


def next_number(dept, doc_type, classification=None, security_level=None, consume=True):
    """Return (code, description). consume=False → preview only (does not advance the counter)."""
    today = dt.date.today()
    rule = match_rule(dept, doc_type, classification)
    pattern, reset, start = (rule["pattern"], rule["reset"], rule["start_at"] or 1) if rule else (DEFAULT_PATTERN, "Yearly", 1)
    skeleton = _render(pattern, dept, doc_type, classification, security_level, today)
    ckey = f"{skeleton}|{_period(reset, today)}"
    conn = db.get_conn()
    row = conn.execute("SELECT last FROM numbering_counters WHERE ckey=?", (ckey,)).fetchone()
    n = (row["last"] + 1) if row else start
    code = _render(pattern, dept, doc_type, classification, security_level, today, n)
    while conn.execute("SELECT 1 FROM documents WHERE doc_code=?", (code,)).fetchone():     # never reuse a number
        n += 1
        code = _render(pattern, dept, doc_type, classification, security_level, today, n)
    if consume:
        conn.execute("INSERT INTO numbering_counters (ckey, last) VALUES (?,?) ON CONFLICT(ckey) DO UPDATE SET last=excluded.last", (ckey, n))
        conn.commit()
    conn.close()
    why = (f"rule #{rule['id']} · {rule['note'] or pattern}" if rule else "built-in default") + f" · counter resets {reset.lower()}"
    return code, why


def peek(dept, doc_type, classification=None, security_level=None):
    """Next number as the *current mode* would issue it (no side effects) → (code, explanation)."""
    if mode() == "dynamic":
        return next_number(dept, doc_type, classification, security_level, consume=False)
    import db_ext
    return db_ext.next_code_fixed(dept, doc_type), "fixed standard DEPT-TYPE-YYYY-NNNN"
