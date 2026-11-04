"""Live notification counts for the top-bar badges and sidebar menu."""
import db
import db_ext
import distribution as dist


def counts(user, dept, is_admin):
    out = {}
    try:
        out["notif"] = len(db_ext.get_notifications(user, only_unread=True))
    except Exception:
        out["notif"] = 0
    try:
        import delegation
        _p = delegation.pending_for_user(user)
        out["pending"] = len(_p)
        out["deleg"] = len([x for x in _p if x["on_behalf_of"]])
    except Exception:
        out["pending"] = out["deleg"] = 0
    try:
        od = db_ext.overdue_approvals()
        out["overdue"] = len([r for r in od if is_admin or r["department"] == dept])
    except Exception:
        out["overdue"] = 0
    try:
        out["triage"] = dist.stats()["triage"] if is_admin or dept == "Medical Records" else 0
    except Exception:
        out["triage"] = 0
    try:
        conn = db.get_conn()
        q = ("SELECT COUNT(*) FROM documents WHERE expiry_date IS NOT NULL AND expiry_date <= date('now','+90 day') "
             "AND status NOT IN ('Disposed','Deleted')" + ("" if is_admin else " AND department=?"))
        out["expiring"] = conn.execute(q, () if is_admin else (dept,)).fetchone()[0]
        out["holds"] = conn.execute("SELECT COUNT(*) FROM documents WHERE legal_hold=1 AND status NOT IN ('Deleted')"
                                    + ("" if is_admin else " AND department=?"), () if is_admin else (dept,)).fetchone()[0]
        conn.close()
    except Exception:
        out["expiring"] = out["holds"] = 0
    return out


# key -> (label, emoji, colour, page key)
CHIPS = [("notif", "Notifications", "🔔", "#C0603C", "9"), ("pending", "Awaiting approval", "✍️", "#1F3864", "4"),
         ("deleg", "Delegated to me", "🏖️", "#1F6F78", "19"), ("overdue", "SLA overdue", "⏰", "#B00020", "4"), ("triage", "Triage queue", "📥", "#B8860B", "12"),
         ("expiring", "Expiring ≤90d", "⌛", "#7B3FA0", "8"), ("holds", "Legal holds", "⚖️", "#2E8B8B", "5")]

# sidebar menu page key -> count key
MENU = {"4": "pending", "9": "notif", "12": "triage", "8": "expiring"}
