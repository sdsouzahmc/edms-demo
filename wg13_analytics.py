import io
import zipfile
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import db
import distribution as dist
import rfp_data
import theme
import analytics_data as A

db.init_db()
dist.init_dist()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("13 · Analytics & Insights",
             "Scanning · OCR quality · workload · routing · search · repository · compliance · business value")

NAVY, TEAL, CORAL, AMBER, GREEN, PURPLE, BLUE, GREY = "#1F3864", "#2E8B8B", "#C0603C", "#B8860B", "#2E7D32", "#6C4FA3", "#4A90C2", "#9AA3AF"
RED = "#B00020"
PAL = [NAVY, TEAL, CORAL, AMBER, GREEN, PURPLE, BLUE]
SEQ = ["#EAF4F4", "#B5DCDC", "#5FB0B0", "#2E8B8B", "#1F5F6B", "#1F3864"]
WEEK = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]


# ----------------------------------------------------------------- helpers
@st.cache_data(show_spinner=False)
def load_history():
    return A.scan_history(), A.approval_history(), A.search_history(), A.ack_history()


def style(fig, h=320, legend=True, title=None):
    fig.update_layout(template="plotly_white", height=h, margin=dict(l=8, r=8, t=(96 if legend and title else 44) if title or legend else 12, b=8),
                      font=dict(size=12, color="#1F2937"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None, font=dict(size=11)), showlegend=legend,
                      title=dict(text=title, font=dict(size=14, color=NAVY), x=0, y=0.98, yanchor="top") if title else None,
                      colorway=PAL, bargap=0.35)
    fig.update_xaxes(showgrid=False, linecolor="#CBD5E1")
    fig.update_yaxes(gridcolor="#E5E7EB", zeroline=False)
    return fig


_n = [0]


def show(fig, **kw):
    _n[0] += 1
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"pc{_n[0]}", **kw)


def top_other(df, col, weight, n=7):
    totals = df.groupby(col)[weight].sum().sort_values(ascending=False)
    keep = list(totals.index[:n])
    out = df.copy()
    out[col] = out[col].where(out[col].isin(keep), "Other")
    cmap = {k: PAL[i % len(PAL)] for i, k in enumerate(keep)}
    cmap["Other"] = GREY
    return out, cmap, keep + (["Other"] if len(totals) > n else [])


def delta_html(cur, prev, higher_is_good=True, unit="", dec=1):
    if prev in (0, None) or pd.isna(prev) or pd.isna(cur):
        return ""
    ch = (cur - prev) / abs(prev) * 100
    good = (ch >= 0) == higher_is_good
    col = GREEN if good else RED
    arrow = "▲" if ch >= 0 else "▼"
    return f'<div style="font-size:0.74rem;color:{col};margin-top:2px">{arrow} {abs(ch):.{dec}f}% vs previous period</div>'


def cols6(n=6):
    a = st.columns(3)
    b = st.columns(3)
    return (a + b)[:n]


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="efs-metric"><div class="val" style="font-size:1.45rem;white-space:nowrap">{value}</div><div class="lbl">{theme.tr(label)}</div>{sub}</div>', unsafe_allow_html=True)


def fmt(n, dec=0):
    return f"{n:,.{dec}f}"


def note(txt):
    st.caption(txt)


def title(txt):
    st.markdown(f'<div class="efs-section-title">{txt}</div>', unsafe_allow_html=True)


def month_start(s):
    return s.dt.to_period("M").dt.to_timestamp()


# ----------------------------------------------------------------- filters
scan_all, appr_all, srch_all, ack_all = load_history()
f1, f2, f3 = st.columns([1.2, 2.2, 1.4])
with f1:
    period_label = st.selectbox("Period", ["Last 30 days", "Last 90 days", "Last 6 months", "Last 12 months"], index=1)
    DAYS = {"Last 30 days": 30, "Last 90 days": 90, "Last 6 months": 182, "Last 12 months": 365}[period_label]
with f2:
    depts = st.multiselect("Departments", rfp_data.DEPARTMENTS, default=[], placeholder="All departments")
with f3:
    section = None
    st.caption("Live repository data + a simulated 12-month operating history (clearly marked) so trends are meaningful in the demo.")

end = pd.Timestamp(A.TODAY)
start = end - pd.Timedelta(days=DAYS)
pstart = start - pd.Timedelta(days=DAYS)


def window(df, col="date", dept_col="dept", prev=False):
    lo, hi = (pstart, start) if prev else (start, end + pd.Timedelta(days=1))
    d = df[(df[col] >= lo) & (df[col] < hi)]
    if depts and dept_col in d.columns:
        d = d[d[dept_col].isin(depts)]
    return d


S, Sp = window(scan_all), window(scan_all, prev=True)
AP, APp = window(appr_all), window(appr_all, prev=True)
Q, Qp = window(srch_all), window(srch_all, prev=True)
K, Kp = window(ack_all), window(ack_all, prev=True)
docs = A.live_documents()
if depts:
    docs = docs[docs["department"].isin(depts)]
wf = A.live_workflow()
if depts:
    wf = wf[wf["department"].isin(depts)]

SECTIONS = ["🏁 Overview", "🖨️ Scanning & OCR", "⚙️ Workload & Productivity", "📬 Distribution & Routing", "🔎 Search & Usage",
            "🗄️ Repository & Records", "🛡️ Compliance & Risk", "💰 Business Value (ROI)", "🧾 Reports & Export"]
section = st.radio("Analytics section", SECTIONS, horizontal=True, label_visibility="collapsed")
st.write("")


def pct(a, b):
    return 100 * a / b if b else 0


def w_avg(df, col, w):
    return float((df[col] * df[w]).sum() / df[w].sum()) if len(df) and df[w].sum() else 0.0


