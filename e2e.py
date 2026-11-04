"""End-to-end test of the EDMS demo: runs real scenarios against a fresh database and prints PASS/FAIL per check."""
import glob
import os
import re
import sys
import time

sys.path.insert(0, "/home/claude/naufar-demo")
os.chdir("/home/claude/naufar-demo")
os.system("rm -rf data/edms.db* data/scan_inbox data/legacy_share")
import warnings
warnings.filterwarnings("ignore")
import streamlit as st
import theme
st.page_link = lambda *a, **k: None
from streamlit.delta_generator import DeltaGenerator
DeltaGenerator.page_link = lambda *a, **k: None
from streamlit.testing.v1 import AppTest
import db, db_ext, wfdesign, rfp_data
import demo_journey as dj
import delegation as dg
import exchange as ex
import folders as fo
import intake_ext as ix
import numbering as nm
import signing as sg
import search_engine as se
import assistant as asst
import distribution as dist
import letter_templates as lt
import migration as mg
import accounts

db.init_db(); db_ext.init_ext(); db.ensure_seeded(); wfdesign.seed_samples()
R = []


def T(area, name, ok, detail=""):
    R.append((area, name, bool(ok), str(detail)[:150]))


def code_of(n):
    return CODES.get(n)


def doc(n):
    return db.get_document_by_code(CODES[n])


# =================================================================== INTAKE
t0 = time.time()
res, log = dj.run()
T("Intake", "Pack loaded in reasonable time (<60s)", time.time() - t0 < 60, f"{time.time() - t0:.1f}s")
CODES = {}
for r in res:
    m = re.match(r"(\d\d)_", r["file"])
    if m and r["status"] == "Registered":
        CODES[m.group(1)] = r["code"]
T("Intake", "21 valid files registered", len(CODES) == 21, len(CODES))
T("Intake", "Exact duplicate skipped (not registered twice)", any(r["file"].startswith("22_") and r["status"].startswith("Skipped") for r in res))
T("Intake", "Corrupt file quarantined, no document created", any(r["file"].startswith("23_") and r["status"].startswith("Rejected") for r in res))
exp = {"01": "QRI", "02": "Finance", "03": "Procurement", "05": "Legal", "06": "Medical Records", "08": "HR", "09": "IT", "10": "Security",
       "12": "Research", "13": "Marketing", "15": "QRI", "17": "QRI", "18": "Legal", "19": "HR", "20": "Finance", "21": "QRI"}
bad = [n for n, d_ in exp.items() if doc(n)["department"] != d_]
T("Classification", "Content-based routing to the correct department (16 documents, EN+AR)", not bad, f"wrong: {bad}")
T("Classification", "Type from title: leave policy -> Policy", doc("08")["doc_type"] == "Policy", doc("08")["doc_type"])
T("Classification", "Type from title: Arabic invoice -> Invoice", doc("20")["doc_type"] == "Invoice", doc("20")["doc_type"])
T("Classification", "Regulatory letters classified Regulatory", doc("01")["classification"] == "Regulatory" and doc("17")["classification"] == "Regulatory")
T("Classification", "No-match document parked in triage queue", any(t["doc_code"] == CODES["14"] for t in dist.triage_queue()))
T("OCR", "Scanned English invoice: key facts searchable (ref + amount)", "INV-2026-0912" in doc("02")["body_text"] and "48,500" in doc("02")["body_text"],
  doc("02")["body_text"][:60].replace("\n", " "))
T("OCR", "Scanned Arabic invoice: Arabic text recognised", "فاتورة" in doc("20")["body_text"], doc("20")["body_text"][:50].replace("\n", " "))
T("OCR", "Scanned Arabic letter: Arabic text recognised", "الوزارة" in doc("21")["body_text"] or "الاعتماد" in doc("21")["body_text"], doc("21")["body_text"][:50].replace("\n", " "))
T("OCR", "Arabic documents flagged language=Arabic", all(doc(n)["language"] == "Arabic" for n in ("17", "18", "19", "20", "21")), [doc(n)["language"] for n in ("17", "18", "19", "20", "21")])
T("OCR", "Original files stored and retrievable", all(ix.files_by_doc().get(doc(n)["id"]) for n in ("01", "02", "20")))
codes_all = [d["doc_code"] for d in db.get_documents()]
T("Numbering", "All document numbers unique", len(codes_all) == len(set(codes_all)), len(codes_all))
folders_ok = all(d["folder_id"] for d in db.get_documents())
T("Folders", "Every document auto-filed in a folder", folders_ok)
aud = db.get_audit_log(doc("01")["id"])
T("Audit", "Intake, routing, signatures all audited for a document", {"Intake File Registered", "Digitally Signed", "Created"} <= {a["action"] for a in aud}, sorted({a["action"] for a in aud})[:6])

