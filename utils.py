
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
