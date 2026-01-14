
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from fuzzywuzzy import fuzz
from database import (
    get_connection,
    insert_case_row,
    update_case,
    update_full_case,
    delete_case,
    log_proceeding,
    load_case_metadata,
    overwrite_cases_table
)
from utils import get_month_year, get_fy, parse_date_safe

def add_new_case_ui():
    """Renders the UI for adding a new case."""
    st.subheader("➕ Add New Case to Database")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(s_no) FROM cases")
        last_s_no = cursor.fetchone()[0] or 0
        cursor.execute("SELECT MAX(CAST(f_no AS INTEGER)) FROM cases WHERE f_no GLOB '[0-9]*'")
        last_f_no = cursor.fetchone()[0] or 0
        df_juris = pd.read_sql("SELECT DISTINCT jurisdiction FROM cases", conn)
        df_locations = pd.read_sql("SELECT DISTINCT court_location FROM cases", conn)

    st.markdown(f"**🧾 Last S. No.:** {last_s_no} &nbsp;&nbsp;&nbsp; **📁 Last File No.:** {last_f_no}")
    next_f_no = str(int(last_f_no) + 1)

    with st.form(key="add_case_form", clear_on_submit=True):
        with st.expander("Case Details", expanded=True):
            f_no = st.text_input("File No", value=next_f_no)
            jurisdiction_options = list(set(["District Court", "High Court", "Supreme Court", "Others"] + df_juris["jurisdiction"].dropna().unique().tolist()))
            jurisdiction = st.selectbox("Jurisdiction", jurisdiction_options, key="add_jurisdiction")
            new_jurisdiction = st.text_input("Or type a new jurisdiction")
            final_jurisdiction = new_jurisdiction.strip() if new_jurisdiction.strip() else jurisdiction
            court_location_options = list(set(["Delhi", "Mumbai", "Ranchi", "Others"] + df_locations["court_location"].dropna().unique().tolist()))
            court_location = st.selectbox("Court Location", court_location_options, key="add_court_location")
            new_court_location = st.text_input("Or type a new court location")
            final_court_location = new_court_location.strip() if new_court_location.strip() else court_location
            case_date = st.date_input("Case Registration Date", value=date.today())
            month_year = get_month_year(case_date.strftime("%Y-%m-%d"))
            fy = get_fy(case_date.strftime("%Y-%m-%d"))
            case_through = st.text_input("Case Through")
            case_type = st.text_input("Case Type")
            case_no = st.text_input("Case No")
            particulars = st.text_area("Particulars")
            court = st.text_input("Court")
        with st.expander("Case Status"):
            next_date_mode = st.selectbox("Next Date", ["Date Awaited", "Pick a Date"], key="add_next_date_mode")
            next_date_db = None
            if next_date_mode == "Pick a Date":
                next_date = st.date_input("📅 Select Next Date", value=date.today())
                next_date_db = next_date.strftime("%Y-%m-%d")
            status = st.selectbox("Status", ["Pending", "Closed", "Awaited"], key="add_status")
            remarks = st.text_area("Remarks")
            last_date = st.date_input("Last Date", value=date.today())

        with get_connection() as conn:
            df_clients = pd.read_sql("SELECT id, name FROM clients", conn)
        client_options = {name: id for id, name in zip(df_clients['id'], df_clients['name'])}
        client_name = st.selectbox("Client", options=list(client_options.keys()), key="add_client")
        client_id = client_options.get(client_name)

        submitted = st.form_submit_button("💾 Add Case")
        if submitted:
            row = {
                "f_no": f_no, "jurisdiction": final_jurisdiction, "court_location": final_court_location,
                "month_year": month_year, "fy": fy, "case_through": case_through,
                "ref_fileno": None, "case_type": case_type, "fir_no": None, "ps": None,
                "case_no": case_no, "particulars": particulars, "court": court,
                "legal_offer_ws_filed": None, "last_date": last_date, "next_date": next_date_db,
                "proceeding": None, "settle_contest": None, "remarks": remarks, "result": None,
                "status": status,
                "file_scaned_y_n": None, "date_of_filing": None, "cnr_no": None,
                "opponent_advocate": None, "opponent_advocate_contact_number": None,
                "client_id": client_id
            }
            insert_case_row(row)
            st.toast("✅ Case added successfully.", icon="✅")

