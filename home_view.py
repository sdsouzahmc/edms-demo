import streamlit as st
import db
import theme
import plotly.graph_objects as go

db.init_db()
theme.inject_css()
theme.sidebar_nav()
import icons
st.markdown(f"""
<div class="efs-hero">
  <div>
    <h2>Every document. Captured, routed, controlled, proven.</h2>
    <p>One repository for scanning &amp; OCR, automatic distribution, versioning, workflow, search, audit and records — with analytics on all of it.</p>
    <div class="chips"><span>🖨️ OCR (EN/AR)</span><span>📬 Auto-distribution</span><span>🔎 Full-text search</span><span>🧾 Immutable audit trail</span><span>📊 Analytics</span><span>🔐 Role-based security</span></div>
  </div>
  <div style="height:190px">{icons.hero_art()}</div>
</div>
""", unsafe_allow_html=True)

s = db.stats()
c1, c2, c3, c4, c5, c6 = st.columns(6)
theme.metric_card("Total Documents", s["total"], c1)
theme.metric_card("Released", s["released"], c2)
theme.metric_card("Pending Approval", s["pending"], c3)
theme.metric_card("Archived", s["archived"], c4)
theme.metric_card("Expiring ≤90 days", s["expiring"], c5)
theme.metric_card("Rejected", s["rejected"], c6)

st.write("")
left, right = st.columns([1.3, 1])

with left:
    st.markdown('<div class="efs-section-title">📖 Recommended Demo Flow — one document, full lifecycle</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div class="efs-card">
    This demo is built around the structure in the solution-demo brief: an
    <b>Incoming Regulatory Letter</b> traced end-to-end through every mandatory
    capability area. Use the sidebar to jump straight to any workgroup, or
    follow the numbered story below in order.
    </div>
    """, unsafe_allow_html=True)

    steps = [
        ("1", "Correspondence & Intake", "Register the incoming letter, auto-number it, classify it, generate a QR code",
         theme.PAGE_FILES["1"]),
        ("2", "OCR & Intelligent Capture", "Scan it, OCR in English/Arabic, auto-extract metadata, auto-classify it, route it to the right department — or run a whole batch hands-free",
         theme.PAGE_FILES["2"]),
        ("3", "Document Control & Versioning", "Check-in/out, create v1.0 → v2.0, compare, publish official version",
         theme.PAGE_FILES["3"]),
        ("4", "Workflow & Approvals", "Route for department review → approval → finance sign-off, with delegation & e-signature",
         theme.PAGE_FILES["4"]),
        ("5", "Security & Compliance", "Switch roles to see RBAC in action — who can see/edit/approve what",
         theme.PAGE_FILES["5"]),
        ("6", "Search & Retrieval", "Ranked full-text search across documents and OCR'd scans — Boolean, phrase, wildcard, typo-tolerant, facets, security-trimmed",
         theme.PAGE_FILES["6"]),
        ("7", "Audit, Governance & Reporting", "See the immutable audit trail and compliance dashboards",
         theme.PAGE_FILES["7"]),
        ("8", "Records, Archiving & Disposal", "Retention countdown, archive, disposal request, destruction evidence",
         theme.PAGE_FILES["8"]),
        ("9", "My Workspace", "Personal dashboard: recent files, bookmarks, pending workflows, notifications, recycle bin",
         theme.PAGE_FILES["9"]),
        ("10", "Administration & Integrations", "AD/SSO sync, Outlook, Office 365, EMR, multi-site, DR, backup & point-in-time restore",
         theme.PAGE_FILES["10"]),
        ("12", "Auto-Distribution", "OCR text → content rules → routed to departments, copies, SLA acknowledgement, triage queue",
         theme.PAGE_FILES["12"]),
        ("13", "Analytics & Insights", "50+ live charts: scanning & OCR quality, workload & SLA, routing, search, repository, compliance risk, ROI model",
         theme.PAGE_FILES["13"]),
        ("11", "RFP Coverage", "Traceability from every RFP requirement group to where this demo proves it",
         theme.PAGE_FILES["11"]),
    ]
    for num, title, desc, path in steps:
        cc1, cc2 = st.columns([0.08, 0.92])
        with cc1:
            st.markdown(f"**{num}**")
        with cc2:
            st.markdown(f"**{title}**  \n<span style='color:#6B7280;font-size:0.88rem'>{desc}</span>",
                         unsafe_allow_html=True)
            st.page_link(path, label=f"Open {title} →")
        st.write("")

with right:
    st.markdown('<div class="efs-section-title">📊 Documents by Status</div>', unsafe_allow_html=True)
    status_colors = {
        "Draft": "#9AA3B2", "Department Review": "#B8860B", "Approval": "#C0603C",
        "Finance Sign-off": "#1F3864", "Released": "#2E7D32", "Rejected": "#B00020",
        "Archived": "#5E35B1", "Disposed": "#888888",
    }
    labels = [r["status"] for r in s["by_status"]]
    values = [r["n"] for r in s["by_status"]]
    colors = [status_colors.get(l, "#999") for l in labels]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.5,
                                  marker=dict(colors=colors))])
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280,
                       showlegend=True, legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="efs-section-title">🏢 Documents by Department</div>', unsafe_allow_html=True)
    dept_labels = [r["department"] for r in s["by_dept"]]
    dept_values = [r["n"] for r in s["by_dept"]]
    fig2 = go.Figure(data=[go.Bar(x=dept_values, y=dept_labels, orientation="h",
                                   marker=dict(color="#2E8B8B"))])
    fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=max(260, 24*len(dept_labels)))
    st.plotly_chart(fig2, use_container_width=True)

st.markdown('<div class="efs-section-title">🧩 Technology Legend</div>', unsafe_allow_html=True)
l1, l2 = st.columns(2)
with l1:
    st.markdown(f"{theme.tag_ms()} Microsoft 365-native: SharePoint repository, Power Automate workflows, "
                 "Power BI dashboards, Active Directory / SSO, Outlook integration", unsafe_allow_html=True)
with l2:
    st.markdown(f"{theme.tag_custom()} Tradify custom build: OCR capture pipeline, QR true-copy verification, "
                 "unified correspondence portal, retention/disposal automation", unsafe_allow_html=True)