# =================================================================== OVERVIEW
if section == SECTIONS[0]:
    pages, pages_p = int(S["pages"].sum()), int(Sp["pages"].sum())
    conf, conf_p = w_avg(S, "ocr_conf", "pages"), w_avg(Sp, "ocr_conf", "pages")
    fp = 100 - pct(S["corrected_pages"].sum(), S["pages"].sum())
    fp_p = 100 - pct(Sp["corrected_pages"].sum(), Sp["pages"].sum())
    st_ = pct(S["auto_routed"].sum(), len(S))
    st_p = pct(Sp["auto_routed"].sum(), len(Sp))
    med, med_p = AP["hours"].median(), APp["hours"].median()
    sla, sla_p = 100 - pct(AP["breached"].sum(), len(AP)), 100 - pct(APp["breached"].sum(), len(APp))
    r1 = cols6()
    kpi(r1[0], "Pages scanned", fmt(pages), delta_html(pages, pages_p))
    kpi(r1[1], "OCR accuracy", f"{conf:.1f}%", delta_html(conf, conf_p))
    kpi(r1[2], "First-pass accuracy", f"{fp:.1f}%", delta_html(fp, fp_p))
    kpi(r1[3], "Straight-through routing", f"{st_:.0f}%", delta_html(st_, st_p))
    kpi(r1[4], "Median approval time", f"{med:.1f} h", delta_html(med, med_p, higher_is_good=False))
    kpi(r1[5], "Approval SLA met", f"{sla:.0f}%", delta_html(sla, sla_p))
    st.write("")
    n_q, n_qp = len(Q), len(Qp)
    zr = pct((Q["hits"] == 0).sum(), len(Q))
    zr_p = pct((Qp["hits"] == 0).sum(), len(Qp))
    ctr = pct(Q["opened"].sum(), len(Q))
    ctr_p = pct(Qp["opened"].sum(), len(Qp))
    open_items = int((wf["status"] == "active").sum()) if len(wf) else 0
    sl = dist.stats()
    r2 = cols6()
    kpi(r2[0], "Searches", fmt(n_q), delta_html(n_q, n_qp))
    kpi(r2[1], "Zero-result rate", f"{zr:.1f}%", delta_html(zr, zr_p, higher_is_good=False))
    kpi(r2[2], "Search success (opened)", f"{ctr:.0f}%", delta_html(ctr, ctr_p))
    kpi(r2[3], "Documents in repository", fmt(len(docs)), '<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">live</div>')
    kpi(r2[4], "Open workflow items", fmt(open_items), '<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">live</div>')
    kpi(r2[5], "Past-SLA deliveries", fmt(sl["overdue"]), '<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">live</div>')
    st.write("")

    title("What the numbers say")
    ins = []
    if len(S):
        by_d = S.groupby("dept")["pages"].sum().sort_values(ascending=False)
        ins.append(f"**{by_d.index[0]}** produced {pct(by_d.iloc[0], by_d.sum()):.0f}% of all scanned pages this period.")
        wk = S.groupby(S["date"].dt.day_name())["pages"].sum().reindex(WEEK).dropna()
        if len(wk):
            ins.append(f"Scanning peaks on **{wk.idxmax()}s** ({fmt(wk.max())} pages) and is lightest on **{wk.idxmin()}s**.")
        poor = pct(S["ocr_conf"].lt(90).sum(), len(S))
        ins.append(f"**{poor:.1f}%** of batches scored below 90% OCR confidence and were routed to operator review; Arabic batches average "
                   f"{w_avg(S[S.language == 'Arabic'], 'ocr_conf', 'pages'):.1f}% vs {w_avg(S[S.language == 'English'], 'ocr_conf', 'pages'):.1f}% for English.")
    if len(AP):
        stg = AP.groupby("stage")["hours"].mean().sort_values(ascending=False)
        ins.append(f"The slowest workflow stage is **{stg.index[0]}** at {stg.iloc[0]:.1f} h on average; "
                   f"{pct(AP['breached'].sum(), len(AP)):.1f}% of stage actions breached their SLA.")
    if len(Q):
        top = Q["query"].value_counts().index[0]
        zq = Q[Q["hits"] == 0]["query"].value_counts()
        ins.append(f"Most frequent search: “{top}”. Top content gap (searches with no result): “{zq.index[0] if len(zq) else '—'}”.")
    if len(K):
        ins.append(f"**{pct(K['on_time'].sum(), len(K)):.0f}%** of automatically routed items were acknowledged within SLA; "
                   f"only {pct(K['reassigned'].sum(), len(K)):.1f}% needed manual reassignment.")
    for t in ins:
        st.markdown(f"- {t}")
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        m = S.groupby(month_start(S["date"]))["pages"].sum().reset_index()
        fig = px.bar(m, x="date", y="pages", color_discrete_sequence=[TEAL])
        show(style(fig, 280, False, "Pages scanned per month"))
    with c2:
        m = AP.groupby(month_start(AP["date"])).size().reset_index(name="n")
        fig = px.bar(m, x="date", y="n", color_discrete_sequence=[NAVY])
        show(style(fig, 280, False, "Workflow approvals completed per month"))
    c3, c4 = st.columns(2)
    with c3:
        m = Q.groupby(month_start(Q["date"])).size().reset_index(name="n")
        fig = px.line(m, x="date", y="n", markers=True, color_discrete_sequence=[CORAL])
        fig.update_traces(line=dict(width=2.5))
        show(style(fig, 280, False, "Searches per month"))
    with c4:
        m = S.groupby(month_start(S["date"])).agg(rate=("auto_routed", "mean")).reset_index()
        m["rate"] *= 100
        fig = px.line(m, x="date", y="rate", markers=True, color_discrete_sequence=[GREEN])
        fig.update_traces(line=dict(width=2.5))
        fig.update_yaxes(range=[50, 100], ticksuffix="%")
        show(style(fig, 280, False, "Straight-through routing rate"))
    note("History is a simulated operating baseline for the demo; repository, workflow and routing tiles marked ‘live’ come from the running system.")

# ============================================================ SCANNING & OCR
elif section == SECTIONS[1]:
    sc = S[S["source"] == "history"] if len(S[S["source"] == "history"]) else S
    pages = int(S["pages"].sum())
    hours = S["minutes"].sum() / 60
    r = cols6()
    kpi(r[0], "Batches", fmt(len(S)), delta_html(len(S), len(Sp)))
    kpi(r[1], "Pages scanned", fmt(pages), delta_html(pages, Sp["pages"].sum()))
    kpi(r[2], "Avg OCR confidence", f"{w_avg(S, 'ocr_conf', 'pages'):.1f}%", delta_html(w_avg(S, "ocr_conf", "pages"), w_avg(Sp, "ocr_conf", "pages")))
    kpi(r[3], "Pages needing correction", f"{pct(S['corrected_pages'].sum(), pages):.1f}%",
        delta_html(pct(S["corrected_pages"].sum(), pages), pct(Sp["corrected_pages"].sum(), Sp["pages"].sum()), higher_is_good=False))
    kpi(r[4], "Re-scan rate", f"{pct(S['rescan_pages'].sum(), pages):.2f}%",
        delta_html(pct(S["rescan_pages"].sum(), pages), pct(Sp["rescan_pages"].sum(), Sp["pages"].sum()), higher_is_good=False))
    kpi(r[5], "Pages per hour", f"{pages / hours:.0f}" if hours else "—", delta_html(pages / hours if hours else 0, Sp["pages"].sum() / (Sp["minutes"].sum() / 60) if Sp["minutes"].sum() else 0))
    st.write("")

    c1, c2 = st.columns([1.6, 1])
    with c1:
        g, cmap, order = top_other(S, "dept", "pages")
        m = g.groupby([month_start(g["date"]).rename("month"), "dept"])["pages"].sum().reset_index()
        fig = px.bar(m, x="month", y="pages", color="dept", color_discrete_map=cmap, category_orders={"dept": order})
        fig.update_traces(marker_line_width=1, marker_line_color="white")
        show(style(fig, 340, True, "Pages scanned per month, by department"))
    with c2:
        d = S.groupby("language")["pages"].sum().reset_index()
        fig = px.pie(d, names="language", values="pages", hole=0.62, color="language", color_discrete_map={"English": NAVY, "Arabic": TEAL})
        fig.update_traces(textinfo="percent+label", marker=dict(line=dict(color="white", width=2)))
        show(style(fig, 340, False, "Language mix (pages)"))

    c1, c2 = st.columns(2)
    with c1:
        dly = S.groupby("date")["pages"].sum().reset_index().sort_values("date")
        dly["avg7"] = dly["pages"].rolling(7, min_periods=1).mean()
        fig = go.Figure()
        fig.add_bar(x=dly["date"], y=dly["pages"], name="Pages per day", marker_color="#B5DCDC")
        fig.add_scatter(x=dly["date"], y=dly["avg7"], name="7-day average", line=dict(color=NAVY, width=2.5), mode="lines")
        show(style(fig, 320, True, "Daily scanning volume"))
    with c2:
        hm = S.assign(wd=S["date"].dt.day_name()).pivot_table(index="wd", columns="hour", values="pages", aggfunc="sum").reindex(WEEK)
        fig = px.imshow(hm, aspect="auto", color_continuous_scale=SEQ, labels=dict(x="Hour of day", y="", color="Pages"))
        show(style(fig, 320, False, "When scanning happens (pages by weekday × hour)"))

    c1, c2 = st.columns(2)
    with c1:
        op = S[S["operator"] != "Live capture"].groupby("operator").agg(pages=("pages", "sum"), minutes=("minutes", "sum"),
                                                                        conf=("ocr_conf", "mean"), corr=("corrected_pages", "sum")).reset_index()
        op["pph"] = op["pages"] / (op["minutes"] / 60)
        fig = px.scatter(op, x="pph", y="conf", size="pages", color="operator", color_discrete_sequence=PAL, size_max=46, text="operator")
        fig.update_traces(textposition="top center", marker=dict(line=dict(width=2, color="white")))
        fig.update_xaxes(title="Pages per hour"); fig.update_yaxes(title="Avg OCR confidence (%)")
        show(style(fig, 340, False, "Operator throughput vs quality (bubble = pages)"))
    with c2:
        stn = S[S["station"] != "Live OCR page"].groupby("station").agg(pages=("pages", "sum"), minutes=("minutes", "sum")).reset_index().sort_values("pages")
        stn["util"] = (stn["minutes"] / 60 / (DAYS * 5 / 7 * 7.5)).clip(upper=1) * 100       # share of a 7.5 h working day
        fig = px.bar(stn, x="pages", y="station", orientation="h", color_discrete_sequence=[TEAL], text=stn["util"].map(lambda v: f"{v:.0f}%"))
        fig.update_traces(textposition="outside"); fig.update_xaxes(range=[0, stn["pages"].max() * 1.2])
        show(style(fig, 340, False, "Scan-station load (pages; label = % of working hours busy)"))

    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(S, x="ocr_conf", color="language", nbins=34, barmode="overlay", opacity=0.75,
                           color_discrete_map={"English": NAVY, "Arabic": TEAL})
        fig.add_vline(x=90, line_dash="dash", line_color=CORAL, annotation_text="review threshold 90%", annotation_position="top left")
        fig.update_xaxes(title="OCR confidence (%)"); fig.update_yaxes(title="Batches")
        show(style(fig, 320, True, "OCR confidence distribution"))
    with c2:
        band = pd.cut(S["ocr_conf"], [0, 90, 95, 101], labels=["Review (<90%)", "Good (90–95%)", "High (≥95%)"])
        b = S.groupby(band, observed=False)["pages"].sum().reset_index()
        fig = px.bar(b, x="ocr_conf", y="pages", color="ocr_conf", color_discrete_map={"Review (<90%)": CORAL, "Good (90–95%)": AMBER, "High (≥95%)": GREEN},
                     text="pages")
        fig.update_xaxes(title=""); fig.update_traces(textposition="outside")
        show(style(fig, 320, False, "Pages by quality band"))

    c1, c2 = st.columns(2)
    with c1:
        t = S.groupby("doc_type").agg(pages=("pages", "sum"), conf=("ocr_conf", "mean")).reset_index().sort_values("pages", ascending=False).head(12)
        fig = px.bar(t.sort_values("pages"), x="pages", y="doc_type", orientation="h", color="conf", color_continuous_scale=SEQ,
                     labels={"conf": "Avg confidence"})
        show(style(fig, 360, False, "Document types captured (colour = avg confidence)"))
    with c2:
        m = S.groupby(month_start(S["date"])).agg(c=("corrected_pages", "sum"), r=("rescan_pages", "sum"), p=("pages", "sum")).reset_index()
        m["Corrected by operator"] = m["c"] / m["p"] * 100
        m["Re-scanned"] = m["r"] / m["p"] * 100
        fig = px.line(m.melt("date", ["Corrected by operator", "Re-scanned"], var_name="Metric", value_name="% of pages"), x="date", y="% of pages",
                      color="Metric", markers=True, color_discrete_sequence=[CORAL, NAVY])
        show(style(fig, 360, True, "Quality trend: corrections and re-scans (% of pages)"))

    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(S, x="pages", nbins=30, color_discrete_sequence=[NAVY])
        fig.update_xaxes(title="Pages per batch"); fig.update_yaxes(title="Batches")
        show(style(fig, 280, False, "Batch size distribution"))
    with c2:
        fig = px.box(S, x="language", y="ocr_conf", color="language", points=False, color_discrete_map={"English": NAVY, "Arabic": TEAL})
        fig.update_yaxes(title="OCR confidence (%)"); fig.update_xaxes(title="")
        show(style(fig, 280, False, "Confidence spread: English vs Arabic"))

    title("Operator review queue — lowest-confidence batches")
    q = S.sort_values("ocr_conf").head(10)[["date", "dept", "operator", "doc_type", "language", "pages", "ocr_conf", "corrected_pages"]].copy()
    q["date"] = q["date"].dt.date
    q.columns = ["Date", "Department", "Operator", "Type", "Language", "Pages", "OCR conf %", "Corrected pages"]
    st.dataframe(q, use_container_width=True, hide_index=True)
    live = int((S["source"] == "live").sum())
    note(f"{live} batch(es) in this window come from live OCR captures made in this demo session; the rest are the simulated operating history.")