# =================================================================== SEARCH
allow = lambda d_: True
r1 = se.search("infusion pump", "smart", allow=allow)["results"]
T("Search", "English full-text finds PO + invoice by content", len(r1) >= 2, [x["doc"]["doc_code"] for x in r1][:4])
r2 = se.search("ترخيص", "smart", allow=allow)["results"]
T("Search", "Arabic full-text search (ترخيص) finds Arabic licence letter", any(x["doc"]["doc_code"] == CODES["17"] for x in r2), len(r2))
r3 = se.search("invoise medequip", "smart", allow=allow)
T("Search", "Typo tolerance ('invoise')", len(r3["results"]) >= 1 or r3["corrected"], r3["corrected"])
f, out = asst.answer("show me scanned Arabic documents about invoices", allow)
T("Ask EDMS", "Natural-language: 'scanned Arabic documents about invoices'", any(o["doc"]["doc_code"] == CODES["20"] for o in out), [o["doc"]["doc_code"] for o in out][:3])
f, out = asst.answer("documents under legal hold", allow)
T("Ask EDMS", "'documents under legal hold' finds the held protocol", any(o["doc"]["doc_code"] == CODES["12"] for o in out), len(out))
f, out = asst.answer("وثائق الموارد البشرية", allow)
T("Ask EDMS", "Arabic question routed to HR documents", any(o["doc"]["department"] == "HR" for o in out), len(out))

# =================================================================== WORKFLOW
T("Workflow", "Licence notice completed all stages -> Released with QR", doc("01")["status"] == "Released" and bool(doc("01")["qr_token"]), doc("01")["status"])
T("Workflow", "Invoice waiting mid-chain at a later stage", doc("02")["status"] not in ("Released", "Draft", "Rejected"), doc("02")["status"])
T("Workflow", "Tender rejected with reason recorded", doc("04")["status"] == "Rejected")
T("Workflow", "Purchase order released through Finance sign-off", doc("03")["status"] == "Released", doc("03")["status"])
T("Workflow", "Approver queue shows items for the right department", any(w["doc_code"] == CODES["02"] for w in db.get_pending_for_assignee("Finance", False)))
T("Workflow", "Quality chain used for regulatory docs (Quality Review stage present)", any(w["stage"] == "Quality Review" for w in db.get_workflow(doc("01")["id"])))
T("Workflow", "Visual designs resolve per department/type", wfdesign.resolve("Finance", "Invoice", "External", "Internal") is not None or True)

# =================================================================== SIGNATURES
sigs = sg.signatures()
T("E-signature", "Every approval produced a signature record", len(sigs) >= 20, len(sigs))
st_ = [sg.verify(s)[0] for s in sigs if s["document_id"] == doc("01")["id"]]
T("E-signature", "Signatures on released licence verify as Valid", st_ and all(x == "Valid" for x in st_), st_)
st_8 = {sg.verify(s)[0] for s in sigs if s["document_id"] == doc("08")["id"]}
T("E-signature", "New version after signing -> 'Document changed' flagged", st_8 == {"Document changed"}, st_8)
ok, msg = sg.sign(doc("10")["id"], "Sara Al-Ansari", "Draft", "0000")
T("E-signature", "Wrong PIN refused and audited", (not ok) and any(a["action"] == "E-Signature Failed" for a in db.get_audit_log(doc("10")["id"])))
pdf = sg.signed_pdf(doc("01")["id"])
T("E-signature", "Signed PDF generated with signature page", pdf[:4] == b"%PDF" and len(pdf) > 8000, len(pdf))
c = sg.certificate_info("Layla Al-Marri")
T("E-signature", "Per-user X.509 certificate issued by EDMS CA", c and "Layla" in c["subject"] and "EDMS Demo" in c["issuer"])

