"""Legacy data migration: scan a SharePoint library / file-server share / scanned-paper batch, map it, dry-run, import, verify."""
import hashlib
import io
import json
import os
import shutil
import time
from datetime import datetime

import db
import folders as fo
import intake_ext as ix
import rfp_data

LEGACY = os.path.join(db.DB_DIR, "legacy_share")
SUPPORTED = (".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg")
TEMP = ("~$", ".tmp", "thumbs.db", ".ds_store")
DEPT_ALIAS = {"hr": "HR", "human resources": "HR", "finance": "Finance", "accounts": "Finance", "legal": "Legal", "nursing": "Nursing",
              "it": "IT", "procurement": "Procurement", "purchasing": "Procurement", "medical records": "Medical Records",
              "records": "Medical Records", "qri": "QRI", "quality": "QRI", "marketing": "Marketing", "security": "Security",
              "laboratory": "Laboratory", "lab": "Laboratory", "research": "Research", "executive": "Executive Offices",
              "facility": "Hospitality, Facility & Vendors", "talent": "Talent Management", "clinical": "Clinical Operations"}
TYPE_KEYS = [("polic", "Policy"), ("procedure", "Procedure"), ("sop", "SOP"), ("contract", "Vendor Agreement"), ("agreement", "Vendor Agreement"),
             ("invoice", "Invoice"), ("purchase", "Purchase Order"), ("po", "Purchase Order"), ("memo", "Memo"), ("circular", "Circular"),
             ("letter", "Letter"), ("scan", "Letter"), ("certificate", "Certificate"), ("audit", "Audit Document"), ("report", "Inspection Report")]


def _c():
    return db.get_conn()


