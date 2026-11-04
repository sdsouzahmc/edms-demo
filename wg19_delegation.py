from datetime import date, timedelta

import pandas as pd
import streamlit as st
import db
import db_ext
import delegation as dg
import rfp_data
import theme

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("19 · Approval Delegation", "Out-of-office rules · cover for staff on leave · scoped, dated and fully audited")

user = theme.current_user()
admin = theme.is_admin()
users = list(rfp_data.ROLES.keys())
st.markdown(f"{theme.tag_custom('Vacation rules — approvals follow the delegate automatically and return when the leave ends')}",
            unsafe_allow_html=True)

allr = dg.rules()
m1, m2, m3, m4 = st.columns(4)
theme.metric_card("Active now", len([r for r in allr if r["state"] == "Active"]), m1)
theme.metric_card("Scheduled", len([r for r in allr if r["state"] == "Scheduled"]), m2)
theme.metric_card("Delegated to me (open items)", dg.delegated_count(user), m3)
theme.metric_card("Actions taken on behalf", len(dg.acted_on_behalf()), m4)
st.write("")

away = dg.is_away(user)
if away:
    st.warning(f"🏖 You are out of office until **{away['end_date']}** — **{away['delegate']}** is covering your approvals.")

tabA, tabB, tabC, tabD = st.tabs(["🏖 Set up delegation", "📋 All delegations", "🤝 Delegated to me", "📜 Actions on behalf"])

# ------------------------------------------------------------- set up -------
with tabA:
    st.markdown('<div class="efs-section-title">New out-of-office / delegation rule</div>', unsafe_allow_html=True)
    if admin:
        st.caption("As Administrator you can set this up for any staff member who is going on leave.")
    else:
        st.caption("Set up cover for yourself. Your Administrator can also set it up for you.")
    with st.container(border=True, key="deleg_form"):
        c1, c2 = st.columns(2)
        who = c1.selectbox("Staff member going on leave", users if admin else [user],
                           index=(users.index(user) if admin else 0), key="dg_who",
                           format_func=lambda u: f"{u} — {rfp_data.ROLES[u]['role']} ({rfp_data.ROLES[u]['dept']})")
        others = [u for u in users if u != who]
        # sensible default: same department colleague first
        others.sort(key=lambda u: (rfp_data.ROLES[u]["dept"] != rfp_data.ROLES[who]["dept"], u))
        to = c2.selectbox("Delegate approvals to", others, key="dg_to",
                          format_func=lambda u: f"{u} — {rfp_data.ROLES[u]['role']} ({rfp_data.ROLES[u]['dept']})")
        d1, d2, d3 = st.columns([1, 1, 1])
        start = d1.date_input("From", value=date.today(), key="dg_from")
        end = d2.date_input("Until (inclusive)", value=date.today() + timedelta(days=7), key="dg_until")
        reason = d3.selectbox("Reason", dg.REASONS, key="dg_reason")
        e1, e2 = st.columns([2, 1])
        scope = e1.multiselect("Only these document types (leave empty = all approvals)", rfp_data.DOC_TYPES, key="dg_types")
        excl = e2.checkbox("Keep Confidential / Restricted with me", key="dg_excl",
                           help="Sensitive documents are not shown to the delegate.")
        note = st.text_area("Note to the delegate (optional)", key="dg_note", height=70,
                            placeholder="e.g. Back on the 15th. Urgent items: call my mobile.")
        errs, warns = dg.validate(who, to, start, end) if end and start else ([], [])
        for e in errs:
            st.error(e)
        for w in warns:
            st.warning(w)
        days = (end - start).days + 1 if end >= start else 0
        st.caption(f"Cover period: **{days} day(s)** · starts "
                   f"{'today' if start == date.today() else str(start)} · automatically ends after {end}. "
                   "No need to switch it off.")
        if st.button("💾 Activate delegation", type="primary", disabled=bool(errs), key="dg_save"):
            dg.add_rule(who, to, start, end, reason, note, scope or None, excl, user)
            st.success(f"Done — from {start} to {end}, **{to}** will see and can approve {who}'s items.")
            st.rerun()

    with st.expander("How it works"):
        st.markdown("""
- During the dates, anything that reaches the absent person's approval queue also appears in the **delegate's** queue, tagged *On behalf of …*.
- The delegate approves or rejects with their **own e-signature**; the record shows who actually acted and for whom.
- The absent person is **notified** of every action taken for them, and every action is written to the audit trail.
- The rule **starts and stops automatically** on the chosen dates. It can be cancelled early at any time.
- Optionally limit to certain document types, or keep Confidential / Restricted documents out of the delegate's reach.
- Different from the one-off **↪ Delegate** button on a single item in the Workflow queue.
        """)

