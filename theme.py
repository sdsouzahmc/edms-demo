"""Shared design tokens, CSS injection, and small UI helpers for the EDMS demo."""
import streamlit as st

NAVY = "#1F3864"
NAVY_DARK = "#152845"
TEAL = "#2E8B8B"      # Microsoft-native components (SharePoint, Power Automate, Power BI, AD/SSO)
CORAL = "#C0603C"     # Tradify-custom built components (OCR pipeline, QR verification, custom portal)
GREEN = "#2E7D32"
AMBER = "#B8860B"
RED = "#B00020"
GREY = "#6B7280"
BG = "#F4F6F9"
CARD = "#FFFFFF"
BORDER = "#E2E6EC"

DEPARTMENTS = [
    "Medical Records", "Human Resources", "Finance", "Procurement",
    "Facilities", "Clinical Operations",
]

CLASSIFICATIONS = ["Internal", "External", "Regulatory"]

SECURITY_LEVELS = ["Public", "Internal", "Restricted", "Confidential"]

WORKFLOW_STAGES = ["Draft", "Department Review", "Approval", "Finance Sign-off", "Released"]

ROLES = {
    "Sara Al-Ansari": {"role": "Records Officer", "dept": "Medical Records", "level": "department_user",
                        "can_approve": True},
    "Omar Al-Kaabi": {"role": "HR User", "dept": "Human Resources", "level": "department_user",
                       "can_approve": True},
    "Fatima Al-Sulaiti": {"role": "Finance User", "dept": "Finance", "level": "department_user",
                           "can_approve": True},
    "Yusuf Al-Marri": {"role": "Administrator", "dept": "IT", "level": "admin",
                        "can_approve": True},
}

CURRENT_USER_KEY = "current_user"


def current_user() -> str:
    return st.session_state.get(CURRENT_USER_KEY, "Sara Al-Ansari")


def current_profile() -> dict:
    return ROLES.get(current_user(), ROLES["Sara Al-Ansari"])


def is_admin() -> bool:
    return current_profile()["level"] == "admin"


def inject_css():
    st.markdown(f"""
    <style>
    [data-testid="stSidebarNav"] {{ display: none; }}
    html, body, [class*="css"] {{ font-family: 'Segoe UI', -apple-system, sans-serif; }}
    .stApp {{ background: {BG}; }}

    .efs-topbar {{
        background: linear-gradient(90deg, {NAVY} 0%, {NAVY_DARK} 100%);
        color: white; padding: 14px 22px; border-radius: 10px; margin-bottom: 18px;
        display: flex; justify-content: space-between; align-items: center;
    }}
    .efs-topbar h1 {{ font-size: 1.25rem; margin: 0; color: white; }}
    .efs-topbar .sub {{ font-size: 0.8rem; opacity: 0.85; margin-top: 2px; }}
    .efs-badge {{
        background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px;
        font-size: 0.75rem; color: white;
    }}

    .efs-card {{
        background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
        padding: 16px 18px; margin-bottom: 12px;
    }}
    .efs-metric {{
        background: {CARD}; border: 1px solid {BORDER}; border-left: 4px solid {TEAL};
        border-radius: 8px; padding: 12px 16px;
    }}
    .efs-metric .val {{ font-size: 1.6rem; font-weight: 700; color: {NAVY}; }}
    .efs-metric .lbl {{ font-size: 0.78rem; color: {GREY}; text-transform: uppercase; letter-spacing: .04em; }}

    .efs-pill {{
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 0.72rem; font-weight: 600; letter-spacing: .02em;
    }}
    .pill-draft {{ background: #EEF0F4; color: {GREY}; }}
    .pill-review {{ background: #FFF4E0; color: {AMBER}; }}
    .pill-approval {{ background: #FFE9DD; color: {CORAL}; }}
    .pill-finance {{ background: #E3ECFB; color: {NAVY}; }}
    .pill-released {{ background: #E6F4EA; color: {GREEN}; }}
    .pill-rejected {{ background: #FBE3E7; color: {RED}; }}
    .pill-archived {{ background: #EDE7F6; color: #5E35B1; }}
    .pill-disposed {{ background: #F0F0F0; color: #888; }}

    .efs-tag-ms {{ background: #E3F2F2; color: {TEAL}; padding: 1px 8px; border-radius: 10px; font-size: 0.68rem; font-weight: 600; }}
    .efs-tag-custom {{ background: #FBEAE3; color: {CORAL}; padding: 1px 8px; border-radius: 10px; font-size: 0.68rem; font-weight: 600; }}

    .efs-section-title {{
        color: {NAVY}; font-weight: 700; font-size: 1.05rem; margin: 6px 0 10px 0;
        border-bottom: 2px solid {TEAL}; padding-bottom: 6px;
    }}
    .efs-stepper {{ display:flex; align-items:center; gap:4px; flex-wrap:wrap; margin: 10px 0; }}
    .efs-step {{
        background:#EEF0F4; color:{GREY}; padding:6px 12px; border-radius:16px; font-size:0.78rem; font-weight:600;
    }}
    .efs-step.done {{ background:{GREEN}; color:white; }}
    .efs-step.active {{ background:{CORAL}; color:white; }}
    .efs-arrow {{ color:{BORDER}; font-size: 1rem; }}

    div[data-testid="stMetricValue"] {{ color: {NAVY}; }}
    .stButton button[kind="primary"] {{ background: {CORAL}; border-color: {CORAL}; }}
    </style>
    """, unsafe_allow_html=True)