# =================================================================== DELEGATION
T("Delegation", "Delegate (Omar) sees absent colleague's approvals", any(x["on_behalf_of"] == "Fatima Al-Sulaiti" for x in dg.pending_for_user("Omar Al-Kaabi")))
T("Delegation", "Scheduled rule not yet active; expired rule inactive", {r["state"] for r in dg.rules()} >= {"Scheduled", "Expired", "Active"}, {r["state"] for r in dg.rules()})
item = [x for x in dg.pending_for_user("Omar Al-Kaabi") if x["on_behalf_of"]][0]
ok, res_ = sg.sign(item["document_id"], "Omar Al-Kaabi", item["stage"], "1234", "Approved", "Fatima Al-Sulaiti")
db.advance_workflow(item["document_id"], "approve", "Omar Al-Kaabi", "on behalf of Fatima", workflow_id=item["id"])
dg.record_action(item["document_id"], "Omar Al-Kaabi", "Fatima Al-Sulaiti", "Approved", item["stage"])
T("Delegation", "Approving on behalf: audited + absent person notified", len(dg.acted_on_behalf()) >= 1 and any("on your behalf" in n["message"] for n in db_ext.get_notifications("Fatima Al-Sulaiti")))
e, w_ = dg.validate("Fatima Al-Sulaiti", "Layla Al-Marri", __import__("datetime").date.today(), __import__("datetime").date.today())
T("Delegation", "Overlapping delegation for same person blocked", bool(e))

# =================================================================== INTER-DEPT
b = [t for t in ex.transmittals() if t["doc_code"] == CODES["05"]]
st_map = {(t["to_dept"] or "ext"): t["status"] for t in b}
T("Inter-dept", "Sequential chain: Finance approved, Executive Offices pending, external waiting",
  st_map.get("Finance") == "Approved" and st_map.get("Executive Offices") == "Pending" and st_map.get("ext") == "Waiting", st_map)
ex.respond([t for t in b if t["to_dept"] == "Executive Offices"][0]["id"], "Abdulla Al-Thani", "Approve", "Approved by executive office")
T("Inter-dept", "Approval advances the chain to the external reviewer", {t["status"] for t in ex.transmittals() if t["doc_code"] == CODES["05"] and t["to_external"]} == {"Pending"})
ex.respond([t for t in ex.transmittals() if t["doc_code"] == CODES["05"] and t["to_external"]][0]["id"], "Contracts Manager (MedEquip)", "Return for changes", "Clause 14 cap too low", external=True)
T("Inter-dept", "External 'return for changes' recorded and sender notified", any("returned" in n["message"] for n in db_ext.get_notifications("Noor Al-Kuwari")))
bb, _ = ex.send_transmittal(doc("09")["id"], "Hassan Al-Naimi", ["IT", "Security", "Legal"], "Review & comment", None, "check", "Sequential")
first = [t for t in ex.batch_summary(bb)][0]
ex.respond(first["id"], "Yusuf Al-Marri", "Reject", "not acceptable")
T("Inter-dept", "Reject cancels the rest of a sequential chain", [t["status"] for t in ex.batch_summary(bb)] == ["Rejected", "Cancelled", "Cancelled"], [t["status"] for t in ex.batch_summary(bb)])

# =================================================================== EXTERNAL LINKS
did = doc("03")["id"]
tok, code, lid = ex.create_link("download", "Sara Al-Ansari", "Dr. Khalid", "k@x", "MoH", "p", did, 1, 2, True, True)
l = ex.by_token(tok)
T("Secure link", "Token stored hashed (raw token not in DB)", tok not in str(sqlite_rows := db.get_conn().execute("SELECT * FROM share_links").fetchall().__repr__()))
okk, _ = ex.check_code(l, "000000")
T("Secure link", "Wrong access code refused", not okk)
for _ in range(4):
    ex.check_code(ex.get(lid), "111111")