def upcoming_cases_ui():
    """Renders the UI for upcoming cases."""
    st.subheader("📅 Upcoming Cases (Next 21 Days + Awaited)")
    today = date.today()
    future = today + timedelta(days=21)

    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT s_no, case_no, f_no, ref_fileno, jurisdiction, next_date, status,
                   particulars, court, court_location, proceeding
            FROM cases
            WHERE status IN ('Pending', 'Awaited')
              AND (next_date BETWEEN ? AND ? OR next_date IS NULL)
            ORDER BY jurisdiction ASC, next_date ASC
        """, conn, params=(today.strftime("%Y-%m-%d"), future.strftime("%Y-%m-%d")))

    if not df.empty:
        df["next_date"] = pd.to_datetime(df["next_date"], errors="coerce")
        df["next_date_str"] = df["next_date"].dt.strftime("%d-%m-%Y").fillna("Date Awaited")
        awaited_df = df[df["next_date"].isna()]
        upcoming_df = df[df["next_date"].notna()]
        view_mode = st.radio("🧭 Choose view mode:", ["Agenda (21‑Day Calendar)", "Date‑wise", "Jurisdiction‑wise"], horizontal=True)

        if view_mode == "Agenda (21‑Day Calendar)":
            st.markdown("### 🗓️ Upcoming Cases Agenda (Next 21 Days)")
            for offset in range(21):
                day = today + timedelta(days=offset)
                day_cases = upcoming_df[upcoming_df["next_date"].dt.date == day]
                if not day_cases.empty:
                    st.markdown(f"<div style='background-color:#f0f8ff;padding:8px 12px;border-left:5px solid #007bff;border-radius:4px;margin-top:20px;margin-bottom:10px;'><h4 style='margin:0;color:#007bff;'>📅 {day.strftime('%A, %d-%m-%Y')}</h4></div>", unsafe_allow_html=True)
                    st.dataframe(day_cases[["f_no", "ref_fileno", "case_no", "jurisdiction", "next_date_str", "status", "particulars", "court", "court_location", "proceeding"]].reset_index(drop=True), width='stretch', hide_index=True)
                else:
                    st.markdown(f"<div style='background-color:#f9f9f9;padding:6px 10px;border-left:3px solid #ccc;border-radius:4px;margin-top:10px;margin-bottom:5px;'><span style='color:#666;'>📅 {day.strftime('%A, %d-%m-%Y')} — No cases</span></div>", unsafe_allow_html=True)

        if not awaited_df.empty:
            st.markdown("### 📭 Cases with 'Date Awaited'")
            for jurisdiction in sorted(awaited_df["jurisdiction"].dropna().unique()):
                st.markdown(f"<div style='background-color:#fff3cd;padding:8px 12px;border-left:5px solid #ffc107;border-radius:4px;margin-top:20px;margin-bottom:10px;'><h4 style='margin:0;color:#856404;'>⏳ <b>{jurisdiction}</b></h4></div>", unsafe_allow_html=True)
                st.dataframe(awaited_df[awaited_df["jurisdiction"] == jurisdiction][["f_no", "ref_fileno", "case_no", "next_date_str", "status", "particulars", "court", "court_location", "proceeding"]].reset_index(drop=True), width='stretch', hide_index=True)

        df["label"] = df["jurisdiction"].fillna("") + " | " + df["f_no"].fillna("") + " | " + df["particulars"].fillna("") + " | " + df["case_no"].fillna("") + " | " + df["next_date_str"]
        case_map = dict(zip(df["label"], df["s_no"]))
        selected_label = st.selectbox("Select a case to view/update", df["label"], key="upcoming_case_selector")
        selected_s_no = case_map.get(selected_label)

        if selected_s_no:
            with get_connection() as conn:
                df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))
            if not df_meta.empty:
                st.session_state.selected_row = df_meta.iloc[0].to_dict()
                st.success("✅ Case loaded. Proceed to Tab 4 to update.")
            else:
                st.warning("⚠️ No metadata found for this case.")
    else:
        st.info("🎉 No upcoming or awaited cases found.")

def search_case_ui():
    """Renders the UI for searching cases."""
    st.subheader("🔍 Search Case")
    search_field = st.radio("Search by", ["f_no", "particulars"])
    search_input = st.text_input(f"Enter part of the {search_field}")
    threshold = st.slider("🎚️ Match threshold", min_value=30, max_value=100, value=70, step=1)

    if search_input:
        with get_connection() as conn:
            df_search = pd.read_sql("SELECT s_no, case_no, f_no, particulars, court, court_location, status, next_date FROM cases WHERE f_no IS NOT NULL OR particulars IS NOT NULL", conn)

        df_search["f_no"] = df_search["f_no"].fillna("").astype(str).str.strip().str.lower()
        df_search["particulars"] = df_search["particulars"].fillna("").astype(str).str.strip().str.lower()
        search_input = search_input.strip().lower()
        df_search["score"] = df_search[search_field].apply(lambda x: fuzz.token_set_ratio(search_input, x) if x else 0)
        filtered = df_search[df_search["score"] >= threshold].sort_values(by="score", ascending=False)

        if not filtered.empty:
            st.subheader(f"📋 Matching Records (Score ≥ {threshold})")
            display_df = filtered.drop(columns=["score"]).reset_index(drop=True)
            if 'next_date' in display_df.columns:
                display_df['next_date'] = pd.to_datetime(display_df['next_date'], errors='coerce').dt.strftime('%d-%m-%Y')
            st.dataframe(display_df, width='stretch', hide_index=True)

            filtered["label"] = filtered["f_no"].astype(str).fillna("") + " | " + filtered["particulars"].fillna("") + " | " + filtered["case_no"].fillna("")
            case_map = dict(zip(filtered["label"], filtered["s_no"]))
            selected_label = st.selectbox("Select a record to view full details", filtered["label"], key="search_case_selector")
            selected_s_no = case_map.get(selected_label)

            if selected_s_no:
                with get_connection() as conn:
                    df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))
                if not df_meta.empty:
                    st.subheader("📋 Full Case Metadata")
                    display_meta_df = df_meta.reset_index(drop=True)
                    for col in display_meta_df.columns:
                        if "date" in col.lower():
                            display_meta_df[col] = pd.to_datetime(display_meta_df[col], errors="coerce").dt.strftime("%d-%m-%Y")
                    st.dataframe(display_meta_df, width='stretch', hide_index=True)
                    st.session_state.selected_row = df_meta.iloc[0].to_dict()
                else:
                    st.warning("⚠️ No full metadata found for this record.")
        else:
            st.warning("No close matches found.")

def update_case_record_ui():
    """Renders the UI for updating a case record."""
    st.subheader("📌 Update Case Record & Log Proceeding")

    if "selected_row" in st.session_state:
        row = st.session_state.selected_row
        s_no = row.get("s_no")

        with st.form(key=f"update_case_form_{s_no}"):
            with st.expander("Case Details", expanded=True):
                case_no = st.text_input("Case Number", row.get("case_no", ""))
                f_no = st.text_input("File No", row.get("f_no", ""))
                particulars = st.text_area("Particulars", row.get("particulars", ""))
            with st.expander("Case Status"):
                status = st.selectbox("Status", ["Pending", "Closed", "Awaited"], index=["Pending", "Closed", "Awaited"].index(row.get("status", "Pending")), key=f"update_status_{s_no}")
                last_date = st.date_input("Last Date", value=parse_date_safe(row.get("last_date")) or date.today())
                next_date_mode = st.selectbox("Next Date", ["Date Awaited", "Pick a Date"], key=f"update_next_date_mode_{s_no}")
                next_date_db = None
                if next_date_mode == "Pick a Date":
                    next_date = st.date_input("📅 Select Next Date", value=parse_date_safe(row.get("next_date")) or date.today())
                    next_date_db = next_date.strftime("%Y-%m-%d")
            with st.expander("Proceedings"):
                proceeding = st.text_area("Proceeding Note", row.get("proceeding", ""))
                proc_date = st.date_input("Proceeding Date", value=date.today())

            with get_connection() as conn:
                df_clients = pd.read_sql("SELECT id, name FROM clients", conn)
            client_options = {name: id for id, name in zip(df_clients['id'], df_clients['name'])}
            client_name = st.selectbox("Client", options=list(client_options.keys()), index=list(client_options.values()).index(row.get("client_id")) if row.get("client_id") in client_options.values() else 0, key=f"update_client_{s_no}")
            client_id = client_options.get(client_name)

            submitted = st.form_submit_button("Update Case Record")
            if submitted:
                try:
                    update_full_case(
                        s_no=s_no, case_no=case_no, f_no=f_no, particulars=particulars,
                        status=status, last_date=last_date.strftime("%Y-%m-%d"), next_date=next_date_db,
                        proceeding=proceeding, client_id=client_id
                    )
                    log_proceeding(
                        case_no or row.get("case_no", ""), f_no, particulars,
                        proc_date.strftime("%Y-%m-%d"), proceeding
                    )
                    st.toast("✅ Case record updated and proceeding logged.", icon="✅")
                except Exception as e:
                    st.toast(f"❌ Error updating case: {e}", icon="❌")

        st.markdown("---")
        with st.expander("Danger Zone"):
            st.warning("⚠️ Deleting a case cannot be undone.")
            if st.checkbox(f"Confirm delete File No. {row.get('f_no')} | Particulars: {row.get('particulars')}"):
                if st.button("🗑️ Delete Case"):
                    try:
                        delete_case(s_no)
                        st.toast(f"❌ Case {row.get('case_no')} deleted permanently.", icon="🗑️")
                    except Exception as e:
                        st.toast(f"❌ Error deleting case: {e}", icon="❌")
    else:
        st.warning("⚠️ Please select a case from Tab 2 or Tab 3 before updating.")

def view_proceedings_ui():
    """Renders the UI for viewing and updating proceedings."""
    st.subheader("📜 Case Proceedings")
    with get_connection() as conn:
        df_cases = pd.read_sql("SELECT s_no, f_no, case_no, particulars FROM cases ORDER BY f_no", conn)

    df_cases["label"] = df_cases.apply(lambda row: f"{row['f_no']} | {row['case_no']} | {row['particulars']}", axis=1)
    case_map = dict(zip(df_cases["label"], df_cases["s_no"]))
    search_query = st.text_input("🔍 Search by File No / Particulars", key="search_query_tab5")
    df_filtered = df_cases[df_cases["label"].str.contains(search_query, case=False, na=False)] if search_query else df_cases
    selected_label = st.selectbox("📂 Select Case", options=["-- Select a case --"] + df_filtered["label"].tolist(), key="proceedings_case_selector")

    if selected_label and selected_label != "-- Select a case --":
        selected_s_no = case_map.get(selected_label)
        with get_connection() as conn:
            df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))

        if not df_meta.empty:
            selected_case = df_meta.iloc[0].to_dict()
            st.success("✅ Case loaded. You can now log proceedings.")

            with st.form(key="log_proceeding_form"):
                proc_date = st.date_input("Date", value=date.today())
                note = st.text_area("Proceeding Note")
                submitted = st.form_submit_button("Log Proceeding")
                if submitted:
                    log_proceeding(selected_case.get("case_no"), selected_case.get("f_no"), selected_case.get("particulars"), proc_date.strftime("%Y-%m-%d"), note)
                    st.success("✅ Proceeding logged successfully.")

            st.subheader("📊 Case Proceedings Summary")
            with get_connection() as conn:
                df_proc = pd.read_sql("SELECT id, date, note, updated_by FROM proceedings_log WHERE case_no = ? AND f_no = ? ORDER BY date DESC", conn, params=(selected_case.get("case_no"), selected_case.get("f_no")))

            if not df_proc.empty:
                df_proc["date"] = pd.to_datetime(df_proc["date"], errors="coerce").dt.strftime("%d-%m-%Y")
                st.dataframe(df_proc.reset_index(drop=True), width='stretch', hide_index=True)
            else:
                st.info("📭 No proceedings logged yet for this case.")

def summary_ui():
    """Renders the summary UI."""
    st.subheader("📊 Case Status Summary")
    with get_connection() as conn:
        df = pd.read_sql("SELECT jurisdiction, status, COUNT(*) as count FROM cases GROUP BY jurisdiction, status", conn)

    if not df.empty:
        import plotly.express as px
        fig = px.bar(df, x="jurisdiction", y="count", color="status", title="Case Status by Jurisdiction")
        st.plotly_chart(fig)
    else:
        st.info("No data to display.")

def jurisdiction_wise_cases_ui():
    """Renders the UI for jurisdiction-wise cases."""
    st.subheader("✏️ Jurisdiction‑Wise Cases")
    with get_connection() as conn:
        df_all = pd.read_sql("""
            SELECT s_no, f_no, case_no, particulars, court, court_location,
                   jurisdiction, status, next_date, last_date, remarks, todo_flag, todo_details
            FROM cases
            WHERE jurisdiction IS NOT NULL
            ORDER BY s_no ASC
        """, conn)

    if not df_all.empty:
        df_all["jurisdiction"] = df_all["jurisdiction"].str.upper().str.strip()
        jurisdictions = sorted(df_all["jurisdiction"].dropna().unique())
        selected_jurisdiction = st.selectbox("Select Jurisdiction", jurisdictions, key="jurisdiction_selector")
        sub_df = df_all[df_all["jurisdiction"] == selected_jurisdiction].copy()
        view_mode = st.radio("Choose view mode:", ["All Cases", "Pending Only", "Closed Only"], index=0, horizontal=True)
        if view_mode == "Closed Only":
            sub_df = sub_df[sub_df["status"].str.upper() == "CLOSED"]
        if view_mode == "Pending Only":
            sub_df = sub_df[sub_df["status"].str.upper() == "PENDING"]

        sub_df["last_date_str"] = pd.to_datetime(sub_df["last_date"], errors="coerce").dt.strftime("%d-%m-%Y")
        sub_df["next_date_str"] = pd.to_datetime(sub_df["next_date"], errors="coerce").dt.strftime("%d-%m-%Y")

        st.markdown(f"### 📋 Records for {selected_jurisdiction.title()} — {view_mode}")
        st.dataframe(sub_df[["f_no", "case_no", "particulars", "court", "court_location", "status", "last_date_str", "next_date_str", "remarks"]].reset_index(drop=True), width='stretch', hide_index=True)
        st.markdown(f"**Total cases in {selected_jurisdiction.title()} ({view_mode}): {len(sub_df)}**")
    else:
        st.info("📭 No cases found with jurisdiction.")

def full_db_viewer_ui():
    """Renders the UI for the full DB viewer."""
    st.subheader("📚 Full Database Viewer")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        st.info("No tables found in the database.")
    else:
        selected_table = st.selectbox("Select a table to view", tables, key="db_viewer_table_selector")
        with get_connection() as conn:
            df = pd.read_sql(f"SELECT * FROM '{selected_table}'", conn)
        for col in df.columns:
            if "date" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d-%m-%Y")
        st.dataframe(df.reset_index(drop=True), width='stretch', hide_index=True)

def overdue_cases_ui():
    """Renders the UI for overdue cases."""
    st.subheader("⏳ Overdue Cases (Pending & Past Next Date + Awaited)")
    today = date.today()

    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT s_no, case_no, f_no, particulars, court, court_location,
                   last_date, next_date, status, jurisdiction, todo_flag, todo_details
            FROM cases
            WHERE status = 'Pending'
              AND (
                    (next_date IS NOT NULL AND next_date != 'Awaited' AND next_date < ?)
                    OR next_date = 'Awaited'
                    OR next_date IS NULL
                  )
            ORDER BY jurisdiction ASC, next_date ASC
        """, conn, params=(today.strftime("%Y-%m-%d"),))

    if not df.empty:
        df["next_date_dt"] = pd.to_datetime(df["next_date"], errors="coerce")
        df["next_date_str"] = df["next_date_dt"].dt.strftime("%d-%m-%Y")
        df.loc[df["next_date"].isna(), "next_date_str"] = "Date Awaited"
        df.loc[df["next_date"] == "Awaited", "next_date_str"] = "Awaited"
        overdue_df = df[(df["next_date"].notna()) & (df["next_date"] != "Awaited") & (df["next_date_dt"] < pd.to_datetime(today))]
        awaited_df = df[(df["next_date"].isna()) | (df["next_date"] == "Awaited")]

        if not overdue_df.empty:
            st.markdown("### ⚠️ Overdue Cases (Past Next Date)")
            for j in sorted(overdue_df["jurisdiction"].dropna().unique()):
                st.markdown(f"<div style='background-color:#ffe9e9;padding:8px 12px;border-left:5px solid #dc3545;border-radius:4px;margin-top:20px;margin-bottom:10px;'><h4 style='margin:0;color:#dc3545;'>⚠️ <b>{j}</b></h4></div>", unsafe_allow_html=True)
                sub_df = overdue_df[overdue_df["jurisdiction"] == j].copy()
                sub_df["last_date"] = pd.to_datetime(sub_df["last_date"], errors="coerce").dt.strftime("%d-%m-%Y")
                with st.expander(f"⚠️ {j} — {len(sub_df)} case(s)", expanded=False):
                    st.dataframe(sub_df[["case_no", "f_no", "particulars", "court", "court_location", "last_date", "next_date_str", "status", "todo_flag", "todo_details"]].reset_index(drop=True), width='stretch', hide_index=True)

        if not awaited_df.empty:
            st.markdown("### 📭 Cases with 'Date Awaited'")
            for j in sorted(awaited_df["jurisdiction"].dropna().unique()):
                st.markdown(f"<div style='background-color:#fff3cd;padding:8px 12px;border-left:5px solid #ffc107;border-radius:4px;margin-top:20px;margin-bottom:10px;'><h4 style='margin:0;color:#856404;'>⏳ <b>{j}</b></h4></div>", unsafe_allow_html=True)
                sub_df = awaited_df[awaited_df["jurisdiction"] == j]
                with st.expander(f"⏳ {j} — {len(sub_df)} case(s)", expanded=False):
                    st.dataframe(sub_df[["case_no", "f_no", "particulars", "court", "court_location", "last_date", "next_date_str", "status", "todo_flag", "todo_details"]].reset_index(drop=True), width='stretch', hide_index=True)
    else:
        st.info("🎉 No overdue or awaited cases found.")