def init():
    conn = _c()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS migration_batches (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, source_type TEXT, source_path TEXT,
        started_by TEXT, started_at TEXT, finished_at TEXT, total INTEGER, imported INTEGER, duplicates INTEGER, skipped INTEGER, failed INTEGER,
        verified INTEGER, seconds REAL);
    CREATE TABLE IF NOT EXISTS migration_items (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, rel_path TEXT, size INTEGER, sha TEXT,
        dept TEXT, doc_type TEXT, status TEXT, doc_code TEXT, detail TEXT, verified INTEGER DEFAULT 0);
    """)
    conn.commit()
    conn.close()


# --------------------------------------------------------------- sample set --
def create_sample(root=LEGACY):
    """Build a realistic messy legacy file share (duplicates, temp files, empty files, odd types, Arabic names)."""
    import fitz
    from docx import Document
    if os.path.isdir(root):
        shutil.rmtree(root)

    def put(rel, data, days_ago):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        t = time.time() - days_ago * 86400
        os.utime(p, (t, t))

    def pdf(title, body):
        d = fitz.open()
        pg = d.new_page()
        pg.insert_text((60, 80), title, fontsize=16)
        y = 120
        for ln in body.split("\n"):
            pg.insert_text((60, y), ln, fontsize=10.5)
            y += 15
        b = d.tobytes()
        d.close()
        return b

    def docx(title, body):
        d = Document()
        d.add_heading(title, 1)
        for ln in body.split("\n"):
            d.add_paragraph(ln)
        bio = io.BytesIO()
        d.save(bio)
        return bio.getvalue()

    leave = pdf("Annual Leave Policy", "Policy No: HR-POL-014\nEffective 2021. All employees accrue 30 calendar days of annual leave.\nRequests are approved by the line manager.")
    put("HR/Policies/Annual_Leave_Policy_2021.pdf", leave, 1400)
    put("HR/Policies/Archive/Annual_Leave_Policy_2021 (copy).pdf", leave, 1380)          # exact duplicate
    put("HR/Contracts/Employment_Contract_Template.docx", docx("Employment Contract", "This contract is made between the Employer and the Employee.\nProbation period is six months."), 900)
    put("HR/Contracts/~$Employment_Contract_Template.docx", b"lock", 900)                 # office temp file
    put("Finance/Invoices/INV_2023_0412.pdf", pdf("Invoice INV-2023-0412", "Supplier: MedEquip Trading\nAmount: QAR 48,500\nDue: 30 days"), 700)
    put("Finance/Invoices/INV_2023_0507.pdf", pdf("Invoice INV-2023-0507", "Supplier: CleanCo Services\nAmount: QAR 12,300\nDue: 30 days"), 650)
    put("Finance/Reports/Budget_Review_Q3.txt", b"Quarterly budget review.\nOperating expenses are 4% below plan.\nCapital projects on schedule.", 400)
    put("Finance/Reports/Thumbs.db", b"x", 400)                                           # system junk
    put("Legal/Contracts/Service_Agreement_MedEquip.pdf", pdf("Service Agreement", "Between the Hospital and MedEquip Trading.\nTerm: five years. Governing law: State of Qatar."), 1200)
    put("Legal/Letters/Notice_to_Supplier.docx", docx("Notice to Supplier", "We refer to the agreement dated 2022.\nPlease remit the corrected certificate within 14 days."), 300)
    put("IT/Procedures/Backup_Procedure.txt", b"Backup procedure.\nDaily incremental backups, weekly full backups. Restore tests quarterly.", 500)
    put("IT/Tools/installer_old.exe", b"MZ\x90\x00binary", 800)                           # unsupported
    put("Nursing/Policies/Hand_Hygiene_Policy.pdf", pdf("Hand Hygiene Policy", "All clinical staff must perform hand hygiene before and after patient contact.\nAudit compliance monthly."), 600)
    put("Nursing/Circulars/تعميم_النظافة.txt", "تعميم إلى جميع أقسام التمريض\nيرجى الالتزام بسياسة نظافة اليدين.".encode("utf-8"), 200)
    put("Procurement/Purchase Orders/PO_5521.txt", b"Purchase Order 5521\nVendor: MedEquip Trading\nItems: infusion pumps x 12", 350)
    put("Procurement/Purchase Orders/PO_empty.pdf", b"", 350)                              # empty file
    put("Records/Scans/old_letter_1.txt", b"Letter from Ministry of Public Health regarding annual inspection.\nPlease prepare documents.", 100)
    put("Misc/Random notes.txt", b"call back Ahmed about the thing", 60)                  # unmapped folder
    # scanned paper: reuse sample images
    adir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    for i, nm in enumerate(["sample_regulatory_letter.png", "sample_supplier_invoice.png"]):
        src = os.path.join(adir, nm)
        if os.path.exists(src):
            put(f"Records/Scans/paper_batch_{i + 1:03d}.png", open(src, "rb").read(), 20 + i)
    return root


# ------------------------------------------------------------------ scanning --
def guess_dept(top):
    return DEPT_ALIAS.get(top.strip().lower()) or next((d for d in rfp_data.DEPARTMENTS if d.lower() == top.strip().lower()), None)


def guess_type(second):
    s = (second or "").lower()
    return next((t for k, t in TYPE_KEYS if k in s), "Letter")


def scan(root):
    items, seen = [], {}
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            parts = rel.split("/")
            data = open(p, "rb").read()
            sha = hashlib.sha256(data).hexdigest()
            it = {"rel": rel, "name": fn, "size": len(data), "sha": sha, "top": parts[0] if len(parts) > 1 else "(root)",
                  "second": parts[1] if len(parts) > 2 else "", "mtime": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S"),
                  "issue": ""}
            low = fn.lower()
            if any(low.startswith(t) or low.endswith(t) or low == t for t in TEMP):
                it["plan"], it["issue"] = "Skip", "Temporary / system file"
            elif len(data) == 0:
                it["plan"], it["issue"] = "Skip", "Empty file"
            elif not low.endswith(SUPPORTED):
                it["plan"], it["issue"] = "Skip", f"Unsupported type {os.path.splitext(fn)[1] or '(none)'}"
            elif len(data) > ix.MAX_BYTES:
                it["plan"], it["issue"] = "Skip", "Larger than 10 MB"
            elif sha in seen:
                it["plan"], it["issue"] = "Skip", f"Duplicate of {seen[sha]}"
            elif ix.already_imported(sha):
                it["plan"], it["issue"] = "Skip", "Already in the EDMS"
            else:
                it["plan"] = "Import"
                seen[sha] = rel
            it["dept"] = guess_dept(it["top"])
            it["type"] = guess_type(it["second"] or it["name"])
            if it["plan"] == "Import" and not it["dept"]:
                it["issue"] = "Folder not mapped to a department — will go to Medical Records for review"
            items.append(it)
    return items


# ----------------------------------------------------------------- the run ---
def run(items, root, user, name, source_type, preserve_dates=True, mirror=True, progress=None):
    t0 = time.time()
    conn = _c()
    cur = conn.execute("INSERT INTO migration_batches (name, source_type, source_path, started_by, started_at) VALUES (?,?,?,?,?)",
                       (name, source_type, root, user, db.now()))
    bid = cur.lastrowid
    conn.commit()
    conn.close()
    imp = dup = skp = fail = ver = 0
    todo = [i for i in items]
    for n, it in enumerate(todo):
        status, code, detail, verified = "Skipped", "", it["issue"], 0
        if it["plan"] == "Import":
            try:
                data = open(os.path.join(root, it["rel"]), "rb").read()
                dept = it["dept"] or "Medical Records"
                r = ix.register_file(it["name"], data, user, f"Migration: {name}", "Incoming", auto_route=False, dept=dept, doc_type=it["type"])
                if r["status"] == "Registered":
                    code = r["code"]
                    conn = _c()
                    d = conn.execute("SELECT id FROM documents WHERE doc_code=?", (code,)).fetchone()
                    if d:
                        fid = fo.ensure_path(dept, "Migrated", *[p for p in it["rel"].split("/")[1:-1]]) if mirror else fo.target_folder(dept, it["type"])
                        sets, par = ["doc_type=?", "folder_id=?"], [it["type"], fid]
                        if preserve_dates:
                            sets += ["created_at=?", "modified_at=?"]
                            par += [it["mtime"], it["mtime"]]
                        conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE id=?", par + [d["id"]])
                        stored = conn.execute("SELECT sha FROM correspondence_files WHERE document_id=? ORDER BY id DESC LIMIT 1", (d["id"],)).fetchone()
                        verified = 1 if stored and stored["sha"] == it["sha"] else 0
                        conn.commit()
                        db.log_audit(d["id"], user, "Migrated from Legacy Source",
                                     f"{it['rel']} · batch '{name}' · sha256 {it['sha'][:12]}… · {'checksum verified' if verified else 'CHECKSUM MISMATCH'}")
                    conn.close()
                    status, detail = "Imported", f"→ {dept} / {it['type']}" + (" (needs review)" if not it["dept"] else "")
                    imp += 1
                    ver += verified
                else:
                    status, detail = "Skipped", r["status"]
                    dup += 1
            except Exception as e:  # noqa: BLE001
                status, detail = "Failed", str(e)[:200]
                fail += 1
        else:
            if it["issue"].startswith(("Duplicate", "Already")):
                status = "Duplicate"
                dup += 1
            else:
                skp += 1
        conn = _c()
        conn.execute("INSERT INTO migration_items (batch_id, rel_path, size, sha, dept, doc_type, status, doc_code, detail, verified) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (bid, it["rel"], it["size"], it["sha"], it["dept"], it["type"], status, code, detail, verified))
        conn.commit()
        conn.close()
        if progress:
            progress((n + 1) / len(todo), it["rel"])
    conn = _c()
    conn.execute("UPDATE migration_batches SET finished_at=?, total=?, imported=?, duplicates=?, skipped=?, failed=?, verified=?, seconds=? WHERE id=?",
                 (db.now(), len(items), imp, dup, skp, fail, ver, round(time.time() - t0, 1), bid))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Migration Batch Completed", f"'{name}': {imp} imported, {dup} duplicates, {skp} skipped, {fail} failed, {ver} checksum-verified")
    return bid


def batches():
    conn = _c()
    rows = [dict(r) for r in conn.execute("SELECT * FROM migration_batches ORDER BY id DESC").fetchall()]
    conn.close()
    return rows


def batch_items(bid):
    conn = _c()
    rows = [dict(r) for r in conn.execute("SELECT * FROM migration_items WHERE batch_id=? ORDER BY id", (bid,)).fetchall()]
    conn.close()
    return rows
