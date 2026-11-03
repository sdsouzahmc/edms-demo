import streamlit as st
import db
import db_ext
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("9 · My Workspace", "User dashboard · bookmarks · pending workflows · notifications · recycle bin")

user = theme.current_user()
prof = theme.current_profile()
st.markdown(f"{theme.tag_ms('SharePoint personal views + Power Automate notifications')}", unsafe_allow_html=True)
st.write("")

pending = db.get_pending_for_assignee(prof["dept"], theme.is_admin())
unread = db_ext.get_notifications(user, only_unread=True)
bms = db_ext.get_bookmarks(user)
c1, c2, c3, c4 = st.columns(4)
theme.metric_card("Pending workflows", len(pending), c1)
theme.metric_card("Unread notifications", len(unread), c2)
theme.metric_card("Bookmarks", len(bms), c3)
theme.metric_card("Recycle bin", len(db_ext.recycle_bin()), c4)
st.write("")

tabs = st.tabs(["🏠 My Dashboard", "🔔 Notifications & Subscriptions", "⭐ Bookmarks", "🗑️ Recycle Bin"])

with tabs[0]:
    l, r = st.columns(2)
    with l:
        st.markdown('<div class="efs-section-title">Recently accessed</div>', unsafe_allow_html=True)
        recent = db_ext.recent_views(user)
        if not recent:
            st.caption("Nothing yet — open a document via Search & Retrieval (View / Log Access).")
        for d in recent:
            st.markdown(f"- **{d['doc_code']}** — {d['title']}  \n  <span style='color:#6B7280;font-size:0.8rem'>{d['last_ts']}</span>",
                        unsafe_allow_html=True)
        st.markdown('<div class="efs-section-title">My bookmarks</div>', unsafe_allow_html=True)
        for d in bms[:6]:
            st.markdown(f"- ⭐ **{d['doc_code']}** — {d['title']}")
        if not bms:
            st.caption("No bookmarks yet.")
    with r:
        st.markdown('<div class="efs-section-title">Pending workflows</div>', unsafe_allow_html=True)
        for w in pending[:8]:
            st.markdown(f"- {theme.pill(w['stage'])} **{w['doc_code']}** — {w['title']}", unsafe_allow_html=True)
        if not pending:
            st.caption("Nothing pending for you.")
        st.page_link(theme.PAGE_FILES["4"], label="→ Open Workflow & Approvals")
        st.markdown('<div class="efs-section-title">Reminders — documents expiring soon</div>', unsafe_allow_html=True)
        soon = [e for e in db_ext.expiry_report() if e["days_left"] is not None and e["days_left"] <= 90
                and (theme.is_admin() or e["department"] == prof["dept"])]
        for e in soon[:6]:
            tag = "🔴 expired" if e["days_left"] < 0 else f"🟠 {e['days_left']} days"
            st.markdown(f"- {tag} — **{e['doc_code']}** {e['title']}")
        if not soon:
            st.caption("No review/expiry dates due in the next 90 days.")

with tabs[1]:
    st.markdown('<div class="efs-section-title">Notifications</div>', unsafe_allow_html=True)
    notes = db_ext.get_notifications(user)
    icons = {"approval": "✍️", "overdue": "⏰", "reminder": "🔔", "info": "ℹ️", "edit": "✏️"}
    for n in notes:
        st.markdown(f"{icons.get(n['kind'], '•')} {'**' if not n['is_read'] else ''}{n['message']}{'**' if not n['is_read'] else ''}  \n"
                    f"<span style='color:#6B7280;font-size:0.8rem'>{n['ts']}</span>", unsafe_allow_html=True)
    if not notes:
        st.caption("No notifications.")
    if notes and st.button("Mark all as read"):
        db_ext.mark_all_read(user)
        st.rerun()
    st.markdown('<div class="efs-section-title">Subscriptions (new / updated document alerts)</div>', unsafe_allow_html=True)
    subs = db_ext.my_subscriptions(user)
    docs = db.get_documents()
    pick = st.selectbox("Subscribe to a document", ["—"] + [f"{d['doc_code']} — {d['title']}" for d in docs])
    if pick != "—" and st.button("Toggle subscription to document"):
        code = pick.split(" — ")[0]
        d = db.get_document_by_code(code)
        on = db_ext.toggle_subscription(user, f"doc:{d['id']}")
        st.success("Subscribed." if on else "Unsubscribed.")
        st.rerun()
    tc1, tc2 = st.columns([2, 1])
    with tc1:
        topic = st.selectbox("Subscribe to a classification topic", ["Regulatory", "External", "Internal"])
    with tc2:
        st.write("")
        if st.button("Toggle topic subscription"):
            db_ext.toggle_subscription(user, f"topic:{topic}")
            st.rerun()
    st.caption("Active: " + (", ".join(subs) if subs else "none"))

with tabs[2]:
    st.markdown('<div class="efs-section-title">Bookmark any document</div>', unsafe_allow_html=True)
    docs = db.get_documents()
    mine = {d["id"] for d in bms}
    for d in docs[:25]:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"{'⭐' if d['id'] in mine else '☆'} **{d['doc_code']}** — {d['title']}  \n"
                        f"<span style='color:#6B7280;font-size:0.8rem'>{d['department']} · {d['doc_type']}</span>",
                        unsafe_allow_html=True)
        with c2:
            if st.button("Remove" if d["id"] in mine else "Bookmark", key=f"bm_{d['id']}"):
                db_ext.toggle_bookmark(user, d["id"])
                st.rerun()

with tabs[3]:
    st.markdown('<div class="efs-section-title">Recycle bin — restore deleted documents</div>', unsafe_allow_html=True)
    st.caption("Deleting a document moves it here (soft delete, fully audited). Documents under legal hold cannot be deleted.")
    bin_ = db_ext.recycle_bin()
    for d in bin_:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"🗑️ **{d['doc_code']}** — {d['title']}  \n<span style='color:#6B7280;font-size:0.8rem'>"
                        f"deleted by {d['deleted_by']} at {d['deleted_at']} · was {d['deleted_from']}</span>", unsafe_allow_html=True)
        with c2:
            if st.button("♻️ Restore", key=f"rs_{d['id']}"):
                db_ext.restore(d["id"], user)
                st.rerun()
    if not bin_:
        st.info("Recycle bin is empty.")
    st.markdown("---")
    st.markdown("**Move a document to the recycle bin**")
    cand = [d for d in db.get_documents() if (theme.is_admin() or d["department"] == prof["dept"])]
    if cand:
        pick = st.selectbox("Document", [f"{d['doc_code']} — {d['title']}" for d in cand], key="del_pick")
        if st.button("🗑️ Delete (soft)"):
            d = db.get_document_by_code(pick.split(" — ")[0])
            if db_ext.soft_delete(d["id"], user):
                st.success("Moved to recycle bin.")
                st.rerun()
            else:
                st.error("Cannot delete — document is under legal hold.")
    else:
        st.caption("No documents in your department.")