def todo_list_ui():
    """Renders the UI for the to-do list."""
    st.subheader("📝 To‑Do & Financial Workflow")
    with get_connection() as conn:
        df_all = pd.read_sql("""
            SELECT s_no, jurisdiction, case_no, f_no, particulars, court, court_location,
                   next_date, status, todo_flag, todo_details
            FROM cases
            ORDER BY jurisdiction ASC, next_date ASC
        """, conn)

    st.markdown("### 📌 Cases in To‑Do List")
    df_todo = df_all[df_all["todo_flag"] == "Yes"].copy()
    if not df_todo.empty:
        df_todo["next_date"] = pd.to_datetime(df_todo["next_date"], errors="coerce").dt.strftime("%d-%m-%Y")
        for j in sorted(df_todo["jurisdiction"].dropna().unique()):
            with st.expander(f"📍 {j} — {len(df_todo[df_todo['jurisdiction']==j])} case(s)", expanded=False):
                sub_df = df_todo[df_todo["jurisdiction"] == j]
                for _, row in sub_df.iterrows():
                    cols = st.columns([1.2, 1, 2, 1.5, 1.5, 1.2, 1, 2, 1])
                    cols[0].write(row["case_no"])
                    cols[1].write(row["f_no"])
                    cols[2].write(row["particulars"])
                    cols[3].write(row["court"])
                    cols[4].write(row["court_location"])
                    cols[5].write(row["next_date"])
                    cols[6].write(row["status"])
                    cols[7].write(row["todo_details"])
                    if cols[8].button("✅ Complete", key=f"todo_complete_{row['s_no']}"):
                        with get_connection() as conn:
                            conn.execute("UPDATE cases SET todo_flag='No', todo_details='' WHERE s_no=?", (row['s_no'],))
                            conn.commit()
                        st.toast(f"🎉 Case {row['case_no']} marked as completed.", icon="🎉")
                        st.rerun()
    else:
        st.info("✅ No cases in To‑Do List.")