# ------------------------------------------------------------- all ----------
with tabB:
    sel = st.multiselect("Show", ["Active", "Scheduled", "Expired", "Cancelled"], default=["Active", "Scheduled"], key="dg_filter")
    rows = [r for r in dg.rules() if r["state"] in sel]
    mine = [r for r in rows if admin or user in (r["delegator"], r["delegate"], r["created_by"])]
    if not mine:
        st.info("No delegations match this filter.")
    for r in mine:
        col = {"Active": "#2E7D32", "Scheduled": "#1F6F78", "Expired": "#6B7280", "Cancelled": "#B00020"}[r["state"]]
        scope = ", ".join(r["types"]) if r["types"] else "All approvals"
        if r["exclude_sensitive"]:
            scope += " · excl. Confidential/Restricted"
        st.markdown(f"""<div class="efs-card" style="border-left:5px solid {col}">
        <b>{r['delegator']}</b> → <b>{r['delegate']}</b>
        <span style="background:{col};color:#fff;border-radius:10px;padding:1px 9px;font-size:.75rem;margin-inline-start:8px">{theme.tr(r['state'])}</span><br>
        📅 {r['start_date']} → {r['end_date']} &nbsp;·&nbsp; {r['reason']} &nbsp;·&nbsp; 🎯 {scope}<br>
        <span style="color:#6B7280;font-size:.8rem">Set by {r['created_by']}{(' · “' + r['note'] + '”') if r['note'] else ''}</span>
        </div>""", unsafe_allow_html=True)
        if r["state"] in ("Active", "Scheduled") and (admin or user in (r["delegator"], r["created_by"])):
            if st.button("✖ Cancel this delegation" if r["state"] == "Active" else "✖ Cancel", key=f"dg_cancel_{r['id']}"):
                dg.cancel_rule(r["id"], user)
                st.rerun()

# ------------------------------------------------------------- to me --------
with tabC:
    cov = dg.covering(user)
    sched = [r for r in dg.rules(False) if r["delegate"] == user and r["state"] == "Scheduled"]
    if admin:
        st.info("You are an Administrator and already see every approval. Switch to a department user in the sidebar to see how a delegate experiences it.")
    for r in cov:
        st.success(f"🤝 Covering **{r['delegator']}** until {r['end_date']}" + (f" — “{r['note']}”" if r["note"] else ""))
    for r in sched:
        st.info(f"⏳ From {r['start_date']} you will cover {r['delegator']} until {r['end_date']}.")
    items = [x for x in dg.pending_for_user(user) if x["on_behalf_of"]]
    if items:
        st.markdown(f"**{len(items)}** item(s) waiting for you on someone's behalf — open **4 · Workflow & Approvals** to act.")
        df = pd.DataFrame([{"Document": x["doc_code"], "Title": x["title"], "Stage": x["stage"],
                            "On behalf of": x["on_behalf_of"], "Classification": x["classification"]} for x in items])
        st.dataframe(df, use_container_width=True, hide_index=True)
    elif not (cov or sched or admin):
        st.info("Nobody has delegated approvals to you at the moment.")
    elif cov:
        st.caption("No open items from the people you are covering right now.")

# ------------------------------------------------------------- audit --------
with tabD:
    acts = dg.acted_on_behalf()
    if not acts:
        st.info("No approvals have been actioned on someone's behalf yet. Switch to a delegate (e.g. Omar Al-Kaabi), approve a Finance item in the Workflow queue, then return here.")
    else:
        st.dataframe(pd.DataFrame([{"Time": a["ts"], "Who acted": a["actor"], "Action": a["action"], "Detail": a["detail"]} for a in acts]),
                     use_container_width=True, hide_index=True)
