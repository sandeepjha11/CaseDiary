
import pandas as pd
from datetime import datetime, date
import re
import streamlit as st
import numpy as np

def normalize(df):
    """Normalizes column names of a DataFrame."""
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^\w]+", "_", regex=True)
        .str.replace(r"_+$", "", regex=True)
    )
    return df

def get_month_year(entry_date: str) -> str:
    """Gets the month and year from a date string."""
    dt = datetime.strptime(entry_date, "%Y-%m-%d")
    return dt.strftime("%b-%Y")

def get_fy(entry_date: str) -> str:
    """Gets the financial year from a date string."""
    dt = datetime.strptime(entry_date, "%Y-%m-%d")
    year = dt.year
    if dt.month >= 4:
        return f"FY {year}-{year+1}"
    else:
        return f"FY {year-1}-{year}"

def sanitize_table_name(case_no):
    """Sanitizes a case number to be used as a table name."""
    name = f"proc_{case_no}"
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if re.match(r'^\d', name):
        name = f"x{name}"
    return name

def sanitize_dates(df, last_col="last_date", next_col="next_date"):
    """Sanitizes date columns in a DataFrame."""
    for col in [last_col, next_col]:
        if col not in df.columns:
            st.warning(f"⚠️ Column '{col}' not found.")
            continue
        df[col] = df[col].astype(str).str.strip().replace(
            {"NaT": None, "Nan": None, "None": None, "Adjourned": None, "Disposed": None, "": None}
        )
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df

def parse_date_safe(val):
    """Safely parses a date value."""
    if val is None or str(val).strip() == "" or str(val) in ["NaT", "Awaited"]:
        return None
    if isinstance(val, pd.Timestamp):
        if pd.isna(val):
            return None
        return val.date()
    if isinstance(val, np.datetime64):
        if pd.isna(val):
            return None
        return pd.to_datetime(val).date()
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        dt = pd.to_datetime(str(val), errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None

def migrate_finance_data(conn):
    """
    Migrates financial data from old columns in the 'cases' table to the 'finance_log' table.
    This is a one-time operation to prevent data loss after the schema change.
    """
    cursor = conn.cursor()

    # Check if migration has already been done
    cursor.execute("PRAGMA user_version")
    user_version = cursor.fetchone()[0]
    if user_version >= 1:
        return "Migration already completed."

    # Check if old finance columns exist
    cursor.execute("PRAGMA table_info(cases)")
    columns = [info[1] for info in cursor.fetchall()]
    old_finance_columns = [
        "fee_raised_full_partial_no", "total_fee", "fee_paid", "fee_due",
        "expenses_incurred_paid", "expenses_due"
    ]
    if not all(col in columns for col in old_finance_columns):
        return "Old finance columns not found. No migration needed."

    # Fetch data from old columns
    cursor.execute(f"SELECT s_no, particulars, date_of_filing, {', '.join(old_finance_columns)} FROM cases")
    cases_data = cursor.fetchall()

    for row in cases_data:
        s_no, particulars, date_of_filing, fee_raised, total_fee, fee_paid, fee_due, expenses_paid, expenses_due = row

        # Use date_of_filing as a fallback for the transaction date
        entry_date = parse_date_safe(date_of_filing) or date.today()

        if total_fee and total_fee > 0:
            # Log the total fee as a receivable income
            cursor.execute("""
                INSERT INTO finance_log (date, type, amount, description, status, case_id)
                VALUES (?, 'Income', ?, ?, 'Receivable', ?)
            """, (entry_date.strftime("%Y-%m-%d"), total_fee, f"Total fee for case: {particulars}", s_no))

        if fee_paid and fee_paid > 0:
            # Log the paid fee as a received income
            cursor.execute("""
                INSERT INTO finance_log (date, type, amount, description, status, case_id)
                VALUES (?, 'Income', ?, ?, 'Received', ?)
            """, (entry_date.strftime("%Y-%m-%d"), fee_paid, f"Fee payment for case: {particulars}", s_no))

        if expenses_paid and expenses_paid > 0:
            # Log the paid expenses
            cursor.execute("""
                INSERT INTO finance_log (date, type, amount, description, status, case_id)
                VALUES (?, 'Expense', ?, ?, 'Paid', ?)
            """, (entry_date.strftime("%Y-%m-%d"), expenses_paid, f"Expenses for case: {particulars}", s_no))

    # After migration, drop the old columns
    for col in old_finance_columns:
        cursor.execute(f"ALTER TABLE cases DROP COLUMN {col}")

    # Mark migration as complete by setting user_version
    cursor.execute("PRAGMA user_version = 1")
    conn.commit()
    return "Financial data migrated successfully."