def finance_tracker_ui():
    """Renders the UI for the finance tracker."""
    st.markdown("<div class='sticky-header'>💼 Log Income or Expense</div>", unsafe_allow_html=True)
    with st.form(key="finance_log_form", clear_on_submit=True):
        entry_type = st.selectbox("Type", ["Income", "Expense"])
        amount = st.number_input("Amount", min_value=0.0, format="%.2f")
        mode = st.selectbox("Mode", ["Cash", "Bank", "UPI", "Other"])
        status = st.selectbox("Status", ["Received", "Receivable"] if entry_type == "Income" else ["Paid", "Pending"])
        description = st.text_area("Description")
        entry_date = st.date_input("Date", value=date.today())
        submitted = st.form_submit_button("Log Entry")
        if submitted:
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO finance_log (date, type, amount, mode, description, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (entry_date.strftime("%Y-%m-%d"), entry_type, amount, mode, description, status))
                conn.commit()
            st.toast("✅ Entry logged successfully.", icon="✅")

    st.subheader("📊 Case Finance Summary")
    with get_connection() as conn:
        df_finance = pd.read_sql("SELECT * FROM finance_log ORDER BY date DESC", conn)

    if not df_finance.empty:
        df_finance["date"] = pd.to_datetime(df_finance["date"], errors="coerce").dt.strftime("%d-%m-%Y")
        st.dataframe(df_finance, width='stretch')
    else:
        st.info("ℹ️ No finance records found.")