# ===================================================== WORKLOAD & PRODUCTIVITY
elif section == SECTIONS[2]:
    cap_per_user = st.slider("Capacity assumption: items one person can action per week", 5, 60, 25)
    weeks = max(1, DAYS / 7)
    arr = AP[AP["stage"] == "Department Review"]
    arr_p = APp[APp["stage"] == "Department Review"]
    active = wf[wf["status"] == "active"] if len(wf) else wf
    r = cols6()
    kpi(r[0], "Items actioned", fmt(len(AP)), delta_html(len(AP), len(APp)))
    kpi(r[1], "Median stage time", f"{AP['hours'].median():.1f} h", delta_html(AP["hours"].median(), APp["hours"].median(), False))
    kpi(r[2], "90th percentile", f"{AP['hours'].quantile(0.9):.1f} h", delta_html(AP["hours"].quantile(0.9), APp["hours"].quantile(0.9), False))
    kpi(r[3], "SLA met", f"{100 - pct(AP['breached'].sum(), len(AP)):.0f}%", delta_html(100 - pct(AP['breached'].sum(), len(AP)), 100 - pct(APp['breached'].sum(), len(APp))))
    kpi(r[4], "Rejected / returned", f"{pct((AP['outcome'] != 'Approved').sum(), len(AP)):.1f}%",
        delta_html(pct((AP['outcome'] != 'Approved').sum(), len(AP)), pct((APp['outcome'] != 'Approved').sum(), len(APp)), False))
    kpi(r[5], "Open items now", fmt(len(active)), '<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">live</div>')
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        if len(active):
            b = active.groupby("assignee").size().reset_index(name="n").sort_values("n")
            fig = px.bar(b, x="n", y="assignee", orientation="h", color_discrete_sequence=[CORAL], text="n")
            fig.update_traces(textposition="outside")
            show(style(fig, 340, False, "Open items by owning department (live)"))
        else:
            st.info("No open workflow items.")
    with c2:
        if len(active):
            b = active.groupby("stage").size().reset_index(name="n")
            order = ["Draft", "Department Review", "Legal Review", "Approval", "Finance Sign-off"]
            b["stage"] = pd.Categorical(b["stage"], [o for o in order if o in set(b["stage"])] + [x for x in b["stage"] if x not in order])
            fig = px.bar(b.sort_values("stage"), x="stage", y="n", color_discrete_sequence=[NAVY], text="n")
            fig.update_traces(textposition="outside")
            show(style(fig, 340, False, "Open items by workflow stage (live)"))

    c1, c2 = st.columns(2)
    with c1:
        s_ = AP.groupby("stage").agg(avg=("hours", "mean"), sla=("sla_hours", "first")).reset_index().sort_values("avg")
        fig = go.Figure()
        fig.add_bar(y=s_["stage"], x=s_["avg"], orientation="h", name="Average hours", marker_color=TEAL, text=s_["avg"].round(1), textposition="outside")
        fig.add_scatter(y=s_["stage"], x=s_["sla"], mode="markers", name="SLA target", marker=dict(symbol="diamond", size=12, color=CORAL, line=dict(width=2, color="white")))
        fig.update_xaxes(title="Hours")
        show(style(fig, 320, True, "Where time goes: average hours per stage vs SLA"))
    with c2:
        bs = AP.groupby("stage").agg(rate=("breached", "mean")).reset_index()
        bs["rate"] *= 100
        fig = px.bar(bs.sort_values("rate"), x="rate", y="stage", orientation="h", color="rate", color_continuous_scale=["#B5DCDC", CORAL], text=bs.sort_values("rate")["rate"].map(lambda v: f"{v:.1f}%"))
        fig.update_traces(textposition="outside"); fig.update_coloraxes(showscale=False)
        show(style(fig, 320, False, "SLA breach rate by stage (bottlenecks)"))

    c1, c2 = st.columns(2)
    with c1:
        mm = AP.groupby(month_start(AP["date"]))["hours"].agg(median="median", p90=lambda s: s.quantile(0.9)).reset_index()
        fig = px.line(mm.melt("date", ["median", "p90"], var_name="Metric", value_name="Hours"), x="date", y="Hours", color="Metric", markers=True,
                      color_discrete_map={"median": NAVY, "p90": CORAL})
        show(style(fig, 320, True, "Stage time trend: median and 90th percentile (hours)"))
    with c2:
        o = AP.groupby(["stage", "outcome"]).size().reset_index(name="n")
        fig = px.bar(o, x="stage", y="n", color="outcome", barmode="stack", color_discrete_map={"Approved": GREEN, "Rejected": CORAL, "Returned": AMBER})
        fig.update_traces(marker_line_width=1, marker_line_color="white")
        show(style(fig, 320, True, "Outcomes by stage"))

    title("Capacity vs demand — utilisation by department")
    util = arr.groupby("dept").size().reset_index(name="arrivals")
    util["per_week"] = util["arrivals"] / weeks
    util["users"] = util["dept"].map(rfp_data.DEPT_USERS).fillna(2)
    util["capacity"] = util["users"] * cap_per_user
    util["util"] = util["per_week"] / util["capacity"] * 100
    util["state"] = np.where(util["util"] > 90, "Overloaded (>90%)", np.where(util["util"] > 70, "Busy (70–90%)", "Healthy (<70%)"))
    fig = px.bar(util.sort_values("util"), x="util", y="dept", orientation="h", color="state",
                 color_discrete_map={"Overloaded (>90%)": RED, "Busy (70–90%)": AMBER, "Healthy (<70%)": GREEN},
                 text=util.sort_values("util")["util"].map(lambda v: f"{v:.0f}%"))
    fig.update_traces(textposition="outside")
    fig.update_xaxes(title="Utilisation (% of weekly capacity)")
    show(style(fig, 520, True))
    note("Utilisation = weekly arrivals ÷ (licensed users in the department × items per person per week). Change the capacity slider above to test staffing scenarios.")

    c1, c2 = st.columns(2)
    with c1:
        wk = AP[AP["stage"] == "Department Review"].copy()
        wk["week"] = wk["date"].dt.to_period("W").dt.start_time
        last = sorted(wk["week"].unique())[-12:]
        hm = wk[wk["week"].isin(last)].pivot_table(index="dept", columns="week", values="hours", aggfunc="count").fillna(0)
        hm.columns = [c.strftime("%d %b") for c in hm.columns]
        fig = px.imshow(hm, aspect="auto", color_continuous_scale=SEQ, labels=dict(color="Items"))
        show(style(fig, 520, False, "Weekly workload heatmap (last 12 weeks)"))
    with c2:
        wt = AP[AP["stage"] == "Department Review"].copy()
        wt["week"] = wt["date"].dt.to_period("W").dt.start_time
        wk2 = wt.groupby("week").size().reset_index(name="n")
        wk2 = wk2.iloc[:-1] if len(wk2) > 2 else wk2
        wk2 = wk2.tail(26)
        x = np.arange(len(wk2))
        if len(wk2) > 3:
            coef = np.polyfit(x, wk2["n"], 1)
            fit = np.polyval(coef, x)
            sd = float(np.std(wk2["n"] - fit))
            fx = np.arange(len(wk2), len(wk2) + 4)
            fy = np.polyval(coef, fx)
            fdates = [wk2["week"].iloc[-1] + pd.Timedelta(weeks=i + 1) for i in range(4)]
            fig = go.Figure()
            fig.add_scatter(x=wk2["week"], y=wk2["n"], mode="lines+markers", name="Actual arrivals", line=dict(color=NAVY, width=2.5))
            fig.add_scatter(x=fdates + fdates[::-1], y=list(fy + 1.64 * sd) + list((fy - 1.64 * sd)[::-1]), fill="toself", mode="none",
                            fillcolor="rgba(46,139,139,0.18)", name="90% range", hoverinfo="skip")
            fig.add_scatter(x=fdates, y=fy, mode="lines+markers", name="Forecast", line=dict(color=TEAL, width=2.5, dash="dash"))
            show(style(fig, 520, True, "Demand forecast — next 4 weeks"))
            note(f"Linear trend on the last {len(wk2)} weeks: expected {fy[-1]:.0f} new items/week by {fdates[-1]:%d %b} (±{1.64 * sd:.0f}).")

    c1, c2 = st.columns(2)
    with c1:
        g, cmap, order = top_other(AP, "dept", "hours", 8)
        fig = px.box(g, x="dept", y="hours", color="dept", color_discrete_map=cmap, points=False, category_orders={"dept": order})
        fig.update_yaxes(title="Hours in stage"); fig.update_xaxes(title="", tickangle=-30)
        show(style(fig, 380, False, "Stage-time spread by department"))
    with c2:
        if len(active):
            now = pd.Timestamp.now()
            age = (now - pd.to_datetime(active["modified_at"])).dt.total_seconds() / 86400
            b = pd.cut(age, [-1, 1, 3, 7, 1e9], labels=["< 1 day", "1–3 days", "3–7 days", "> 7 days"])
            ag = b.value_counts().reindex(["< 1 day", "1–3 days", "3–7 days", "> 7 days"]).reset_index()
            ag.columns = ["Age", "Items"]
            fig = px.bar(ag, x="Age", y="Items", color="Age", text="Items",
                         color_discrete_map={"< 1 day": GREEN, "1–3 days": TEAL, "3–7 days": AMBER, "> 7 days": RED})
            fig.update_traces(textposition="outside")
            show(style(fig, 380, False, "Ageing of open items (live)"))

