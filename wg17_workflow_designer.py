import json
import streamlit as st
import db
import db_ext
import rfp_data
import theme
import wfdesign as wd

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("17 · Workflow Designer", "Design approval flows visually · conditions, assignees, SLA, e-signature · simulate · publish live with versioning")

user = theme.current_user()
can_publish = theme.is_admin()
st.markdown(f"{theme.tag_custom('Visual designer — no code, changes apply to new documents immediately')}", unsafe_allow_html=True)

# --------------------------------------------------------------- scope ------
s1, s2, s3 = st.columns([1.3, 1.3, 1.6])
dept = s1.selectbox("Department", rfp_data.DEPARTMENTS, key="wfd_dept")
dtype = s2.selectbox("Document type (blank = department default)", [""] + rfp_data.DOC_TYPES, key="wfd_type",
                     format_func=lambda x: x or "(department default)")
scope = f"{dept}|{dtype}"
if st.session_state.get("wfd_scope") != scope:
    st.session_state["wfd_scope"] = scope
    st.session_state["wfd_steps"] = wd.current_steps(dept, dtype)
    st.session_state["wfd_sel"] = None
steps = st.session_state["wfd_steps"]
pub = wd.latest(dept, dtype, "Published")
with s3:
    tpl = st.selectbox("Start from a template", ["—"] + list(wd.TEMPLATES), key="wfd_tpl")
    if tpl != "—" and st.session_state.get("wfd_tpl_applied") != (scope, tpl):
        st.session_state["wfd_steps"] = steps = wd.from_template(tpl)
        st.session_state["wfd_tpl_applied"] = (scope, tpl)
        st.session_state["wfd_sel"] = None
st.caption(("Live design: **v%d** · %s · published %s by %s" % (pub["version"], pub["name"], pub["updated_at"][:16], pub["updated_by"]))
           if pub else "No visual design published for this scope yet — new documents use the default chain shown below.")

tabs = st.tabs(["🧩 Designer", "🧪 Simulate", "🕘 Versions", "📚 Live designs"])

with tabs[0]:
    # palette
    st.markdown('<div class="efs-section-title">Add a step</div>', unsafe_allow_html=True)
    pc = st.columns(5) + st.columns(5)
    for i, (k, (col, em, nm)) in enumerate(wd.KINDS.items()):
        if pc[i].button(f"{em} {k}", key=f"add_{k}", use_container_width=True):
            ns = wd.new_step(k, nm if nm not in [s["name"] for s in steps] else f"{nm} {len(steps) + 1}",
                             esign=k in ("Approval", "Sign-off", "Executive"))
            steps.append(ns)
            st.session_state["wfd_sel"] = ns["id"]
            st.rerun()

    sel = st.session_state.get("wfd_sel")
    st.markdown(wd.svg(steps, selected=sel), unsafe_allow_html=True)
    if not steps:
        st.info("The flow is empty — add steps from the palette above or pick a template.")
    else:
        ids = [s["id"] for s in steps]
        labels = {s["id"]: f"{i + 1}. {s['name']}" for i, s in enumerate(steps)}
        sel = st.radio("Select a step to edit", ids, format_func=lambda x: labels[x], horizontal=True,
                       index=ids.index(sel) if sel in ids else 0, key="wfd_sel_radio")
        st.session_state["wfd_sel"] = sel
        i = ids.index(sel)
        s = steps[i]
        with st.container(border=True):
            st.markdown(f"**Step settings — {s['name']}**")
            a, b, c = st.columns(3)
            s["name"] = a.text_input("Step name", s["name"], key=f"n_{sel}")
            s["kind"] = b.selectbox("Step type", list(wd.KINDS), index=list(wd.KINDS).index(s["kind"]), key=f"k_{sel}")
            s["assignee"] = c.selectbox("Assigned to", ["(owner department)"] + rfp_data.DEPARTMENTS,
                                        index=(["(owner department)"] + rfp_data.DEPARTMENTS).index(s["assignee"]) if s["assignee"] in rfp_data.DEPARTMENTS + ["(owner department)"] else 0,
                                        key=f"as_{sel}")
            d1, d2, d3 = st.columns(3)
            s["role"] = d1.selectbox("Approver", ["Any approver", "Head of department", "Two approvers (all must approve)"],
                                     index=["Any approver", "Head of department", "Two approvers (all must approve)"].index(s.get("role", "Any approver")), key=f"r_{sel}")
            s["sla_h"] = d2.number_input("SLA (hours)", 1, 720, int(s["sla_h"]), key=f"sla_{sel}")
            s["esign"] = d3.checkbox("✍ Electronic signature required", s["esign"], key=f"es_{sel}")
            x1, x2 = st.columns(2)
            s["mode"] = x1.selectbox("Execution", ["Sequential", "Parallel with previous"],
                                     index=["Sequential", "Parallel with previous"].index(s.get("mode", "Sequential")), key=f"md_{sel}",
                                     disabled=i == 0, help="Sequential: starts after the previous step finishes. Parallel: starts at the same time as the previous step.")
            if i == 0:
                s["mode"] = "Sequential"
            s["join"] = x2.selectbox("When the parallel group finishes", ["All must approve", "Any one approves"],
                                     index=["All must approve", "Any one approves"].index(s.get("join", "All must approve")), key=f"jn_{sel}",
                                     disabled=s["mode"] == "Sequential" and not (i + 1 < len(steps) and steps[i + 1].get("mode") == "Parallel with previous"),
                                     help="Applies to the whole parallel group (taken from its first step).")
            e1, e2 = st.columns(2)
            s["cond"] = e1.selectbox("Run this step", wd.COND_FIELDS, index=wd.COND_FIELDS.index(s["cond"]), key=f"c_{sel}")
            if s["cond"] == "Classification is":
                opts = db.CLASSIFICATIONS
            elif s["cond"] == "Security level at least":
                opts = wd.LEVELS[2:]
            elif s["cond"] == "Document type is":
                opts = rfp_data.DOC_TYPES
            else:
                opts = None
            if opts:
                s["cval"] = e2.selectbox("Value", opts, index=opts.index(s["cval"]) if s["cval"] in opts else 0, key=f"cv_{sel}")
            else:
                s["cval"] = ""
            m1, m2, m3, m4 = st.columns(4)
            if m1.button("⬅ Move earlier", disabled=i == 0, key=f"up_{sel}"):
                steps[i - 1], steps[i] = steps[i], steps[i - 1]
                st.rerun()
            if m2.button("Move later ➡", disabled=i == len(steps) - 1, key=f"dn_{sel}"):
                steps[i + 1], steps[i] = steps[i], steps[i + 1]
                st.rerun()
            if m3.button("⧉ Duplicate", key=f"dup_{sel}"):
                cp = dict(s, id=wd.new_step()["id"], name=s["name"] + " (copy)")
                steps.insert(i + 1, cp)
                st.session_state["wfd_sel"] = cp["id"]
                st.rerun()
            if m4.button("🗑 Remove step", key=f"rm_{sel}"):
                steps.pop(i)
                st.session_state["wfd_sel"] = None
                st.rerun()

    st.markdown('<div class="efs-section-title">Check & publish</div>', unsafe_allow_html=True)
    msgs = wd.validate(steps)
    for lvl, m in msgs:
        {"error": st.error, "warn": st.warning, "ok": st.success}[lvl](m)
    has_err = any(l == "error" for l, _ in msgs)
    note = st.text_input("Change note (kept in version history)", placeholder="e.g. Added Legal Review for external contracts")
    b1, b2, b3 = st.columns([1, 1, 2])
    if b1.button("💾 Save as draft", disabled=has_err or not steps):
        v = wd.save(dept, dtype, tpl if tpl != "—" else "Custom flow", steps, user, False, note)
        st.success(f"Draft v{v} saved (not live).")
    if b2.button("🚀 Publish live", type="primary", disabled=has_err or not steps or not can_publish):
        v = wd.save(dept, dtype, tpl if tpl != "—" else "Custom flow", steps, user, True, note)
        st.success(f"Published v{v}. Every new {dtype or 'document'} registered for {dept} now follows this flow. Documents already in flight keep their current chain.")
        st.balloons()
    if not can_publish:
        b3.caption("Only Administrators can publish — you can save drafts for review.")