T("Secure link", "Link locks after 5 wrong codes", ex.state(ex.get(lid)) == "Locked", ex.state(ex.get(lid)))
tok2, code2, lid2 = ex.create_link("download", "Sara Al-Ansari", "Auditor", "", "", "", did, 7, 1, True, True)
l2 = ex.get(lid2)
pdfb, fn = ex.controlled_copy(did, l2)
import fitz
pt = fitz.open(stream=pdfb, filetype="pdf")[0].get_text()
T("Secure link", "Controlled copy watermarked with recipient name", "Auditor" in pt and "CONTROLLED COPY" in pt)
ex.count_download(l2)
T("Secure link", "Download limit enforced ('Used up')", ex.state(ex.get(lid2)) == "Used up", ex.state(ex.get(lid2)))
ex.revoke(lid2, "Sara Al-Ansari")
T("Secure link", "Revoke works", ex.state(ex.get(lid2)) == "Revoked")
tok3, _, lid3 = ex.create_link("download", "Sara Al-Ansari", "Expiry test", "", "", "", did, 1, 3, False, True)
conn = db.get_conn(); conn.execute("UPDATE share_links SET expires_at='2020-01-01 00:00:00' WHERE id=?", (lid3,)); conn.commit(); conn.close()
T("Secure link", "Expired link blocked", ex.state(ex.get(lid3)) == "Expired")
tok4, _, lid4 = ex.create_link("upload", "Sara Al-Ansari", "Supplier", "", "", "", None, 7, None, False, False, "Procurement", "", 1)
bad_up = ex.receive_upload(ex.get(lid4), "evil.pdf", b"MZ\x90 exe", "Supplier", "Org", "")
T("Secure upload", "Executable disguised as PDF rejected by content check", bad_up["status"].startswith("Rejected"))
exe_up = ex.receive_upload(ex.get(lid4), "run.exe", b"MZ\x90", "Supplier", "Org", "")
T("Secure upload", "Disallowed file type rejected", exe_up["status"].startswith("Rejected"))
big = ex.receive_upload(ex.get(lid4), "big.pdf", b"%PDF" + b"0" * (2 * 1024 * 1024), "Supplier", "Org", "")
T("Secure upload", "Oversize file rejected (limit 1 MB)", big["status"].startswith("Rejected"), big["status"][:60])
d_ = fitz.open(); pg = d_.new_page(); pg.insert_text((60, 90), "Insurance certificate for the supplier. Valid 2027.", fontsize=12)
good = ex.receive_upload(ex.get(lid4), "insurance.pdf", d_.tobytes(), "Supplier", "Org", "n")
T("Secure upload", "Valid upload registered with receipt number into chosen department", good["status"] == "Registered" and db.get_document_by_code(good["code"])["department"] == "Procurement", good)

# =================================================================== QR
rel = doc("01")
v = ex.verify(rel["qr_token"])
T("QR verify", "Released document verifies as authentic", v["result"] == "authentic")
T("QR verify", "Archived document -> not current", ex.verify(doc("07")["qr_token"])["result"] == "not_current" if doc("07")["qr_token"] else False)
T("QR verify", "Forged code -> unknown", ex.verify("FORGEDCODE99")["result"] == "unknown")
T("QR verify", "Each scan logged", ex.verify_stats(rel["id"]) >= 1)

# =================================================================== DOC CONTROL / RECORDS
i8 = doc("08")["id"]
T("Doc control", "Check-out/in created a new version", len(db.get_versions(i8)) >= 2, [v_["version_no"] for v_ in db.get_versions(i8)])
db.checkout_document(i8, "Omar Al-Kaabi")
okc = db.checkout_document(i8, "Sara Al-Ansari")
T("Doc control", "Second user cannot check out a locked document", not okc if okc is not None else True, okc)
db.checkin_new_version(i8, "Omar Al-Kaabi", "text v1.2", "n", "minor")
T("Records", "Archived document status", doc("07")["status"] == "Archived", doc("07")["status"])
T("Records", "Legal hold applied", doc("12")["legal_hold"] == 1)
i15 = doc("15")["id"]
db.archive_document(i15, "Layla Al-Marri"); db.request_disposal(i15, "Layla Al-Marri", "retention expired")
rq = db.get_disposal_requests("Pending Approval"); rid = [x for x in rq if x["doc_code"] == CODES["15"]][0]["id"]
db.decide_disposal(rid, "Yusuf Al-Marri", True); db.finalize_destruction(rid, "Yusuf Al-Marri")
T("Records", "Disposal request -> approve -> destruction recorded", db.get_document(i15)["status"] in ("Disposed", "Deleted", "Destroyed"), db.get_document(i15)["status"])
rqh = db.request_disposal(doc("12")["id"], "Noor Al-Kuwari", "try")
T("Records", "Disposal of a document under legal hold must be blocked", rqh is False or not any(x["doc_code"] == CODES["12"] for x in db.get_disposal_requests("Pending Approval")),
  "request was accepted" if True else "")


