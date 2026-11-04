"""Intake helpers: text extraction (OCR / PDF / Word), registering files from the user's computer or a shared scan folder."""
import hashlib
import io
import os
import shutil
import db
import db_ext
import distribution as dist
from ocr_utils import run_ocr, extract_metadata, auto_name

EXT_OK = (".png", ".jpg", ".jpeg", ".pdf", ".docx", ".txt")
MAX_BYTES = 10 * 1024 * 1024
BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FOLDER = os.path.join(db.DB_DIR, "scan_inbox")


def folder():
    conn = db.get_conn()
    r = conn.execute("SELECT value FROM settings WHERE key='intake_folder'").fetchone()
    conn.close()
    return r["value"] if r else DEFAULT_FOLDER


def set_folder(path, user):
    conn = db.get_conn()
    conn.execute("INSERT INTO settings (key, value) VALUES ('intake_folder', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (path,))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Intake Folder Changed", path, field="intake_folder", new=path)


def list_folder():
    p = folder()
    if not os.path.isdir(p):
        return []
    out = []
    for f in sorted(os.listdir(p)):
        fp = os.path.join(p, f)
        if os.path.isfile(fp) and f.lower().endswith(EXT_OK):
            out.append({"name": f, "path": fp, "size": os.path.getsize(fp), "mtime": os.path.getmtime(fp)})
    return out


def extract_text(name, data):
    """Return (text, method). Images → Tesseract OCR (English+Arabic); PDF → text layer or OCR; DOCX/TXT → direct."""
    n = name.lower()
    try:
        if n.endswith((".png", ".jpg", ".jpeg")):
            from PIL import Image
            return run_ocr(Image.open(io.BytesIO(data)).convert("RGB"), lang="eng+ara").strip(), "OCR (EN/AR)"
        if n.endswith(".pdf"):
            import fitz
            from PIL import Image
            doc = fitz.open(stream=data, filetype="pdf")
            txt, ocr = [], False
            for pg in doc:
                t = pg.get_text().strip()
                if not t:
                    pix = pg.get_pixmap(dpi=170)
                    t = run_ocr(Image.frombytes("RGB", (pix.width, pix.height), pix.samples), lang="eng+ara").strip()
                    ocr = True
                txt.append(t)
            return "\n\n".join(txt), ("OCR (EN/AR)" if ocr else "PDF text layer")
        if n.endswith(".docx"):
            from docx import Document
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs), "Word text"
        if n.endswith(".txt"):
            return data.decode("utf-8", "ignore"), "Plain text"
    except Exception as e:
        return "", f"unreadable ({e})"
    return "", "unsupported"


def already_imported(sha):
    conn = db.get_conn()
    r = conn.execute("SELECT document_id FROM correspondence_files WHERE sha=?", (sha,)).fetchone()
    conn.close()
    return r["document_id"] if r else None


def store_file(doc_id, name, data, origin, user):
    mime = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "png": "image/png",
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "txt": "text/plain"}.get(name.rsplit(".", 1)[-1].lower(), "application/octet-stream")
    conn = db.get_conn()
    conn.execute("INSERT INTO correspondence_files (document_id, filename, mime, data, sha, origin, uploaded_by, ts) VALUES (?,?,?,?,?,?,?,?)",
                 (doc_id, name, mime, data, hashlib.sha256(data).hexdigest(), origin, user, db.now()))
    conn.commit()
    conn.close()


def files_by_doc():
    conn = db.get_conn()
    rows = conn.execute("SELECT id, document_id, filename, origin FROM correspondence_files").fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["document_id"], []).append(r)
    return out


def get_file(fid):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM correspondence_files WHERE id=?", (fid,)).fetchone()
    conn.close()
    return r


def register_file(name, data, user, origin, direction="Incoming", auto_route=True, dept=None):
    """Extract text, name, classify, route and register one file as incoming correspondence. Returns a result dict."""
    sha = hashlib.sha256(data).hexdigest()
    dup = already_imported(sha)
    if dup:
        d = db.get_document(dup)
        return {"file": name, "status": "Skipped — already registered", "code": d["doc_code"] if d else "", "routed": "", "method": ""}
    if len(data) > MAX_BYTES:
        return {"file": name, "status": "Skipped — larger than 10 MB", "code": "", "routed": "", "method": ""}
    text, method = extract_text(name, data)
    meta = extract_metadata(text) if text else {}
    title = auto_name(meta, os.path.splitext(name)[0]) or os.path.splitext(name)[0]
    dec = dist.analyse(text, title, meta.get("Sender", "")) if text else {"primary": None, "classification": None, "doc_type": None, "hits": [], "copies": []}
    department = (dec["primary"] if auto_route and dec["primary"] else None) or dept or "Medical Records"
    arabic = any("؀" <= ch <= "ۿ" for ch in text)
    doc_id, code = db.create_document(title, department, dec["classification"] or "External", "Internal", dec["doc_type"] or "Letter",
                                      "Scan" if name.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")) else "Upload",
                                      "Arabic" if arabic else "English", text or f"[{name}] — no text could be extracted", user, sender=meta.get("Sender", ""))
    db.log_correspondence(doc_id, direction, f"{origin}", meta.get("Sender", ""), "", meta.get("Subject", title), user)
    db.log_audit(doc_id, user, "Intake File Registered", f"{name} via {origin} · text by {method}")
    store_file(doc_id, name, data, origin, user)
    if auto_route and text:
        dist.distribute(doc_id, user, apply_dept=True, notify=True, text=text)
    return {"file": name, "status": "Registered", "code": code, "routed": (dec["primary"] if auto_route and dec["primary"] else department) or "Triage",
            "method": method, "words": len(text.split())}


def import_folder(user, names=None, auto_route=True):
    """Register every (selected) file in the shared scan folder, then move it to a 'processed' sub-folder."""
    p = folder()
    done = os.path.join(p, "processed")
    os.makedirs(done, exist_ok=True)
    results = []
    for f in list_folder():
        if names is not None and f["name"] not in names:
            continue
        with open(f["path"], "rb") as fh:
            data = fh.read()
        r = register_file(f["name"], data, user, "Shared scan folder", "Incoming", auto_route)
        results.append(r)
        if r["status"] in ("Registered",) or r["status"].startswith("Skipped — already"):
            try:
                shutil.move(f["path"], os.path.join(done, f["name"]))
            except OSError:
                pass
    return results


def drop_samples():
    """Demo helper: place the sample scanned letters into the watch folder (simulates the scanner saving to the share)."""
    p = folder()
    os.makedirs(p, exist_ok=True)
    src = os.path.join(BASE, "assets")
    n = 0
    if os.path.isdir(src):
        for f in sorted(os.listdir(src)):
            if f.endswith(".png") and not os.path.exists(os.path.join(p, f)) and not os.path.exists(os.path.join(p, "processed", f)):
                shutil.copy(os.path.join(src, f), os.path.join(p, f))
                n += 1
                if n >= 4:
                    break
    return n
