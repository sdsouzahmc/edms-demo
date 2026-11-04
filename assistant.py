"""Rule-based conversational document finder (no external AI service).

Understands plain sentences such as "show pending finance invoices", "how many contracts expire soon",
"scanned letters from MOPH", "latest HR policies in Arabic", and answers with document cards.
"""
import re
import db
import search_engine as se
from rfp_data import DEPARTMENTS

DEPT_ALIAS = {"hr": "HR", "human resources": "HR", "finance": "Finance", "financial": "Finance", "legal": "Legal", "it": "IT",
              "nursing": "Nursing", "lab": "Laboratory", "laboratory": "Laboratory", "procurement": "Procurement",
              "marketing": "Marketing", "research": "Research", "security": "Security", "qri": "QRI", "quality": "QRI",
              "medical records": "Medical Records", "executive": "Executive Offices", "talent": "Talent Management",
              "pharmacy": "Physicians, Dental & Pharmacy", "physicians": "Physicians, Dental & Pharmacy",
              "facility": "Hospitality, Facility & Vendors", "facilities": "Hospitality, Facility & Vendors", "clinical operations": "Clinical Operations",
              "psychosocial": "Psychosocial Interventions (PSI)", "psi": "Psychosocial Interventions (PSI)",
              "المالية": "Finance", "الموارد البشرية": "HR", "القانونية": "Legal", "التمريض": "Nursing", "المشتريات": "Procurement",
              "المختبر": "Laboratory", "تقنية المعلومات": "IT", "الأمن": "Security"}
STATUS_WORDS = {"pending": ["Department Review", "Approval", "Finance Sign-off"], "awaiting": ["Department Review", "Approval", "Finance Sign-off"],
                "approval": ["Approval"], "in review": ["Department Review"], "review": ["Department Review"],
                "released": ["Released"], "published": ["Released"], "official": ["Released"], "approved": ["Released"],
                "draft": ["Draft"], "drafts": ["Draft"], "archived": ["Archived"], "archive": ["Archived"],
                "rejected": ["Rejected"], "finance sign-off": ["Finance Sign-off"],
                "معتمد": ["Released"], "مسودة": ["Draft"], "مؤرشف": ["Archived"], "معلق": ["Department Review", "Approval", "Finance Sign-off"]}
LEVELS = {"confidential": "Confidential", "restricted": "Restricted", "سري": "Confidential"}
NOISE = {"show", "me", "find", "get", "list", "give", "search", "for", "the", "a", "an", "of", "in", "from", "all", "any", "please", "can",
         "you", "i", "need", "want", "look", "looking", "is", "are", "there", "do", "we", "have", "documents", "document", "docs", "doc",
         "files", "file", "about", "related", "to", "regarding", "latest", "recent", "newest", "new", "how", "many", "count", "number",
         "what", "which", "that", "with", "and", "or", "scanned", "scans", "scan", "ocr", "expiring", "expire", "expires", "soon", "legal",
         "hold", "under", "arabic", "english", "department", "dept", "by", "my", "our", "us", "on", "at", "are", "was", "were",
         "أريد", "ابحث", "عن", "أظهر", "اعرض", "مستندات", "مستند", "وثائق", "كل", "في", "من"}
WORDMAP = {"pending": "", "awaiting": "", "released": "", "approved": "", "published": "", "official": "", "draft": "", "drafts": "",
           "archived": "", "archive": "", "rejected": "", "confidential": "", "restricted": "", "review": "", "approval": ""}


