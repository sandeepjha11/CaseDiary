
import streamlit as st
import pandas as pd
from database import get_connection
from utils import migrate_finance_data

def finance_ui():
    """Renders the consolidated finance UI."""
    st.subheader("💼 Consolidated Finance")

    with st.expander("⚠️ Database Migration Tool", expanded=True):
        st.warning(
            "**Important:** The database schema has been updated to better manage financial data. "
            "Old billing columns have been removed from the main cases table and consolidated into a new `finance_log` table. "
            "To avoid data loss, please migrate your existing financial records."
        )
        if st.button("Migrate Financial Data Now"):
            with get_connection() as conn:
                result = migrate_finance_data(conn)
                st.success(result)

    with get_connection() as conn:
        df_cases = pd.read_sql("SELECT s_no, f_no, case_no, particulars FROM cases ORDER BY f_no", conn)

    df_cases["label"] = df_cases.apply(lambda row: f"{row['f_no']} | {row['case_no']} | {row['particulars']}", axis=1)
    case_map = {label: s_no for label, s_no in zip(df_cases["label"], df_cases["s_no"])}

    selected_label = st.selectbox("📂 Select Case", options=["-- Select a case --"] + df_cases["label"].tolist(), key="finance_case_selector")

    if selected_label and selected_label != "-- Select a case --":
        selected_s_no = case_map.get(selected_label)
        with get_connection() as conn:
            df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))

        if not df_meta.empty:
            selected_case = df_meta.iloc[0].to_dict()
            st.success(f"✅ Loaded financial records for: {selected_case.get('particulars')}")

            # Placeholders for the rest of the UI
            st.markdown("### Financial Summary")
            financial_summary_ui(selected_case)

            st.markdown("### Transaction Log")
            transaction_log_ui(selected_case)

            st.markdown("### Add New Transaction")
            add_transaction_ui(selected_case)
    else:
        st.info("Select a case to view its financial details.")

def add_transaction_ui(case):
    """Renders the UI for adding a new transaction."""
    with st.form(key="add_transaction_form", clear_on_submit=True):
        entry_type = st.selectbox("Type", ["Income", "Expense"])
        amount = st.number_input("Amount", min_value=0.0, format="%.2f")
        mode = st.selectbox("Mode", ["Cash", "Bank", "UPI", "Other"])
        status = st.selectbox("Status", ["Received", "Receivable"] if entry_type == "Income" else ["Paid", "Pending"])
        description = st.text_area("Description")
        entry_date = st.date_input("Date", value=pd.to_datetime("today").date())
        submitted = st.form_submit_button("Log Transaction")
        if submitted:
            add_transaction(case['s_no'], case['case_no'], case['f_no'], case['particulars'], entry_date, entry_type, amount, mode, description, status)
            st.toast("Transaction added successfully.", icon="✅")

def financial_summary_ui(case):
    """Renders the financial summary for a case."""
    df = get_transactions_for_case(case['s_no'])
    if not df.empty:
        income = df[df['type'] == 'Income']['amount'].sum()
        expense = df[df['type'] == 'Expense']['amount'].sum()
        net = income - expense
        st.metric("Total Income", f"₹{income:,.2f}")
        st.metric("Total Expense", f"₹{expense:,.2f}")
        st.metric("Net", f"₹{net:,.2f}")
    else:
        st.info("No financial records for this case yet.")

def transaction_log_ui(case):
    """Renders the transaction log for a case."""
    df = get_transactions_for_case(case['s_no'])
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%d-%m-%Y')
        st.dataframe(df, width='stretch')
    else:
        st.info("No transactions to display.")