# ================================================== DISTRIBUTION & ROUTING
elif section == SECTIONS[3]:
    stt = dist.stats()
    rate = pct(K["auto_routed"].sum(), len(K))
    r = cols6()
    kpi(r[0], "Items routed (live)", fmt(stt["routed"]), '<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">live</div>')
    kpi(r[1], "In triage (live)", fmt(stt["triage"]), '<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">live</div>')
    kpi(r[2], "Auto-routed (period)", f"{rate:.0f}%", delta_html(rate, pct(Kp["auto_routed"].sum(), len(Kp))))
    kpi(r[3], "Acknowledged on time", f"{pct(K['on_time'].sum(), len(K)):.0f}%", delta_html(pct(K["on_time"].sum(), len(K)), pct(Kp["on_time"].sum(), len(Kp))))
    kpi(r[4], "Median acknowledgement", f"{K['ack_hours'].median():.1f} h", delta_html(K["ack_hours"].median(), Kp["ack_hours"].median(), False))
    kpi(r[5], "Manual re-assignments", f"{pct(K['reassigned'].sum(), len(K)):.1f}%", delta_html(pct(K["reassigned"].sum(), len(K)), pct(Kp["reassigned"].sum(), len(Kp)), False))
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if stt["by_rule"]:
            d = pd.DataFrame(stt["by_rule"], columns=["Rule", "Documents"]).sort_values("Documents")
            fig = px.bar(d, x="Documents", y="Rule", orientation="h", color_discrete_sequence=[TEAL], text="Documents")
            fig.update_traces(textposition="outside")
            show(style(fig, 360, False, "Documents routed per rule (live)"))
    with c2:
        if stt["by_dept"]:
            d = pd.DataFrame(stt["by_dept"], columns=["Department", "Deliveries"]).sort_values("Deliveries")
            fig = px.bar(d, x="Deliveries", y="Department", orientation="h", color_discrete_sequence=[CORAL], text="Deliveries")
            fig.update_traces(textposition="outside")
            show(style(fig, 360, False, "Deliveries per department (live)"))
    c1, c2 = st.columns(2)
    with c1:
        m = K.groupby(month_start(K["date"])).agg(auto=("auto_routed", "mean"), ontime=("on_time", "mean"), re=("reassigned", "mean")).reset_index()
        m = m.melt("date", ["auto", "ontime", "re"], var_name="Metric", value_name="Rate")
        m["Rate"] *= 100
        m["Metric"] = m["Metric"].map({"auto": "Auto-routed", "ontime": "Acknowledged on time", "re": "Manually re-assigned"})
        fig = px.line(m, x="date", y="Rate", color="Metric", markers=True, color_discrete_map={"Auto-routed": NAVY, "Acknowledged on time": GREEN, "Manually re-assigned": CORAL})
        fig.update_yaxes(ticksuffix="%")
        show(style(fig, 330, True, "Routing quality over time"))
    with c2:
        fig = px.histogram(K, x="ack_hours", nbins=40, color_discrete_sequence=[NAVY])
        fig.update_xaxes(title="Hours to acknowledge", range=[0, min(80, K["ack_hours"].quantile(0.99) if len(K) else 80)]); fig.update_yaxes(title="Deliveries")
        show(style(fig, 330, False, "Acknowledgement time distribution"))
    c1, c2 = st.columns(2)
    with c1:
        d = K.groupby("dept").agg(on=("on_time", "mean"), n=("on_time", "size")).reset_index()
        d["on"] *= 100
        d = d.sort_values("on")
        fig = px.bar(d, x="on", y="dept", orientation="h", color="on", color_continuous_scale=["#E8B4A0", TEAL], range_color=[50, 100], text=d["on"].map(lambda v: f"{v:.0f}%"))
        fig.update_traces(textposition="outside"); fig.update_coloraxes(showscale=False)
        fig.update_xaxes(range=[0, 110], title="% acknowledged within SLA")
        show(style(fig, 520, False, "Acknowledgement SLA compliance by department"))
    with c2:
        lg = A.live_table("SELECT matched FROM dist_log WHERE matched != ''")
        if len(lg):
            kw = lg["matched"].str.split(", ").explode().str.strip().str.lower().value_counts().head(14).reset_index()
            kw.columns = ["Keyword", "Hits"]
            fig = px.bar(kw.sort_values("Hits"), x="Hits", y="Keyword", orientation="h", color_discrete_sequence=[PURPLE], text="Hits")
            fig.update_traces(textposition="outside")
            show(style(fig, 520, False, "Keywords that triggered routing (live)"))
    title("Document flow: capture channel → rule → department (live)")
    fl = A.live_table("SELECT d.source, l.rule_name, l.target_dept FROM dist_log l JOIN documents d ON d.id=l.document_id "
                      "WHERE l.role='Primary' AND l.target_dept!='Unrouted'")
    if len(fl):
        fl["source"] = fl["source"].map(lambda s: {"Scan": "OCR scan", "Postal": "Postal mail", "Email": "Email"}.get(s, s))
        nodes = list(pd.unique(pd.concat([fl["source"], fl["rule_name"], fl["target_dept"]])))
        idx = {n: i for i, n in enumerate(nodes)}
        links = pd.concat([fl.groupby(["source", "rule_name"]).size().reset_index(name="v").rename(columns={"source": "a", "rule_name": "b"}),
                           fl.groupby(["rule_name", "target_dept"]).size().reset_index(name="v").rename(columns={"rule_name": "a", "target_dept": "b"})])
        fig = go.Figure(go.Sankey(node=dict(label=nodes, pad=14, thickness=16, color=[TEAL] * len(nodes), line=dict(color="white", width=1)),
                                  link=dict(source=links["a"].map(idx), target=links["b"].map(idx), value=links["v"], color="rgba(46,139,139,0.28)")))
        show(style(fig, 420, False))
    c1, c2 = st.columns(2)
    with c1:
        sm = A.live_table("SELECT status, COUNT(*) n FROM dist_log GROUP BY status")
        if len(sm):
            fig = px.pie(sm, names="status", values="n", hole=0.6, color="status",
                         color_discrete_map={"Acknowledged": GREEN, "Delivered": AMBER, "Needs triage": CORAL, "Triaged": TEAL})
            show(style(fig, 300, True, "Delivery status (live)"))
    with c2:
        cp = A.live_table("SELECT document_id, COUNT(*)-1 AS copies FROM dist_log WHERE target_dept!='Unrouted' GROUP BY document_id")
        if len(cp):
            fig = px.histogram(cp, x="copies", nbins=6, color_discrete_sequence=[NAVY])
            fig.update_xaxes(title="Copies sent per document", dtick=1); fig.update_yaxes(title="Documents")
            show(style(fig, 300, False, "Copies distributed per document (live)"))

