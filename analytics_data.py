"""Analytics data layer.

Two sources feed every chart:
  * LIVE   - read from the running repository (documents, workflow, distribution log, audit, e-signature ...)
  * HISTORY- a deterministic 12-month operating history generated for the demo (scanning batches, approval
             cycles, search activity). It is clearly labelled as simulated in the UI; in production the same
             tables are filled by the capture stations, workflow engine and search service.
"""
import datetime as dt
import numpy as np
import pandas as pd
import db
import rfp_data

TODAY = dt.date.today()
DEPTS = rfp_data.DEPARTMENTS
OPERATORS = {   # fictional capture operators and the department pool they mostly serve
    "Mariam T.": ["Medical Records", "Nursing", "Physicians, Dental & Pharmacy"],
    "Khalid N.": ["Medical Records", "Psychosocial Interventions (PSI)", "Clinical Operations"],
    "Noora H.": ["HR", "Finance", "Procurement", "Talent Management"],
    "Ahmed E.": ["Hospitality, Facility & Vendors", "Security", "IT", "Legal"],
    "Sara A.": ["Medical Records", "QRI", "Executive Offices", "Research", "Marketing", "Laboratory"],
}
STATIONS = ["Station 1 · Records Room A", "Station 2 · Records Room B", "Station 3 · Finance Office", "Station 4 · Mobile Cart"]
DEPT_W = {d: 1.0 for d in DEPTS}
DEPT_W.update({"Medical Records": 9, "Nursing": 3.2, "Finance": 3.5, "HR": 2.6, "Procurement": 2.6, "Legal": 1.8,
               "Hospitality, Facility & Vendors": 2.8, "Physicians, Dental & Pharmacy": 2.4, "QRI": 1.6, "Executive Offices": 1.8})
DEPT_TYPES = {
    "Medical Records": ["Medical Record", "Regulatory Letter", "Letter"], "Finance": ["Invoice", "Payment Approval", "Purchase Order"],
    "Procurement": ["Purchase Order", "Tender", "Supplier Record"], "HR": ["Employee Contract", "Appraisal", "Certificate"],
    "Legal": ["Vendor Agreement", "SLA", "Service Contract"], "Hospitality, Facility & Vendors": ["Maintenance Log", "Service Contract", "Inspection Report"],
}
DEFAULT_TYPES = ["Letter", "Memo", "Policy", "Certificate", "Regulatory Letter"]
STAGE_PARAMS = {  # median hours in stage, sla hours
    "Department Review": (9, 24), "Approval": (14, 24), "Finance Sign-off": (21, 48), "Legal Review": (26, 48),
}
QUERIES = [("invoice qar", 9), ("fire safety", 5), ("maintenance log", 6), ("patient discharge", 8), ("contract AND expired", 4),
           ("moph licence", 6), ("purchase order", 7), ("leave policy", 5), ("employee contract", 4), ("hvac", 3),
           ("accreditation evidence", 4), ("vendor agreement", 4), ("sla", 3), ("tender evaluation", 3), ("اتفاقية", 2),
           ("calibration certificate", 2), ("legal hold", 2), ("insurance", 1), ("cctv", 2), ("shift roster", 2),
           ("pharmacy formulary", 1), ("covid protocol", 1), ("parking permit", 1), ("board minutes 2019", 1)]
ZERO_RESULT = {"insurance", "covid protocol", "parking permit", "board minutes 2019", "shift roster", "pharmacy formulary"}


def _rng(k=0):
    return np.random.RandomState(2026 + k)


def _workdays(days):
    out = []
    for i in range(days, -1, -1):
        d = TODAY - dt.timedelta(days=i)
        if d.weekday() not in (4, 5):        # Qatar working week: Sunday-Thursday
            out.append(d)
    return out