with tabs[1]:
    st.caption("Try a sample document against the design above — steps whose condition is not met are skipped (faded).")
    q1, q2, q3 = st.columns(3)
    cl = q1.selectbox("Classification", db.CLASSIFICATIONS, key="sim_cl")
    sl = q2.selectbox("Security level", wd.LEVELS, index=1, key="sim_sl")
    dt_ = q3.selectbox("Document type", rfp_data.DOC_TYPES, key="sim_dt")
    active = {s["id"] for s in steps if wd.matches(s, cl, sl, dt_)}
    st.markdown(wd.svg(steps, active=active), unsafe_allow_html=True)
    on = [s for s in steps if s["id"] in active]
    gs = wd.grouped(on)
    parts = ["Draft"] + [(g[0]["name"] if len(g) == 1 else "[ " + " ‖ ".join(x["name"] for x in g) + (" · any one" if g[0].get("join") == "Any one approves" else " · all") + " ]") for g in gs] + ["Released"]
    st.markdown("**Resulting path:** " + " → ".join(f"`{p}`" for p in parts))
    total = sum(max(x["sla_h"] for x in g) for g in gs)          # a parallel group takes as long as its slowest branch
    seq_total = sum(x["sla_h"] for x in on)
    sg = sum(1 for x in on if x["esign"])
    st.markdown(f"Target turnaround **{total} h** (≈ {total / 24:.1f} days)" + (f" — **{seq_total - total} h faster** than running everything one after another ({seq_total} h)" if seq_total > total else "")
                + f" · **{sg}** e-signature(s) · **{len(on)}** of **{len(steps)}** steps apply.")

with tabs[2]:
    hist = wd.history(dept, dtype)
    if not hist:
        st.caption("No saved versions yet for this scope.")
    for h in hist:
        steps_h = json.loads(h["steps"])
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**v{h['version']}** · {theme.pill('Released') if h['status'] == 'Published' else h['status']} · {h['updated_by']} · {h['updated_at'][:16]}"
                    f"  \n{' → '.join(s['name'] for s in steps_h)}  \n<span style='color:#6B7280;font-size:.8rem'>{h['note'] or ''}</span>", unsafe_allow_html=True)
        if c2.button("↩ Restore & publish", key=f"rs_{h['id']}", disabled=not can_publish or h["status"] == "Published"):
            wd.restore(h["id"], user)
            st.session_state.pop("wfd_scope", None)
            st.rerun()

with tabs[3]:
    rows = wd.all_published()
    st.markdown(f"**{len(rows)}** visual design(s) are live. Open one to see the flow; use the department / document type selectors above to edit it.")
    for r in rows:
        ss = json.loads(r["steps"])
        with st.expander(f"🟢 {r['department']} · {r['doc_type'] or 'department default'} — {r['name']} (v{r['version']}) · {len(ss)} steps"):
            st.caption(f"{r['note'] or ''}  ·  published by {r['updated_by']} · {r['updated_at'][:16]}")
            st.markdown(wd.svg(ss, per_row=5), unsafe_allow_html=True)