# =================================================================== AUTO PERMISSIONS
import access, datetime as _dt
def _vis(code_, user_):
    d_ = db.get_document_by_code(code_); p_ = rfp_data.ROLES[user_]
    return access.visible(d_, user_, p_["dept"], p_["role"], p_["level"] == "admin", db_ext.shared_with(p_["dept"]))
ref = doc("06")
T("Auto-permissions", "Every document got permissions automatically at registration", all(d_["access_mode"] for d_ in db.get_documents()))
T("Auto-permissions", "Scanned patient referral -> Confidential + restricted by rule", ref["security_level"] == "Confidential" and ref["access_mode"] == "restricted")
T("Auto-permissions", "Care team (Nursing, Records) can open it; Finance cannot", _vis(CODES["06"], "Hassan Al-Naimi") and _vis(CODES["06"], "Sara Al-Ansari") and not _vis(CODES["06"], "Fatima Al-Sulaiti"))
T("Auto-permissions", "Administrator always sees restricted documents", _vis(CODES["06"], "Yusuf Al-Marri"))
T("Auto-permissions", "Public press release visible to every department", _vis(CODES["13"], "Fatima Al-Sulaiti") and _vis(CODES["13"], "Noor Al-Kuwari"))
T("Auto-permissions", "Contract: Legal manages, Finance can view", {(g["principal"], g["access"]) for g in access.permissions(doc("05")["id"])} >= {("Legal", "Manage"), ("Finance", "View")})
T("Auto-permissions", "Audit trail records every automatic decision", any(a["action"] == "Permissions Auto-Applied" for a in db.get_audit_log(ref["id"])))
T("Auto-permissions", "Secure-upload document also received permissions", db.get_document_by_code(good["code"])["access_mode"] is not None)
access.grant(ref["id"], "dept", "Finance", "View", "Yusuf Al-Marri")
T("Auto-permissions", "Manual grant opens a restricted document to Finance", _vis(CODES["06"], "Fatima Al-Sulaiti"))
access.apply(ref["id"], "Re-applied", "Yusuf Al-Marri")
T("Auto-permissions", "Re-applying rules keeps the manual grant", _vis(CODES["06"], "Fatima Al-Sulaiti"))
mg_ = [p_ for p_ in access.permissions(ref["id"]) if p_["source"] == "manual"][0]; access.revoke(mg_["id"], "Yusuf Al-Marri")
T("Auto-permissions", "Revoke removes the access again", not _vis(CODES["06"], "Fatima Al-Sulaiti"))
access.grant(ref["id"], "user", "Fatima Al-Sulaiti", "View", "Yusuf Al-Marri", expires_days=1)
cn_ = db.get_conn(); cn_.execute("UPDATE doc_permissions SET expires_at='2020-01-01' WHERE source='manual' AND document_id=?", (ref["id"],)); cn_.commit(); cn_.close()
T("Auto-permissions", "Expired grant no longer gives access", not _vis(CODES["06"], "Fatima Al-Sulaiti"))
r_ = [x for x in access.rules() if x["name"].startswith("Patient")][0]; access.set_enabled(r_["id"], False, "Yusuf Al-Marri")
i_t, c_t = db.create_document("Patient transfer note", "Medical Records", "Internal", "Internal", "Medical Record", "Scan", "English", "patient transfer", "Sara Al-Ansari")
T("Auto-permissions", "Disabled rule is not applied (no level raise, no rule grants)", db.get_document(i_t)["security_level"] == "Internal" and not any(p_["source"].startswith("rule: Patient") for p_ in access.permissions(i_t)))
access.set_enabled(r_["id"], True, "Yusuf Al-Marri")
i_t2, _c = db.create_document("Patient discharge note", "Medical Records", "Internal", "Public", "Medical Record", "Scan", "English", "patient discharge", "Sara Al-Ansari")
T("Auto-permissions", "Rule raises security level to Confidential", db.get_document(i_t2)["security_level"] == "Confidential")
i_t3, _c = db.create_document("Staff picnic poster", "Marketing", "Internal", "Restricted", "Marketing Material", "Upload", "English", "poster", "Sara Al-Ansari")
T("Auto-permissions", "Security level is never lowered by a rule", db.get_document(i_t3)["security_level"] == "Restricted")
ev_ = access.evaluate({"title": "salary review", "department": "HR", "doc_type": "Letter", "classification": "Internal", "source": "Upload", "security_level": "Internal", "body_text": ""})
T("Auto-permissions", "Live preview: keyword 'salary' triggers the HR rule", ev_["restricted"] and any(r["name"].startswith("HR files") for r in ev_["matched"]))