def cleanup_ui():
    """Renders the UI for database cleanup."""
    st.subheader("🗑️ Database Cleanup (Drop Unwanted Tables)")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

    st.write("📋 Current tables in database:")
    st.dataframe(pd.DataFrame(tables, columns=["Table Name"]), width='stretch', hide_index=True)
    protected = {"cases", "finance_log", "proceedings_log", "clients"}
    unwanted = [t for t in tables if t not in protected]

    if unwanted:
        st.warning("⚠️ The following tables look unwanted:")
        selected_table = st.selectbox("Select table to drop", [""] + unwanted, key="cleanup_table_selector")
        if selected_table:
            if st.button("🗑️ Drop Selected Table"):
                with get_connection() as conn:
                    conn.execute(f"DROP TABLE IF EXISTS {selected_table}")
                    conn.commit()
                st.toast(f"✅ Table '{selected_table}' dropped successfully.", icon="✅")
    else:
        st.info("🎉 No unwanted tables found. Only valid tables are present.")

def monthly_finance_overview_ui():
    """Renders the UI for the monthly finance overview."""
    st.subheader("📊 Monthly Finance Overview")
    with get_connection() as conn:
        df_all_finance = pd.read_sql("SELECT * FROM finance_log ORDER BY date DESC", conn)

    if not df_all_finance.empty:
        df_all_finance["date"] = pd.to_datetime(df_all_finance["date"], errors="coerce")
        df_all_finance["month"] = df_all_finance["date"].dt.strftime("%B %Y")
        available_months = sorted(df_all_finance["month"].dropna().unique(), reverse=True)
        selected_month = st.selectbox("📅 Filter by Month", options=["All"] + available_months, key="monthly_finance_month_selector")
        if selected_month != "All":
            df_all_finance = df_all_finance[df_all_finance["month"] == selected_month]

        income_received = df_all_finance.query("type == 'Income' and status == 'Received'")["amount"].sum()
        income_receivable = df_all_finance.query("type == 'Income' and status == 'Receivable'")["amount"].sum()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Income Received", f"₹{income_received:,.2f}")
            st.metric("Income Receivable", f"₹{income_receivable:,.2f}")
        with col2:
            st.metric("Expense Paid", f"₹{expense_paid:,.2f}")
            st.metric("Expense Pending", f"₹{expense_pending:,.2f}")

        df_all_finance["date"] = df_all_finance["date"].dt.strftime("%d-%m-%Y")
        with st.expander("📋 View All Finance Entries"):
            st.dataframe(df_all_finance.reset_index(drop=True), width='stretch', hide_index=True)
    else:
        st.info("ℹ️ No finance records found.")