def interpret(q):
    ql = q.lower().strip()
    hold_q = "legal hold" in ql or "حجز" in ql
    ql = ql.replace("legal hold", " hold ")          # 'legal' here is not the Legal department
    f = {"dept": [], "status": [], "level": None, "ocr": False, "expiring": False, "hold": False, "lang": None,
         "newest": False, "count": False}
    for alias, dept in sorted(DEPT_ALIAS.items(), key=lambda x: -len(x[0])):
        if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", ql) and dept not in f["dept"]:
            f["dept"].append(dept)
    for d in DEPARTMENTS:
        if d.lower() in ql and d not in f["dept"]:
            f["dept"].append(d)
    for w, sts in sorted(STATUS_WORDS.items(), key=lambda x: -len(x[0])):
        if re.search(rf"(?<![\w]){re.escape(w)}(?![\w])", ql):
            f["status"] += [s for s in sts if s not in f["status"]]
    for w, lv in LEVELS.items():
        if w in ql:
            f["level"] = lv
    f["ocr"] = bool(re.search(r"\b(scanned|scans?|ocr)\b|ممسوح", ql))
    f["expiring"] = bool(re.search(r"\bexpir|\bdue\b|renew|تنتهي|منتهي", ql))
    f["hold"] = hold_q or "حجز" in ql
    f["lang"] = "Arabic" if ("arabic" in ql or "بالعربية" in ql) else ("English" if "english" in ql else None)
    f["newest"] = bool(re.search(r"\b(latest|recent|newest|last)\b", ql))
    f["count"] = bool(re.search(r"\bhow many\b|\bcount\b|\bnumber of\b|كم عدد", ql))
    words = [w for w in re.findall(r"[\w؀-ۿ]+", ql) if w not in NOISE and w not in WORDMAP]
    dept_words = set(w for d in f["dept"] for w in re.findall(r"\w+", d.lower())) | set(a for a in DEPT_ALIAS if a in ql for a in a.split())
    words = [w for w in words if w not in dept_words]
    f["terms"] = [_stem(w) for w in words]
    return f


AR_EN = {"فاتورة": "invoice", "فواتير": "invoice", "عقد": "contract", "عقود": "contract", "سياسة": "policy", "سياسات": "policy", "خطاب": "letter",
         "خطابات": "letter", "رسالة": "letter", "تعميم": "circular", "شهادة": "certificate", "ترخيص": "licence", "رخصة": "licence",
         "تقرير": "report", "مناقصة": "tender", "شراء": "purchase", "دفع": "payment", "مريض": "patient", "تفتيش": "inspection", "سلامة": "safety",
         "حريق": "fire", "إجازة": "leave", "موظف": "employee", "اتفاقية": "agreement", "مورد": "vendor", "صيانة": "maintenance"}


def _stem(w):
    if w in AR_EN:
        return AR_EN[w]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("ses"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def describe(f):
    bits = []
    if f["terms"]:
        bits.append("about **" + " ".join(f["terms"]) + "**")
    if f["dept"]:
        bits.append("in **" + ", ".join(f["dept"]) + "**")
    if f["status"]:
        bits.append("status **" + " / ".join(f["status"]) + "**")
    if f["level"]:
        bits.append(f"**{f['level']}**")
    if f["ocr"]:
        bits.append("**scanned (OCR)**")
    if f["expiring"]:
        bits.append("**expiring ≤ 90 days**")
    if f["hold"]:
        bits.append("under **legal hold**")
    if f["lang"]:
        bits.append(f"in **{f['lang']}**")
    return ", ".join(bits) or "everything you can access"


def answer(q, allow):
    f = interpret(q)
    res = []
    if f["terms"]:
        info = se.search(" ".join(f["terms"]), "nl", allow=allow)
        res = info["results"]
        if not res:                                   # typo-tolerant smart-mode fallback
            res = se.search(" ".join(f["terms"]), "smart", allow=allow)["results"]
    else:
        res = se.search("", "smart", allow=allow)["results"]
    out = []
    for o in res:
        d = o["doc"]
        if f["dept"] and d["department"] not in f["dept"]:
            continue
        if f["status"] and d["status"] not in f["status"]:
            continue
        if f["level"] and d["security_level"] != f["level"]:
            continue
        if f["ocr"] and d["source"] != "Scan":
            continue
        if f["expiring"] and not (d["expiry_date"] and d["expiry_date"] <= _soon()):
            continue
        if f["hold"] and not d["legal_hold"]:
            continue
        if f["lang"] and d["language"] != f["lang"]:
            continue
        out.append(o)
    if f["newest"] or not f["terms"]:
        out.sort(key=lambda o: o["doc"]["created_at"] or "", reverse=True)
    return f, out


def _soon():
    conn = db.get_conn()
    v = conn.execute("SELECT date('now','+90 day')").fetchone()[0]
    conn.close()
    return v
