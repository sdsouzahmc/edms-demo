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

from rfp_data import DEPARTMENTS, ROLES  # noqa: E402

CLASSIFICATIONS = ["Internal", "External", "Regulatory"]
SECURITY_LEVELS = ["Public", "Internal", "Restricted", "Confidential"]
WORKFLOW_STAGES = ["Draft", "Department Review", "Approval", "Finance Sign-off", "Released"]

CURRENT_USER_KEY = "current_user"


AR = {
    "Home / Lifecycle Story": "الرئيسية", "Home": "الرئيسية",
    "1 · Correspondence & Intake": "١ · المراسلات والاستلام", "2 · OCR & Intelligent Capture": "٢ · التعرف الضوئي والالتقاط الذكي",
    "3 · Document Control & Versioning": "٣ · التحكم بالوثائق والإصدارات", "4 · Workflow & Approvals": "٤ · سير العمل والاعتمادات",
    "5 · Security & Compliance": "٥ · الأمن والامتثال", "6 · Search & Retrieval": "٦ · البحث والاسترجاع",
    "7 · Audit, Governance & Reporting": "٧ · التدقيق والحوكمة والتقارير", "8 · Records, Archiving & Disposal": "٨ · السجلات والأرشفة والإتلاف",
    "9 · My Workspace": "٩ · مساحة عملي", "10 · Administration & Integrations": "١٠ · الإدارة والتكامل",
    "11 · RFP Coverage": "١١ · مصفوفة الامتثال",
    "Enterprise Document Management System — Working Demo": "نظام إدارة الوثائق المؤسسي — عرض تشغيلي",
    "Total Documents": "إجمالي الوثائق", "Released": "الوثائق المصدرة", "Pending Approval": "بانتظار الاعتماد",
    "Archived": "المؤرشفة", "Expiring ≤90 days": "تنتهي خلال ٩٠ يوماً", "Rejected": "المرفوضة",
    "Enterprise Document Management System": "نظام إدارة الوثائق المؤسسي", "Viewing as": "المستخدم الحالي",
    "My Workspace": "مساحة عملي", "Administration & Integrations": "الإدارة والتكامل",
    "Draft": "مسودة", "Department Review": "مراجعة القسم", "Approval": "اعتماد", "Finance Sign-off": "اعتماد مالي",
    "Documents visible to this user": "الوثائق المتاحة للمستخدم", "Language": "اللغة",
}


def lang() -> str:
    return st.session_state.get("lang", "en")


def tr(text: str) -> str:
    """Translate UI strings to Arabic when the Arabic interface is selected (RFP 2.3.9 / 3.09)."""
    if lang() == "ar":
        return AR.get(text, text)
    return text


def current_user() -> str:
    return st.session_state.get(CURRENT_USER_KEY, "Sara Al-Ansari")


def current_profile() -> dict:
    return ROLES.get(current_user(), ROLES["Sara Al-Ansari"])


def is_admin() -> bool:
    return current_profile()["level"] == "admin"


def inject_css():
    RTL_CSS = '[data-testid="stMain"], [data-testid="stSidebar"] { direction: rtl; text-align: right; }' if lang() == 'ar' else ''
    st.markdown(f"""
    <style>
    [data-testid="stSidebarNav"] {{ display: none; }}
    {RTL_CSS}
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

    @media (max-width: 768px) {{
        .block-container {{ padding: 3.2rem 0.8rem 2rem 0.8rem !important; }}
        .efs-topbar {{ flex-direction: column; align-items: flex-start; gap: 8px; padding: 12px 14px; }}
        .efs-topbar h1 {{ font-size: 1.05rem; }}
        .efs-badge {{ font-size: 0.7rem; }}
        .efs-metric .val {{ font-size: 1.25rem; }}
        .efs-card {{ padding: 12px 12px; overflow-wrap: anywhere; }}
        .efs-step {{ font-size: 0.7rem; padding: 4px 8px; }}
        .stButton button {{ width: 100%; min-height: 44px; }}
        div[data-testid="stHorizontalBlock"] {{ gap: 0.6rem; flex-wrap: wrap !important; }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
            min-width: 100% !important; flex: 1 1 100% !important; }}
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(4)) > div[data-testid="stColumn"] {{
            min-width: calc(50% - 0.6rem) !important; flex: 1 1 calc(50% - 0.6rem) !important; }}
        .efs-metric {{ padding: 8px 12px; margin-bottom: 0.4rem; }}
        .stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] {{ overflow-x: auto; }}
    }}
    .st-key-mobilenav {{ display: none; }}
    @media (max-width: 768px) {{ .st-key-mobilenav {{ display: block; }} }}
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
            <h1>{tr(title)}</h1>
            <div class="sub">{tr(subtitle)}</div>
        </div>
        <div class="efs-badge">👤 {current_user()} &nbsp;·&nbsp; {prof['role']} &nbsp;·&nbsp; {prof['dept']}</div>
    </div>
    """, unsafe_allow_html=True)


