"""Approval delegation / out-of-office rules.

A rule says: between START and END, everything that lands in <delegator>'s approval queue
is ALSO visible to, and can be actioned by, <delegate> - optionally limited to some document
types and optionally excluding Confidential / Restricted documents.
Every action taken under a rule is audited as "on behalf of" and the absent person is notified.
"""
import json
from datetime import date, timedelta

import db
import db_ext
import rfp_data

REASONS = ["Annual leave", "Sick leave", "Business trip", "Training / conference", "Maternity / paternity", "Other"]
SENSITIVE = ("Confidential", "Restricted", "Highly Confidential", "Secret")


def init():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS delegation_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        delegator TEXT NOT NULL,
        delegate TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        reason TEXT,
        note TEXT,
        doc_types TEXT,              -- JSON list, NULL = all types
        exclude_sensitive INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active', -- active | cancelled
        created_by TEXT,
        created_at TEXT
    );
    """)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM delegation_rules").fetchone()[0]
    conn.close()
    if n == 0:
        _seed()


def _seed():
    t = date.today()
    d = lambda k: (t + timedelta(days=k)).isoformat()
    add_rule("Fatima Al-Sulaiti", "Omar Al-Kaabi", d(-1), d(10), "Annual leave",
             "Back on the 15th. Urgent items: call my mobile.", None, True, "Yusuf Al-Marri", quiet=True)
    add_rule("Hassan Al-Naimi", "Layla Al-Marri", d(5), d(19), "Training / conference",
             "Nursing approvals to QRI while I am at the accreditation course.", None, False, "Hassan Al-Naimi", quiet=True)
    add_rule("Noor Al-Kuwari", "Sara Al-Ansari", d(-20), d(-12), "Business trip",
             "", ["Contract", "Policy"], False, "Noor Al-Kuwari", quiet=True)


# -------------------------------------------------------------------- rules --
def rules(include_cancelled=True):
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM delegation_rules ORDER BY start_date DESC, id DESC").fetchall()]
    conn.close()
    for r in rows:
        r["types"] = json.loads(r["doc_types"]) if r["doc_types"] else None
        r["state"] = state(r)
    return rows if include_cancelled else [r for r in rows if r["state"] != "Cancelled"]


def state(r, today=None):
    today = (today or date.today()).isoformat()
    if r["status"] == "cancelled":
        return "Cancelled"
    if today < r["start_date"]:
        return "Scheduled"
    if today > r["end_date"]:
        return "Expired"
    return "Active"


def validate(delegator, delegate, start, end):
    """Return (errors, warnings)."""
    err, warn = [], []
    if delegator == delegate:
        err.append("A person cannot delegate to themselves.")
    if end < start:
        err.append("The end date is before the start date.")
    if not err:
        s, e = start.isoformat(), end.isoformat()
        for r in rules(include_cancelled=False):
            if r["state"] == "Expired":
                continue
            overlap = not (e < r["start_date"] or s > r["end_date"])
            if overlap and r["delegator"] == delegator:
                err.append(f"{delegator} already has a delegation to {r['delegate']} from {r['start_date']} to {r['end_date']} - cancel or shorten it first.")
            if overlap and r["delegator"] == delegate and r["delegate"] == delegator:
                err.append(f"Circular delegation: {delegate} has already delegated to {delegator} for these dates.")
            if overlap and r["delegator"] == delegate:
                warn.append(f"{delegate} is also away ({r['start_date']} to {r['end_date']}, covered by {r['delegate']}). Approvals do not chain - they stay with {delegate}'s delegate only if you choose them directly.")
    return err, warn


def add_rule(delegator, delegate, start, end, reason, note, doc_types, exclude_sensitive, actor, quiet=False):
    s = start if isinstance(start, str) else start.isoformat()
    e = end if isinstance(end, str) else end.isoformat()
    conn = db.get_conn()
    cur = conn.execute("""INSERT INTO delegation_rules (delegator, delegate, start_date, end_date, reason, note, doc_types,
                          exclude_sensitive, status, created_by, created_at) VALUES (?,?,?,?,?,?,?,?, 'active', ?, ?)""",
                       (delegator, delegate, s, e, reason, note, json.dumps(doc_types) if doc_types else None,
                        1 if exclude_sensitive else 0, actor, db.now()))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    if not quiet:
        scope = ("selected document types" if doc_types else "all approvals") + (", excluding Confidential/Restricted" if exclude_sensitive else "")
        db.log_audit(None, actor, "Delegation Created", f"{delegator} -> {delegate}, {s} to {e} ({reason}); {scope}")
        db_ext.notify(delegate, f"{delegator} has delegated approvals to you from {s} to {e}. They will appear in your approval queue.", None, "approval")
        if actor != delegator:
            db_ext.notify(delegator, f"{actor} set up an out-of-office delegation for you: {delegate}, {s} to {e}.", None, "approval")
    return rid


def cancel_rule(rid, actor):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM delegation_rules WHERE id=?", (rid,)).fetchone()
    conn.execute("UPDATE delegation_rules SET status='cancelled' WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    if r:
        db.log_audit(None, actor, "Delegation Cancelled", f"{r['delegator']} -> {r['delegate']} ({r['start_date']} to {r['end_date']})")
        db_ext.notify(r["delegate"], f"The delegation from {r['delegator']} was cancelled.", None, "approval")


def is_away(user):
    for r in rules(False):
        if r["delegator"] == user and r["state"] == "Active":
            return r
    return None


def covering(user):
    """Active rules under which `user` is the delegate."""
    return [r for r in rules(False) if r["delegate"] == user and r["state"] == "Active"]


# ----------------------------------------------------------------- the queue --
_SQL = """SELECT w.*, d.title, d.doc_code, d.department, d.classification, d.doc_type
          FROM workflow w JOIN documents d ON d.id = w.document_id
          WHERE w.status='active' AND {where} ORDER BY w.id DESC"""


def _query(where, params):
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(_SQL.format(where=where), params).fetchall()]
    conn.close()
    return rows


def pending_for_user(user):
    """Own approvals + approvals that reach this user through a delegation rule.
    Each row gets 'on_behalf_of' (None for own items) and 'via_rule'."""
    prof = rfp_data.ROLES.get(user)
    if not prof:
        return []
    admin = prof["level"] == "admin"
    own = db.get_pending_for_assignee(prof["dept"], admin)
    out = {}
    for r in own:
        r = dict(r)
        r.update(on_behalf_of=None, via_rule=None)
        out[r["id"]] = r
    conn = db.get_conn()
    for r in conn.execute("SELECT w.*, d.title, d.doc_code, d.department, d.classification, d.doc_type FROM workflow w "
                          "JOIN documents d ON d.id=w.document_id WHERE w.status='active' AND w.delegated_to=?", (user,)).fetchall():
        r = dict(r)
        if r["id"] not in out:
            r.update(on_behalf_of=f"{r['assignee'] or r['department']} team (item delegated)", via_rule=None)
            out[r["id"]] = r
    conn.close()
    if not admin:                              # an administrator already sees everything
        for rule in covering(user):
            dprof = rfp_data.ROLES.get(rule["delegator"])
            if not dprof:
                continue
            for r in db.get_pending_for_assignee(dprof["dept"], dprof["level"] == "admin"):
                r = dict(r)
                if r["id"] in out:
                    continue
                if rule["types"] and r.get("doc_type") not in rule["types"]:
                    continue
                if rule["exclude_sensitive"] and r.get("classification") in SENSITIVE:
                    continue
                r.update(on_behalf_of=rule["delegator"], via_rule=rule["id"])
                out[r["id"]] = r
    return sorted(out.values(), key=lambda x: -x["id"])


def delegated_count(user):
    return len([r for r in pending_for_user(user) if r["on_behalf_of"]])


def acted_on_behalf(limit=200):
    return [dict(r) for r in db.get_audit_log(None, limit=1000) if "on behalf of" in (r["detail"] or "")][:limit]


def record_action(doc_id, actor, on_behalf_of, action, stage):
    """Audit + notify the absent person when someone acts for them."""
    db.log_audit(doc_id, actor, f"{action} on behalf", f"{actor} {action.lower()} '{stage}' on behalf of {on_behalf_of} (delegation)")
    d = db.get_document(doc_id)
    if on_behalf_of in rfp_data.ROLES:
        db_ext.notify(on_behalf_of, f"{actor} {action.lower()} '{stage}' for {d['doc_code']} on your behalf.", doc_id, "approval")
