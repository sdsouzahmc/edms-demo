"""Reference data aligned to the tender's scope-of-work: departments, document types,
retention schedules, classification trees, sites, users. No client-identifying text."""

# SOW §1.2.3 — estimated users per department (2026-2030)
DEPT_USERS = {
    "Medical Records": 10, "Psychosocial Interventions (PSI)": 5, "Nursing": 5,
    "Physicians, Dental & Pharmacy": 5, "Clinical Operations": 3, "Executive Offices": 6,
    "Laboratory": 1, "HR": 3, "Finance": 3, "Procurement": 3, "Marketing": 2, "QRI": 2,
    "Talent Management": 2, "Legal": 2, "Research": 2, "Security": 2, "IT": 3,
    "Hospitality, Facility & Vendors": 5,
}
DEPARTMENTS = list(DEPT_USERS.keys())

RETENTION_SCHEDULES = {
    "Patient Record - 25 years": 25,
    "HR Records - 7 years": 7,
    "Finance Records - 10 years": 10,
    "Procurement Records - 6 years": 6,
    "Facility & Infrastructure - 15 years": 15,
    "Clinical SOP - 10 years": 10,
    "Accreditation Evidence - 10 years": 10,
    "Legal & Contracts - 10 years": 10,
    "Research Records - 15 years": 15,
    "Marketing Materials - 3 years": 3,
    "IT & Security Records - 5 years": 5,
    "General Correspondence - 3 years": 3,
}

# SOW §2.2.8 — document types the system must manage
DOC_TYPES = [
    "Employee Contract", "Appraisal", "Certificate", "Purchase Order", "Supplier Record",
    "Tender", "Invoice", "Payment Approval", "Audit Document", "SOP", "Maintenance Log",
    "Facility Record", "System Configuration", "SLA", "Vendor Agreement", "Policy",
    "Procedure", "AutoCAD Drawing", "Building Plan", "Equipment Manual",
    "Maintenance Schedule", "Service Contract", "Inspection Report",
    "Compliance Certificate", "Marketing Material", "Campaign Document", "Event Plan",
    "Branding Asset", "Medical Record", "Regulatory Letter", "Letter", "Memo", "Circular", "Research Protocol",
]

# document types that need Finance sign-off in the approval chain (conditional routing)
FINANCE_TYPES = {"Purchase Order", "Invoice", "Payment Approval", "Tender", "Service Contract",
                  "Vendor Agreement", "SLA"}

# prefix codes for standardised numbering  DEPT-TYPE-YYYY-NNNN
DEPT_CODE = {
    "Medical Records": "MR", "Psychosocial Interventions (PSI)": "PSI", "Nursing": "NUR",
    "Physicians, Dental & Pharmacy": "PDP", "Clinical Operations": "CLO", "Executive Offices": "EXO",
    "Laboratory": "LAB", "HR": "HR", "Finance": "FIN", "Procurement": "PRC", "Marketing": "MKT",
    "QRI": "QRI", "Talent Management": "TLM", "Legal": "LEG", "Research": "RES",
    "Security": "SEC", "IT": "IT", "Hospitality, Facility & Vendors": "HFV",
}
TYPE_CODE = {
    "Employee Contract": "CTR", "Appraisal": "APR", "Certificate": "CRT", "Purchase Order": "PO",
    "Supplier Record": "SUP", "Tender": "TND", "Invoice": "INV", "Payment Approval": "PAY",
    "Audit Document": "AUD", "SOP": "SOP", "Maintenance Log": "MLG", "Facility Record": "FAC",
    "System Configuration": "CFG", "SLA": "SLA", "Vendor Agreement": "VEN", "Policy": "POL",
    "Procedure": "PRO", "AutoCAD Drawing": "DWG", "Building Plan": "BPL", "Equipment Manual": "MAN",
    "Maintenance Schedule": "MSC", "Service Contract": "SVC", "Inspection Report": "INS",
    "Compliance Certificate": "CMP", "Marketing Material": "MKM", "Campaign Document": "CMD",
    "Event Plan": "EVT", "Branding Asset": "BRD", "Medical Record": "MED",
    "Regulatory Letter": "REG", "Letter": "LTR", "Memo": "MEM", "Circular": "CIR", "Research Protocol": "RPR",
}

# multi-level classification tree (alternative to folder hierarchy) — SOW matrix 1.6-1.8, 1.21
CLASS_TREE = {
    "Clinical": {"Patient Records": ["Medical Record"], "Clinical Governance": ["SOP", "Procedure", "Policy"],
                  "Research": ["Research Protocol"]},
    "Corporate": {"People": ["Employee Contract", "Appraisal", "Certificate"],
                   "Finance & Supply": ["Purchase Order", "Invoice", "Payment Approval", "Tender",
                                        "Supplier Record", "Vendor Agreement", "SLA", "Service Contract"],
                   "Governance": ["Policy", "Audit Document", "Memo", "Circular"]},
    "Facilities & Infrastructure": {"Drawings & Plans": ["AutoCAD Drawing", "Building Plan"],
                                     "Maintenance": ["Maintenance Log", "Maintenance Schedule",
                                                      "Equipment Manual", "Facility Record"],
                                     "Compliance": ["Inspection Report", "Compliance Certificate"],
                                     "IT": ["System Configuration"]},
    "Marketing & Communications": {"Campaigns": ["Marketing Material", "Campaign Document", "Event Plan"],
                                    "Brand": ["Branding Asset"]},
    "Regulatory & Correspondence": {"Regulatory": ["Regulatory Letter"], "Internal / External": ["Memo", "Circular"]},
}

SITES = [
    ("Main Campus — Doha", "Primary", "On-prem data centre", "Active"),
    ("Satellite Clinic (planned)", "Secondary", "Azure Qatar region", "Provisioned"),
    ("Virtual / Remote Sites", "Virtual", "Browser + mobile access", "Active"),
]

# demo users (name -> profile). dept must be one of DEPARTMENTS (or IT for admin)
ROLES = {
    "Sara Al-Ansari": {"role": "Records Officer", "dept": "Medical Records", "level": "department_user", "can_approve": True},
    "Omar Al-Kaabi": {"role": "HR Manager", "dept": "HR", "level": "department_user", "can_approve": True},
    "Fatima Al-Sulaiti": {"role": "Finance Controller", "dept": "Finance", "level": "department_user", "can_approve": True},
    "Hassan Al-Naimi": {"role": "Nursing Supervisor", "dept": "Nursing", "level": "department_user", "can_approve": True},
    "Layla Al-Marri": {"role": "QRI Officer", "dept": "QRI", "level": "department_user", "can_approve": True},
    "Noor Al-Kuwari": {"role": "Legal Counsel", "dept": "Legal", "level": "department_user", "can_approve": True},
    "Yusuf Al-Marri": {"role": "Administrator", "dept": "IT", "level": "admin", "can_approve": True},
}
