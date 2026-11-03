import streamlit as st
import pandas as pd
import db
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("11 · RFP Coverage", "Traceability: RFP requirement group → proposal response key → where this demo proves it")

# (RFP ref, requirement group, M/O, proposal key, demo page, status)
D, P, N = "Demonstrated", "Partly demonstrated", "Not in demo"
ROWS = [
    ("1.0", "Mask patient PII/PHI from infrastructure roles & data in transit", "M", "CC", "5 · Security › Masking", D),
    ("1.1, 1.41", "Central repository for all content types & formats", "M", "C", "3 · Document Control", P),
    ("1.2", "Large file sizes", "M", "C", "— (platform capability)", N),
    ("1.3", "Bulk upload with custom metadata", "M", "C", "2 · OCR (batch path described)", P),
    ("1.5", "Group-based views without multiple renditions", "M", "CC", "5 · Security (role views)", D),
    ("1.6-1.8, 1.21", "Multiple taxonomies, classification trees, multi-category", "M", "C", "6 · Search › Classification tree", D),
    ("1.9-1.14", "Versioning, check-in/out, published vs draft, admin override", "M", "C", "3 · Document Control", D),
    ("1.15-1.17, 1.26, 2.05", "Audit trail of access, changes, workflow", "M", "C", "7 · Audit", D),
    ("1.18", "Users save their own report templates", "M", "CC", "7 · Audit › My Report Templates", D),
    ("1.19, 1.22, 5.13", "Admin dashboards: overdue, expiring, compliance, audit readiness", "M", "C/CC", "7 · Audit › Audit Readiness", D),
    ("1.24", "Resource utilisation monitoring", "M", "C", "10 · Admin › Monitoring", D),
    ("1.25, 1.30, 1.48, 1.49", "Notifications, subscriptions, reminders", "M/O", "C", "9 · My Workspace", D),
    ("1.27", "Browser-based remotely accessible admin console", "M", "C", "10 · Administration", D),
    ("1.28, 1.29, 1.32-1.35", "Multi-tier, HA ≥ 99.7%, failover, replication, data sovereignty", "M", "C", "10 · Admin › Sites, HA/DR", P),
    ("1.31, 5.07", "Secure e-signature with usage reporting", "M", "CC", "4 · Workflow · 5 › E-Signature", D),
    ("1.36-1.38", "Storage types / tiers with retention", "M", "CC", "10 · Admin › Storage tiers", P),
    ("1.39", "Import, store, declare and use templates", "M", "C", "—", N),
    ("1.40", "Import from network drives & file servers (migration)", "M", "C", "— (migration phase)", N),
    ("1.42, 2.09", "Register & declare a record so it cannot be altered", "M", "C", "3 · Document Control › Declare Record", D),
    ("1.43", "Metadata formats + automatic extraction", "M", "CC", "2 · OCR", D),
    ("1.44-1.46", "Classification library, security classification, classification-based rules", "M", "C", "5 · Security", D),
    ("1.47, 1.54, 2.2.10.5", "Auto numbering / naming, status & effective-date tracking", "M/O", "C/CC", "1 · Correspondence · all pages (e.g. FIN-INV-2026-0001)", D),
    ("1.50-1.52", "Retention, archiving, approved disposition with evidence", "M", "C/CC", "8 · Records", D),
    ("1.53", "Recycle bin & restore", "M", "C", "9 · My Workspace › Recycle Bin", D),
    ("2.01-2.02, 2.06, 2.11-2.15, 2.21", "RBAC, department isolation, controlled cross-department sharing", "M", "C", "5 · Security", D),
    ("2.03, 7.04", "Active Directory compatibility & user/group sync", "M", "C", "10 · Admin › Identity", P),
    ("2.07", "Access permissions audit report", "M", "C", "5 · Security › Access Report", D),
    ("2.08, 2.16, 2.17", "Encryption, public/private key, hardening guidelines", "M", "C", "— (described in proposal §13)", N),
    ("2.10", "Inactivity log-off", "O", "C", "5 · Security › Policy (setting only)", P),
    ("2.18-2.22", "SSO, MFA, password complexity / expiry, lockout with admin override", "M", "C", "5 · Security › Authentication Policy", D),
    ("3.04, 3.05", "Bookmarks & user dashboard (recent, pending workflows)", "M", "C", "9 · My Workspace", D),
    ("3.09, 2.3.9", "Bilingual English / Arabic interface with instant switch", "M", "C", "Sidebar language switch (core UI)", P),
    ("3.01-3.03, 3.06-3.08", "Shortcuts, help button, separate admin UI, drag-drop dashboards", "M/O", "C/CC", "—", N),
    ("4.01-4.22", "Search: ranked full-text index incl. OCR text, Boolean, phrase, wildcard, typo correction, facets, range, history, templates, saved, export, ZIP", "M", "C", "6 · Search (SQLite FTS5, BM25 ranking, highlighted snippets)", D),
    ("4.x, 9.07", "Search over scanned documents by their OCR'd text", "M", "C", "6 · Search › OCR-only filter; 2 · OCR batch", D),
    ("2.4.1-2.4.3, 5.x", "Automatic distribution / routing of incoming & scanned items by content rules, with copies, SLA and triage", "M", "C/CC", "12 · Auto-Distribution", D),
    ("4.11", "Natural-language search (concept based)", "M", "C", "6 · Search › Natural language (demo uses concept expansion)", P),
    ("4.18", "e-Discovery incl. legal hold", "M", "C", "6 · Search export + 8 · Legal hold", P),
    ("5.01-5.06, 5.08, 5.09", "Review & approval workflow, delegation, queue, audit trail", "M", "C", "4 · Workflow", D),
    ("5.10", "Ad-hoc / dynamic processes", "M", "C", "4 · Workflow › Ad-hoc Routing", D),
    ("5.11, 5.12", "Workflow designer; form / screen designer", "M", "C/CC", "4 · Workflow › Designer (chains only)", P),
    ("5.14", "Complex routing, branching, conditions, parallelism", "M", "C", "4 · Workflow (conditional by doc type; no parallel)", P),
    ("6.01-6.04", "Viewer: open, print, zoom, preview", "M/O", "C", "3 · Document Control › Viewer", P),
    ("6.05-6.11", "Annotation, redaction with reasons, burn-in, restricted visibility", "O", "CC", "3 · Document Control › Viewer", D),
    ("6.12-6.13", "Visual and text-level compare", "O", "CC", "3 · Compare Versions (text only)", P),
    ("7.01, 7.03", "SharePoint, Office 365, Teams / Groups integration", "M", "C", "10 · Admin › Integrations (simulated)", P),
    ("7.05, 7.07", "APIs for third-party integration and reporting", "M", "C", "10 · Admin › API sample", P),
    ("7.06, 2.2.10.1", "Outlook email capture", "M", "C", "10 · Admin › Outlook capture (simulated)", P),
    ("7.08", "CMIS support", "M", "NC", "10 · Admin (disclosed as not native)", N),
    ("7.09, 2.2.10.10", "Compliance engine (ISO, CARF, MOPH, MOF)", "M", "CC", "7 · Audit › Audit Readiness", P),
    ("2.2.10.4", "EMR integration — secure patient document upload", "M", "—", "10 · Admin › EMR (simulated)", P),
    ("8.01-8.06", "AI platform, LLM assistant, cross-document Q&A, translation", "O", "SM", "—", N),
    ("9.01, 9.04", "Built-in scanning, zonal OCR", "O", "CC", "2 · OCR › Capture controls", D),
    ("9.03, 9.05, 9.14, 9.16", "OCR English + Arabic, operator verification, manual correction", "M", "C", "2 · OCR (real Tesseract)", D),
    ("9.06, 9.15", "Barcode / ICR capture; machine-learning adaptation", "O", "CC/SM", "—", N),
    ("9.07, 9.13", "Attribute mapping; upload to multiple locations", "M", "C", "2 · OCR", D),
    ("9.08-9.12", "Zoom, re-scan, brightness/contrast, batch separation, de-skew/de-speckle", "M", "CC", "2 · OCR › Capture controls", P),
    ("10.01", "Mobile / tablet access", "O", "C", "Responsive layout + ☰ Menu", D),
    ("11.01-11.02", "Backup, restore to user-defined recovery point", "M", "C", "10 · Admin › Backup & Recovery", D),
    ("2.4.1-2.4.3", "Incoming / outgoing mail coding, registration, copies, tracking", "M", "C", "1 · Correspondence (+ dispatch tracker)", D),
    ("2.4.5, 2.4.6", "Intermediate / physical records, external storage", "M", "CC", "8 · Records › Physical records", D),
    ("2.2.7", "Migration from SharePoint & shared drives", "M", "C", "— (project phase)", N),
]

df = pd.DataFrame(ROWS, columns=["RFP ref", "Requirement group", "M/O", "Proposal key", "Where in demo", "Demo status"])
n = len(df)
c1, c2, c3, c4 = st.columns(4)
theme.metric_card("Requirement groups", n, c1)
theme.metric_card("Demonstrated", int((df["Demo status"] == D).sum()), c2)
theme.metric_card("Partly demonstrated", int((df["Demo status"] == P).sum()), c3)
theme.metric_card("Not in demo", int((df["Demo status"] == N).sum()), c4)
st.write("")
pick = st.multiselect("Filter by demo status", [D, P, N], default=[D, P, N])
view = df[df["Demo status"].isin(pick)]
st.dataframe(view, use_container_width=True, hide_index=True, height=520)
st.download_button("⬇ Export traceability matrix (CSV)", view.to_csv(index=False).encode("utf-8-sig"), "rfp_traceability.csv")
st.caption("Proposal key: C = compliant out-of-box · CC = by customisation/configuration · SM = separate module · NC = not compliant. "
           "Items marked 'simulated' show the behaviour and audit trail without connecting to live external systems.")