# ========================================================== SEARCH & USAGE
elif section == SECTIONS[4]:
    r = cols6()
    kpi(r[0], "Searches", fmt(len(Q)), delta_html(len(Q), len(Qp)))
    kpi(r[1], "Searches per working day", f"{len(Q) / max(1, Q['date'].nunique()):.0f}", "")
    kpi(r[2], "Zero-result rate", f"{pct((Q['hits'] == 0).sum(), len(Q)):.1f}%", delta_html(pct((Q["hits"] == 0).sum(), len(Q)), pct((Qp["hits"] == 0).sum(), len(Qp)), False))
    kpi(r[3], "Opened a result", f"{pct(Q['opened'].sum(), len(Q)):.0f}%", delta_html(pct(Q["opened"].sum(), len(Q)), pct(Qp["opened"].sum(), len(Qp))))
    kpi(r[4], "Median time to find", f"{Q['seconds_to_find'].median():.0f} s", delta_html(Q["seconds_to_find"].median(), Qp["seconds_to_find"].median(), False))
    kpi(r[5], "Found via OCR text", f"{pct(Q['ocr_hit'].sum(), len(Q)):.0f}%", delta_html(pct(Q["ocr_hit"].sum(), len(Q)), pct(Qp["ocr_hit"].sum(), len(Qp))))
    st.write("")
    c1, c2 = st.columns([1.6, 1])
    with c1:
        d = Q.groupby("date").size().reset_index(name="n").sort_values("date")
        d["avg7"] = d["n"].rolling(7, min_periods=1).mean()
        fig = go.Figure()
        fig.add_bar(x=d["date"], y=d["n"], name="Searches per day", marker_color="#B5DCDC")
        fig.add_scatter(x=d["date"], y=d["avg7"], name="7-day average", line=dict(color=NAVY, width=2.5))
        show(style(fig, 320, True, "Search volume"))
    with c2:
        h = Q.groupby("hour").size().reset_index(name="n")
        fig = px.bar(h, x="hour", y="n", color_discrete_sequence=[TEAL])
        fig.update_xaxes(title="Hour of day", dtick=1)
        show(style(fig, 320, False, "Searches by hour"))
    c1, c2 = st.columns(2)
    with c1:
        t = Q["query"].value_counts().head(12).reset_index()
        t.columns = ["Query", "Searches"]
        fig = px.bar(t.sort_values("Searches"), x="Searches", y="Query", orientation="h", color_discrete_sequence=[NAVY], text="Searches")
        fig.update_traces(textposition="outside")
        show(style(fig, 400, False, "Most frequent queries"))
    with c2:
        z = Q[Q["hits"] == 0]["query"].value_counts().head(10).reset_index()
        z.columns = ["Query", "Searches with no result"]
        fig = px.bar(z.sort_values("Searches with no result"), x="Searches with no result", y="Query", orientation="h", color_discrete_sequence=[CORAL], text="Searches with no result")
        fig.update_traces(textposition="outside")
        show(style(fig, 400, False, "Content gaps — what people look for and cannot find"))
    c1, c2 = st.columns(2)
    with c1:
        fun = [len(Q), int((Q["hits"] > 0).sum()), int(Q["opened"].sum()), int(Q["downloaded"].sum())]
        fig = go.Figure(go.Funnel(y=["Searches", "Returned results", "Opened a document", "Downloaded"], x=fun, marker=dict(color=[NAVY, "#2F5D8A", TEAL, "#5FB0B0"]),
                                  textinfo="value+percent initial"))
        show(style(fig, 340, False, "Search-to-document funnel"))
    with c2:
        md = Q.groupby("mode").size().reset_index(name="n")
        fig = px.pie(md, names="mode", values="n", hole=0.6, color="mode", color_discrete_map={"Smart": NAVY, "Natural language": TEAL})
        show(style(fig, 340, True, "Search mode used"))
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(Q.dropna(subset=["seconds_to_find"]), x="seconds_to_find", nbins=40, color_discrete_sequence=[PURPLE])
        fig.update_xaxes(title="Seconds from query to opening a document", range=[0, 120]); fig.update_yaxes(title="Searches")
        show(style(fig, 320, False, "Time to find"))
    with c2:
        m = Q.groupby(month_start(Q["date"])).agg(ocr=("ocr_hit", "mean"), zero=("hits", lambda s: (s == 0).mean()), op=("opened", "mean")).reset_index()
        m = m.melt("date", ["ocr", "zero", "op"], var_name="Metric", value_name="Share")
        m["Share"] *= 100
        m["Metric"] = m["Metric"].map({"ocr": "Found via OCR text", "zero": "No result", "op": "Opened a result"})
        fig = px.line(m, x="date", y="Share", color="Metric", markers=True, color_discrete_map={"Found via OCR text": TEAL, "No result": CORAL, "Opened a result": NAVY})
        fig.update_yaxes(ticksuffix="%")
        show(style(fig, 320, True, "Search effectiveness over time"))
    c1, c2 = st.columns(2)
    with c1:
        ad = Q.groupby("dept").size().reset_index(name="Searches")
        ad["Per user"] = ad["Searches"] / ad["dept"].map(rfp_data.DEPT_USERS).fillna(2)
        fig = px.bar(ad.sort_values("Per user"), x="Per user", y="dept", orientation="h", color_discrete_sequence=[TEAL])
        fig.update_xaxes(title="Searches per licensed user")
        show(style(fig, 420, False, "Adoption by department"))
    with c2:
        dd = docs.sort_values("id").copy()
        rs = np.random.RandomState(7)
        dd["opens"] = (rs.lognormal(3.0, 0.8, len(dd)) * (1 + (dd["status"] == "Released") * 0.8)).astype(int)
        top = dd.sort_values("opens", ascending=False).head(10)
        fig = px.bar(top.sort_values("opens"), x="opens", y="doc_code", orientation="h", color_discrete_sequence=[CORAL], hover_data=["title"], text="opens")
        fig.update_traces(textposition="outside")
        show(style(fig, 420, False, "Most-opened documents (simulated counts on live documents)"))

