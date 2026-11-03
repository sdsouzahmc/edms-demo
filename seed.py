"""One-time seed: realistic sample documents across departments so every
workgroup page has something to demonstrate against. Safe to re-run — it
checks for existing data first."""
import os
import db
import datetime as dt

SEED_DOCS = [
    # title, dept, classification, security, type, source, lang, body, sender, recipient, retention, target_stage
    ("Annual Facility License Renewal Requirements", "Medical Records", "Regulatory", "Restricted",
     "Regulatory Letter", "Postal", "English",
     "Ministry of Public Health annual licensing renewal requirements. Submit updated policy "
     "documentation, staff credentialing records, and facility inspection reports within 30 days.",
     "Ministry of Public Health", "Compliance Officer", "Patient-Adjacent Admin - 10 years", "Released"),

    ("Revised Staff Leave Policy", "Human Resources", "Internal", "Internal",
     "Policy", "Email", "English",
     "Revised staff leave policy effective immediately. Updated annual leave accrual rates and a "
     "new process for emergency leave requests.", "HR Department", "All Department Heads",
     "HR Records - 7 years", "Released"),

    ("Medical Supplies Q4 Purchase Order", "Procurement", "External", "Internal",
     "Purchase Order", "Email", "English",
     "Purchase order PO-2026-0417 for medical supplies Q4 replenishment, Gulf Medical Supplies "
     "W.L.L., amount QAR 48,900, delivery required by 10/10/2026.",
     "Procurement Department", "Gulf Medical Supplies W.L.L.", "Procurement Records - 6 years", "Approval"),

    ("Vendor Invoice - Facility Maintenance Contract", "Finance", "External", "Restricted",
     "Invoice", "Email", "English",
     "Invoice for Q3 facility maintenance contract services. Payment terms net 30 days. "
     "Amount QAR 22,300.", "Doha Facility Services", "Accounts Payable",
     "Finance Records - 10 years", "Finance Sign-off"),

    ("Fire Safety Inspection Report", "Facilities", "Regulatory", "Internal",
     "Inspection Report", "Postal", "English",
     "Annual fire safety inspection report. All systems passed inspection with two minor "
     "recommendations for signage updates.", "Qatar Civil Defence", "Facilities Manager",
     "Facility Records - 5 years", "Released"),

    ("Clinical SOP - Patient Intake Assessment", "Clinical Operations", "Internal", "Confidential",
     "SOP", "Upload", "English",
     "Standard operating procedure for patient intake assessment covering initial screening, "
     "risk assessment, and care plan initiation.", "Clinical Operations", "All Clinical Staff",
     "Patient-Adjacent Admin - 10 years", "Department Review"),

    ("Employment Contract Template - 2026", "Human Resources", "Internal", "Confidential",
     "Contract", "Upload", "English",
     "Standard employment contract template for new hires, updated for 2026 compliance with "
     "Qatar labour law amendments.", "HR Department", "Legal",
     "HR Records - 7 years", "Draft"),

    ("Budget Variance Report - September", "Finance", "Internal", "Restricted",
     "Report", "Upload", "English",
     "Monthly budget variance report showing departmental spend against approved budget for "
     "September 2026.", "Finance Department", "Executive Office",
     "Finance Records - 10 years", "Released"),

    ("Supplier Agreement - IT Hardware Framework", "Procurement", "External", "Internal",
     "Agreement", "Postal", "English",
     "Three-year framework agreement for IT hardware procurement and support services.",
     "TechSource Qatar", "Procurement Department", "Procurement Records - 6 years", "Released"),

    ("Equipment Maintenance Log - HVAC System", "Facilities", "Internal", "Internal",
     "Maintenance Log", "Upload", "English",
     "Quarterly HVAC maintenance log covering filter replacement, system calibration, and "
     "performance checks.", "Facilities Team", "Facilities Manager",
     "Facility Records - 5 years", "Released"),

    ("Staff Credential Verification - Nursing", "Clinical Operations", "Internal", "Confidential",
     "Credential Record", "Upload", "Arabic",
     "ملف التحقق من اعتماد طاقم التمريض وسجلات الترخيص المهني للموظفين الجدد.",
     "Clinical Operations", "HR Department", "Patient-Adjacent Admin - 10 years", "Approval"),

    ("Expired Vendor Contract - Legacy Cleaning Services", "Facilities", "External", "Internal",
     "Contract", "Upload", "English",
     "Cleaning services contract that expired in 2023 and is scheduled for disposal review "
     "per retention schedule.", "CleanPro Services", "Facilities", "Facility Records - 5 years",
     "Archived"),
]


def run():
    db.init_db()
    conn = db.get_conn()
    existing = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
    conn.close()
    if existing > 0:
        print(f"Already seeded ({existing} documents). Skipping.")
        return

    for (title, dept, classification, sec, dtype, source, lang, body, sender, recipient,
         retention, target_stage) in SEED_DOCS:
        actor = {
            "Medical Records": "Sara Al-Ansari", "Human Resources": "Omar Al-Kaabi",
            "Finance": "Fatima Al-Sulaiti",
        }.get(dept, "Yusuf Al-Marri")

        doc_id, code = db.create_document(
            title=title, department=dept, classification=classification, security_level=sec,
            doc_type=dtype, source=source, language=lang, body_text=body, created_by=actor,
            sender=sender, recipient=recipient, retention_label=retention,
        )
        if source in ("Postal", "Email"):
            db.log_correspondence(doc_id, "Incoming", source, sender, recipient, title, actor)

        # advance workflow toward the seeded target stage so each page has variety
        stage_order = {s: i for i, s in enumerate(db.WORKFLOW_STAGES)}
        target_idx = stage_order.get(target_stage, 0)
        if target_stage in ("Released",):
            steps = len(db.WORKFLOW_STAGES) - 1
        elif target_stage == "Archived":
            steps = len(db.WORKFLOW_STAGES) - 1
        else:
            steps = target_idx

        for _ in range(steps):
            db.advance_workflow(doc_id, "approve", actor, "Seed data — approved for demo")

        if target_stage == "Archived":
            db.archive_document(doc_id, actor)

    # one disposal request pending for the records/archiving workgroup
    docs = db.get_documents(include_disposed=True)
    archived = [d for d in docs if d["status"] == "Archived"]
    if archived:
        db.request_disposal(archived[0]["id"], "Yusuf Al-Marri",
                             "Retention period expired; cleaning services contract superseded in 2024.")

    print(f"Seeded {len(SEED_DOCS)} documents with correspondence, versions, workflow and audit history.")


if __name__ == "__main__":
    run()
