
import streamlit as st
import pandas as pd
from datetime import date
from database import (
    initialize_tables,
    create_finance_table,
    create_proceedings_table,
    create_clients_table,
    export_all_tables_to_excel,
    overwrite_cases_table,
    get_connection
)
from utils import normalize, sanitize_dates
from ui_components import (
    add_new_case_ui,
    upcoming_cases_ui,
    search_case_ui,
    update_case_record_ui,
    view_proceedings_ui,
    summary_ui
)
from client_ui import client_management_ui

def main():
    st.set_page_config("📚 SANDEEP JHA Case Diary", layout="wide")
    st.title("📚 Sj Case Diary")

    if "initialized" not in st.session_state:
        initialize_tables()
        create_finance_table()
        create_proceedings_table()
        create_clients_table()
        with get_connection() as conn:
            try:
                conn.execute("ALTER TABLE cases ADD COLUMN client_id INTEGER")
            except:
                pass
        st.session_state.initialized = True

    with st.sidebar:
        st.header("📤 Upload/Export")
        uploaded_file = st.file_uploader("Upload Excel", type=["xlsx", "csv"])
        if uploaded_file:
            if st.button("Import from Excel"):
                try:
                    df_raw = pd.read_excel(uploaded_file, sheet_name="Master")
                    df = normalize(df_raw)
                    df = sanitize_dates(df)
                    overwrite_cases_table(df)
                except Exception as e:
                    st.error(f"❌ Error reading Excel file: {e}")

        if st.button("Export to Excel"):
            excel_data = export_all_tables_to_excel()
            st.download_button(
                label="📥 Download case_diary_export.xlsx",
                data=excel_data,
                file_name="case_diary_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    tabs = st.tabs([
        "➕ Add New Case",
        "📅 Upcoming Cases",
        "🔍 Search Case",
        "📌 Update Case Record",
        "📜 View & Update Proceedings",
        "📊 Summary",
        "💼 Client Management"
    ])

    with tabs[0]:
        add_new_case_ui()
    with tabs[1]:
        upcoming_cases_ui()
    with tabs[2]:
        search_case_ui()
    with tabs[3]:
        update_case_record_ui()
    with tabs[4]:
        view_proceedings_ui()
    with tabs[5]:
        summary_ui()
    with tabs[6]:
        client_management_ui()

if __name__ == "__main__":
    import plotly.express as px
    main()