def scan_history(days=365):
    r = _rng(1)
    rows, bid = [], 1
    wd = _workdays(days)
    dws = np.array([DEPT_W[d] for d in DEPTS])
    dws = dws / dws.sum()
    n = len(wd)
    for i, d in enumerate(wd):
        growth = 0.8 + 0.9 * i / n                      # ramp-up as more departments go live
        k = r.poisson(5.2 * growth)
        for _ in range(k):
            dept = DEPTS[r.choice(len(DEPTS), p=dws)]
            ops = [o for o, pool in OPERATORS.items() if dept in pool] or list(OPERATORS)
            op = ops[r.randint(len(ops))]
            lang = "Arabic" if r.rand() < 0.17 else "English"
            hand = r.rand() < 0.07                      # poor quality / handwriting
            base = 96.8 if lang == "English" else 91.5
            conf = float(np.clip(r.normal(base - (11 if hand else 0), 2.0 if not hand else 4.0) + 0.9 * i / n, 62, 99.7))
            pages = int(np.clip(r.lognormal(3.8, 0.7), 4, 420))
            corrected = int(r.binomial(pages, min(0.6, (100 - conf) / 100 * 0.85)))
            rescan = int(r.binomial(pages, 0.01 + (100 - conf) * 0.0014))
            pph = float(np.clip(r.normal(255 + (20 if op in ("Mariam T.", "Noora H.") else 0), 38), 120, 420))
            hour = int(np.clip(r.normal(10.6, 2.0), 7, 15))
            rows.append({
                "batch_id": bid, "date": pd.Timestamp(d), "hour": hour, "dept": dept, "operator": op,
                "station": STATIONS[r.randint(len(STATIONS))], "doc_type": (DEPT_TYPES.get(dept) or DEFAULT_TYPES)[r.randint(3 if dept in DEPT_TYPES else 5)],
                "language": lang, "pages": pages, "ocr_conf": round(conf, 1), "corrected_pages": corrected, "rescan_pages": rescan,
                "minutes": round(pages / pph * 60 + r.uniform(2, 6), 1), "poor_quality": hand,
                "auto_routed": bool(r.rand() < (0.76 + 0.17 * i / n)), "source": "history"})
            bid += 1
    df = pd.DataFrame(rows)
    return pd.concat([df, _live_scans(bid)], ignore_index=True)


def _live_scans(start_id):
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM documents WHERE source='Scan' AND status NOT IN ('Deleted','Disposed')").fetchall()
    conn.close()
    out = []
    for i, d in enumerate(rows):
        words = len((d["body_text"] or "").split())
        out.append({"batch_id": start_id + i, "date": pd.Timestamp((d["created_at"] or str(TODAY))[:10]), "hour": 10, "dept": d["department"],
                    "operator": "Live capture", "station": "Live OCR page", "doc_type": d["doc_type"], "language": d["language"],
                    "pages": 1, "ocr_conf": 95.0, "corrected_pages": 0, "rescan_pages": 0, "minutes": 0.5, "poor_quality": False,
                    "auto_routed": True, "source": "live"})
    return pd.DataFrame(out)


