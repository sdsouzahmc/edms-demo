"""Loads the sample document pack through the real intake pipeline, then moves the documents through workflow,
signatures, inter-department routing, secure links, retention and versioning so every dashboard has realistic activity."""
import io
import os
import re
import shutil
import zipfile
from datetime import date, timedelta

import db
import db_ext
import distribution as dist
import exchange as ex
import intake_ext as ix
import rfp_data
import signing as sg

BASE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(BASE, "assets", "sample_pack")


def pack_files():
    return sorted(f for f in os.listdir(PACK) if f.lower().endswith(".pdf")) if os.path.isdir(PACK) else []


def pack_zip():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for f in pack_files():
            z.write(os.path.join(PACK, f), f)
    return bio.getvalue()


def _actor(dept, stage_assignee=None):
    d = stage_assignee or dept
    for u, p in rfp_data.ROLES.items():
        if p["dept"] == d and p["can_approve"] and p["level"] != "admin":
            return u
    return "Yusuf Al-Marri"


def advance(doc_id, steps, log, label=""):
    """Sign and approve up to `steps` workflow steps as the responsible users."""
    done = 0
    while done < steps:
        rows = [r for r in db.get_workflow(doc_id) if r["status"] == "active"]
        if not rows:
            break
        r = rows[0]
        d = db.get_document(doc_id)
        who = _actor(d["department"], r["assignee"] if r["assignee"] in rfp_data.DEPARTMENTS else None)
        ok, res = sg.sign(doc_id, who, r["stage"], sg.DEMO_PIN, "Approved")
        if not ok:
            break
        db.advance_workflow(doc_id, "approve", who, f"Approved via e-signature {res['short']}", workflow_id=r["id"])
        log.append((d["doc_code"], f"{r['stage']} approved & signed by {who}"))
        done += 1
    return done