def metric_card(label, value, col=None):
    target = col if col is not None else st
    target.markdown(f"""
    <div class="efs-metric"><div class="val">{value}</div><div class="lbl">{tr(label)}</div></div>
    """, unsafe_allow_html=True)


PAGE_FILES = {
    "home": "home_view.py", "1": "wg1_correspondence.py", "2": "wg2_ocr.py", "3": "wg3_document_control.py",
    "4": "wg4_workflow.py", "5": "wg5_security.py", "6": "wg6_search.py", "7": "wg7_audit.py",
    "8": "wg8_records.py", "9": "wg9_workspace.py", "10": "wg10_admin.py", "11": "wg11_coverage.py", "12": "wg12_distribution.py",
    "13": "wg13_analytics.py",
}
NAV = [("home", "🏠 Home / Lifecycle Story"), ("1", "1 · Correspondence & Intake"), ("2", "2 · OCR & Intelligent Capture"),
       ("3", "3 · Document Control & Versioning"), ("4", "4 · Workflow & Approvals"), ("5", "5 · Security & Compliance"),
       ("6", "6 · Search & Retrieval"), ("7", "7 · Audit, Governance & Reporting"), ("8", "8 · Records, Archiving & Disposal"),
       ("9", "9 · My Workspace"), ("10", "10 · Administration & Integrations"), ("11", "11 · RFP Coverage"), ("12", "12 · Auto-Distribution"),
       ("13", "13 · Analytics & Insights")]


def _label(label):
    emoji = label.split(" ")[0] if label[0] in "🏠" else ""
    core = label.replace("🏠 ", "")
    return (emoji + " " if emoji else "") + tr(core)


def sidebar_nav():
    names = list(ROLES.keys())
    current = current_user()
    with st.sidebar:
        st.markdown("### 📁 EDMS Demo")
        st.caption(tr("Enterprise Document Management System"))
        with st.form("quick_search", clear_on_submit=True):
            qs = st.text_input("Quick search", placeholder="🔎 Search documents & scans", label_visibility="collapsed", key="qs_sidebar")
            go = st.form_submit_button("Search", use_container_width=True)
        if go and qs.strip():
            st.session_state["global_q"] = qs.strip()
            st.switch_page(PAGE_FILES["6"])
        st.divider()
        for k, label in NAV:
            st.page_link(PAGE_FILES[k], label=_label(label))
        st.divider()
        st.caption(tr("Language"))
        pick = st.radio("Language", ["English", "العربية"], index=0 if lang() == "en" else 1,
                        horizontal=True, label_visibility="collapsed", key="lang_radio")
        new_lang = "en" if pick == "English" else "ar"
        if new_lang != lang():
            st.session_state["lang"] = new_lang
            st.rerun()
        st.caption(tr("Viewing as"))
        choice = st.selectbox("Switch user / role", names, index=names.index(current), label_visibility="collapsed")
        if choice != current:
            st.session_state[CURRENT_USER_KEY] = choice
            st.rerun()
        prof = ROLES[choice]
        st.caption(f"{prof['role']} · {prof['dept']}")
        try:
            import db_ext
            unread = len(db_ext.get_notifications(choice, only_unread=True))
            if unread:
                st.page_link(PAGE_FILES["9"], label=f"🔔 {unread} new notification(s)")
        except Exception:
            pass
    # mobile-only quick menu (sidebar is collapsed on phones)
    with st.container(key="mobilenav"):
        with st.expander("☰ Menu · pages & switch user"):
            for k, label in NAV:
                st.page_link(PAGE_FILES[k], label=_label(label))
            m_choice = st.selectbox("Viewing as", names, index=names.index(choice), key="m_user")
            if m_choice != choice:
                st.session_state[CURRENT_USER_KEY] = m_choice
                st.rerun()