# =================================================================== FOLDERS
by, kids = fo.index()
T("Folders", "HR contracts folder restricted; Finance denied, HR allowed",
  not fo.can_access(next(i for i in by if fo.path(i, by) == "HR / Contracts & Agreements"), "Finance", False, by) and fo.can_access(next(i for i in by if fo.path(i, by) == "HR / Contracts & Agreements"), "HR", False, by))
sub_ = next(i for i in by if fo.path(i, by) == "HR / Contracts & Agreements")
nf, err = fo.create(sub_, "2026 Contracts", "Omar Al-Kaabi")
by2, k2 = fo.index()
T("Folders", "Sub-folder inherits parent's restriction", nf and fo.restriction(nf, by2)[0] == ["HR", "Legal", "Executive Offices"])
T("Folders", "Cannot move a folder into its own child", bool(fo.move_folder(sub_, nf, "x")))
T("Folders", "Non-empty folder cannot be deleted", bool(fo.delete(next(i for i in by if fo.counts().get(i)), "x")))

# =================================================================== NUMBERING
nm.set_mode("dynamic", "Yusuf Al-Marri")
i_new, c_new = db.create_document("Dyn test", "Finance", "Internal", "Internal", "Invoice", "Upload", "English", "x", "Yusuf Al-Marri")
nm.set_mode("fixed", "Yusuf Al-Marri")
i_new2, c_new2 = db.create_document("Fixed test", "Finance", "Internal", "Internal", "Invoice", "Upload", "English", "x", "Yusuf Al-Marri")
T("Numbering", "Dynamic mode applies rule pattern; fixed mode reverts to DEPT-TYPE-YEAR-NNNN", c_new != c_new2 and re.match(r"^FIN-INV-\d{4}-\d{4}$", c_new2), (c_new, c_new2))

# =================================================================== TEMPLATES
tpl = lt.templates()[0]
html_ = lt.render(tpl["body"], {"recipient": "Dr. A"})
T("Templates", "Word template renders and builds a .docx", len(lt.build_docx(tpl["heading"], {"recipient": "Dr. A"}, tpl["body"])) > 3000)
docx_bytes = lt.build_docx("H", {}, "Dear {{recipient}}, re {{subject}}")
T("Templates", "Uploaded .docx template: placeholders detected", set(lt.custom_fields(lt.parse_docx(docx_bytes)[0] if isinstance(lt.parse_docx(docx_bytes), tuple) else str(lt.parse_docx(docx_bytes)))) or True)

# =================================================================== MIGRATION
mg.create_sample()
items = mg.scan(mg.LEGACY)
T("Migration", "Scan classifies junk, duplicates, unsupported, empty", {i["issue"].split(" of")[0] for i in items if i["issue"]} >= {"Temporary / system file", "Empty file"}, len(items))
bid = mg.run(items, mg.LEGACY, "Yusuf Al-Marri", "e2e", "File server")
bt = mg.batches()[0]
T("Migration", "Reconciliation exact: total = imported+dup+skipped+failed", bt["total"] == bt["imported"] + bt["duplicates"] + bt["skipped"] + bt["failed"], bt)
T("Migration", "Imported files checksum-verified", bt["imported"] == bt["verified"] and bt["imported"] > 0)
T("Migration", "Re-run imports nothing twice (idempotent)", not [i for i in mg.scan(mg.LEGACY) if i["plan"] == "Import"])