def pill(status: str) -> str:
    mapping = {
        "Draft": "pill-draft", "Department Review": "pill-review", "Approval": "pill-approval",
        "Finance Sign-off": "pill-finance", "Released": "pill-released", "Rejected": "pill-rejected",
        "Archived": "pill-archived", "Disposed": "pill-disposed",
    }
    cls = mapping.get(status, "pill-draft")
    return f'<span class="efs-pill {cls}">{status}</span>'


def tag_ms(label="Microsoft 365 native"):
    return f'<span class="efs-tag-ms">{label}</span>'


def tag_custom(label="Tradify custom build"):
    return f'<span class="efs-tag-custom">{label}</span>'


def topbar(title: str, subtitle: str = ""):
    prof = current_profile()
    st.markdown(f"""
    <div class="efs-topbar">
        <div>
            <h1>{title}</h1>
            <div class="sub">{subtitle}</div>
        </div>
        <div class="efs-badge">👤 {current_user()} &nbsp;·&nbsp; {prof['role']} &nbsp;·&nbsp; {prof['dept']}</div>
    </div>
    """, unsafe_allow_html=True)


def metric_card(label, value, col=None):
    target = col if col is not None else st
    target.markdown(f"""
    <div class="efs-metric"><div class="val">{value}</div><div class="lbl">{label}</div></div>
    """, unsafe_allow_html=True)


PAGE_FILES = {
    "home": "home_view.py",
    "1": "wg1_correspondence.py",
    "2": "wg2_ocr.py",
    "3": "wg3_document_control.py",
    "4": "wg4_workflow.py",
    "5": "wg5_security.py",
    "6": "wg6_search.py",
    "7": "wg7_audit.py",
    "8": "wg8_records.py",
}


def sidebar_nav():
    with st.sidebar:
        st.markdown(f"### 📁 EDMS Demo")
        st.caption("Enterprise Document Management System")
        st.divider()
        st.page_link(PAGE_FILES["home"], label="🏠 Home / Lifecycle Story", icon=None)
        st.page_link(PAGE_FILES["1"], label="1 · Correspondence & Intake")
        st.page_link(PAGE_FILES["2"], label="2 · OCR & Intelligent Capture")
        st.page_link(PAGE_FILES["3"], label="3 · Document Control & Versioning")
        st.page_link(PAGE_FILES["4"], label="4 · Workflow & Approvals")
        st.page_link(PAGE_FILES["5"], label="5 · Security & Compliance")
        st.page_link(PAGE_FILES["6"], label="6 · Search & Retrieval")
        st.page_link(PAGE_FILES["7"], label="7 · Audit, Governance & Reporting")
        st.page_link(PAGE_FILES["8"], label="8 · Records, Archiving & Disposal")
        st.divider()
        st.caption("Viewing as")
        names = list(ROLES.keys())
        current = current_user()
        choice = st.selectbox("Switch user / role", names, index=names.index(current),
                               label_visibility="collapsed")
        if choice != current:
            st.session_state[CURRENT_USER_KEY] = choice
            st.rerun()
        prof = ROLES[choice]
        st.caption(f"{prof['role']} · {prof['dept']}")