# ================================================ REPOSITORY & RECORDS
elif section == SECTIONS[5]:
    docs_ = docs.copy()
    n = len(docs_)
    ver = A.live_table("SELECT document_id, COUNT(*) v FROM versions GROUP BY document_id")
    scan_pages_year = int(scan_all[scan_all["date"] >= end - pd.Timedelta(days=365)]["pages"].sum())
    r = cols6()
    kpi(r[0], "Documents (live)", fmt(n))
    kpi(r[1], "OCR-captured", fmt(int((docs_["source"] == "Scan").sum())))
    kpi(r[2], "Released / published", fmt(int((docs_["status"] == "Released").sum())))
    kpi(r[3], "On legal hold", fmt(int(docs_["legal_hold"].fillna(0).astype(int).sum())) if "legal_hold" in docs_ else "0")
    kpi(r[4], "Avg versions per doc", f"{ver['v'].mean():.1f}" if len(ver) else "—")
    kpi(r[5], "Est. storage (12 mo)", f"{scan_pages_year * 0.18 / 1024:.1f} GB")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        d = docs_.groupby("department").size().reset_index(name="n").sort_values("n")
        fig = px.bar(d, x="n", y="department", orientation="h", color_discrete_sequence=[TEAL], text="n")
        fig.update_traces(textposition="outside")
        show(style(fig, 460, False, "Documents by department"))
    with c2:
        t = docs_.groupby("doc_type").size().reset_index(name="n").sort_values("n", ascending=False).head(14)
        fig = px.bar(t.sort_values("n"), x="n", y="doc_type", orientation="h", color_discrete_sequence=[NAVY], text="n")
        fig.update_traces(textposition="outside")
        show(style(fig, 460, False, "Documents by type"))
    c1, c2, c3 = st.columns(3)
    with c1:
        s = docs_.groupby("status").size().reset_index(name="n")
        fig = px.pie(s, names="status", values="n", hole=0.58, color_discrete_sequence=PAL)
        show(style(fig, 300, True, "By status"))
    with c2:
        s = docs_.groupby("classification").size().reset_index(name="n")
        fig = px.pie(s, names="classification", values="n", hole=0.58, color_discrete_sequence=[NAVY, TEAL, CORAL])
        show(style(fig, 300, True, "By classification"))
    with c3:
        s = docs_.groupby("security_level").size().reset_index(name="n")
        fig = px.pie(s, names="security_level", values="n", hole=0.58, color="security_level",
                     color_discrete_map={"Public": GREEN, "Internal": TEAL, "Restricted": AMBER, "Confidential": RED})
        show(style(fig, 300, True, "By security level"))
    tm = docs_.groupby(["department", "doc_type"]).size().reset_index(name="n")
    fig = px.treemap(tm, path=[px.Constant("All"), "department", "doc_type"], values="n", color="department", color_discrete_sequence=PAL + [GREY])
    fig.update_traces(marker=dict(line=dict(width=2, color="white")))
    show(style(fig, 420, False, "Repository map: department → document type"))
    c1, c2 = st.columns(2)
    with c1:
        e = docs_.dropna(subset=["expiry_date"]).copy()
        e["exp"] = pd.to_datetime(e["expiry_date"], errors="coerce")
        e = e[(e["exp"] >= end) & (e["exp"] <= end + pd.Timedelta(days=730))]
        m = e.groupby(month_start(e["exp"])).size().reset_index(name="n")
        fig = px.bar(m, x="exp", y="n", color_discrete_sequence=[CORAL], text="n")
        fig.update_traces(textposition="outside")
        show(style(fig, 330, False, "Retention / expiry timeline — next 24 months (live)"))
    with c2:
        r_ = docs_.groupby(docs_["retention_schedule"].fillna("Not assigned")).size().reset_index(name="n").sort_values("n")
        r_.columns = ["Retention schedule", "n"]
        fig = px.bar(r_, x="n", y="Retention schedule", orientation="h", color_discrete_sequence=[PURPLE], text="n")
        fig.update_traces(textposition="outside")
        show(style(fig, 330, False, "Retention schedule coverage (live)"))
    c1, c2 = st.columns(2)
    with c1:
        g = scan_all[scan_all["source"] == "history"].copy()
        g = g.groupby(month_start(g["date"]))["pages"].sum().cumsum().reset_index()
        g["GB"] = g["pages"] * 0.18 / 1024
        fig = px.area(g, x="date", y="GB", color_discrete_sequence=[TEAL])
        fig.update_yaxes(title="GB (estimated at 0.18 MB per scanned page)")
        show(style(fig, 330, False, "Digital archive growth since go-live (simulated)"))
    with c2:
        tiers = pd.DataFrame({"Tier": ["Hot (≤ 1 year)", "Warm (1–3 years)", "Cold (> 3 years)"],
                              "GB": [round(scan_pages_year * 0.18 / 1024, 1), round(scan_pages_year * 0.18 / 1024 * 1.6, 1), round(scan_pages_year * 0.18 / 1024 * 2.4, 1)]})
        fig = px.bar(tiers, x="Tier", y="GB", color="Tier", color_discrete_sequence=[CORAL, AMBER, BLUE], text="GB")
        fig.update_traces(textposition="outside")
        show(style(fig, 330, False, "Storage by tier (illustrative)"))
    c1, c2 = st.columns(2)
    with c1:
        comp = pd.DataFrame({
            "Field": ["Document type", "Sender / source", "Retention schedule", "Expiry date", "Classification", "Language"],
            "Complete %": [100 * docs_[c].fillna("").astype(str).str.strip().ne("").mean() if n else 0
                           for c in ["doc_type", "sender", "retention_schedule", "expiry_date", "classification", "language"]]})
        fig = px.bar(comp.sort_values("Complete %"), x="Complete %", y="Field", orientation="h", color="Complete %", color_continuous_scale=["#E8B4A0", TEAL], range_color=[0, 100],
                     text=comp.sort_values("Complete %")["Complete %"].map(lambda v: f"{v:.0f}%"))
        fig.update_traces(textposition="outside"); fig.update_coloraxes(showscale=False); fig.update_xaxes(range=[0, 115])
        show(style(fig, 330, False, "Metadata completeness (live)"))
    with c2:
        if len(ver):
            fig = px.histogram(ver, x="v", nbins=8, color_discrete_sequence=[NAVY])
            fig.update_xaxes(title="Versions per document", dtick=1); fig.update_yaxes(title="Documents")
            show(style(fig, 330, False, "Version churn (live)"))
    pr = A.live_table("SELECT site, status, COUNT(*) n FROM physical_records GROUP BY site, status")
    if len(pr):
        fig = px.bar(pr, x="site", y="n", color="status", color_discrete_sequence=PAL)
        fig.update_traces(marker_line_width=1, marker_line_color="white")
        show(style(fig, 300, True, "Physical & intermediate records by site (live)"))