def run(user="Yusuf Al-Marri", move=True, progress=None):
    """Returns (intake_results, journey_log)."""
    inbox = ix.folder()
    os.makedirs(inbox, exist_ok=True)
    for f in pack_files():
        if not os.path.exists(os.path.join(inbox, f)) and not os.path.exists(os.path.join(inbox, "processed", f)):
            shutil.copy(os.path.join(PACK, f), os.path.join(inbox, f))
    results = ix.import_folder(user, None, True)
    for r in results:
        r["file"] = r.get("file")
    log = []
    if not move:
        return results, log
    codes = {}
    for r in results:
        m = re.match(r"(\d\d)_", r["file"] or "")
        if m and r.get("code") and r["status"] == "Registered":
            codes[m.group(1)] = r["code"]
    if not codes:
        return results, log
    conn = db.get_conn()
    if conn.execute("SELECT value FROM settings WHERE key='journey_done'").fetchone():
        conn.close()
        return results, log
    conn.close()

    def did(n):
        c = codes.get(n)
        d = db.get_document_by_code(c) if c else None
        return d["id"] if d else None

    def step(n, k, label):
        i = did(n)
        if i:
            advance(i, k, log, label)

    # 01 licence notice (QRI): through the whole chain -> Released, QR issued
    step("01", 9, "licence")
    # 02 invoice: two stages, waits at Finance sign-off
    step("02", 2, "invoice")
    # 03 purchase order: released
    step("03", 9, "po")
    # 04 tender: rejected at the first review
    i = did("04")
    if i:
        advance(i, 1, log)
        rows = [r for r in db.get_workflow(i) if r["status"] == "active"]
        if rows:
            who = _actor(db.get_document(i)["department"], None)
            db.advance_workflow(i, "reject", who, "Closing date too short — re-issue with 3 weeks", workflow_id=rows[0]["id"])
            log.append((codes["04"], f"Rejected by {who}: closing date too short"))
    # 05 service agreement: inter-department sequential review + external vendor review link
    i = did("05")
    if i:
        advance(i, 1, log)
        batch, einfo = ex.send_transmittal(i, "Noor Al-Kuwari", ["Finance", "Executive Offices"], "Approve", date.today() + timedelta(days=7),
                                           "Please confirm commercial terms, then executive sign-off.", "Sequential",
                                           {"name": "MedEquip — Contracts Manager", "org": "MedEquip Trading W.L.L.", "email": "contracts@medequip.example", "days": 7, "use_code": True})
        t = [x for x in ex.batch_summary(batch) if x["to_dept"] == "Finance"][0]
        log.append((codes["05"], f"Sequential transmittal {batch}: Finance → Executive Offices → external vendor review"))
        ex.respond(t["id"], "Fatima Al-Sulaiti", "Approve", "Commercial terms acceptable.")
        log.append((codes["05"], "Finance approved the transmittal; now with Executive Offices"))
    # 06 referral: first stage only
    step("06", 1, "referral")
    # 07 discharge summary: released, then archived with a retention label
    i = did("07")
    if i:
        advance(i, 9, log)
        db.archive_document(i, "Sara Al-Ansari")
        log.append((codes["07"], "Released, then archived to the Medical Records archive"))
    # 08 HR policy: released, then a new version is checked out and in (earlier signatures show 'document changed')
    i = did("08")
    if i:
        advance(i, 9, log)
        db.checkout_document(i, "Omar Al-Kaabi")
        d = db.get_document(i)
        db.checkin_new_version(i, "Omar Al-Kaabi", (d["body_text"] or "") + "\n\nRev 4: carry-forward limit reduced to 7 days.", "Annual review — carry-forward limit", "minor")
        log.append((codes["08"], "Checked out, edited and checked in as a new version (v1.1)"))
    step("09", 1, "incident")
    # 12 research protocol: legal hold
    i = did("12")
    if i:
        db.toggle_legal_hold(i, "Noor Al-Kuwari", True)
        log.append((codes["12"], "Legal hold applied by Legal Counsel"))
    # 15 audit report: released
    step("15", 9, "audit")
    # external download link for the released licence file
    i = did("01")
    if i:
        tok, code, lid = ex.create_link("download", "Layla Al-Marri", "Licensing Officer", "licensing@moph.example", "Ministry of Public Health",
                                        "Updated licence documentation", i, 7, 3, True, True)
        ex.count_download(ex.get(lid))
        log.append((codes["01"], "Secure link shared with the Ministry (code-protected, watermarked); 1 download so far"))
    # upload request fulfilled by a supplier
    tok, code, lid = ex.create_link("upload", "Hassan Al-Naimi", "Linen Supplier Rep", "sales@linen.example", "Gulf Linen Co.", "Upload request", None, 7, None, True, False,
                                    "Procurement", "Please upload your trade licence and insurance certificate.", 5)
    import fitz
    d_ = fitz.open()
    pg = d_.new_page()
    pg.insert_text((60, 90), "Trade licence copy - Gulf Linen Co.", fontsize=14)
    pg.insert_text((60, 120), "Supplier registration for the laundry tender. Licence valid to 2027.", fontsize=10)
    r = ex.receive_upload(ex.get(lid), "Gulf_Linen_Trade_Licence.pdf", d_.tobytes(), "Gulf Linen Co. rep", "Gulf Linen Co.", "As requested")
    log.append((r.get("code") or "—", "Received from a supplier through a secure upload link"))
    conn = db.get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('journey_done', ?)", (db.now(),))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Demo Journey Loaded", f"{len(results)} files through intake; {len(log)} movements")
    return results, log


def auto_load(user="Yusuf Al-Marri"):
    """Load the sample pack + movement once, automatically, so a fresh deployment is never empty."""
    conn = db.get_conn()
    done = conn.execute("SELECT value FROM settings WHERE key='journey_done'").fetchone()
    conn.close()
    if not done:
        try:
            run(user)
        except Exception:
            pass
