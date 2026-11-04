"""Shared design tokens, CSS injection, and small UI helpers for the EDMS demo."""
import re
import streamlit as st
import i18n
i18n.install()

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
        return AR.get(text) or i18n.translate(text)
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
    .efs-nbs {{ display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }}
    .efs-nb {{ display:inline-flex; align-items:center; gap:5px; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.28); border-radius:20px; padding:3px 4px 3px 9px; font-size:.72rem; color:#fff; }}
    .efs-nb .n {{ background:var(--c); color:#fff; font-weight:800; border-radius:12px; min-width:22px; text-align:center; padding:1px 7px; font-size:.74rem; box-shadow:0 0 0 2px rgba(255,255,255,.55); }}
    .efs-nb .e {{ font-size:.85rem; }}
    @media (max-width: 900px) {{ .efs-nb .l {{ display:none; }} }}
    #MainMenu, footer, [data-testid="stToolbarActions"], [data-testid="stDeployButton"], [data-testid="stAppDeployButton"],
    [data-testid="stMainMenu"], [data-testid="stStatusWidget"], [data-testid="stDecoration"], .stDeployButton, .viewerBadge_container__r5tak,
    [class*="viewerBadge"], [data-testid="stHeaderActionElements"] {{ display: none !important; visibility: hidden !important; }}
    header[data-testid="stHeader"] {{ background: transparent !important; height: 2.2rem; }}
    [data-testid="stToolbar"] {{ display: flex !important; visibility: visible !important; }}
    [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {{
        display: flex !important; visibility: visible !important; opacity: 1 !important; }}
    html body button[data-testid="stExpandSidebarButton"] {{ background: #FFFFFF !important; color: #1F3864 !important; border: 1px solid #1F3864 !important; border-radius: 10px !important; padding: 6px 8px !important; box-shadow: 0 2px 6px rgba(31,56,100,.25); }}
    html body button[data-testid="stExpandSidebarButton"] *, html body button[data-testid="stExpandSidebarButton"] svg {{ fill: #1F3864 !important; color: #1F3864 !important; }}
    {RTL_CSS}
    html, body, [class*="css"] {{ font-family: 'Segoe UI', -apple-system, sans-serif; }}
    .stApp {{ background: {BG}; }}

    .efs-topbar {{
        background:
          radial-gradient(circle at 92% 20%, rgba(127,209,199,.28) 0, rgba(127,209,199,0) 38%),
          radial-gradient(circle at 8% 120%, rgba(255,255,255,.10) 0, rgba(255,255,255,0) 40%),
          linear-gradient(100deg, {NAVY_DARK} 0%, {NAVY} 52%, #1F6F78 100%);
        color: white; padding: 16px 22px; border-radius: 14px; margin-bottom: 18px;
        display: flex; justify-content: space-between; align-items: center; gap: 12px;
        box-shadow: 0 6px 18px rgba(21,40,69,.18);
    }}
    .efs-topicon {{ display:inline-flex; align-items:center; justify-content:center; width:46px; height:46px; border-radius:13px;
        background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.25); flex:none; }}
    .efs-hero {{ display:grid; grid-template-columns: 1.25fr 1fr; gap: 10px; align-items:center;
        background: linear-gradient(110deg, {NAVY_DARK} 0%, {NAVY} 55%, #1F6F78 100%); color:#fff; border-radius:16px;
        padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 8px 22px rgba(21,40,69,.22); overflow:hidden; }}
    .efs-hero h2 {{ color:#fff; margin:0 0 6px 0; font-size:1.55rem; line-height:1.2; }}
    .efs-hero p {{ margin:0 0 12px 0; opacity:.9; font-size:.92rem; }}
    .efs-hero .chips span {{ display:inline-block; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25);
        border-radius:20px; padding:3px 11px; font-size:.74rem; margin:0 6px 6px 0; }}
    .efs-del {{ background:#FBE3E7; color:{RED}; text-decoration:line-through; padding:0 3px; border-radius:3px; }}
    .efs-ins {{ background:#E1F3E4; color:{GREEN}; padding:0 3px; border-radius:3px; font-weight:600; }}
    .efs-old {{ background:#FBE3E7; color:{RED}; text-decoration:line-through; padding:2px 8px; border-radius:6px; font-size:.8rem; }}
    .efs-new {{ background:#E1F3E4; color:{GREEN}; padding:2px 8px; border-radius:6px; font-size:.8rem; font-weight:600; }}
    .efs-tl {{ display:flex; gap:12px; padding: 12px 14px; background:{CARD}; border:1px solid {BORDER}; border-left:4px solid var(--c,{TEAL});
        border-radius:12px; margin-bottom:10px; box-shadow:0 1px 3px rgba(31,56,100,.05); transition: box-shadow .15s, transform .15s; }}
    .efs-tl:hover {{ box-shadow:0 6px 16px rgba(31,56,100,.12); transform: translateY(-1px); }}
    .efs-tl .t {{ font-weight:700; color:{NAVY}; }}
    .efs-tl .m {{ font-size:.78rem; color:{GREY}; margin-top:3px; display:flex; flex-wrap:wrap; gap:4px 12px; align-items:center; }}
    .efs-hash {{ font-family: ui-monospace, Menlo, monospace; font-size:.7rem; background:#EEF2F7; color:{NAVY}; padding:1px 6px; border-radius:5px; }}
    @media (max-width: 768px) {{ .efs-hero {{ grid-template-columns: 1fr; }} .efs-topicon {{ width:38px; height:38px; }} }}
    .efs-topbar h1 {{ font-size: 1.25rem; margin: 0; color: white; }}
    .efs-topbar .sub {{ font-size: 0.8rem; opacity: 0.85; margin-top: 2px; }}
    .efs-badge {{
        background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px;
        font-size: 0.75rem; color: white;
    }}

    .efs-card {{
        background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
        padding: 16px 18px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(31,56,100,.06);
    }}
    .efs-metric {{
        background: {CARD}; border: 1px solid {BORDER}; border-left: 4px solid {TEAL};
        border-radius: 10px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(31,56,100,.06);
        background: linear-gradient(180deg, #FFFFFF 0%, #F7FAFB 100%);
    }}
    .efs-metric .val {{ font-size: 1.6rem; font-weight: 700; color: {NAVY}; }}
    .efs-metric .lbl {{ overflow-wrap: normal; word-break: normal; hyphens: none; font-size: 0.72rem; color: {GREY}; text-transform: uppercase; letter-spacing: .04em; }}

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
    import icons
    prof = current_profile()
    key = title.split(" ")[0].strip("·") if title[:1].isdigit() else "home"
    ic = icons.svg(icons.PAGE_ICON.get(key, "document"), 26, "#FFFFFF", 1.6)
    check_access(key)
    import badges
    bc = badges.counts(current_user(), prof["dept"], is_admin())
    chips = "".join(
        f'<span class="efs-nb" title="{lbl}" style="--c:{col}"><span class="e">{em}</span><span class="l">{tr(lbl)}</span><span class="n">{bc[k]}</span></span>'
        for k, lbl, em, col, _p in badges.CHIPS if bc.get(k))
    st.markdown(f"""
    <div class="efs-topbar">
        <div style="display:flex;gap:14px;align-items:center">
            <span class="efs-topicon">{ic}</span>
            <div><h1>{strip_no(tr(title))}</h1><div class="sub">{tr(subtitle)}</div></div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end"><div class="efs-nbs">{chips}</div></div>
    </div>
    """, unsafe_allow_html=True)
    breadcrumb(key)


def breadcrumb(key):
    """Home › Journey group › Page — Home and the group are clickable so the user can step back."""
    if key == "home" or key not in PAGE_FILES:
        return
    import favs
    me = current_user()
    if st.session_state.get("_last_page") != key:         # count a visit once per navigation, not per rerun
        st.session_state["_last_page"] = key
        favs.track(me, key)
    is_f = favs.is_fav(me, key)
    grp = next((g for g in GROUPS if key in g[3]), None)
    page = strip_no(tr(dict(NAV).get(key, key)))
    st.markdown("""<style>.st-key-efs_bc{margin:-6px 0 6px 0}.st-key-efs_bc{flex-direction:row!important;flex-wrap:wrap;align-items:center;gap:4px!important}.st-key-efs_bc>div{width:auto!important;flex:0 0 auto!important}.st-key-efs_bc button{margin-left:14px;padding:2px 12px;min-height:0;font-size:.8rem}.st-key-efs_bc a,.st-key-efs_bc p{font-size:.82rem!important;margin:0!important;white-space:nowrap}
    .st-key-efs_bc [data-testid=stPageLink] a{padding:2px 8px;border-radius:14px;background:#EEF3F8;color:#1F3864}
    .st-key-efs_bc [data-testid=stPageLink] a:hover{background:#DCE7F3}.efs-bc-sep{color:#9CA3AF;padding-top:3px}
    .efs-bc-cur{font-weight:700;color:#1F3864;padding:2px 8px}</style>""", unsafe_allow_html=True)
    with st.container(key="efs_bc"):
        st.page_link(PAGE_FILES["home"], label=tr("Home"), icon="🏠")
        if grp:
            st.markdown("<span class='efs-bc-sep'>›</span>", unsafe_allow_html=True)
            st.page_link(PAGE_FILES[grp[3][0]], label=tr(grp[0]), icon=grp[1])
        st.markdown("<span class='efs-bc-sep'>›</span>", unsafe_allow_html=True)
        st.markdown(f"<span class='efs-bc-cur'>{page}</span>", unsafe_allow_html=True)
        st.button(("★ " + tr("In favourites")) if is_f else ("☆ " + tr("Add to favourites")), key="fav_toggle",
                  help=tr("Pin this page to the top of your menu"), on_click=favs.toggle, args=(me, key))


def _mark_read(user):
    import db_ext
    db_ext.mark_all_read(user)


def alerts_bar(current, prof, allowed, bc):
    """Pinned strip (stays visible while scrolling): quick actions, alerts bell and the signed-in user."""
    import accounts, badges, db_ext, icons
    unread = db_ext.get_notifications(current, only_unread=True)
    n = len(unread)
    st.markdown("""<style>
    .st-key-alertbar{position:fixed!important;top:10px;right:64px;z-index:1000000;display:flex!important;flex-direction:row!important;flex-wrap:nowrap;justify-content:flex-end;width:auto!important;
      align-items:center;gap:10px!important;background:rgba(244,246,250,.95);backdrop-filter:blur(6px);padding:5px 10px;border-radius:34px;border:1px solid #E3E8F0;box-shadow:0 4px 14px rgba(31,56,100,.12)}
    @media (max-width:768px){.st-key-alertbar{position:static!important;margin-bottom:6px;flex-wrap:wrap;border-radius:14px}}
    .st-key-alertbar>div{width:auto!important;flex:0 0 auto!important}
    .st-key-alertbar button[kind=secondary],.st-key-alertbar [data-testid=stPopover] button{border-radius:20px;padding:3px 14px;min-height:0;font-weight:600}
    .st-key-alertbar .efs-upill{display:flex;align-items:center;gap:9px;background:#fff;border:1px solid #E3E8F0;border-radius:30px;padding:4px 14px 4px 5px}
    .efs-arow{display:flex;gap:8px;font-size:.84rem;padding:5px 0;border-bottom:1px dashed #E5E7EB}.efs-arow .t{color:#9CA3AF;font-size:.72rem}
    </style>""", unsafe_allow_html=True)
    with st.container(key="alertbar"):
        # ---- quick actions
        items = [("4", "✍️", "Approvals waiting for me", bc.get("pending", 0)), ("1", "📥", "Register a new document", 0),
                 ("6", "🔎", "Search documents", 0), ("20", "🔐", "Send securely / request upload", bc.get("xdept", 0)),
                 ("12", "📬", "Triage queue", bc.get("triage", 0)), ("23", "🖋️", "My signature & PIN", 0), ("19", "🏖️", "Set a delegate (leave)", 0)]
        with st.popover("⚡ " + tr("Quick actions")):
            for k, em, lab, cnt in items:
                if k in allowed and k in PAGE_FILES:
                    st.page_link(PAGE_FILES[k], label=tr(lab) + (f"  ({cnt})" if cnt else ""), icon=em)
        # ---- alerts bell
        with st.popover(f"🔔 {n}" if n else "🔔"):
            st.markdown(f"**{tr('Needs your attention')}**")
            attn = [("✍️", "Awaiting approval", bc.get("pending", 0), "4"), ("⏰", "SLA overdue", bc.get("overdue", 0), "4"),
                    ("🔁", "Inter-dept requests", bc.get("xdept", 0), "20"), ("📥", "Triage queue", bc.get("triage", 0), "12")]
            shown = False
            for em, lab, cnt, k in attn:
                if cnt and k in allowed:
                    shown = True
                    st.page_link(PAGE_FILES[k], label=f"{tr(lab)} — {cnt}", icon=em)
            if not shown:
                st.caption(tr("Nothing needs your attention right now."))
            st.markdown(f"**{tr('New notifications')}**")
            if not unread:
                st.caption(tr("You are all caught up."))
            for r in unread[:6]:
                st.markdown(f"<div class='efs-arow'><div>🔔</div><div>{r['message']}<div class='t'>{(r['ts'] or '')[:16]}</div></div></div>", unsafe_allow_html=True)
            if unread:
                st.button("✔ " + tr("Mark all as read"), key="alerts_markread", on_click=_mark_read, args=(current,), use_container_width=True)
            if "9" in allowed:
                st.page_link(PAGE_FILES["9"], label=tr("Open all notifications"), icon="📨")
        # ---- user
        st.markdown(f"<div class='efs-upill'>{icons.avatar(current, 30, '#2E8B8B')}<div style='line-height:1.15'><div style='font-weight:700;font-size:.85rem;color:{NAVY}'>{current}</div>"
                    f"<div style='font-size:.7rem;color:{GREY}'>{prof['role']} · {prof['dept']}</div></div></div>", unsafe_allow_html=True)


def userbar():
    return                                   # the signed-in user now lives in the pinned alerts bar
    import icons
    prof = current_profile()
    st.markdown(f"""<div style="display:flex;justify-content:flex-end;margin-bottom:8px"><div style="display:flex;align-items:center;gap:10px;background:#fff;
    border:1px solid {BORDER};border-radius:30px;padding:5px 16px 5px 6px;box-shadow:0 1px 3px rgba(31,56,100,.08)">{icons.avatar(current_user(), 34, "#2E8B8B")}
    <div style="line-height:1.2"><div style="font-weight:700;color:{NAVY};font-size:.9rem">Welcome, {current_user()}</div>
    <div style="font-size:.74rem;color:{GREY}">{prof['role']} · {prof['dept']}</div></div></div></div>""", unsafe_allow_html=True)


def metric_card(label, value, col=None):
    target = col if col is not None else st
    target.markdown(f"""
    <div class="efs-metric"><div class="val">{value}</div><div class="lbl">{tr(label)}</div></div>
    """, unsafe_allow_html=True)


PAGE_FILES = {
    "home": "home_view.py", "1": "wg1_correspondence.py", "2": "wg2_ocr.py", "3": "wg3_document_control.py",
    "4": "wg4_workflow.py", "5": "wg5_security.py", "6": "wg6_search.py", "7": "wg7_audit.py",
    "8": "wg8_records.py", "9": "wg9_workspace.py", "10": "wg10_admin.py", "11": "wg11_coverage.py", "12": "wg12_distribution.py",
    "13": "wg13_analytics.py", "14": "wg14_users.py", "15": "wg15_roles.py", "16": "wg16_assistant.py", "17": "wg17_workflow_designer.py", "18": "wg18_numbering.py", "19": "wg19_delegation.py", "20": "wg20_exchange.py", "21": "wg21_folders.py", "22": "wg22_migration.py", "23": "wg23_signature.py",
}
NAV = [("home", "Home / Lifecycle Story"), ("1", "1 · Correspondence & Intake"), ("2", "2 · OCR & Intelligent Capture"),
       ("3", "3 · Document Control & Versioning"), ("4", "4 · Workflow & Approvals"), ("5", "5 · Security & Compliance"),
       ("6", "6 · Search & Retrieval"), ("7", "7 · Audit, Governance & Reporting"), ("8", "8 · Records, Archiving & Disposal"),
       ("9", "9 · My Workspace"), ("10", "10 · Administration & Integrations"), ("11", "11 · RFP Coverage"), ("12", "12 · Auto-Distribution"),
       ("13", "13 · Analytics & Insights"),
       ("14", "14 · User Management"), ("15", "15 · Role Management"), ("16", "16 · Ask EDMS — Search Assistant"), ("17", "17 · Workflow Designer"), ("18", "18 · Numbering Rules"), ("19", "19 · Approval Delegation"), ("20", "20 · Secure Exchange"), ("21", "21 · Folders & Classification"), ("22", "22 · Data Migration"), ("23", "23 · My Signature & Certificate")]


# Menu grouped along the end-to-end document journey (page keys stay stable; numbers are no longer shown)
GROUPS = [
    ("Capture & Intake", "📥", "#2E8B8B", ["1", "2", "12", "22"]),
    ("Organise & Control", "🗂️", "#6C4FA3", ["21", "3", "18"]),
    ("Process & Approve", "🔀", "#B8860B", ["4", "23", "17", "19"]),
    ("Share & Collaborate", "🤝", "#C0603C", ["20", "9"]),
    ("Find & Ask", "🔎", "#4A90C2", ["6", "16"]),
    ("Retain & Govern", "🗄️", "#2E7D32", ["8", "5", "7", "13"]),
    ("Administer", "⚙️", "#6B7280", ["14", "15", "10", "11"]),
]
_NUM = re.compile(r"^[0-9\u0660-\u0669]+\s*[\u00b7.]\s*")


def strip_no(s):
    return _NUM.sub("", s)


def _label(label):
    emoji = label.split(" ")[0] if label[0] in "🏠" else ""
    core = label.replace("🏠 ", "")
    return (emoji + " " if emoji else "") + strip_no(tr(core))


def _menu_set(mode):
    st.session_state["menu_mode"] = mode
    st.session_state["menu_ver"] = st.session_state.get("menu_ver", 0) + 1      # new widget identity -> expanders re-open/close


def _current_page_key():
    """Which page file is running right now (so its menu group stays open)."""
    import sys, os
    names = {v: k for k, v in PAGE_FILES.items()}
    f = sys._getframe()
    while f:
        k = names.get(os.path.basename(f.f_code.co_filename))
        if k:
            return k
        f = f.f_back
    return None


def _group_header(i, name, em, col):
    return (f'<div style="margin:12px 0 2px 2px;display:flex;align-items:center;gap:7px;font-size:.68rem;font-weight:800;letter-spacing:.06em;'
            f'text-transform:uppercase;color:{col}"><span style="background:{col};color:#fff;border-radius:50%;width:18px;height:18px;display:inline-flex;'
            f'align-items:center;justify-content:center;font-size:.66rem">{i}</span>{em} {tr(name)}<span style="flex:1;height:1px;background:{col}44"></span></div>')


def _on_lang(key):
    st.session_state["lang"] = "en" if st.session_state.get(key) == "English" else "ar"


def _lang_switch(key="lang_radio"):
    # one widget state per radio, always mirrored from the single source of truth ('lang') -> no double render / flicker
    st.session_state[key] = "English" if lang() == "en" else "العربية"
    st.radio("Language", ["English", "العربية"], horizontal=True, label_visibility="collapsed", key=key,
             on_change=_on_lang, args=(key,))


def _login_screen():
    import accounts
    import icons
    st.markdown("""<style>
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], header[data-testid="stHeader"] { display:none !important; }
    .block-container { max-width: 1100px; padding-top: 2rem !important; }
    .efs-lhero { background: linear-gradient(120deg, #152845 0%, #1F3864 55%, #1F6F78 100%); color:#fff; border-radius:18px; padding:28px 28px 22px 28px;
        box-shadow:0 10px 28px rgba(21,40,69,.25); min-height: 420px; }
    .efs-lhero h1 { color:#fff; font-size:1.8rem; line-height:1.2; margin:14px 0 8px 0; }
    .efs-lhero li { margin: 6px 0; font-size:.9rem; opacity:.95; }
    .efs-rolecard { display:flex; gap:10px; align-items:center; background:#fff; border:1px solid #E2E6EC; border-left:5px solid var(--c); border-radius:12px;
        padding:9px 12px; margin-bottom:4px; }
    </style>""", unsafe_allow_html=True)
    _sp, _lg = st.columns([3, 1.3])
    with _lg:
        _lang_switch()
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        st.markdown(f"""<div class="efs-lhero">
        <div style="display:flex;align-items:center;gap:10px">{icons.chip("database", "#7FD1C7", 44)}<div style="font-weight:800;font-size:1.25rem;line-height:1.1">EDMS<br><span style="font-weight:500;font-size:.78rem;opacity:.8">Enterprise Document Management</span></div></div>
        <h1>Sign in to the document workspace</h1>
        <div style="height:150px">{icons.hero_art()}</div>
        <ul style="padding-left:18px;margin-top:10px"><li>Role-based menus — each role sees only what it needs</li>
        <li>Every sign-in and change is written to the immutable audit trail</li><li>Account lock-out after repeated failures</li></ul></div>""", unsafe_allow_html=True)
    with right:
        t1, t2 = st.tabs(["🔑 Sign in", "🎭 Demo access by role"])
        with t1:
            with st.form("login_form"):
                uname = st.text_input("User name", placeholder="e.g. Sara Al-Ansari")
                pw = st.text_input("Password", type="password")
                go = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if go:
                ok, msg = accounts.authenticate(uname, pw)
                if ok:
                    accounts.record_login(msg)
                    st.session_state["auth_user"] = msg
                    st.session_state[CURRENT_USER_KEY] = msg
                    st.rerun()
                else:
                    st.error(msg)
            st.caption(f"Demo accounts share the password **{accounts.DEMO_PASSWORD}**. Five wrong attempts lock an account (an administrator unlocks it).")
        with t2:
            st.caption("One click sign-in for demonstration — pick a person to see the system through that role.")
            us = [u for u in accounts.users() if u["active"]]
            rmap = {r["name"]: r for r in accounts.roles()}
            cols = st.columns(2)
            for i, u in enumerate(us):
                r = rmap.get(u["role"], {"color": "#6B7280", "modules": []})
                with cols[i % 2]:
                    st.markdown(f"""<div class="efs-rolecard" style="--c:{r['color']}">{icons.avatar(u['username'], 36, r['color'])}
                    <div style="line-height:1.2"><b style="color:#1F3864">{u['username']}</b><br><span style="font-size:.76rem;color:#6B7280">{u['role']} · {u['dept']}</span></div></div>""",
                                unsafe_allow_html=True)
                    if st.button(f"Enter as {u['role']}", key=f"qa_{u['username']}", use_container_width=True):
                        st.session_state["auth_user"] = u["username"]
                        st.session_state[CURRENT_USER_KEY] = u["username"]
                        accounts.record_login(u["username"], "Demo quick access")
                        st.rerun()
    st.stop()


def logout():
    import accounts
    accounts.record_logout(current_user())
    for k in ("auth_user", CURRENT_USER_KEY):
        st.session_state.pop(k, None)
    st.rerun()


def check_access(key):
    """Block a page when the signed-in user's role does not include the module."""
    import accounts
    import icons
    if key == "home" or key in accounts.allowed_modules(current_user()):
        return
    label = accounts.MODULES.get(key, (key,))[0]
    st.markdown(f"""<div class="efs-card" style="text-align:center;padding:36px">{icons.chip('lock', '#B00020', 56)}
    <h3 style="color:{NAVY};margin:12px 0 4px 0">Access restricted</h3>
    <div style="color:{GREY}">Your role <b>{current_profile()['role']}</b> does not include <b>{label}</b>.<br>
    Ask an administrator to adjust the role in <i>Role Management</i>, or sign in with a different account.</div></div>""", unsafe_allow_html=True)
    db_log = __import__("db")
    db_log.log_audit(None, current_user(), "Access Denied", f"Tried to open module: {label}", "Denied")
    st.stop()


def sidebar_nav():
    import accounts
    import icons as _ic
    accounts.init_accounts()
    if not st.session_state.get("auth_user") or st.session_state["auth_user"] not in ROLES:
        st.session_state.pop("auth_user", None)
        _login_screen()
    current = st.session_state["auth_user"]
    st.session_state[CURRENT_USER_KEY] = current
    prof = ROLES[current]
    rinfo = accounts.role(prof["role"]) or {"color": "#2E8B8B", "modules": []}
    allowed = accounts.allowed_modules(current) | {"home"}
    menu_css = "".join(
        f'.st-key-nav_{k} a {{ border-left: 5px solid {accounts.MODULES[k][2]}; background: {accounts.MODULES[k][2]}12; border-radius: 10px; margin: 2px 0; padding-left: 10px; }}'
        f'.st-key-nav_{k} a:hover {{ background: {accounts.MODULES[k][2]}26; }}' for k in accounts.MODULES)
    grp_css = "".join(
        f".st-key-grp_{i} [data-testid=stExpander]{{border:none;background:transparent;margin:6px 0 0 0}}"
        f".st-key-grp_{i} [data-testid=stExpander] summary{{padding:0 8px!important;min-height:30px!important;line-height:1.1;border-left:4px solid {g[2]};border-radius:8px;background:{g[2]}14}}"
        f".st-key-grp_{i} [data-testid=stExpander] summary p{{margin:0!important;font-size:.74rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:{g[2]}}}"
        f".st-key-grp_{i} [data-testid=stExpander] details>div{{padding:2px 0 0 4px}}"
        for i, g in enumerate(GROUPS, start=1))
    st.markdown(f"<style>{menu_css}{grp_css}"
                ".st-key-menu_expand button,.st-key-menu_collapse button{min-height:0;padding:2px 4px;font-size:.72rem}"
                ".st-key-favbox{background:#FFF8E1;border:1px solid #F1DFA1;border-radius:12px;padding:6px 8px 4px;margin:6px 0}"
                ".efs-favh{font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#8A6D00;margin:2px 0 0 2px}"
                ".st-key-favbox button{min-height:0;padding:0 6px;font-size:.75rem;border:none;background:transparent;color:#8A6D00}.st-key-fav_restore button{font-size:.7rem;border:1px dashed #E0CC84}.st-key-favbox a{border-radius:8px}.st-key-favbox a p{font-weight:600;font-size:.8rem}"
                ".st-key-navmenu a p { font-weight:600; font-size:.8rem; white-space:normal; line-height:1.15; }"
                '[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] { box-shadow: 0 0 0 2px #1F386433; }'
                "</style>", unsafe_allow_html=True)
    import badges
    _bc = badges.counts(current, prof["dept"], (prof["level"] == "admin"))
    with st.sidebar:
        st.markdown(f'<div style="font-size:.7rem;color:{GREY};margin:-6px 0 -10px 2px">🌐 {tr("Language")}</div>', unsafe_allow_html=True)
        _lang_switch()
        st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0 8px 0">{_ic.chip("database", "#2E8B8B", 38)}<div style="font-weight:800;color:{NAVY};font-size:1.15rem;line-height:1.1">EDMS<br><span style="font-weight:500;font-size:.72rem;color:{GREY}">Working Demo</span></div></div>', unsafe_allow_html=True)
        st.markdown(f"""<div style="background:linear-gradient(120deg,{NAVY} 0%,#1F6F78 100%);border-radius:14px;padding:12px 14px;color:#fff;display:flex;gap:10px;align-items:center;box-shadow:0 4px 12px rgba(21,40,69,.2)">
        {_ic.avatar(current, 42, rinfo['color'])}<div style="line-height:1.25"><div style="font-weight:700">{current}</div>
        <div style="font-size:.74rem;opacity:.9">{prof['role']}</div><div style="font-size:.7rem;opacity:.75">{prof['dept']}</div></div></div>""", unsafe_allow_html=True)
        if st.button("⎋ Sign out", key="logout_btn", use_container_width=True):
            logout()
        with st.form("quick_search", clear_on_submit=True):
            qs = st.text_input("Quick search", placeholder="🔎 Search documents & scans", label_visibility="collapsed", key="qs_sidebar")
            go = st.form_submit_button("Search", use_container_width=True)
        if go and qs.strip():
            st.session_state["global_q"] = qs.strip()
            st.switch_page(PAGE_FILES["6"])
        import favs as _fv
        _fav = [k for k in _fv.favs(current) if k in allowed and k in PAGE_FILES]
        _top = [k for k in _fv.most_used(current, 3, exclude=_fav) if k in allowed and k in PAGE_FILES]
        _lb = dict(NAV)
        _hid = _fv.hidden(current)
        if _fav or _top or _hid:
            with st.container(key="favbox"):
                if _fav:
                    st.markdown(f'<div class="efs-favh">⭐ {tr("Favourites")}</div>', unsafe_allow_html=True)
                    for k in _fav:
                        c1, c2 = st.columns([6, 1], vertical_alignment="center")
                        with c1, st.container(key=f"fav_{k}"):
                            st.page_link(PAGE_FILES[k], label=_label(_lb[k]), icon=accounts.MODULES[k][1])
                        c2.button("✕", key=f"unfav_{k}", help=tr("Remove from favourites"), on_click=_fv.toggle, args=(current, k))
                if _top:
                    st.markdown(f'<div class="efs-favh">🔥 {tr("Most used")}</div>', unsafe_allow_html=True)
                    for k in _top:
                        c1, c2 = st.columns([6, 1], vertical_alignment="center")
                        with c1, st.container(key=f"top_{k}"):
                            st.page_link(PAGE_FILES[k], label=_label(_lb[k]), icon=accounts.MODULES[k][1])
                        c2.button("✕", key=f"hide_{k}", help=tr("Remove from Most used"), on_click=_fv.hide, args=(current, k))
                if _hid:
                    st.button("↺ " + tr("Restore removed shortcuts") + f" ({len(_hid)})", key="fav_restore", on_click=_fv.unhide_all,
                              args=(current,), use_container_width=True)
        with st.container(key="navmenu"):
            _lbl = dict(NAV)
            with st.container(key="nav_home"):
                st.page_link(PAGE_FILES["home"], label=_label(_lbl["home"]), icon=accounts.MODULES["home"][1])
            # ---- collapsible journey groups: "Expand all / Collapse all" + remembered state
            cur = _current_page_key()
            ver = st.session_state.get("menu_ver", 0)
            mode = st.session_state.get("menu_mode", "all")
            b1, b2 = st.columns(2)
            b1.button("▾ " + tr("Expand all"), key="menu_expand", use_container_width=True, on_click=_menu_set, args=("all",))
            b2.button("▸ " + tr("Collapse all"), key="menu_collapse", use_container_width=True, on_click=_menu_set, args=("none",))
            for gi, (gname, gem, gcol, gkeys) in enumerate(GROUPS, start=1):
                vis = [k for k in gkeys if k in allowed]
                if not vis:
                    continue
                tot = sum(_bc.get(badges.MENU.get(k, ""), 0) for k in vis if k in badges.MENU)
                is_open = (mode == "all") or (cur in vis)
                lab = f"{gem} {tr(gname)}" + (f"  🔴 {tot}" if tot else "") + "\u200b" * ver
                with st.container(key=f"grp_{gi}"):
                    with st.expander(lab, expanded=is_open):
                        for k in vis:
                            with st.container(key=f"nav_{k}"):
                                n = _bc.get(badges.MENU.get(k, ""), 0) if k in badges.MENU else 0
                                st.page_link(PAGE_FILES[k], label=_label(_lbl[k]) + (f"  🔴 {n}" if n else ""), icon=accounts.MODULES[k][1])
        st.divider()
        try:
            import db_ext
            unread = len(db_ext.get_notifications(current, only_unread=True))
            if unread:
                st.page_link(PAGE_FILES["9"], label=f"🔔 {unread} new notification(s)")
        except Exception:
            pass
    alerts_bar(current, prof, allowed, _bc)
    # mobile-only quick menu (sidebar is collapsed on phones)
    with st.container(key="mobilenav"):
        with st.expander("☰ Menu · pages & account"):
            _lang_switch("lang_radio_m")
            _lbl = dict(NAV)
            st.page_link(PAGE_FILES["home"], label=_label(_lbl["home"]), icon=accounts.MODULES["home"][1])
            for gi, (gname, gem, gcol, gkeys) in enumerate(GROUPS, start=1):
                vis = [k for k in gkeys if k in allowed]
                if vis:
                    st.caption(f"{gi} · {gem} {tr(gname)}")
                    for k in vis:
                        st.page_link(PAGE_FILES[k], label=_label(_lbl[k]), icon=accounts.MODULES[k][1])
            st.caption(f"{current} · {prof['role']}")
            if st.button("⎋ Sign out", key="logout_m"):
                logout()