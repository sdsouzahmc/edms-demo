import streamlit as st
import db

st.set_page_config(page_title="EDMS Demo", page_icon="📁", layout="wide")
db.init_db()
db.ensure_seeded()

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
]

pg = st.navigation(pages, position="hidden")
pg.run()