# =============================================================== COMPLIANCE
elif section == SECTIONS[6]:
    now = pd.Timestamp.now()
    dd = docs.copy()
    wf_active = wf[wf["status"] == "active"].copy() if len(wf) else wf
    if len(wf_active):
        wf_active["age"] = (now - pd.to_datetime(wf_active["modified_at"])).dt.total_seconds() / 86400
    overdue_live = int((wf_active["age"] > 2).sum()) if len(wf_active) else 0
    exp = pd.to_datetime(dd["expiry_date"], errors="coerce")
    e30 = int(((exp >= now) & (exp <= now + pd.Timedelta(days=30))).sum())
    e90 = int(((exp >= now) & (exp <= now + pd.Timedelta(days=90))).sum())
    expired = int((exp < now).sum())
    stt = dist.stats()
    low_conf = int((S["ocr_conf"] < 90).sum())
    r = cols6()
    kpi(r[0], "Overdue approvals (live)", fmt(overdue_live))
    kpi(r[1], "Expiring ≤ 30 days", fmt(e30))
    kpi(r[2], "Expiring ≤ 90 days", fmt(e90))
    kpi(r[3], "Past retention expiry", fmt(expired))
    kpi(r[4], "Past-SLA deliveries", fmt(stt["overdue"]))
    kpi(r[5], "Low-confidence OCR batches", fmt(low_conf))
    st.write("")

    title("Compliance scorecard by department")
    rows = []
    for dpt in rfp_data.DEPARTMENTS:
        if depts and dpt not in depts:
            continue
        a = appr_all[(appr_all["dept"] == dpt) & (appr_all["date"] >= start)]
        k = ack_all[(ack_all["dept"] == dpt) & (ack_all["date"] >= start)]
        d_ = docs[docs["department"] == dpt] if not depts else docs[docs["department"] == dpt]
        meta = 100 * d_[["doc_type", "retention_schedule", "classification"]].fillna("").astype(str).apply(lambda c: c.str.strip().ne("")).mean().mean() if len(d_) else np.nan
        ov = wf_active[wf_active["department"] == dpt] if len(wf_active) else wf_active
        ov_n = int((ov["age"] > 2).sum()) if len(ov) else 0
        rows.append({"Department": dpt, "Approval SLA": 100 - pct(a["breached"].sum(), len(a)) if len(a) else np.nan,
                     "Acknowledged on time": pct(k["on_time"].sum(), len(k)) if len(k) else np.nan, "Metadata complete": meta,
                     "No overdue items": 100 if ov_n == 0 else max(0, 100 - 25 * ov_n)})
    sc = pd.DataFrame(rows).set_index("Department")
    sc["Compliance score"] = sc.mean(axis=1, skipna=True)
    sc = sc.sort_values("Compliance score")
    fig = px.imshow(sc.round(0), aspect="auto", color_continuous_scale=["#E8B4A0", "#F5E3A0", TEAL], zmin=40, zmax=100, text_auto=True)
    fig.update_xaxes(side="top")
    show(style(fig, 560, False))
    note("Score = average of approval-SLA compliance, on-time acknowledgement, metadata completeness and absence of overdue items (0–100).")

    c1, c2 = st.columns(2)
    with c1:
        au = A.live_table("SELECT action, COUNT(*) n FROM audit_log GROUP BY action ORDER BY n DESC LIMIT 14")
        if len(au):
            fig = px.bar(au.sort_values("n"), x="n", y="action", orientation="h", color_discrete_sequence=[NAVY], text="n")
            fig.update_traces(textposition="outside")
            show(style(fig, 420, False, "Audit events by action (live)"))
    with c2:
        ac = A.live_table("SELECT actor, COUNT(*) n FROM audit_log GROUP BY actor ORDER BY n DESC LIMIT 10")
        if len(ac):
            fig = px.bar(ac.sort_values("n"), x="n", y="actor", orientation="h", color_discrete_sequence=[TEAL], text="n")
            fig.update_traces(textposition="outside")
            show(style(fig, 420, False, "Most active users in the audit trail (live)"))
    c1, c2 = st.columns(2)
    with c1:
        es = A.live_table("SELECT signer, COUNT(*) n FROM esign_log GROUP BY signer ORDER BY n DESC")
        if len(es):
            fig = px.bar(es.sort_values("n"), x="n", y="signer", orientation="h", color_discrete_sequence=[PURPLE], text="n")
            fig.update_traces(textposition="outside")
            show(style(fig, 340, False, "Electronic signatures applied per user (live)"))
    with c2:
        dd2 = dd.copy()
        dd2["exp"] = pd.to_datetime(dd2["expiry_date"], errors="coerce")
        bk = pd.cut((dd2["exp"] - now).dt.days, [-10000, 0, 30, 60, 90, 180, 10000], labels=["Expired", "≤ 30 d", "31–60 d", "61–90 d", "91–180 d", "> 180 d"])
        b = bk.value_counts().reindex(["Expired", "≤ 30 d", "31–60 d", "61–90 d", "91–180 d", "> 180 d"]).reset_index()
        b.columns = ["Window", "Documents"]
        fig = px.bar(b, x="Window", y="Documents", color="Window", text="Documents",
                     color_discrete_map={"Expired": RED, "≤ 30 d": CORAL, "31–60 d": AMBER, "61–90 d": "#D9B84A", "91–180 d": TEAL, "> 180 d": GREEN})
        fig.update_traces(textposition="outside")
        show(style(fig, 340, False, "Time to retention expiry (live)"))
    c1, c2 = st.columns(2)
    with c1:
        r0 = np.random.RandomState(11)
        months = pd.date_range(end - pd.Timedelta(days=365), end, freq="MS")
        fl = pd.DataFrame({"Month": months, "Failed sign-ins": r0.poisson(26, len(months)), "Lock-outs": r0.poisson(3, len(months))})
        fig = px.bar(fl.melt("Month", var_name="Event", value_name="n"), x="Month", y="n", color="Event", barmode="group", color_discrete_map={"Failed sign-ins": AMBER, "Lock-outs": RED})
        show(style(fig, 320, True, "Authentication events (simulated history)"))
    with c2:
        sl = AP.groupby(month_start(AP["date"])).agg(b=("breached", "mean")).reset_index()
        sl["Breach rate %"] = sl["b"] * 100
        fig = px.line(sl, x="date", y="Breach rate %", markers=True, color_discrete_sequence=[CORAL])
        show(style(fig, 320, False, "Approval SLA breach rate over time"))

    title("Risk register (auto-generated from the indicators above)")
    def lvl(v, a, b):
        return "🔴 High" if v >= b else ("🟠 Medium" if v >= a else "🟢 Low")
    risks = [
        ("Approvals waiting more than 2 days", overdue_live, lvl(overdue_live, 1, 4), "Escalate to department head; enable auto-reminders"),
        ("Documents expiring within 90 days", e90, lvl(e90, 3, 8), "Start renewal workflow; confirm retention action"),
        ("Deliveries past acknowledgement SLA", stt["overdue"], lvl(stt["overdue"], 1, 5), "Notify department managers; review routing rule SLA"),
        ("Items in triage queue", stt["triage"], lvl(stt["triage"], 2, 6), "Assign manually and extend routing keywords"),
        ("OCR batches below 90% confidence", low_conf, lvl(low_conf, 15, 60), "Re-scan at higher DPI; add operator review step"),
        ("Documents past retention expiry", expired, lvl(expired, 1, 5), "Raise disposal request or apply legal hold"),
    ]
    st.dataframe(pd.DataFrame(risks, columns=["Risk", "Indicator", "Level", "Recommended action"]), use_container_width=True, hide_index=True)