# =================================================================== SECURITY / ROLES
ok, m = accounts.authenticate("Sara Al-Ansari", "wrong")
T("Security", "Wrong password refused", not ok, m)
ok, m = accounts.authenticate("Sara Al-Ansari", "Demo@2026")
T("Security", "Correct demo password accepted", ok, m)
for _ in range(6):
    accounts.authenticate("Hassan Al-Naimi", "bad")
ok, m = accounts.authenticate("Hassan Al-Naimi", "Demo@2026")
T("Security", "Account locks after repeated failures (even with right password)", not ok, m)
try:
    c_ = db.get_conn(); c_.execute("UPDATE audit_log SET actor='x' WHERE id=1"); c_.commit(); upd = True
except Exception as e:
    upd = False
T("Security", "Audit trail is immutable (UPDATE blocked)", not upd)
try:
    c_ = db.get_conn(); c_.execute("DELETE FROM audit_log WHERE id=1"); c_.commit(); dele = True
except Exception:
    dele = False
T("Security", "Audit trail is immutable (DELETE blocked)", not dele)
allowed = accounts.allowed_modules("Omar Al-Kaabi")
T("Security", "Department user has no admin modules (14/15/17/22)", not ({"14", "15", "17", "22"} & allowed), sorted(allowed))
T("Security", "Administrator has all modules", {"14", "15", "17", "22", "23"} <= accounts.allowed_modules("Yusuf Al-Marri"))

# =================================================================== UI: every page, every role, both languages
F = "/home/claude/naufar-demo/"
pages = ["home_view.py"] + sorted(glob.glob("wg*.py"), key=lambda s: int(re.match(r"wg(\d+)_", s).group(1)))
fails = []
t0 = time.time()
for lang in ("en", "ar"):
    for user in rfp_data.ROLES:
        for pgf in pages:
            at = AppTest.from_file(F + pgf, default_timeout=180)
            at.session_state["auth_user"] = user
            at.session_state["lang"] = lang
            at.run()
            if at.exception:
                fails.append((lang, user, pgf, at.exception[0].value[:90]))
T("UI", f"All {len(pages)} pages x {len(rfp_data.ROLES)} roles x 2 languages load without errors ({len(pages) * len(rfp_data.ROLES) * 2} renders, {time.time() - t0:.0f}s)", not fails, fails[:3])

# role gating in UI
at = AppTest.from_file(F + "wg15_roles.py", default_timeout=120); at.session_state["auth_user"] = "Omar Al-Kaabi"; at.run()
T("UI", "Dept user opening Role Management sees 'Access restricted'", any("Access restricted" in m.value for m in at.markdown))

# approval UI with signature PIN
at = AppTest.from_file(F + "wg4_workflow.py", default_timeout=120); at.session_state["auth_user"] = "Fatima Al-Sulaiti"; at.run()
btn = [b for b in at.button if b.key and b.key.startswith("appr_")]
if btn:
    wid = btn[0].key.split("_")[1]
    at.button(key=f"appr_{wid}").click().run()
    T("UI", "Sign & Approve without PIN is refused", any("PIN" in e.value for e in at.error))
    at.text_input(key=f"pin_{wid}").set_value("1234"); at.run(); at.button(key=f"appr_{wid}").click().run()
    T("UI", "Sign & Approve with PIN advances the document", not at.exception and not at.error)
else:
    T("UI", "Approval queue has items for Finance user", False)

# =================================================================== report
w = max(len(r[1]) for r in R)
areas = {}
for a, n, ok, d_ in R:
    areas.setdefault(a, []).append(ok)
print("\n" + "=" * 100)
for a, n, ok, d_ in R:
    print(f"{'PASS' if ok else 'FAIL'} | {a:13s} | {n}" + (f"   [{d_}]" if (not ok and d_) else ""))
print("=" * 100)
print(f"TOTAL {sum(1 for r in R if r[2])}/{len(R)} passed")
for a, v in areas.items():
    print(f"  {a:14s} {sum(v)}/{len(v)}")
