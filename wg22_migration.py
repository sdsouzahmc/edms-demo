import pandas as pd
import streamlit as st
import db
import db_ext
import migration as mg
import rfp_data
import theme

db.init_db()
db_ext.init_ext()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("22 · Data Migration", "SharePoint · file servers · scanned paper → EDMS · analyse, map, dry-run, import, verify")

user = theme.current_user()
st.markdown(f"{theme.tag_custom('Migration toolkit — repeatable, checksum-verified, fully audited')}", unsafe_allow_html=True)

SOURCES = ["SharePoint Online library", "Windows file server / network share", "Scanned paper batch"]
ss = st.session_state
bl = mg.batches()
m1, m2, m3, m4 = st.columns(4)
theme.metric_card("Migration batches", len(bl), m1)
theme.metric_card("Files imported", sum(b["imported"] or 0 for b in bl), m2)
theme.metric_card("Duplicates avoided", sum(b["duplicates"] or 0 for b in bl), m3)
theme.metric_card("Checksum-verified", sum(b["verified"] or 0 for b in bl), m4)
st.write("")

t1, t2, t3, t4, t5 = st.tabs(["1 · Source", "2 · Analyse & map", "3 · Dry-run & migrate", "4 · Verification report", "ℹ️ Method"])

# ---------------------------------------------------------------- source ----
with t1:
    st.markdown('<div class="efs-section-title">Choose what to migrate</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    stype = c1.radio("Source type", SOURCES, key="mg_type")
    path = c2.text_input("Source location", value=ss.get("mg_path", mg.LEGACY), key="mg_path_in",
                         help="Production: SharePoint site URL (Graph API) or \\\\server\\share (SMB). Demo: a folder on the application server.")
    ss["mg_path"] = path
    st.caption("In the live project the connectors read SharePoint through Microsoft Graph and file servers through SMB, using a read-only service account. "
               "The demo reads a folder on this server so you can see the whole process end to end.")
    if st.button("🧪 Create a sample legacy share (messy on purpose)", key="mg_sample", disabled=not theme.is_admin()):
        mg.create_sample(path)
        ss.pop("mg_items", None)
        st.success("Sample created: duplicates, temp files, empty file, an .exe, Arabic file names, an unmapped folder and two scanned images.")
    import os
    if os.path.isdir(path):
        n = sum(len(f) for _, _, f in os.walk(path))
        st.info(f"📁 Source found — {n} file(s). Continue to step 2.")
    else:
        st.warning("Source folder not found. Create the sample above, or enter an existing folder path.")

# ---------------------------------------------------------------- analyse ---
with t2:
    import os
    path = ss.get("mg_path", mg.LEGACY)
    if not os.path.isdir(path):
        st.info("Select a source in step 1 first.")
    else:
        if st.button("🔎 Analyse source" if "mg_items" not in ss else "🔄 Re-scan source", type="primary", key="mg_scan"):
            with st.spinner("Scanning and fingerprinting files…"):
                ss["mg_items"] = mg.scan(path)
        items = ss.get("mg_items")
        if items:
            imp = [i for i in items if i["plan"] == "Import"]
            dups = [i for i in items if i["issue"].startswith(("Duplicate", "Already"))]
            sk = [i for i in items if i["plan"] == "Skip" and i not in dups]
            a, b, c, d = st.columns(4)
            theme.metric_card("Files found", len(items), a)
            theme.metric_card("Ready to import", len(imp), b)
            theme.metric_card("Duplicates", len(dups), c)
            theme.metric_card("Skipped (junk / unsupported)", len(sk), d)
            st.markdown('<div class="efs-section-title">Mapping — where each legacy folder goes</div>', unsafe_allow_html=True)
            st.caption("Top folder → department, second-level folder → document type. Detected automatically; correct anything below before migrating.")
            combos = sorted({(i["top"], i["second"]) for i in imp})
            base = pd.DataFrame([{"Top folder": t, "Sub-folder": s, "Files": sum(1 for i in imp if (i["top"], i["second"]) == (t, s)),
                                  "Department": next((i["dept"] for i in imp if (i["top"], i["second"]) == (t, s)), None) or "⚠ unmapped",
                                  "Document type": next(i["type"] for i in imp if (i["top"], i["second"]) == (t, s))} for t, s in combos])
            if not base.empty:
                ed = st.data_editor(base, hide_index=True, use_container_width=True, key="mg_map", disabled=["Top folder", "Sub-folder", "Files"],
                                    column_config={"Department": st.column_config.SelectboxColumn(options=["⚠ unmapped"] + rfp_data.DEPARTMENTS),
                                                   "Document type": st.column_config.SelectboxColumn(options=rfp_data.DOC_TYPES)})
                for _, r in ed.iterrows():
                    for i in imp:
                        if (i["top"], i["second"]) == (r["Top folder"], r["Sub-folder"]):
                            i["dept"] = None if r["Department"] == "⚠ unmapped" else r["Department"]
                            i["type"] = r["Document type"]
            st.markdown('<div class="efs-section-title">Inventory</div>', unsafe_allow_html=True)
            flt = st.radio("Show", ["All", "Ready", "Duplicates", "Skipped"], horizontal=True, key="mg_flt")
            view = {"All": items, "Ready": imp, "Duplicates": dups, "Skipped": sk}[flt]
            st.dataframe(pd.DataFrame([{"Path": i["rel"], "KB": round(i["size"] / 1024, 1), "Modified": i["mtime"][:10], "Plan": i["plan"],
                                        "Department": i["dept"] or "—", "Type": i["type"], "Note": i["issue"]} for i in view]),
                         use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- run -------
with t3:
    items = ss.get("mg_items")
    if not items:
        st.info("Analyse the source first (step 2).")
    else:
        imp = [i for i in items if i["plan"] == "Import"]
        st.markdown('<div class="efs-section-title">Dry-run — what will happen</div>', unsafe_allow_html=True)
        per = {}
        for i in imp:
            per[i["dept"] or "Medical Records (review)"] = per.get(i["dept"] or "Medical Records (review)", 0) + 1
        st.dataframe(pd.DataFrame([{"Department": k, "Files to import": v} for k, v in sorted(per.items())]), use_container_width=True, hide_index=True)
        st.caption(f"{len(imp)} file(s) will be imported; {len(items) - len(imp)} will be skipped. Nothing has been changed yet.")
        o1, o2 = st.columns(2)
        pres = o1.checkbox("Keep original file dates", value=True, key="mg_pres")
        mir = o2.checkbox("Rebuild the legacy folder structure under  Department / Migrated /", value=True, key="mg_mir")
        nm = st.text_input("Batch name", value=f"{ss.get('mg_type', mg.__name__).split(' ')[0]} migration {pd.Timestamp.now():%Y-%m-%d}", key="mg_name")
        if st.button(f"🚚 Migrate {len(imp)} file(s) now", type="primary", disabled=not theme.is_admin() or not imp, key="mg_run"):
            bar = st.progress(0.0, text="Starting…")
            bid = mg.run(items, ss["mg_path"], user, nm, ss.get("mg_type", SOURCES[1]), pres, mir,
                         progress=lambda p, f: bar.progress(p, text=f"Importing {f}"))
            bar.empty()
            ss["mg_last"] = bid
            ss.pop("mg_items", None)
            st.success("Migration finished — open step 4 for the verification report.")
        if not theme.is_admin():
            st.caption("Only an Administrator can run a migration.")

# ---------------------------------------------------------------- report ----
with t4:
    bl = mg.batches()
    if not bl:
        st.info("No migration has been run yet.")
    else:
        pick = st.selectbox("Batch", [b["id"] for b in bl], format_func=lambda i: next(f"#{b['id']} · {b['name']} · {b['started_at'][:16]}" for b in bl if b["id"] == i),
                            index=0, key="mg_batch")
        b = next(x for x in bl if x["id"] == pick)
        its = mg.batch_items(pick)
        a1, a2, a3, a4, a5 = st.columns(5)
        theme.metric_card("In source", b["total"], a1)
        theme.metric_card("Imported", b["imported"], a2)
        theme.metric_card("Duplicates", b["duplicates"], a3)
        theme.metric_card("Skipped", b["skipped"], a4)
        theme.metric_card("Failed", b["failed"], a5)
        ok = b["imported"] == b["verified"] and not b["failed"]
        (st.success if ok else st.warning)(
            f"{'✅' if ok else '⚠️'} Reconciliation: {b['total']} source files = {b['imported']} imported + {b['duplicates']} duplicates + {b['skipped']} skipped + {b['failed']} failed. "
            f"Checksum verification: {b['verified']} of {b['imported']} imported files match the source byte-for-byte. "
            f"Run time {b['seconds']} s, by {b['started_by']}.")
        df = pd.DataFrame([{"Source path": i["rel_path"], "Result": i["status"], "EDMS reference": i["doc_code"], "Verified": "✔" if i["verified"] else "",
                            "Detail": i["detail"]} for i in its])
        flt = st.radio("Show", ["All", "Imported", "Duplicate", "Skipped", "Failed"], horizontal=True, key="mg_rflt")
        st.dataframe(df if flt == "All" else df[df["Result"] == flt], use_container_width=True, hide_index=True)
        st.download_button("⬇ Download full report (CSV)", df.to_csv(index=False).encode("utf-8-sig"), file_name=f"migration_batch_{pick}.csv",
                           mime="text/csv", key="mg_csv")
        st.caption("Every imported document carries an audit entry with its legacy path and checksum, so each record can be traced back to its source.")

with t5:
    st.markdown("""
**Migration method (as proposed for the project)**

1. **Discover** — read-only connection to SharePoint / file servers / the paper-scanning output; inventory every file with size, date and SHA-256.
2. **Cleanse** — drop temporary and system files, empty files and unsupported types; detect exact duplicates inside the source and against what is already in the EDMS.
3. **Map** — legacy folders to department, document type and EDMS folder; unmapped content lands in a review queue, never lost.
4. **Dry-run** — counts per department before anything is written; business owners sign off the mapping.
5. **Migrate** — OCR (English + Arabic), classification, numbering, folder placement and original dates preserved; audit entry per document.
6. **Verify** — checksum compared source vs. stored file, reconciliation of every source file to an outcome, exceptions list for the business owners.
7. **Repeat** — delta runs until cut-over; duplicates are skipped automatically, so batches can be re-run safely.

Demo scope: the connectors are replaced by a folder on this server; SharePoint metadata/permissions mapping and delta tokens are project-phase work.
    """)
