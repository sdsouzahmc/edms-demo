"""Seed data aligned to the RFP scope: the 18 departments, the document types in SOW 2.2.8,
correspondence categories (internal / external / regulatory), retention schedules and
physical records. Safe to re-run: skips if data already exists."""
import db
import db_ext
import rfp_data

U = {  # department -> acting user
    "Medical Records": "Sara Al-Ansari", "HR": "Omar Al-Kaabi", "Finance": "Fatima Al-Sulaiti",
    "Nursing": "Hassan Al-Naimi", "QRI": "Layla Al-Marri", "Legal": "Noor Al-Kuwari",
}

# title, dept, class, security, type, source, lang, body, sender, recipient, retention, stage
SEED_DOCS = [
    ("Annual Facility Licence Renewal Requirements", "Executive Offices", "Regulatory", "Restricted",
     "Regulatory Letter", "Postal", "English",
     "Ministry of Public Health (MOPH) annual licence renewal. Submit updated policies, staff credentialing "
     "records and facility inspection reports within 30 days. Reference MOPH-2026-0417.",
     "Ministry of Public Health", "Chief Executive Officer", "General Correspondence - 3 years", "Released"),
    ("CARF Accreditation Evidence Pack - Standards Section 1", "QRI", "Internal", "Restricted",
     "Audit Document", "Upload", "English",
     "Evidence pack for CARF accreditation covering person-centred care planning, risk management and "
     "performance improvement. ISO 9001 internal audit cross-references included.",
     "QRI Office", "Executive Offices", "Accreditation Evidence - 10 years", "Released"),
    ("Patient Admission Record Template - Residential Programme", "Medical Records", "Internal", "Confidential",
     "Medical Record", "Upload", "English",
     "Patient admission record template. Patient: Mohammed K., QID 2889****1234, DOB 12/03/1990. "
     "Diagnosis recorded in EMR. PHI - restricted to authorised clinical and records staff only.",
     "Medical Records", "Clinical Operations", "Patient Record - 25 years", "Released"),
    ("Employment Contract - Senior Counsellor (Template 2026)", "HR", "Internal", "Confidential",
     "Employee Contract", "Upload", "English",
     "Standard employment contract for senior counsellors, updated for Qatar Labour Law amendments. "
     "Probation, end-of-service benefits and confidentiality clauses.",
     "HR Department", "Legal", "HR Records - 7 years", "Approval"),
    ("Annual Performance Appraisal - Nursing Team 2026", "Nursing", "Internal", "Restricted",
     "Appraisal", "Upload", "English",
     "Annual performance appraisal forms for the nursing team, objectives and competency ratings.",
     "Nursing Supervisor", "HR", "HR Records - 7 years", "Department Review"),
    ("Professional Licence Certificate - Clinical Psychologist", "Talent Management", "Internal", "Restricted",
     "Certificate", "Scan", "English",
     "Professional practice licence certificate for clinical psychologist, valid until 2027, "
     "verified against MOPH register.", "MOPH", "Talent Management", "HR Records - 7 years", "Released"),
    ("Medical Supplies Q4 Purchase Order", "Procurement", "External", "Internal",
     "Purchase Order", "Email", "English",
     "Purchase order PO-2026-0417 for medical supplies Q4 replenishment, Gulf Medical Supplies W.L.L., "
     "amount QAR 48,900, delivery required by 10/12/2026.",
     "Procurement", "Gulf Medical Supplies W.L.L.", "Procurement Records - 6 years", "Finance Sign-off"),
    ("Tender Evaluation - Laboratory Analyser Replacement", "Procurement", "Internal", "Restricted",
     "Tender", "Upload", "English",
     "Technical and commercial evaluation of three bids for laboratory analyser replacement. "
     "Recommended supplier scored 86 percent against weighted criteria.",
     "Procurement Committee", "Executive Offices", "Procurement Records - 6 years", "Approval"),
    ("Supplier Record - Doha Facility Services", "Procurement", "External", "Internal",
     "Supplier Record", "Upload", "English",
     "Approved supplier file: commercial registration, tax card, insurance certificate, and performance rating.",
     "Doha Facility Services", "Procurement", "Procurement Records - 6 years", "Released"),
    ("Vendor Invoice - Q3 Facility Maintenance", "Finance", "External", "Restricted",
     "Invoice", "Email", "English",
     "Invoice INV-7731 for Q3 facility maintenance services. Payment terms net 30 days. Amount QAR 22,300.",
     "Doha Facility Services", "Accounts Payable", "Finance Records - 10 years", "Finance Sign-off"),
    ("Payment Approval - Laboratory Consumables", "Finance", "Internal", "Restricted",
     "Payment Approval", "Upload", "English",
     "Payment approval memo for laboratory consumables, amount QAR 15,800, budget code LAB-CON-26.",
     "Finance", "Laboratory", "Finance Records - 10 years", "Department Review"),
    ("Statutory Audit Working Papers FY2025", "Finance", "Regulatory", "Confidential",
     "Audit Document", "Upload", "English",
     "External audit working papers FY2025, MOF reporting schedule and management letter responses.",
     "External Auditor", "Finance", "Finance Records - 10 years", "Released"),
    ("Clinical SOP - Patient Intake Assessment", "Clinical Operations", "Internal", "Confidential",
     "SOP", "Upload", "English",
     "Standard operating procedure for patient intake assessment: initial screening, risk assessment and "
     "care plan initiation. Aligned with CARF standards.",
     "Clinical Operations", "All Clinical Staff", "Clinical SOP - 10 years", "Department Review"),
    ("SOP - Group Therapy Session Delivery", "Psychosocial Interventions (PSI)", "Internal", "Restricted",
     "SOP", "Upload", "English",
     "Standard operating procedure for facilitated group therapy sessions, consent, confidentiality and "
     "incident reporting for the psychosocial interventions programme.",
     "PSI Programme Lead", "PSI Team", "Clinical SOP - 10 years", "Released"),
    ("Medication Storage and Dispensing Policy", "Physicians, Dental & Pharmacy", "Internal", "Restricted",
     "Policy", "Upload", "English",
     "Policy on controlled medication storage, dispensing, double-check and disposal of expired stock.",
     "Pharmacy", "Nursing", "Clinical SOP - 10 years", "Released"),
    ("Laboratory Specimen Handling Procedure", "Laboratory", "Internal", "Internal",
     "Procedure", "Upload", "English",
     "Specimen labelling, transport, chain of custody, and rejection criteria for toxicology samples.",
     "Laboratory", "Nursing", "Clinical SOP - 10 years", "Released"),
    ("Research Protocol - Aftercare Outcomes Study", "Research", "Internal", "Confidential",
     "Research Protocol", "Upload", "English",
     "Observational study protocol on aftercare outcomes for residential programme graduates. "
     "Ethics review pending. Data protection assessment attached.",
     "Research Unit", "Executive Offices", "Research Records - 15 years", "Draft"),
    ("Data Protection and Management Policy", "Legal", "Internal", "Internal",
     "Policy", "Upload", "English",
     "Organisation data protection policy aligned to PDPPL Law No. 13 of 2016, HIPAA, GDPR and the "
     "Qatar National Data Policy. Defines data owners, retention and breach notification.",
     "Legal", "All Departments", "Legal & Contracts - 10 years", "Released"),
    ("Service Contract - HVAC Maintenance (3 years)", "Hospitality, Facility & Vendors", "External", "Internal",
     "Service Contract", "Postal", "English",
     "Three-year HVAC planned preventive maintenance contract with quarterly service visits and "
     "emergency call-out terms. Value QAR 310,000.",
     "CoolTech Qatar", "Facilities Manager", "Facility & Infrastructure - 15 years", "Approval"),
    ("HVAC Preventive Maintenance Log - Q3", "Hospitality, Facility & Vendors", "Internal", "Internal",
     "Maintenance Log", "Upload", "English",
     "Quarterly HVAC maintenance log: filter replacement, calibration and performance checks.",
     "Facilities Team", "Facilities Manager", "Facility & Infrastructure - 15 years", "Released"),
    ("Residential Wing - Ground Floor Plan (AutoCAD)", "Hospitality, Facility & Vendors", "Internal", "Restricted",
     "AutoCAD Drawing", "Upload", "English",
     "AutoCAD drawing DWG rev C, residential wing ground floor plan with fire exits and services risers.",
     "Facilities Team", "Security", "Facility & Infrastructure - 15 years", "Released"),
    ("Fire Safety Inspection Report", "Security", "Regulatory", "Internal",
     "Inspection Report", "Postal", "English",
     "Annual fire safety inspection report. All systems passed, two minor recommendations on signage.",
     "Qatar Civil Defence", "Security", "Facility & Infrastructure - 15 years", "Released"),
    ("Security Incident Response Procedure", "Security", "Internal", "Restricted",
     "Procedure", "Upload", "English",
     "Procedure for security incidents, visitor access control, escalation and reporting to executive office.",
     "Security", "All Staff", "IT & Security Records - 5 years", "Approval"),
    ("Electrical Compliance Certificate 2026", "Hospitality, Facility & Vendors", "Regulatory", "Internal",
     "Compliance Certificate", "Scan", "English",
     "Electrical installation compliance certificate issued by KAHRAMAA, valid 12 months.",
     "KAHRAMAA", "Facilities Manager", "Facility & Infrastructure - 15 years", "Released"),
    ("IT Service Level Agreement - Network Provider", "IT", "External", "Internal",
     "SLA", "Upload", "English",
     "SLA with network provider: 99.7 percent availability, 4-hour response for severity 1 incidents.",
     "Network Provider", "IT", "IT & Security Records - 5 years", "Finance Sign-off"),
    ("System Configuration Baseline - Production Servers", "IT", "Internal", "Confidential",
     "System Configuration", "Upload", "English",
     "Hardening baseline and configuration items for production servers, patch levels and backup policy.",
     "IT", "IT", "IT & Security Records - 5 years", "Released"),
    ("Autumn Awareness Campaign Plan", "Marketing", "Internal", "Internal",
     "Campaign Document", "Upload", "English",
     "Community awareness campaign plan on substance use prevention: channels, budget, KPIs and calendar.",
     "Marketing", "Executive Offices", "Marketing Materials - 3 years", "Approval"),
    ("Annual Conference Event Plan", "Marketing", "Internal", "Internal",
     "Event Plan", "Upload", "English",
     "Event plan for the annual conference: venue, speakers, run of show and visitor flow.",
     "Marketing", "Hospitality, Facility & Vendors", "Marketing Materials - 3 years", "Released"),
    ("Brand Guidelines v3 (Branding Asset)", "Marketing", "Internal", "Public",
     "Branding Asset", "Upload", "English",
     "Brand guidelines: logo usage, colour palette, typography, templates for letters and presentations.",
     "Marketing", "All Departments", "Marketing Materials - 3 years", "Released"),
    ("Staff Circular - Updated Leave Policy", "HR", "Internal", "Internal",
     "Circular", "Email", "English",
     "Circular to all staff announcing revised annual leave accrual and emergency leave procedure effective "
     "1 November 2026.", "HR", "All Departments", "General Correspondence - 3 years", "Released"),
    ("Internal Memo - Executive Committee Meeting Minutes", "Executive Offices", "Internal", "Confidential",
     "Memo", "Upload", "English",
     "Minutes of the executive committee meeting: strategic priorities and delegation of authority decisions.",
     "Executive Offices", "Executive Committee", "General Correspondence - 3 years", "Released"),
    ("ملف التحقق من اعتماد طاقم التمريض", "Nursing", "Internal", "Confidential",
     "Certificate", "Scan", "Arabic",
     "ملف التحقق من اعتماد طاقم التمريض وسجلات الترخيص المهني للموظفين الجدد.",
     "التمريض", "الموارد البشرية", "HR Records - 7 years", "Approval"),
    ("تعميم - سياسة الإجازات المحدثة", "HR", "Internal", "Internal",
     "Circular", "Email", "Arabic",
     "تعميم إلى جميع الموظفين بشأن تحديث سياسة الإجازات السنوية والإجازة الطارئة.",
     "الموارد البشرية", "جميع الإدارات", "General Correspondence - 3 years", "Released"),
    ("Expired Vendor Contract - Legacy Cleaning Services", "Hospitality, Facility & Vendors", "External", "Internal",
     "Vendor Agreement", "Upload", "English",
     "Cleaning services agreement that expired in 2023 and is scheduled for disposal review per retention schedule.",
     "CleanPro Services", "Facilities", "Facility & Infrastructure - 15 years", "Archived"),
]