def approval_history(days=365):
    r = _rng(2)
    rows = []
    wd = _workdays(days)
    n = len(wd)
    users_by_dept = {}
    for nme, p in rfp_data.ROLES.items():
        users_by_dept.setdefault(p["dept"], []).append(nme)
    dws = np.array([DEPT_W[d] for d in DEPTS])
    dws = dws / dws.sum()
    for i, d in enumerate(wd):
        k = r.poisson(14 * (0.8 + 0.8 * i / n))
        for _ in range(k):
            dept = DEPTS[r.choice(len(DEPTS), p=dws)]
            dtype = (DEPT_TYPES.get(dept) or DEFAULT_TYPES)[r.randint(3 if dept in DEPT_TYPES else 5)]
            stages = ["Department Review", "Approval"]
            if dtype in rfp_data.FINANCE_TYPES:
                stages.append("Finance Sign-off")
            if dept == "Legal" or dtype in ("Vendor Agreement", "SLA", "Service Contract"):
                stages.insert(1, "Legal Review")
            t = pd.Timestamp(d) + pd.Timedelta(hours=int(r.randint(7, 15)))
            approver = (users_by_dept.get(dept) or ["Yusuf Al-Marri"])[0]
            for st_ in stages:
                med, sla = STAGE_PARAMS[st_]
                hrs = float(r.lognormal(np.log(med), 0.65) * (1.15 - 0.3 * i / n))     # cycle times improve over the year
                outcome = r.choice(["Approved", "Rejected", "Returned"], p=[0.92, 0.05, 0.03])
                rows.append({"date": pd.Timestamp(d), "completed": t + pd.Timedelta(hours=hrs), "dept": dept, "doc_type": dtype, "stage": st_,
                             "approver": approver, "hours": round(hrs, 1), "sla_hours": sla, "breached": hrs > sla, "outcome": outcome})
                t += pd.Timedelta(hours=hrs)
                if outcome != "Approved":
                    break
    return pd.DataFrame(rows)


def search_history(days=365):
    r = _rng(3)
    rows = []
    wd = _workdays(days)
    n = len(wd)
    q, w = zip(*QUERIES)
    w = np.array(w, float) / sum(w)
    users = list(rfp_data.ROLES.keys())
    for i, d in enumerate(wd):
        k = r.poisson(34 * (0.5 + 1.4 * i / n))          # search adoption grows
        for _ in range(k):
            qq = q[r.choice(len(q), p=w)]
            zero = qq in ZERO_RESULT
            hits = 0 if zero else int(np.clip(r.lognormal(1.6, 0.8), 1, 60))
            opened = (not zero) and r.rand() < 0.74
            usr = users[r.randint(len(users))]
            rows.append({"date": pd.Timestamp(d), "hour": int(np.clip(r.normal(11, 2.6), 7, 16)), "query": qq, "user": usr,
                         "dept": rfp_data.ROLES[usr]["dept"], "mode": "Natural language" if r.rand() < 0.28 else "Smart",
                         "hits": hits, "opened": opened, "downloaded": opened and r.rand() < 0.35,
                         "seconds_to_find": float(np.clip(r.lognormal(2.7, 0.6), 4, 240)) if opened else np.nan,
                         "ocr_hit": (not zero) and r.rand() < 0.38})
    return pd.DataFrame(rows)


def ack_history(days=365):
    """Distribution acknowledgement times (hours) by department."""
    r = _rng(4)
    rows = []
    wd = _workdays(days)
    n = len(wd)
    dws = np.array([DEPT_W[d] for d in DEPTS])
    dws = dws / dws.sum()
    for i, d in enumerate(wd):
        for _ in range(r.poisson(9 * (0.8 + 0.9 * i / n))):
            dept = DEPTS[r.choice(len(DEPTS), p=dws)]
            sla = int(r.choice([4, 8, 24, 48], p=[0.1, 0.25, 0.4, 0.25]))
            hrs = float(r.lognormal(np.log(sla * 0.45), 0.6))
            rows.append({"date": pd.Timestamp(d), "dept": dept, "sla_hours": sla, "ack_hours": round(hrs, 1), "on_time": hrs <= sla,
                         "auto_routed": r.rand() < (0.8 + 0.14 * i / n), "reassigned": r.rand() < 0.04})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ live data
def live_documents():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM documents WHERE status NOT IN ('Deleted','Disposed')").fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows])


def live_workflow():
    conn = db.get_conn()
    rows = conn.execute("SELECT w.*, d.doc_code, d.title, d.department, d.doc_type, d.modified_at FROM workflow w "
                        "JOIN documents d ON d.id=w.document_id WHERE d.status NOT IN ('Deleted','Disposed')").fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows])


def live_table(sql, params=()):
    conn = db.get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        rows = []
    conn.close()
    return pd.DataFrame([dict(r) for r in rows])