# ============================================================= BUSINESS VALUE
elif section == SECTIONS[7]:
    st.markdown("An illustrative model of what automation returns. **Every assumption is editable** — replace them with the customer's own figures.")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        m_index = st.number_input("Manual indexing time per document (min)", 0.5, 30.0, 4.0, 0.5)
        pages_per_doc = st.number_input("Average pages per document", 1.0, 40.0, 8.0, 1.0)
    with a2:
        m_route = st.number_input("Manual routing / distribution per document (min)", 0.5, 30.0, 3.0, 0.5)
        m_copy = st.number_input("Cost per physical copy / courier (QAR)", 0.0, 50.0, 2.5, 0.5)
    with a3:
        m_search = st.number_input("Time saved per search vs manual lookup (min)", 0.5, 60.0, 6.0, 0.5)
        m_chase = st.number_input("Approval chasing saved per approval (min)", 0.0, 30.0, 4.0, 0.5)
    with a4:
        rate = st.number_input("Loaded staff cost (QAR / hour)", 20.0, 500.0, 85.0, 5.0)
        sol = st.number_input("Annual solution cost (QAR)", 0.0, 5_000_000.0, 420_000.0, 10_000.0, help="Licence + support + hosting; enter your own figure")
    scale = 365 / DAYS
    n_docs = S["pages"].sum() / pages_per_doc * scale
    auto_share = S["auto_routed"].mean() if len(S) else 0.85
    n_search = len(Q) * scale
    n_appr = AP["doc_type"].count() * scale
    copies = n_docs * auto_share * 1.6
    lev = {
        "OCR auto-indexing": n_docs * m_index / 60 * rate * (1 - 0.08),          # 8% still needs operator correction
        "Automatic routing": n_docs * auto_share * m_route / 60 * rate,
        "Faster search": n_search * m_search / 60 * rate * 0.74,                    # only successful searches
        "Workflow automation": n_appr * m_chase / 60 * rate,
        "Print / courier avoided": copies * m_copy,
    }
    total = sum(lev.values())
    hours = (total - lev["Print / courier avoided"]) / rate
    fte = hours / 1800
    net = total - sol
    r = cols6(5)
    kpi(r[0], "Annual value", f"QAR {total / 1000:,.0f}k")
    kpi(r[1], "Hours returned / yr", fmt(hours))
    kpi(r[2], "FTE equivalent", f"{fte:.1f}")
    kpi(r[3], "ROI", f"{net / sol * 100:,.0f}%" if sol else "—")
    kpi(r[4], "Payback", f"{sol / total * 12:.1f} months" if total else "—")
    st.write("")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        names = list(lev.keys()) + ["Total value"]
        fig = go.Figure(go.Waterfall(x=names, measure=["relative"] * len(lev) + ["total"], y=list(lev.values()) + [0],
                                     increasing=dict(marker=dict(color=TEAL)), totals=dict(marker=dict(color=NAVY)),
                                     text=[f"{v / 1000:,.0f}k" for v in lev.values()] + [f"{total / 1000:,.0f}k"], textposition="outside"))
        fig.update_yaxes(title="QAR per year")
        show(style(fig, 380, False, "Where the annual value comes from"))
    with c2:
        mo = pd.DataFrame({"Month": range(1, 13)})
        mo["Cumulative net (QAR)"] = (total / 12 * mo["Month"]) - sol
        fig = px.line(mo, x="Month", y="Cumulative net (QAR)", markers=True, color_discrete_sequence=[NAVY])
        fig.add_hline(y=0, line_dash="dash", line_color=CORAL)
        fig.update_xaxes(dtick=1)
        show(style(fig, 380, False, "Cumulative net benefit, year 1"))
    title("Volumes behind the model (annualised from the selected period)")
    st.dataframe(pd.DataFrame({"Driver": ["Documents captured by OCR", "Auto-routed share", "Searches", "Workflow approvals", "Physical copies avoided"],
                               "Annual volume": [f"{n_docs:,.0f}", f"{auto_share * 100:.0f}%", f"{n_search:,.0f}", f"{n_appr:,.0f}", f"{copies:,.0f}"]}),
                 use_container_width=True, hide_index=True)
    title("Sensitivity — annual value by staff cost and automation adoption")
    rates = [60, 85, 110, 135]
    adopt = [0.5, 0.75, 1.0]
    tab = pd.DataFrame({f"{int(a * 100)}% adoption": [f"{total * (rt / rate) * a / 1000:,.0f}k" for rt in rates] for a in adopt}, index=[f"QAR {rt}/h" for rt in rates])
    st.dataframe(tab, use_container_width=True)
    note("Model outputs are illustrative and scale directly with the assumptions above. Volumes come from the demo's operating history, not from a customer.")

# ============================================================ REPORTS & EXPORT
else:
    datasets = {
        "scanning_batches.csv": S, "workflow_stage_actions.csv": AP, "search_activity.csv": Q, "distribution_acknowledgements.csv": K,
        "live_documents.csv": docs.drop(columns=["body_text"], errors="ignore"),
        "live_distribution_log.csv": A.live_table("SELECT l.*, d.doc_code, d.title FROM dist_log l JOIN documents d ON d.id=l.document_id"),
        "live_audit_log.csv": A.live_table("SELECT * FROM audit_log"),
        "live_esignatures.csv": A.live_table("SELECT * FROM esign_log"),
    }
    title("Analytics datasets")
    info = pd.DataFrame([{"Dataset": k, "Rows": len(v), "Columns": v.shape[1], "Source": "live" if k.startswith("live") else "history (simulated) + live captures"} for k, v in datasets.items()])
    st.dataframe(info, use_container_width=True, hide_index=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in datasets.items():
            z.writestr(k, v.to_csv(index=False))
    st.download_button("⬇ Download all datasets (ZIP of CSV)", buf.getvalue(), "edms_analytics_datasets.zip")
    title("Scheduled reports (simulated delivery)")
    sched = pd.DataFrame([
        {"Report": "Executive scanning & OCR summary", "Schedule": "Every Sunday 07:00", "Recipients": "Executive Offices, Medical Records", "Format": "PDF / CSV"},
        {"Report": "Workflow SLA & bottleneck report", "Schedule": "Daily 06:30", "Recipients": "Department heads", "Format": "CSV"},
        {"Report": "Routing & acknowledgement compliance", "Schedule": "Daily 07:30", "Recipients": "Records Officer, QRI", "Format": "CSV"},
        {"Report": "Retention & expiry look-ahead (90 days)", "Schedule": "1st of month", "Recipients": "Legal, QRI", "Format": "PDF"},
        {"Report": "Search content-gap report", "Schedule": "Monthly", "Recipients": "Records Officer, IT", "Format": "CSV"},
        {"Report": "Audit readiness pack", "Schedule": "Quarterly", "Recipients": "QRI, Executive Offices", "Format": "PDF"},
    ])
    st.dataframe(sched, use_container_width=True, hide_index=True)
    pick = st.selectbox("Run a report now", sched["Report"].tolist())
    src = {"Executive scanning & OCR summary": "scanning_batches.csv", "Workflow SLA & bottleneck report": "workflow_stage_actions.csv",
           "Routing & acknowledgement compliance": "distribution_acknowledgements.csv", "Retention & expiry look-ahead (90 days)": "live_documents.csv",
           "Search content-gap report": "search_activity.csv", "Audit readiness pack": "live_audit_log.csv"}[pick]
    st.download_button(f"⬇ Download “{pick}” ({src})", datasets[src].to_csv(index=False).encode("utf-8-sig"), src)
    with st.expander("Data dictionary & definitions"):
        st.markdown("""
- **OCR confidence** — engine-reported mean word confidence per batch, weighted by pages in summaries.
- **First-pass accuracy** — share of pages that needed no operator correction.
- **Straight-through routing** — items placed with the owning department by content rules with no manual step.
- **Stage time** — hours between a document entering and leaving a workflow stage; **SLA breach** = stage time above the stage target.
- **Utilisation** — weekly arrivals ÷ (licensed users × items per person per week).
- **Compliance score** — mean of approval SLA, on-time acknowledgement, metadata completeness and absence of overdue items.
- **Live** data is read from the running repository; **history (simulated)** is a deterministic 12-month baseline generated for the demo.
""")