def run():
    db.init_db()
    db_ext.init_ext()
    conn = db.get_conn()
    existing = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
    conn.close()
    if existing > 0:
        print(f"Already seeded ({existing} documents). Skipping.")
        return

    ids = {}
    for (title, dept, classification, sec, dtype, source, lang, body, sender, recipient,
         retention, target_stage) in SEED_DOCS:
        actor = U.get(dept, "Yusuf Al-Marri")
        doc_id, code = db.create_document(
            title=title, department=dept, classification=classification, security_level=sec,
            doc_type=dtype, source=source, language=lang, body_text=body, created_by=actor,
            sender=sender, recipient=recipient, retention_label=retention)
        ids[title] = doc_id
        if source in ("Postal", "Email"):
            db.log_correspondence(doc_id, "Incoming", "Postal Mail" if source == "Postal" else "Email / Outlook",
                                  sender, recipient, title, actor)

        names = [r["stage"] for r in db.get_workflow(doc_id)]
        if target_stage in ("Released", "Archived"):
            steps = len(names) - 1
        elif target_stage in names:
            steps = names.index(target_stage)
        else:
            steps = 0
        for _ in range(steps):
            stage = next(w["stage"] for w in db.get_workflow(doc_id) if w["status"] == "active")
            db.advance_workflow(doc_id, "approve", actor, "Seed data - approved for demo")
            db_ext.log_esign(doc_id, actor, stage)
        if target_stage == "Archived":
            db.archive_document(doc_id, actor)

    conn = db.get_conn()
    # --- make the dashboards meaningful: overdue approvals, expiring and expired documents ---
    for title, days in [("Employment Contract - Senior Counsellor (Template 2026)", 9),
                        ("Annual Performance Appraisal - Nursing Team 2026", 6),
                        ("Tender Evaluation - Laboratory Analyser Replacement", 12),
                        ("Payment Approval - Laboratory Consumables", 5),
                        ("Medical Supplies Q4 Purchase Order", 4)]:
        conn.execute("UPDATE documents SET modified_at=datetime('now', ?) WHERE id=?", (f"-{days} day", ids[title]))
    for title, delta in [("Professional Licence Certificate - Clinical Psychologist", "+34 day"),
                         ("Electrical Compliance Certificate 2026", "+58 day"),
                         ("Brand Guidelines v3 (Branding Asset)", "+75 day"),
                         ("Staff Circular - Updated Leave Policy", "-12 day"),
                         ("Autumn Awareness Campaign Plan", "+21 day")]:
        conn.execute("UPDATE documents SET expiry_date=date('now', ?) WHERE id=?", (delta, ids[title]))
    conn.execute("UPDATE documents SET legal_hold=1 WHERE id=?", (ids["Statutory Audit Working Papers FY2025"],))
    conn.execute("UPDATE documents SET site='Main Campus — Doha'")
    conn.commit()
    conn.close()

    # --- one disposal request ---
    arch = [d for d in db.get_documents(include_disposed=True) if d["status"] == "Archived"]
    if arch:
        db.request_disposal(arch[0]["id"], "Yusuf Al-Marri",
                            "Retention period expired; cleaning services agreement superseded in 2024.")

    # --- workflow templates (configured via the designer) ---
    db_ext.save_template("Legal", "", ["Draft", "Department Review", "Legal Review", "Approval", "Released"], "Yusuf Al-Marri")
    db_ext.save_template("QRI", "", ["Draft", "Department Review", "Quality Review", "Approval", "Released"], "Yusuf Al-Marri")

    # --- workspace: bookmarks, subscriptions, notifications ---
    for u, titles in {"Sara Al-Ansari": ["Annual Facility Licence Renewal Requirements",
                                         "Patient Admission Record Template - Residential Programme"],
                      "Fatima Al-Sulaiti": ["Vendor Invoice - Q3 Facility Maintenance"],
                      "Omar Al-Kaabi": ["Staff Circular - Updated Leave Policy"]}.items():
        for t in titles:
            db_ext.toggle_bookmark(u, ids[t])
            db_ext.toggle_subscription(u, f"doc:{ids[t]}")
    db_ext.toggle_subscription("Sara Al-Ansari", "topic:Regulatory")
    db_ext.notify("Fatima Al-Sulaiti", "Invoice INV-7731 is awaiting your Finance Sign-off.",
                  ids["Vendor Invoice - Q3 Facility Maintenance"], "approval")
    db_ext.notify("Omar Al-Kaabi", "Employment Contract template has been waiting for Approval for 9 days (SLA 3 days).",
                  ids["Employment Contract - Senior Counsellor (Template 2026)"], "overdue")
    db_ext.notify("Sara Al-Ansari", "New MOPH regulatory letter registered and released.",
                  ids["Annual Facility Licence Renewal Requirements"], "info")
    db_ext.notify("Sara Al-Ansari", "Reminder: Professional Licence Certificate review date is in 34 days.",
                  ids["Professional Licence Certificate - Clinical Psychologist"], "reminder")

    # --- outgoing dispatch / internal comms ---
    for title, cat, kind, rcp, status in [
        ("Annual Facility Licence Renewal Requirements", "Regulatory", "Letter", "Ministry of Public Health", "Dispatched"),
        ("Staff Circular - Updated Leave Policy", "Internal", "Circular", "All Departments", "Dispatched"),
        ("Internal Memo - Executive Committee Meeting Minutes", "Internal", "Memo", "Executive Committee", "Approved"),
        ("Medical Supplies Q4 Purchase Order", "External", "Letter", "Gulf Medical Supplies W.L.L.", "Drafted")]:
        db_ext.create_dispatch(ids[title], cat, kind, rcp, "Records; Legal", "Sara Al-Ansari")
    conn = db.get_conn()
    rows = conn.execute("SELECT id, status FROM dispatch").fetchall()
    conn.close()
    for r in rows:
        target = {"Dispatched": 3, "Approved": 1, "Drafted": 0}
        want = {1: 3, 2: 3, 3: 1, 4: 0}[r["id"]]
        for _ in range(want):
            db_ext.advance_dispatch(r["id"], "Sara Al-Ansari")

    # --- physical / intermediate records ---
    for box, desc, dept, site, loc, cust, until in [
        ("BX-0001", "Legacy patient files 2012-2015 (paper)", "Medical Records", "Main Campus — Doha", "Records Room A / Rack 3", "Sara Al-Ansari", "2040-12-31"),
        ("BX-0002", "Closed procurement files 2019-2021", "Procurement", "Offsite Storage Provider", "Warehouse 2 / Bay 14", "Third-party custodian", "2027-12-31"),
        ("BX-0003", "HR personnel files - former staff", "HR", "Main Campus — Doha", "Records Room B / Rack 1", "Omar Al-Kaabi", "2031-06-30"),
        ("BX-0004", "Finance vouchers FY2016-FY2018", "Finance", "Offsite Storage Provider", "Warehouse 2 / Bay 3", "Third-party custodian", "2028-12-31")]:
        db_ext.add_physical(box, desc, dept, site, loc, cust, until)

    db_ext.sync_ad()
    db_ext.make_backup("Initial baseline (post-seed)", "System", "Scheduled")
    print(f"Seeded {len(SEED_DOCS)} documents aligned to the RFP scope.")


if __name__ == "__main__":
    run()
