import streamlit as st
import db
import db_ext

st.set_page_config(page_title="EDMS Demo", page_icon="📁", layout="wide")
import os, glob
# one-time reset if a database from an older demo version is present
_marker = os.path.join(db.DB_DIR, ".seed_rfp2")
if os.path.exists(db.DB_PATH) and not os.path.exists(_marker):
    for _f in glob.glob(db.DB_PATH + "*"):
        try:
            os.remove(_f)
        except OSError:
            pass
os.makedirs(db.DB_DIR, exist_ok=True)
db.init_db()
db_ext.init_ext()
db.ensure_seeded()
import wfdesign
wfdesign.seed_samples()
open(_marker, 'w').write('rfp2')

import demo_journey
demo_journey.auto_load()   # sample documents + their movement are present from the first visit

# public secure-exchange portal: opened from an emailed link, no EDMS login
_x = st.query_params.get("x")
if _x:
    import external_portal
    external_portal.render(_x)
    st.stop()

_v = st.query_params.get("v")
if _v:
    import external_portal
    external_portal.render_verify(_v)
    st.stop()

pages = [
    st.Page("home_view.py", title="Home", icon="🏠", default=True),
    st.Page("wg1_correspondence.py", title="1 · Correspondence & Intake"),
    st.Page("wg2_ocr.py", title="2 · OCR & Intelligent Capture"),
    st.Page("wg3_document_control.py", title="3 · Document Control & Versioning"),
    st.Page("wg4_workflow.py", title="4 · Workflow & Approvals"),
    st.Page("wg5_security.py", title="5 · Security & Compliance"),
    st.Page("wg6_search.py", title="6 · Search & Retrieval"),
    st.Page("wg7_audit.py", title="7 · Audit, Governance & Reporting"),
    st.Page("wg8_records.py", title="8 · Records, Archiving & Disposal"),
    st.Page("wg9_workspace.py", title="9 · My Workspace"),
    st.Page("wg10_admin.py", title="10 · Administration & Integrations"),
    st.Page("wg11_coverage.py", title="11 · RFP Coverage"),
    st.Page("wg12_distribution.py", title="12 · Auto-Distribution"),
    st.Page("wg13_analytics.py", title="13 · Analytics & Insights"),
    st.Page("wg14_users.py", title="14 · User Management"),
    st.Page("wg15_roles.py", title="15 · Role Management"),
    st.Page("wg16_assistant.py", title="16 · Ask EDMS"),
    st.Page("wg17_workflow_designer.py", title="17 · Workflow Designer"),
    st.Page("wg18_numbering.py", title="18 · Numbering Rules"),
    st.Page("wg19_delegation.py", title="19 · Approval Delegation"),
    st.Page("wg20_exchange.py", title="20 · Secure Exchange"),
    st.Page("wg21_folders.py", title="21 · Folders & Classification"),
    st.Page("wg22_migration.py", title="22 · Data Migration"),
    st.Page("wg23_signature.py", title="23 · My Signature & Certificate"),
]

pg = st.navigation(pages, position="hidden")
pg.run()
