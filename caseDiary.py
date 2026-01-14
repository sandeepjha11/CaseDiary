import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta
from fuzzywuzzy import fuzz
import re
import io
from datetime import datetime
from rapidfuzz import fuzz


# ✅ DB Connection
def get_connection():
    return sqlite3.connect(r"D:\Legal\CASE RECORD\case_diary.db")

# ✅ Initialize required tables
def initialize_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # ✅ Create 'cases' table if not exists (no DROP!)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            s_no INTEGER PRIMARY KEY AUTOINCREMENT,
            f_no TEXT, jurisdiction TEXT, court_location TEXT, month_year TEXT, fy TEXT,
            case_through TEXT, ref_fileno TEXT, case_type TEXT, fir_no TEXT, ps TEXT, case_no TEXT,
            particulars TEXT, court TEXT, legal_offer_ws_filed TEXT, last_date TEXT, next_date TEXT,
            proceeding TEXT, settle_contest TEXT, remarks TEXT, result TEXT, status TEXT,
            fee_raised_full_partial_no TEXT, fee_receipt_month TEXT, fee_part_1 TEXT,
            fee_part_2 TEXT, total_fee TEXT, expense TEXT, bill_no TEXT, file_scaned_y_n TEXT,
            date_of_filing TEXT, cnr_no TEXT, opponent_advocate TEXT, opponent_advocate_contact_number TEXT,
            todo_flag TEXT DEFAULT 'No',
            todo_details TEXT DEFAULT ''
        )
    """)

    # ✅ Create update_log table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS update_log (
            case_no TEXT, field TEXT, old_value TEXT, new_value TEXT,
            updated_on TEXT, updated_by TEXT, particulars TEXT
        )
    """)

    # ✅ Safe migrations: add new workflow columns if missing
    for alter_sql in [
        "ALTER TABLE cases ADD COLUMN closed_date TEXT",
        "ALTER TABLE cases ADD COLUMN bills_raised TEXT DEFAULT 'No'",
        "ALTER TABLE cases ADD COLUMN fee_status TEXT DEFAULT 'Awaited'"
    ]:
        try:
            cursor.execute(alter_sql)
        except Exception:
            pass  # column already exists

    conn.commit()
    conn.close()

if "initialized" not in st.session_state:
    initialize_tables()
    st.session_state.initialized = True

conn = get_connection()
cursor = conn.cursor()
cursor.execute("UPDATE cases SET jurisdiction = UPPER(TRIM(jurisdiction)) WHERE jurisdiction IS NOT NULL")
cursor.execute("UPDATE cases SET court_location = UPPER(TRIM(court_location)) WHERE court_location IS NOT NULL")
conn.commit()
conn.close()


# ✅ Normalize columns
def normalize(df):
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^\w]+", "_", regex=True)
        .str.replace(r"_+$", "", regex=True)
    )
    return df



# ✅ Ensure finance_log table exists
def create_finance_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS finance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT CHECK(type IN ('Income', 'Expense')) NOT NULL,
            amount REAL NOT NULL,
            mode TEXT,
            description TEXT,
            status TEXT CHECK(status IN ('Received', 'Receivable', 'Paid', 'Pending')) DEFAULT 'Received',
            case_no TEXT,
            f_no TEXT
        )
    """)
    conn.commit()
    conn.close()

# Run this once at startup
create_finance_table()
def patch_finance_table():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE finance_log ADD COLUMN particulars TEXT")
        conn.commit()
        st.success("✅ 'particulars' column added to finance_log.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            st.info("ℹ️ 'particulars' column already exists.")
        else:
            st.error(f"❌ Error updating table: {e}")
    finally:
        conn.close()


from datetime import datetime

def get_month_year(entry_date: str) -> str:
    dt = datetime.strptime(entry_date, "%Y-%m-%d")
    return dt.strftime("%b-%Y")   # e.g. "Dec-2025"

def get_fy(entry_date: str) -> str:
    dt = datetime.strptime(entry_date, "%Y-%m-%d")
    year = dt.year
    if dt.month >= 4:   # April or later
        return f"FY {year}-{year+1}"
    else:               # Jan–Mar
        return f"FY {year-1}-{year}"

def create_proceedings_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proceedings_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_no TEXT,
            f_no TEXT,
            particulars TEXT,
            date TEXT,
            note TEXT,
            updated_by TEXT
        )
    """)
    conn.commit()
    conn.close()
create_proceedings_table()
# Run this once at startup
# patch_finance_table()  (USE IT WHENEVER NEED TO PATCH THE TABLE)

# ✅ Insert a row into cases
def insert_case_row(row: dict):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO cases (
            f_no, jurisdiction, court_location, month_year, fy,
            case_through, ref_fileno, case_type, fir_no, ps, case_no,
            particulars, court, legal_offer_ws_filed, last_date, next_date,
            proceeding, settle_contest, remarks, result, status,
            fee_raised_full_partial_no, fee_status, fee_receipt_month, fee_part_1,
            fee_part_2, total_fee, expense, bill_no, file_scaned_y_n,
            date_of_filing, cnr_no, opponent_advocate, opponent_advocate_contact_number
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        row.get("f_no"),
        row.get("jurisdiction"),
        row.get("court_location"),
        row.get("month_year"),
        row.get("fy"),
        row.get("case_through"),
        row.get("ref_fileno"),
        row.get("case_type"),
        row.get("fir_no"),
        row.get("ps"),
        row.get("case_no"),
        row.get("particulars"),
        row.get("court"),
        row.get("legal_offer_ws_filed"),
        str(row.get("last_date")) if row.get("last_date") else None,
        str(row.get("next_date")) if row.get("next_date") else None,
        row.get("proceeding"),
        row.get("settle_contest"),
        row.get("remarks"),
        row.get("result"),
        row.get("status"),
        row.get("fee_raised_full_partial_no"),
        row.get("fee_status"),
        row.get("fee_receipt_month"),
        row.get("fee_part_1"),
        row.get("fee_part_2"),
        row.get("total_fee"),
        row.get("expense"),
        row.get("bill_no"),
        row.get("file_scaned_y_n"),
        str(row.get("date_of_filing")) if row.get("date_of_filing") else None,
        row.get("cnr_no"),
        row.get("opponent_advocate"),
        row.get("opponent_advocate_contact_number")
    ))

    conn.commit()
    conn.close()


# ✅ Update case with logging


def update_case(old_case_no, new_case_no, next_date, status, remarks, proceeding, title, f_no=None):
    conn = get_connection()
    cursor = conn.cursor()

    # ✅ Try to fetch using case_no, fallback to f_no
    if old_case_no:
        old = pd.read_sql("""
            SELECT case_no, next_date, status, remarks, proceeding, particulars
            FROM cases WHERE case_no = ?
        """, conn, params=(old_case_no,))
    elif f_no:
        old = pd.read_sql("""
            SELECT case_no, next_date, status, remarks, proceeding, particulars
            FROM cases WHERE f_no = ?
        """, conn, params=(f_no,))
    else:
        st.error("❌ Cannot update: No case_no or f_no provided.")
        conn.close()
        return

    if old.empty:
        st.warning("⚠️ No matching record found to update.")
        conn.close()
        return

    # ✅ Extract stored values
    stored = old.iloc[0]
    stored_case_no = stored["case_no"]
    stored_next_date = stored["next_date"]
    stored_status = stored["status"]
    stored_remarks = stored["remarks"]
    stored_proceeding = stored["proceeding"]

    # ✅ Use fallback WHERE clause
    where_clause = "case_no = ?" if old_case_no else "f_no = ?"
    where_val = old_case_no if old_case_no else f_no

    # ✅ Perform update
    cursor.execute(f"""
        UPDATE cases SET
            case_no = ?, next_date = ?, status = ?, remarks = ?, proceeding = ?
        WHERE {where_clause}
    """, (new_case_no, next_date, status, remarks, proceeding, where_val))
    conn.commit()

    # ✅ Log changes only if values differ
    fields = ["case_no", "next_date", "status", "remarks", "proceeding"]
    old_vals = [stored_case_no, stored_next_date, stored_status, stored_remarks, stored_proceeding]
    new_vals = [new_case_no, next_date, status, remarks, proceeding]

    for field, old_val, new_val in zip(fields, old_vals, new_vals):
        if str(old_val) != str(new_val):
            cursor.execute("""
                INSERT INTO update_log (
                    case_no, field, old_value, new_value, updated_on, updated_by, particulars
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                new_case_no, field, str(old_val), str(new_val),
                str(date.today()), "SANDEEP JHA", title
            ))

    conn.commit()
    conn.close()

def update_case_in_db(old_case_no, new_case_no, f_no, particulars, status):
    conn = get_connection()
    cursor = conn.cursor()

    # ✅ Update using f_no as fallback key
    cursor.execute("""
        UPDATE cases SET
            case_no = ?, f_no = ?, particulars = ?, status = ?
        WHERE f_no = ?
    """, (new_case_no, f_no, particulars, status, f_no))

    # ✅ Optional: log update
    cursor.execute("""
        INSERT INTO update_log (
            case_no, field, old_value, new_value, updated_on, updated_by, particulars
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        new_case_no, "status", "N/A", status,
        str(date.today()), "SANDEEP JHA", particulars
    ))

    conn.commit()
    conn.close()

def sanitize_table_name(case_no):
    name = f"proc_{case_no}"
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if re.match(r'^\d', name):
        name = f"x{name}"
    return name

def log_proceeding(case_no, f_no, particulars, proc_date,note ):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO proceedings_log (case_no, f_no, particulars, date, note, updated_by)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (case_no, f_no, particulars, proc_date, note, "Sandeep Jha"))
    conn.commit()
    conn.close()

def load_case_metadata(case_no):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(case_no,))
    conn.close()
    if not df.empty:
        for col in ["next_date", "last_date", "date_of_filing"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d-%m-%Y")
    return df

def export_all_tables_to_excel(db_path="D:\Legal\CASE RECORD\case_diary.db", filename="case_diary_export.xlsx"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for table in tables:
            try:
                df = pd.read_sql(f"SELECT * FROM '{table}'", conn)
                df.to_excel(writer, index=False, sheet_name=table[:31])
            except Exception as e:
                print(f"Skipping table {table}: {e}")
    conn.close()
    return output.getvalue()

def sanitize_dates(df, last_col="last_date", next_col="next_date"):
    for col in [last_col, next_col]:
        if col not in df.columns:
            st.warning(f"⚠️ Column '{col}' not found.")
            continue
        df[col] = df[col].astype(str).str.strip().replace(
            {"NaT": None, "Nan": None, "None": None, "Adjourned": None, "Disposed": None, "": None}
        )
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df

from datetime import date

from datetime import date

def update_full_case(
    s_no=None,
    case_no=None,
    f_no=None,
    jurisdiction=None,
    court_location=None,
    month_year=None,
    fy=None,
    case_through=None,
    ref_fileno=None,
    case_type=None,
    fir_no=None,
    ps=None,
    particulars=None,
    court=None,
    legal_offer_ws_filed=None,
    last_date=None,
    next_date=None,
    proceeding=None,
    settle_contest=None,
    remarks=None,
    result=None,
    status=None,
    fee_raised_full_partial_no=None,
    fee_status=None,
    fee_receipt_month=None,
    fee_part_1=None,
    fee_part_2=None,
    total_fee=None,
    expense=None,
    bill_no=None,
    file_scaned_y_n=None,
    date_of_filing=None,
    cnr_no=None,
    opponent_advocate=None,
    opponent_advocate_contact_number=None,
    todo_flag=None,
    todo_details=None,
    bills_raised=None,   # ✅ new optional field
):
    """Update a case record in the database. Only non-None and non-empty fields are updated.
       If status is set to 'Closed', always overwrite closed_date with today.
    """
    conn = get_connection()
    cursor = conn.cursor()

    fields, values = [], []

    for col, val in [
        ("case_no", case_no),
        ("f_no", f_no),
        ("jurisdiction", jurisdiction),
        ("court_location", court_location),
        ("month_year", month_year),
        ("fy", fy),
        ("case_through", case_through),
        ("ref_fileno", ref_fileno),
        ("case_type", case_type),
        ("fir_no", fir_no),
        ("ps", ps),
        ("particulars", particulars),
        ("court", court),
        ("legal_offer_ws_filed", legal_offer_ws_filed),
        ("last_date", last_date),
        ("next_date", next_date),
        ("proceeding", proceeding),
        ("settle_contest", settle_contest),
        ("remarks", remarks),
        ("result", result),
        ("status", status),
        ("fee_raised_full_partial_no", fee_raised_full_partial_no),
        ("fee_status", fee_status),
        ("fee_receipt_month", fee_receipt_month),
        ("fee_part_1", fee_part_1),
        ("fee_part_2", fee_part_2),
        ("total_fee", total_fee),
        ("expense", expense),
        ("bill_no", bill_no),
        ("file_scaned_y_n", file_scaned_y_n),
        ("date_of_filing", date_of_filing),
        ("cnr_no", cnr_no),
        ("opponent_advocate", opponent_advocate),
        ("opponent_advocate_contact_number", opponent_advocate_contact_number),
        ("todo_flag", todo_flag),
        ("todo_details", todo_details),
        ("bills_raised", bills_raised),
    ]:
        if val is not None and str(val).strip() != "":
            fields.append(f"{col} = ?")
            values.append(val)

    # ✅ Always overwrite closed_date if status is Closed
    if status is not None and status.strip().upper() == "CLOSED":
        closed_date_val = date.today().strftime("%Y-%m-%d")
        fields.append("closed_date = ?")
        values.append(closed_date_val)

    if not fields:
        conn.close()
        return

    values.append(s_no)
    sql = f"UPDATE cases SET {', '.join(fields)} WHERE s_no = ?"
    print("DEBUG SQL:", sql, values)  # ✅ optional debug
    cursor.execute(sql, values)

    conn.commit()
    conn.close()

def delete_case(s_no: int):
    """Delete a case record by its primary key (s_no)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cases WHERE s_no = ?", (s_no,))
    conn.commit()
    conn.close()


import sqlite3
import pandas as pd
import streamlit as st
import os

def get_connection():
    return sqlite3.connect(r"D:\Legal\CASE RECORD\case_diary.db")

def overwrite_cases_table(df: pd.DataFrame):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # ✅ Clear existing data
        cursor.execute("DELETE FROM cases")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'cases'")

        # ✅ Drop s_no to let SQLite assign fresh IDs
        if "s_no" in df.columns:
            df = df.drop(columns=["s_no"])

        # ✅ Insert fresh data
        df.to_sql("cases", conn, if_exists="append", index=False)
        conn.commit()

        # ✅ Confirm success
        st.success(f"✅ {len(df)} rows inserted into 'cases' table with s_no starting from 1.")
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

        conn.close()

    except Exception as e:
        st.error(f"❌ Error during overwrite: {e}")


from datetime import date, datetime
import pandas as pd
import numpy as np

def parse_date_safe(val):
    """Convert DB/DF values into a valid date for st.date_input."""
    if val is None or str(val).strip() == "" or str(val) in ["NaT", "Awaited"]:
        return None   # special case: no valid date
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



# ✅ Layout
st.set_page_config("📚 SANDEEP JHA Case Diary", layout="wide")
st.title("📚 Sj Case Diary")

# ✅ Sidebar: Excel Upload
with st.sidebar:
    st.header("📤 Upload Excel")

    # ✅ Step 1: Upload and preview
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx", "csv"])
    confirm_wipe = st.checkbox("⚠️ Confirm: Overwrite existing case records")

    if uploaded_file:
        try:
            df_raw = pd.read_excel(uploaded_file, sheet_name="Master")
            st.subheader("📋 Raw Excel Preview")
            st.dataframe(df_raw.reset_index(drop=True), use_container_width=True, hide_index=True)
            st.write(f"✅ Rows loaded: {len(df_raw)}")
        except Exception as e:
            st.error(f"❌ Error reading Excel file: {e}")
    else:
        st.info("📂 Please upload an Excel file to preview.")

    # ✅ Step 2: Import logic
    if uploaded_file and confirm_wipe and st.button("Import"):
        try:
            df = pd.read_excel(uploaded_file, sheet_name="Master")
            df = normalize(df)

            expected_cols = 35
            if len(df.columns) != expected_cols:
                st.warning(f"⚠️ Expected {expected_cols} columns, but found {len(df.columns)}.")
                st.write("📄 Excel Columns:", df.columns.tolist())

            df = sanitize_dates(df, last_col="last_date", next_col="next_date")

            required_cols = ["case_no", "last_date", "next_date"]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                st.warning(f"⚠️ Missing columns: {missing}. Showing fallback preview.")
                st.dataframe(df.head().reset_index(drop=True), use_container_width=True, hide_index=True)

            else:
                st.subheader("🧼 Preview Cleaned Dates")
                st.dataframe(df[required_cols].reset_index(drop=True), use_container_width=True, hide_index=True)


            # ✅ Final overwrite
            overwrite_cases_table(df)

        except Exception as e:
            st.error(f"❌ Import failed: {e}")

    
        # ✅ Step 4: Post-import audit
        conn = get_connection()
        df_check = pd.read_sql("SELECT case_no, particulars, next_date FROM cases LIMIT 10", conn)
        conn.close()
        st.subheader("📋 Sample Inserted Data")
        st.dataframe(df_check.reset_index(drop=True), use_container_width=True, hide_index=True)


        # ✅ Optional: Audit blank case_no or next_date
        blank_case_no = df_check[df_check["case_no"].isna() | (df_check["case_no"].astype(str).str.strip() == "")]
        blank_next_date = df_check[df_check["next_date"].isna() | (df_check["next_date"].astype(str).str.strip() == "")]

        if not blank_case_no.empty:
            st.warning(f"⚠️ {len(blank_case_no)} rows have blank case_no. These will not be searchable.")
            st.dataframe(blank_case_no.reset_index(drop=True), use_container_width=True, hide_index=True)

        if not blank_next_date.empty:
            st.warning(f"⚠️ {len(blank_next_date)} rows have blank next_date. These will not appear in 'Upcoming Cases'.")
            st.dataframe(blank_next_date.reset_index(drop=True), use_container_width=True, hide_index=True)


    # ✅ Step 5: Export entire database
    st.markdown("### 📤 Export Entire Database")
    if st.button("Export to Excel"):
        excel_data = export_all_tables_to_excel()
        st.download_button(
            label="📥 Download case_diary_export.xlsx",
            data=excel_data,
            file_name="case_diary_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    if st.button("🧨 Reset Entire Database"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS cases")
        cursor.execute("DROP TABLE IF EXISTS update_log")
        conn.commit()
        conn.close()
        st.success("✅ Database has been reset.")

    
# ✅ Tabs
tab1, tab2, tab3, tab4, tab6, tab5, tab7, tab9, tab10, tab11, tab12, tab13, tab14  = st.tabs([
    "➕ Add New Case",       
    "📅 Upcoming Cases",     
    "🔍 Search Case",        
    "📌 Update Case Record", 
    "✏️ Jurisdiction-Wise Cases",
    "📜 View & Update Proceedings",        
    "📚 Full DB",            
    "⏳ Overdue Cases",      
    "⏳ To-Do List",         
    "💼 Finance Tracker",    
    "📊 Monthly Finance Overview",             
    "📊 Summary",            
    "CleanUp",               
             
])
# ✅ Tab 1: Add New Case
with tab1:
    st.subheader("➕ Add New Case to Database")

    # ✅ Fetch last s_no and f_no from DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(s_no) FROM cases")
    last_s_no = cursor.fetchone()[0] or 0

    cursor.execute("SELECT MAX(CAST(f_no AS INTEGER)) FROM cases WHERE f_no GLOB '[0-9]*'")
    last_f_no = cursor.fetchone()[0] or 0
    conn.close()

    # ✅ Show last values
    st.markdown(f"**🧾 Last S. No.:** {last_s_no} &nbsp;&nbsp;&nbsp; **📁 Last File No.:** {last_f_no}")

    # ✅ Auto-fill next f_no
    next_f_no = str(int(last_f_no) + 1)

    # ✅ Basic fields
    f_no = st.text_input("File No", value=next_f_no, key="add_f_no")
   
    # Default jurisdiction for new case
    jurisdiction_value = "Supreme Court"

    # Default options
    default_jurisdiction_options = ["District Court", "High Court", "Supreme Court", "Others"]

    # Load distinct jurisdictions from DB
    conn = get_connection()
    df_juris = pd.read_sql("SELECT DISTINCT jurisdiction FROM cases", conn)
    conn.close()

    # Merge DB values with defaults
    db_juris = df_juris["jurisdiction"].dropna().unique().tolist()
    jurisdiction_options = list(set(default_jurisdiction_options + db_juris))

    # Ensure current value is valid
    if jurisdiction_value not in jurisdiction_options:
        jurisdiction_options.append(jurisdiction_value)

    jurisdiction_index = jurisdiction_options.index(jurisdiction_value)

    # Dropdown
    jurisdiction = st.selectbox(
        "Jurisdiction (choose existing)",
        jurisdiction_options,
        index=jurisdiction_index,
        key="add_jurisdiction"
    )

    # Free-text fallback
    new_jurisdiction = st.text_input(
        "Or type a new jurisdiction",
        key="new_jurisdiction"
    )

    # Final value: if user typed something, use that; else use dropdown
    final_jurisdiction = new_jurisdiction.strip() if new_jurisdiction.strip() else jurisdiction


    # Default court_location for new case
    court_location_value = "Supreme Court"   # you can set your preferred default

    # Default options
    default_location_options = ["Delhi", "Mumbai", "Ranchi", "Others"]

    # Load distinct court locations from DB
    conn = get_connection()
    df_locations = pd.read_sql("SELECT DISTINCT court_location FROM cases", conn)
    conn.close()

    # Merge DB values with defaults
    db_locations = df_locations["court_location"].dropna().unique().tolist()
    court_location_options = list(set(default_location_options + db_locations))

    # Ensure current value is valid
    if court_location_value not in court_location_options:
        court_location_options.append(court_location_value)

    court_location_index = court_location_options.index(court_location_value)

    # Dropdown
    court_location = st.selectbox(
        "Court Location (choose existing)",
        court_location_options,
        index=court_location_index,
        key="add_court_location"
    )

    # Free-text fallback
    new_court_location = st.text_input(
        "Or type a new court location",
        key="new_court_location"
    )

    # Final value: if user typed something, use that; else use dropdown
    final_court_location = new_court_location.strip() if new_court_location.strip() else court_location

    case_date = st.date_input("Case Registration Date", value=date.today(), key="case_date")

    month_year = get_month_year(case_date.strftime("%Y-%m-%d"))
    fy = get_fy(case_date.strftime("%Y-%m-%d"))


    case_through = st.text_input("Case Through", key="add_case_through")
    case_type = st.text_input("Case Type", key="add_case_type")

    case_no = st.text_input("Case No", key="add_case_no")
    
    particulars = st.text_area("Particulars", key="add_particulars")
    
    court = st.text_input("Court", key="add_court")
    

    next_date_mode = st.selectbox("Next Date", ["Date Awaited", "Pick a Date"], key="add_next_date_mode")
    if next_date_mode == "Pick a Date":
        next_date = st.date_input("📅 Select Next Date", value=date.today(), key="add_next_date_picker")
        next_date_db = next_date.strftime("%Y-%m-%d")
    else:
        next_date_db = None

    # ✅ Status dropdown fix
    status_value = "Pending"  # default for new case
    status_index = ["Pending", "Closed", "Awaited"].index(status_value)
    status = st.selectbox("Status", ["Pending", "Closed", "Awaited"], index=status_index, key="add_status")

    # ✅ Optional fields
    remarks = st.text_area("Remarks", key="add_remarks")
    last_date = st.date_input("Last Date", value=date.today(), key="add_last_date")

    # ✅ Insert logic
    if st.button("💾 Add Case", key="add_case_button"):
        row = {
            "f_no": f_no,
            "jurisdiction": final_jurisdiction,
            "court_location": court_location,
            "month_year": month_year,
            "fy": fy,
            "case_through": case_through,
            "ref_fileno": None,
            "case_type": case_type,
            "fir_no": None,
            "ps": None,
            "case_no": case_no,
            "particulars": particulars,
            "court": court,
            "legal_offer_ws_filed": None,
            "last_date": last_date,
            "next_date": next_date_db,
            "proceeding": None,
            "settle_contest": None,
            "remarks": remarks,
            "result": None,
            "status": status,
            "fee_raised_full_partial_no": None,
            "fee_status": None,
            "fee_receipt_month": None,
            "fee_part_1": None,
            "fee_part_2": None,
            "total_fee": None,
            "expense": None,
            "bill_no": None,
            "file_scaned_y_n": None,
            "date_of_filing": None,
            "cnr_no": None,
            "opponent_advocate": None,
            "opponent_advocate_contact_number": None
        }

        insert_case_row(row)
        st.success("✅ Case added successfully.")


# ✅ Tab 2: Upcoming Cases
with tab2:
    st.subheader("📅 Upcoming Cases (Next 21 Days + Awaited)")

    today = date.today()
    future = today + timedelta(days=21)

    # ✅ Load upcoming + awaited cases
    conn = get_connection()
    df = pd.read_sql("""
        SELECT s_no, case_no, f_no, ref_fileno, jurisdiction, next_date, status,
               particulars, court, court_location, proceeding
        FROM cases
        WHERE status IN ('Pending', 'Awaited')
          AND (next_date BETWEEN ? AND ? OR next_date IS NULL)
        ORDER BY jurisdiction ASC, next_date ASC
    """, conn, params=(today.strftime("%Y-%m-%d"), future.strftime("%Y-%m-%d")))
    conn.close()

    if not df.empty:
        df["next_date"] = pd.to_datetime(df["next_date"], errors="coerce")
        df["next_date_str"] = df["next_date"].dt.strftime("%d-%m-%Y").fillna("Date Awaited")

        awaited_df = df[df["next_date"].isna()]
        upcoming_df = df[df["next_date"].notna()]

        # ✅ Toggle for view mode
        view_mode = st.radio(
            "🧭 Choose view mode:",
            ["Agenda (21‑Day Calendar)", "Date‑wise", "Jurisdiction‑wise"],
            index=0,
            horizontal=True
        )

        # ✅ Agenda view
        if view_mode == "Agenda (21‑Day Calendar)":
            st.markdown("### 🗓️ Upcoming Cases Agenda (Next 21 Days)")
            for offset in range(0, 21):
                day = today + timedelta(days=offset)
                day_cases = upcoming_df[upcoming_df["next_date"].dt.date == day]

                if not day_cases.empty:
                    st.markdown(f"""
                        <div style='background-color:#f0f8ff;padding:8px 12px;
                                    border-left:5px solid #007bff;border-radius:4px;
                                    margin-top:20px;margin-bottom:10px;'>
                            <h4 style='margin:0;color:#007bff;'>📅 {day.strftime('%A, %d-%m-%Y')}</h4>
                        </div>
                    """, unsafe_allow_html=True)

                    sub_df = day_cases[[
                        "f_no","ref_fileno","case_no","jurisdiction","next_date_str","status",
                        "particulars","court","court_location","proceeding"
                    ]]
                    st.dataframe(sub_df.reset_index(drop=True),
                                 use_container_width=True, hide_index=True)
                else:
                    st.markdown(f"""
                        <div style='background-color:#f9f9f9;padding:6px 10px;
                                    border-left:3px solid #ccc;border-radius:4px;
                                    margin-top:10px;margin-bottom:5px;'>
                            <span style='color:#666;'>📅 {day.strftime('%A, %d-%m-%Y')} — No cases</span>
                        </div>
                    """, unsafe_allow_html=True)

        # ✅ Date‑wise grouping
        elif view_mode == "Date‑wise":
            st.markdown("### 📅 Upcoming Cases (Date‑wise)")
            grouped = upcoming_df.sort_values("next_date").groupby("next_date")
            for date_obj, group in grouped:
                date_str = date_obj.strftime("%d-%m-%Y")
                st.markdown(f"""
                    <div style='background-color:#e9f5ff;padding:8px 12px;
                                border-left:5px solid #007bff;border-radius:4px;
                                margin-top:20px;margin-bottom:10px;'>
                        <h4 style='margin:0;color:#007bff;'>📅 <b>{date_str}</b></h4>
                    </div>
                """, unsafe_allow_html=True)

                sub_df = group[[
                    "f_no","ref_fileno","case_no","next_date_str","status",
                    "particulars","court","court_location","proceeding"
                ]]
                st.dataframe(sub_df.reset_index(drop=True),
                             use_container_width=True, hide_index=True)

        # ✅ Jurisdiction‑wise grouping
        elif view_mode == "Jurisdiction‑wise":
            st.markdown("### 🏛️ Upcoming Cases (Jurisdiction‑wise)")
            filtered_df = upcoming_df[upcoming_df["jurisdiction"].notna()]
            for jurisdiction in sorted(filtered_df["jurisdiction"].unique()):
                st.markdown(f"""
                    <div style='background-color:#e9f5ff;padding:8px 12px;
                                border-left:5px solid #007bff;border-radius:4px;
                                margin-top:20px;margin-bottom:10px;'>
                        <h4 style='margin:0;color:#007bff;'>🏛️ <b>{jurisdiction}</b></h4>
                    </div>
                """, unsafe_allow_html=True)

                sub_df = filtered_df[filtered_df["jurisdiction"] == jurisdiction][[
                    "f_no","ref_fileno","case_no","next_date_str","status",
                    "particulars","court","court_location","proceeding"
                ]]
                st.dataframe(sub_df.reset_index(drop=True),
                             use_container_width=True, hide_index=True)

        # ✅ Awaited cases
        if not awaited_df.empty:
            st.markdown("### 📭 Cases with 'Date Awaited'")
            for jurisdiction in sorted(awaited_df["jurisdiction"].dropna().unique()):
                st.markdown(f"""
                    <div style='background-color:#fff3cd;padding:8px 12px;
                                border-left:5px solid #ffc107;border-radius:4px;
                                margin-top:20px;margin-bottom:10px;'>
                        <h4 style='margin:0;color:#856404;'>⏳ <b>{jurisdiction}</b></h4>
                    </div>
                """, unsafe_allow_html=True)

                sub_df = awaited_df[awaited_df["jurisdiction"] == jurisdiction][[
                    "f_no","ref_fileno","case_no","next_date_str","status",
                    "particulars","court","court_location","proceeding"
                ]]
                st.dataframe(sub_df.reset_index(drop=True),
                             use_container_width=True, hide_index=True)
                
        # ✅ Dropdown selector
        df["label"] = (
            df["jurisdiction"].fillna("") + " | " +
            df["f_no"].fillna("") + " | " +
            df["particulars"].fillna("") + " | " +
            df["case_no"].fillna("") + " | " +
            df["next_date_str"]
        )
        case_map = dict(zip(df["label"], df["s_no"]))
        selected_label = st.selectbox("Select a case to view/update", df["label"])
        selected_s_no = case_map.get(selected_label)

        if selected_s_no:
            conn = get_connection()
            df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))
            conn.close()

            if not df_meta.empty:
                st.session_state.selected_row = df_meta.iloc[0].to_dict()
                st.session_state.pop(f"last_date_{selected_s_no}", None)
                st.session_state.pop(f"next_date_{selected_s_no}", None)
                st.success("✅ Case loaded. Proceed to Tab 4 to update.")
            else:
                st.warning("⚠️ No metadata found for this case.")
        else:
            st.warning("⚠️ Invalid selection. Please choose a valid case.")
    else:
        st.info("🎉 No upcoming or awaited cases found.")

# ✅ Tab 3: Fuzzy Search by f_no or particulars
with tab3:
    st.subheader("🔍 Search Case")

    # ✅ Choose search field
    search_field = st.radio("Search by", ["f_no", "particulars"])
    search_input = st.text_input(f"Enter part of the {search_field}")
    threshold = st.slider("🎚️ Match threshold", min_value=30, max_value=100, value=70, step=1)

    if search_input:
        conn = get_connection()
        df_search = pd.read_sql("""
            SELECT s_no, case_no, f_no, particulars, court, court_location, status, next_date
            FROM cases
            WHERE f_no IS NOT NULL OR particulars IS NOT NULL
        """, conn)

        # ✅ Normalize both fields for consistent matching
        df_search["f_no"] = df_search["f_no"].fillna("").astype(str).str.strip().str.lower()
        df_search["particulars"] = df_search["particulars"].fillna("").astype(str).str.strip().str.lower()

        # ✅ Normalize search input
        search_input = search_input.strip().lower()

        # ✅ Compute fuzzy score depending on chosen field
        df_search["score"] = df_search[search_field].apply(
            lambda x: fuzz.token_set_ratio(search_input, x) if x else 0
        )

        # ✅ Filter by threshold
        filtered = df_search[df_search["score"] >= threshold].sort_values(by="score", ascending=False)

        if not filtered.empty:
            st.subheader(f"📋 Matching Records (Score ≥ {threshold})")
            st.dataframe(
                filtered.drop(columns=["score"]).reset_index(drop=True),
                use_container_width=True,
                hide_index=True
            )

            # ✅ Build label and map to s_no
            filtered["label"] = (
                filtered["f_no"].astype(str).fillna("") + " | " +
                filtered["particulars"].fillna("") + " | " +
                filtered["case_no"].fillna("")
            )
            case_map = dict(zip(filtered["label"], filtered["s_no"]))
            selected_label = st.selectbox("Select a record to view full details", filtered["label"])
            selected_s_no = case_map.get(selected_label)

            if selected_s_no:
                df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))
                conn.close()

                if not df_meta.empty:
                    st.subheader("📋 Full Case Metadata")
                    st.dataframe(df_meta.reset_index(drop=True), use_container_width=True, hide_index=True)
                    st.session_state.selected_row = df_meta.iloc[0].to_dict()
                else:
                    st.warning("⚠️ No full metadata found for this record.")
            else:
                st.warning("⚠️ Invalid selection. Please choose a valid case.")
        else:
            st.warning("No close matches found.")


# ✅ Tab 4: Update & Log
with tab4:
    st.subheader("📌 Update Case Record & Log Proceeding")

    if "selected_row" in st.session_state:
        row = st.session_state.selected_row
        s_no = row.get("s_no")

        # Core identifiers
        case_no = st.text_input("Case Number", row.get("case_no", ""), key=f"case_no_{s_no}")
        f_no = st.text_input("File No", row.get("f_no", ""), key=f"f_no_{s_no}")
        ref_fileno = st.text_input("Reference Filing No", row.get("ref_fileno", ""), key=f"ref_fileno_{s_no}")
        fir_no = st.text_input("FIR No", row.get("fir_no", ""), key=f"fir_no_{s_no}")
        ps = st.text_input("Police Station", row.get("ps", ""), key=f"ps_{s_no}")
        particulars = st.text_area("Particulars", row.get("particulars", ""), key=f"particulars_{s_no}")

        # Court info
        jurisdiction = st.text_input("Jurisdiction", row.get("jurisdiction", ""), key=f"jurisdiction_{s_no}")
        court_location = st.text_area("Court Location", row.get("court_location", ""), key=f"court_location_{s_no}")
        court = st.text_input("Court", row.get("court", ""), key=f"court_{s_no}")
        legal_offer_ws_filed = st.text_input("Legal Offer WS Filed", row.get("legal_offer_ws_filed", ""), key=f"ws_filed_{s_no}")
        case_through = st.text_input("Case Through", row.get("case_through", ""), key=f"case_through_{s_no}")
        case_type = st.text_input("Case Type", row.get("case_type", ""), key=f"case_type_{s_no}")

        # Dates
        month_year = st.text_input("Month-Year", row.get("month_year", ""), key=f"month_year_{s_no}")
        fy = st.text_input("Financial Year", row.get("fy", ""), key=f"fy_{s_no}")
        last_date_val = parse_date_safe(row.get("last_date"))
        last_date = st.date_input("Last Date", value=last_date_val or date.today(), key=f"last_date_{s_no}")

        next_date_mode = st.selectbox("Next Date", ["Date Awaited", "Pick a Date"], key=f"next_date_mode_{s_no}")
        if next_date_mode == "Pick a Date":
            next_date_val = parse_date_safe(row.get("next_date"))
            next_date = st.date_input("📅 Select Next Date", value=next_date_val or date.today(), key=f"next_date_picker_{s_no}")
            next_date_db = next_date.strftime("%Y-%m-%d")
        else:
            next_date_db = None

        date_of_filing = st.text_input("Date of Filing", row.get("date_of_filing", ""), key=f"date_of_filing_{s_no}")
        cnr_no = st.text_input("CNR No", row.get("cnr_no", ""), key=f"cnr_no_{s_no}")

        # Proceedings
        proceeding = st.text_area("Proceeding Note", row.get("proceeding", ""), key=f"proceeding_{s_no}")
        settle_contest = st.selectbox("Settle/Contest", ["Settle", "Contest", "Unknown"], key=f"Unknown_{s_no}")
        remarks = st.text_area("Remarks", row.get("remarks", ""), key=f"remarks_{s_no}")
        result = st.text_input("Result", row.get("result", ""), key=f"result_{s_no}")
        status_value = row.get("status") or "Pending"
        status_options = ["Pending", "Closed", "Awaited"]

        status = st.selectbox(
            "Status",
            status_options,
            index=status_options.index(status_value) if status_value in status_options else 0,
            key=f"status_{s_no}"
)

        # Fees
        fee_raised_full_partial_no = st.text_input("Fee Raised (Full/Partial/No)", row.get("fee_raised_full_partial_no", ""), key=f"fee_raised_{s_no}")
        fee_status = st.text_input("Fee Status", row.get("fee_status", ""), key=f"fee_status_{s_no}")
        fee_receipt_month = st.text_input("Fee Receipt Month", row.get("fee_receipt_month", ""), key=f"fee_receipt_month_{s_no}")
        fee_part_1 = st.text_input("Fee Part 1", row.get("fee_part_1", ""), key=f"fee_part1_{s_no}")
        fee_part_2 = st.text_input("Fee Part 2", row.get("fee_part_2", ""), key=f"fee_part2_{s_no}")
        total_fee = st.text_input("Total Fee", row.get("total_fee", ""), key=f"total_fee_{s_no}")
        expense = st.text_input("Expense", row.get("expense", ""), key=f"expense_{s_no}")
        bill_no = st.text_input("Bill No", row.get("bill_no", ""), key=f"bill_no_{s_no}")

        # Flags
        file_scaned_y_n = st.selectbox("File Scanned?", ["Yes", "No"], index=0 if row.get("file_scaned_y_n") == "Yes" else 1, key=f"file_scaned_{s_no}")
        todo_flag = st.selectbox("Add to To‑Do List?", ["No", "Yes"], index=0 if row.get("todo_flag") != "Yes" else 1, key=f"todo_flag_{s_no}")
        todo_details = st.text_area("To‑Do Details", row.get("todo_details", ""), key=f"todo_details_{s_no}")

        # Opponent info
        opponent_advocate = st.text_input("Opponent Advocate", row.get("opponent_advocate", ""), key=f"opp_adv_{s_no}")
        opponent_advocate_contact_number = st.text_input("Opponent Advocate Contact", row.get("opponent_advocate_contact_number", ""), key=f"opp_adv_contact_{s_no}")

        # Proceeding Date (define BEFORE update call)
        proc_date = st.date_input("Proceeding Date", value=date.today(), key=f"proc_date_{s_no}")

        # Update button
        if st.button("Update Case Record", key=f"update_button_{s_no}"):
            update_full_case(
                s_no=s_no,
                case_no=case_no,
                f_no=f_no,
                jurisdiction=jurisdiction,
                court_location=court_location,
                month_year=month_year,
                fy=fy,
                case_through=case_through,
                ref_fileno=ref_fileno,
                case_type=case_type,
                fir_no=fir_no,
                ps=ps,
                particulars=particulars,
                court=court,
                legal_offer_ws_filed=legal_offer_ws_filed,
                last_date=last_date.strftime("%Y-%m-%d") if last_date else None,
                next_date=next_date_db,
                proceeding=proceeding,
                settle_contest=settle_contest,
                remarks=remarks,
                result=result,
                status=status,
                fee_raised_full_partial_no=fee_raised_full_partial_no,
                fee_status=fee_status,
                fee_receipt_month=fee_receipt_month,
                fee_part_1=fee_part_1,
                fee_part_2=fee_part_2,
                total_fee=total_fee,
                expense=expense,
                bill_no=bill_no,
                file_scaned_y_n=file_scaned_y_n,
                date_of_filing=date_of_filing,
                cnr_no=cnr_no,
                opponent_advocate=opponent_advocate,
                opponent_advocate_contact_number=opponent_advocate_contact_number,
                todo_flag=todo_flag,
                todo_details=todo_details,
            )

            log_proceeding(
                case_no or row.get("case_no", ""),
                f_no,
                particulars,
                proc_date.strftime("%Y-%m-%d"),
                proceeding,
                
            )
            st.success("✅ Case record updated and proceeding logged.")

        # Delete section
        st.markdown("---")
        st.warning("⚠️ Danger Zone: Deleting a case cannot be undone.")
        confirm_delete = st.checkbox(
            f"Confirm delete File No. {row.get('f_no')} | Particulars: {row.get('particulars')}",
            key=f"confirm_delete_{s_no}"
        )
        if confirm_delete:
            if st.button("🗑️ Delete Case", key=f"delete_button_{s_no}"):
                delete_case(s_no)
                st.error(f"❌ Case {row.get('case_no')} deleted permanently.")
    else:
        st.warning("⚠️ Please select a case from Tab 2 or Tab 3 before updating.")

# ✅ Tab 5: View Proceedings
with tab5:
    st.subheader("📜 Case Proceedings")

    # ✅ Load case master data
    conn = get_connection()
    df_cases = pd.read_sql("SELECT s_no, f_no, case_no, particulars FROM cases ORDER BY f_no", conn)
    conn.close()

    df_cases["label"] = df_cases.apply(
        lambda row: f"{row['f_no']} | {row['case_no']} | {row['particulars']}", axis=1
    )
    case_map = dict(zip(df_cases["label"], df_cases["s_no"]))

    # ✅ Search + dropdown
    search_query = st.text_input(
        "🔍 Search by File No / Particulars",
        key="search_query_tab5"   # 🔑 unique key
    )
    df_filtered = df_cases[df_cases["label"].str.contains(search_query, case=False, na=False)] if search_query else df_cases
    selected_label = st.selectbox(
        "📂 Select Case",
        options=["-- Select a case --"] + df_filtered["label"].tolist(),
        key="select_case_tab5"
    )

    selected_case = None
    if selected_label:
        selected_s_no = case_map.get(selected_label)
        if selected_s_no:
            conn = get_connection()
            df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))
            conn.close()
            if not df_meta.empty:
                selected_case = df_meta.iloc[0].to_dict()
                st.success("✅ Case loaded. You can now log proceedings.")

    # ✅ Logging form
    if selected_case:
        proc_date = st.date_input(
            "Date",
            value=date.today(),
            key="proc_date_tab5"   # 🔑 unique key
        )
        note = st.text_area(
            "Proceeding Note",
            key="note_tab5"        # 🔑 unique key
        )
        if st.button("Log Proceeding", key="log_proc_tab5"):   # 🔑 unique key
            log_proceeding(
                selected_case.get("case_no"),
                selected_case.get("f_no"),
                selected_case.get("particulars"),
                proc_date.strftime("%Y-%m-%d"),
                note,
                
            )
            st.success("✅ Proceeding logged successfully.")

        # ✅ Case Proceedings Summary
        st.subheader("📊 Case Proceedings Summary")
        conn = get_connection()
        df_proc = pd.read_sql("""
            SELECT id, date, note, updated_by
            FROM proceedings_log
            WHERE case_no = ? AND f_no = ?
            ORDER BY date DESC
        """, conn, params=(selected_case.get("case_no"), selected_case.get("f_no")))
        conn.close()

        if not df_proc.empty:
            df_proc["date"] = pd.to_datetime(df_proc["date"], errors="coerce").dt.strftime("%d-%m-%Y")
            st.dataframe(df_proc.reset_index(drop=True), use_container_width=True, hide_index=True)

            # ✅ Proceedings Editor
            st.subheader("✏️ Edit Proceeding Entry")
            df_proc["label"] = df_proc.apply(
                lambda row: f"{row['id']} | {row['date']} | {row['note'][:30]}...", axis=1
            )
            entry_map = dict(zip(df_proc["label"], df_proc["id"]))
            selected_entry = st.selectbox(
                "🔍 Select Proceeding to Edit",
                options=[""] + list(entry_map.keys()),
                key="select_proc_tab5"   # 🔑 unique key
            )

            if selected_entry:
                entry_id = entry_map[selected_entry]
                conn = get_connection()
                df_entry = pd.read_sql("SELECT * FROM proceedings_log WHERE id = ?", conn, params=(entry_id,))
                conn.close()

                if not df_entry.empty:
                    entry_data = df_entry.iloc[0].to_dict()
                    st.success("✅ Proceeding loaded for editing.")

                    new_date = st.date_input(
                        "Date",
                        pd.to_datetime(entry_data["date"]).date(),
                        key=f"edit_date_{entry_id}"   # 🔑 unique key per entry
                    )
                    new_note = st.text_area(
                        "Proceeding Note",
                        value=entry_data["note"],
                        key=f"edit_note_{entry_id}"   # 🔑 unique key per entry
                    )

                    if st.button("💾 Save Changes", key=f"save_proc_{entry_id}"):   # 🔑 unique key per entry
                        conn = get_connection()
                        conn.execute("""
                            UPDATE proceedings_log
                            SET date = ?, note = ?
                            WHERE id = ?
                        """, (new_date.strftime("%Y-%m-%d"), new_note, entry_id))
                        conn.commit()
                        conn.close()
                        st.success("✅ Proceeding updated successfully.")
        else:
            st.info("📭 No proceedings logged yet for this case.")

# ✅ Tab 6: Update Log
SHOW_TAB6 = False

if SHOW_TAB6:


    with tab6:
        st.subheader("📝 Update Log")
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM update_log ORDER BY updated_on DESC", conn)
        conn.close()

        if not df.empty:
            df["updated_on"] = pd.to_datetime(df["updated_on"], errors="coerce").dt.strftime("%d-%m-%Y")
            st.dataframe(df.reset_index(drop=True), use_container_width=True, hide_index=True)
        else:
            st.info("📭 No updates logged yet.")

# ✅ Tab 7: Full DB Viewer
with tab7:
    st.subheader("📚 Full Database Viewer")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        st.info("No tables found in the database.")
    else:
        selected_table = st.selectbox("Select a table to view", tables)
        df = pd.read_sql(f"SELECT * FROM '{selected_table}'", conn)

        for col in df.columns:
            if "date" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d-%m-%Y")

        st.dataframe(df.reset_index(drop=True), use_container_width=True, hide_index=True)
    conn.close()

# ✅ Tab 8: Modify Update Log
SHOW_TAB8 = False

if SHOW_TAB8:

    with tab8:
        st.subheader("✏️ Modify Update Log Entry")
        case_no = st.text_input("Enter Case No to search logs")

        if case_no:
            conn = get_connection()
            df_log = pd.read_sql("SELECT rowid, * FROM update_log WHERE case_no = ?", conn, params=(case_no,))
            conn.close()

            if df_log.empty:
                st.warning("No log entries found for this case.")
            else:
                selected_row = st.selectbox("Select log entry to modify", df_log["rowid"].astype(str))
                entry = df_log[df_log["rowid"] == int(selected_row)].iloc[0]

                new_field = st.text_input("Field", entry["field"])
                new_old_value = st.text_input("Old Value", entry["old_value"])
                new_new_value = st.text_input("New Value", entry["new_value"])
                new_updated_on = st.date_input("Updated On", pd.to_datetime(entry["updated_on"], errors="coerce"))

                if st.button("💾 Save Changes"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE update_log
                        SET field = ?, old_value = ?, new_value = ?, updated_on = ?
                        WHERE rowid = ?
                    """, (new_field, new_old_value, new_new_value, new_updated_on.strftime("%Y-%m-%d"), int(selected_row)))
                    conn.commit()
                    conn.close()
                    st.success("✅ Log entry updated successfully.")

# ✅ Tab 9: Overdue Cases
with tab9:
    #st.subheader("⏳ Overdue Cases (Pending & Past Next Date + Awaited)")
    today = date.today()

    # ✅ Load overdue + awaited cases
    conn = get_connection()
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
    conn.close()

    if not df.empty:
        # ✅ Keep raw next_date for logic, create display column
        df["next_date_dt"] = pd.to_datetime(df["next_date"], errors="coerce")
        df["next_date_str"] = df["next_date_dt"].dt.strftime("%d-%m-%Y")
        df.loc[df["next_date"].isna(), "next_date_str"] = "Date Awaited"
        df.loc[df["next_date"] == "Awaited", "next_date_str"] = "Awaited"

        # ✅ Split into overdue vs awaited
        overdue_df = df[(df["next_date"].notna()) & (df["next_date"] != "Awaited") & (df["next_date_dt"] < pd.to_datetime(today))]
        awaited_df = df[(df["next_date"].isna()) | (df["next_date"] == "Awaited")]

        # ✅ Overdue cases section
        if not overdue_df.empty:
            st.markdown("### ⚠️ Overdue Cases (Past Next Date)")
            for j in sorted(overdue_df["jurisdiction"].dropna().unique()):
                st.markdown(f"""
                    <div style='background-color:#ffe9e9;padding:8px 12px;
                                border-left:5px solid #dc3545;border-radius:4px;
                                margin-top:20px;margin-bottom:10px;'>
                        <h4 style='margin:0;color:#dc3545;'>⚠️ <b>{j}</b></h4>
                    </div>
                """, unsafe_allow_html=True)

                sub_df = overdue_df[overdue_df["jurisdiction"] == j][[
                    "case_no","f_no","particulars","court","court_location",
                    "last_date","next_date_str","status","todo_flag","todo_details"
                ]]
                with st.expander(f"⚠️ {j} — {len(sub_df)} case(s)", expanded=False):
                    st.dataframe(sub_df.reset_index(drop=True),
                                use_container_width=True, hide_index=True)

                #st.dataframe(sub_df.reset_index(drop=True), use_container_width=True, hide_index=True)

        # ✅ Awaited cases section
        if not awaited_df.empty:
            st.markdown("### 📭 Cases with 'Date Awaited'")
            for j in sorted(awaited_df["jurisdiction"].dropna().unique()):
                st.markdown(f"""
                    <div style='background-color:#fff3cd;padding:8px 12px;
                                border-left:5px solid #ffc107;border-radius:4px;
                                margin-top:20px;margin-bottom:10px;'>
                        <h4 style='margin:0;color:#856404;'>⏳ <b>{j}</b></h4>
                    </div>
                """, unsafe_allow_html=True)

                sub_df = awaited_df[awaited_df["jurisdiction"] == j][[
                    "case_no","f_no","particulars","court","court_location",
                    "last_date","next_date_str","status","todo_flag","todo_details"
                ]]
                with st.expander(f"⏳ {j} — {len(sub_df)} case(s)", expanded=False):
                    st.dataframe(sub_df.reset_index(drop=True),
                                use_container_width=True, hide_index=True)
                #st.dataframe(sub_df.reset_index(drop=True), use_container_width=True, hide_index=True)

        # ✅ Build dropdown (includes both overdue + awaited)
        df["label"] = (
            df["jurisdiction"].fillna("") + " | " +
            df["f_no"].fillna("") + " | " +
            df["particulars"].fillna("") + " | " +
            df["case_no"].fillna("") + " | " +
            df["next_date_str"]
        )
        case_map = dict(zip(df["label"], df["s_no"]))
        selected_label = st.selectbox("Select a case to update", df["label"])
        selected_s_no = case_map.get(selected_label)

        if selected_s_no:
            df_meta = load_case_metadata(selected_s_no)
            if not df_meta.empty:
                row = df_meta.iloc[0].to_dict()
                st.session_state.selected_row = row

                st.subheader("📌 Update Overdue / Awaited Case")

                # ✅ Editable fields
                new_case_no = st.text_input("Case Number", row.get("case_no",""), key=f"overdue_case_no_{row['s_no']}")
                particulars = st.text_area("Particulars", row.get("particulars",""), key=f"overdue_particulars_{row['s_no']}")
                court = st.text_input("Court", row.get("court",""), key=f"overdue_court_{row['s_no']}")

                # ✅ Last Date
                last_date = st.date_input("Last Date", parse_date_safe(row.get("last_date")), key=f"overdue_last_date_{row['s_no']}")

                # ✅ Next Date with Awaited option
                next_date_mode = st.selectbox("Next Date", ["Date Awaited","Pick a Date"],
                                              key=f"overdue_next_date_mode_{row['s_no']}")
                if next_date_mode == "Pick a Date":
                    next_date_val = parse_date_safe(row.get("next_date"))
                    next_date = st.date_input("📅 Select Next Date",
                                              value=next_date_val if next_date_val else date.today(),
                                              key=f"overdue_next_date_picker_{row['s_no']}")
                    next_date_db = next_date.strftime("%Y-%m-%d")
                else:
                    next_date_db = "Awaited"

                # ✅ Proceeding + status
                proceeding = st.text_area("Proceeding Note", row.get("proceeding",""), key=f"overdue_proceeding_{row['s_no']}")
                status_value = row.get("status") or "Pending"
                status = st.selectbox("Status", ["Pending","Closed","Awaited"],
                                      index=["Pending","Closed","Awaited"].index(status_value),
                                      key=f"overdue_status_{row['s_no']}")

                proc_date = st.date_input("Proceeding Date", today, key=f"overdue_proc_date_{row['s_no']}")

                # ✅ To‑Do fields
                todo_flag = st.selectbox("Add to To‑Do List?", ["No","Yes"],
                                         index=0 if row.get("todo_flag")!="Yes" else 1,
                                         key=f"overdue_todo_flag_{row['s_no']}")
                todo_details = st.text_area("To‑Do Details", row.get("todo_details",""),
                                            key=f"overdue_todo_details_{row['s_no']}")

                # ✅ Update button
                if st.button("Update Overdue Case", key=f"update_overdue_button_{row['s_no']}"):
                    update_full_case(
                        s_no=row.get("s_no"),
                        case_no=new_case_no,
                        ref_fileno=row.get("ref_fileno", ""),         # ✅ added
                        fir_no=row.get("fir_no", ""),                 # ✅ added
                        ps=row.get("ps", ""),                         # ✅ added
                        particulars=particulars,
                        court_location=row.get("court_location", ""), # ✅ added
                        court=court,
                        legal_offer_ws_filed=row.get("legal_offer_ws_filed", ""),  # ✅ added
                        last_date=last_date.strftime("%Y-%m-%d"),
                        next_date=next_date_db,
                        proceeding=proceeding,
                        settle_contest=row.get("settle_contest", "Unknown"),       # ✅ added
                        remarks=row.get("remarks", ""),             # ✅ added
                        status=status,
                        f_no=row.get("f_no", ""),                   # ✅ added
                        todo_flag=todo_flag,
                        todo_details=todo_details
                    )
                    log_proceeding(new_case_no or row.get("case_no",""),
                                   row.get("f_no",""),
                                   row.get("particulars",""),
                                   proceeding,
                                   proc_date.strftime("%Y-%m-%d"))
                    st.success("✅ Case record updated and proceeding logged.")
            else:
                st.warning("⚠️ No metadata found for this case.")
    else:
        st.info("🎉 No overdue or awaited cases found.")


# ✅ Tab 10: To-Do List + Financial Workflow
with tab10:
    st.subheader("📝 To‑Do & Financial Workflow")
    today = date.today()

    # Load ALL cases
    conn = get_connection()
    df_all = pd.read_sql("""
        SELECT s_no, jurisdiction, case_no, f_no, particulars, court, court_location,
               next_date, status, todo_flag, todo_details, closed_date, bills_raised, fee_status
        FROM cases
        ORDER BY jurisdiction ASC, next_date ASC
    """, conn)
    conn.close()

    # Load fees table
    conn = get_connection()
    df_fees = pd.read_sql("SELECT * FROM fees ORDER BY bill_date DESC", conn)
    conn.close()

    # Format dates
    df_all["next_date"] = pd.to_datetime(df_all["next_date"], errors="coerce").dt.strftime("%d-%m-%Y")

    # ✅ Section 1: To‑Do List
    st.markdown("### 📌 Cases in To‑Do List")
    df_todo = df_all[df_all["todo_flag"] == "Yes"]
    if not df_todo.empty:
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
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE cases SET todo_flag='No', todo_details='' WHERE s_no=?", (row['s_no'],))
                        conn.commit()
                        conn.close()
                        st.success(f"🎉 Case {row['case_no']} marked as completed.")
                        st.rerun()
    else:
        st.info("✅ No cases in To‑Do List.")

    # ✅ Section 2: Bills to be Raised
    st.markdown("### 📌 Bills to be Raised")

    closed_cases = df_all[
        (df_all["status"].str.upper() == "CLOSED") &
        (df_all["closed_date"].notna()) & (df_all["closed_date"].str.strip() != "")
    ]

    if not closed_cases.empty:
        with st.expander(f"📍 Bills to be Raised — {len(closed_cases)} case(s)", expanded=False):
            for _, row in closed_cases.iterrows():
                cols = st.columns([1.2, 1, 2, 1.5, 1.5, 1.5])
                cols[0].write(row["case_no"])
                cols[1].write(row["f_no"])
                cols[2].write(row["particulars"])
                cols[3].write(row["court"])
                bills_flag = row.get("bills_raised") or "No"
                bills_choice = cols[4].selectbox("Bills Raised?", ["No","Yes"],
                                                index=0 if bills_flag!="Yes" else 1,
                                                key=f"bills_flag_{row['s_no']}")
                if cols[5].button("Update", key=f"bills_update_{row['s_no']}"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE cases SET bills_raised=? WHERE s_no=?", (bills_choice, row['s_no']))
                    conn.commit()
                    if bills_choice == "Yes":
                        cursor.execute("""
                            INSERT INTO fees (case_s_no, file_no, court_location, case_title,
                                            case_through, bill_category, bill_amount, bill_date, received)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row['s_no'], row['f_no'], row['court_location'], row['particulars'],
                            "IL", "Final Bill", 0, today.strftime("%d-%m-%Y"), "No"
                        ))
                        conn.commit()
                    conn.close()
                    st.success(f"✅ Bills status updated for Case {row['case_no']}.")
                    st.rerun()
    else:
        st.info("✅ No closed cases with valid Closed Date found.")

    
    
    # ✅ Section 3: Fees Awaited
st.markdown("### 💰 Fees Awaited")

fees_awaited = df_fees[df_fees["received"].str.upper() != "YES"]

if not fees_awaited.empty:
    fees_awaited["bill_date"] = pd.to_datetime(fees_awaited["bill_date"], errors="coerce").dt.strftime("%d-%m-%Y")
    fees_awaited["received_date"] = pd.to_datetime(fees_awaited["received_date"], errors="coerce").dt.strftime("%d-%m-%Y")
    fees_awaited["bill_amount"] = fees_awaited["bill_amount"].fillna(0).astype(int)
    fees_awaited["received_amount"] = fees_awaited["received_amount"].fillna(0).astype(int)

    with st.expander(f"📍 Fees Awaited — {len(fees_awaited)} record(s)", expanded=False):
        for _, row in fees_awaited.iterrows():
            cols = st.columns([1.2, 1, 2, 1.5, 1.5, 1.5, 1.5, 1.5])
            cols[0].write(row["file_no"])
            cols[1].write(row["claim_no"])
            cols[2].write(row["case_title"])
            cols[3].write(row["bill_category"])
            cols[4].write(row["bill_amount"])
            cols[5].write(row["bill_date"])

            received_amount = cols[6].number_input(
                "Received Amount",
                value=int(row.get("received_amount") or 0),
                step=1,
                key=f"recv_amt_{row['id']}"
            )

            raw_val = row.get("received_date")
            parsed = pd.to_datetime(raw_val, errors="coerce")
            default_date = parsed.date() if not pd.isna(parsed) else None

            received_date = cols[6].date_input(
                "Received Date",
                value=default_date if default_date else None,
                key=f"recv_date_{row['id']}"
            )

            if cols[7].button("✅ Mark Received", key=f"mark_recv_{row['id']}"):
                conn = get_connection()
                cursor = conn.cursor()

                # Update fees table
                cursor.execute("""
                    UPDATE fees
                    SET received = 'Yes',
                        received_amount = ?,
                        received_date = ?
                    WHERE id = ?
                """, (
                    int(received_amount),
                    received_date.strftime("%Y-%m-%d") if received_date else None,
                    row['id']
                ))
                conn.commit()

                # ✅ Check for duplicate in finance_log
                cursor.execute("""
                    SELECT COUNT(*) FROM finance_log
                    WHERE type='Income' AND status='Received'
                      AND amount=? AND date=? AND case_no=? AND f_no=? AND particulars=?
                """, (
                    int(received_amount),
                    received_date.strftime("%Y-%m-%d") if received_date else date.today().strftime("%Y-%m-%d"),
                    row.get("case_no",""),
                    row.get("file_no",""),
                    row.get("case_title","")
                ))
                exists = cursor.fetchone()[0]

                if exists == 0:
                    cursor.execute("""
                        INSERT INTO finance_log (date, type, amount, mode, description, status, case_no, f_no, particulars)
                        VALUES (?, 'Income', ?, 'Bank', ?, 'Received', ?, ?, ?)
                    """, (
                        received_date.strftime("%Y-%m-%d") if received_date else date.today().strftime("%Y-%m-%d"),
                        int(received_amount),
                        f"Fee received for {row['case_title']}",
                        row.get("case_no",""),
                        row.get("file_no",""),
                        row.get("case_title","")
                    ))
                    conn.commit()

                conn.close()
                st.success(f"💰 Fee marked received and logged in Finance for File {row['file_no']}.")
                st.rerun()
else:
    st.info("✅ No fees awaited.")


    # ✅ Section 4: Fees Received (history)
    st.markdown("### 📜 Fees Received (History)")

    fees_received = df_fees[df_fees["received"].str.upper() == "YES"]

    if not fees_received.empty:
        fees_received["bill_date"] = pd.to_datetime(fees_received["bill_date"], errors="coerce").dt.strftime("%d-%m-%Y")
        fees_received["received_date"] = pd.to_datetime(fees_received["received_date"], errors="coerce").dt.strftime("%d-%m-%Y")
        fees_received["bill_amount"] = fees_received["bill_amount"].fillna(0).astype(int)
        fees_received["received_amount"] = fees_received["received_amount"].fillna(0).astype(int)

        with st.expander(f"📍 Fees Received — {len(fees_received)} record(s)", expanded=False):
            st.table(fees_received[[
                "file_no","claim_no","court_location","case_title",
                "bill_category","bill_amount","bill_date",
                "received_date","received_amount"
            ]])

            total_billed = int(fees_received["bill_amount"].sum())
            total_received = int(fees_received["received_amount"].sum())
            outstanding = total_billed - total_received

            st.write(f"**Total Billed:** ₹{total_billed:,}")
            st.write(f"**Total Received:** ₹{total_received:,}")
            st.write(f"**Outstanding:** ₹{outstanding:,}")
    else:
        st.info("✅ No fees received yet.")

    # Load fees table
    conn = get_connection()
    df_fees = pd.read_sql("""
        SELECT id, case_s_no, file_no, claim_no, court_location, case_title,
            bill_category, bill_amount, bill_date, received, received_date, received_amount
        FROM fees
        ORDER BY bill_date DESC
    """, conn)
    conn.close()

    if not df_fees.empty:
        # Safely format dates
        df_fees["bill_date_str"] = pd.to_datetime(df_fees["bill_date"], errors="coerce").dt.strftime("%d-%m-%Y")
        df_fees["received_date_str"] = pd.to_datetime(df_fees["received_date"], errors="coerce").dt.strftime("%d-%m-%Y")

        # Replace NaT with blank strings
        df_fees["bill_date_str"] = df_fees["bill_date_str"].fillna("")
        df_fees["received_date_str"] = df_fees["received_date_str"].fillna("")

        # Ensure amounts are integers
        df_fees["bill_amount"] = df_fees["bill_amount"].fillna(0).astype(int)
        df_fees["received_amount"] = df_fees["received_amount"].fillna(0).astype(int)

        # Build dropdown label
        df_fees["label"] = (
            df_fees["file_no"].fillna("") + " | " +
            df_fees["claim_no"].fillna("") + " | " +
            df_fees["case_title"].fillna("") + " | " +
            df_fees["bill_category"].fillna("") + " | " +
            df_fees["bill_date_str"]
        )

        fee_map = dict(zip(df_fees["label"], df_fees["id"]))
        selected_label = st.selectbox("Select a fee record to update", df_fees["label"])
        selected_id = fee_map.get(selected_label)

        if selected_id:
            row = df_fees[df_fees["id"] == selected_id].iloc[0].to_dict()

            st.subheader("📌 Update Fee Record")

            # Editable fields
            bill_amount = st.number_input("Bill Amount", value=int(row.get("bill_amount") or 0), step=1)
            bill_date = st.date_input("Bill Date",
                                    value=pd.to_datetime(row.get("bill_date"), errors="coerce").date()
                                            if row.get("bill_date") else date.today())
            received_flag = st.selectbox("Received?", ["No","Yes","NOT REQUIRED"],
                                        index=0 if str(row.get("received")).upper()!="YES" else 1)
            received_amount = st.number_input("Received Amount", value=int(row.get("received_amount") or 0), step=1)

            # Allow blank received_date
            parsed = pd.to_datetime(row.get("received_date"), errors="coerce")
            default_date = parsed.date() if not pd.isna(parsed) else None
            received_date = st.date_input("Received Date", value=default_date if default_date else None)

            if st.button("Update Fee Record", key=f"update_fee_{row['id']}"):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE fees
                    SET bill_amount = ?, bill_date = ?, received = ?, 
                        received_amount = ?, received_date = ?
                    WHERE id = ?
                """, (
                    int(bill_amount),
                    bill_date.strftime("%Y-%m-%d"),
                    received_flag,
                    int(received_amount),
                    received_date.strftime("%Y-%m-%d") if received_date else None,
                    row['id']
                ))
                conn.commit()
                conn.close()
                st.success("✅ Fee record updated successfully.")
                st.rerun()
    else:
        st.info("🎉 No fee records found.")



# ✅ Tab 11: Finance Log
with tab11:
    st.markdown("<div class='sticky-header'>💼 Log Income or Expense</div>", unsafe_allow_html=True)

    # ✅ Load case master data
    conn = get_connection()
    df_cases = pd.read_sql("SELECT s_no, f_no, case_no, particulars FROM cases ORDER BY f_no", conn)
    conn.close()

    df_cases["label"] = df_cases.apply(
        lambda row: f"{row['f_no']} | {row['case_no']} | {row['particulars']}", axis=1
    )
    case_map = dict(zip(df_cases["label"], df_cases["s_no"]))

    # ✅ Search + dropdown
    search_query = st.text_input("🔍 Search by File No / Particulars", key="search_query_tab11")
    df_filtered = df_cases[df_cases["label"].str.contains(search_query, case=False, na=False)] if search_query else df_cases
    selected_label = st.selectbox("📂 Select Case", options=[""] + df_filtered["label"].tolist(), key="select_case_tab11")

    selected_case = None
    if selected_label:
        selected_s_no = case_map.get(selected_label)
        if selected_s_no:
            conn = get_connection()
            df_meta = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(selected_s_no,))
            conn.close()
            if not df_meta.empty:
                selected_case = df_meta.iloc[0].to_dict()
                st.success("✅ Case loaded. You can now log income or expense.")

    # ✅ Logging form
    if selected_case:
        entry_type = st.selectbox("Type", ["Income", "Expense"], key="entry_type_tab11")
        amount = st.number_input("Amount", min_value=0.0, format="%.2f", key="amount_tab11")
        mode = st.selectbox("Mode", ["Cash", "Bank", "UPI", "Other"], key="mode_tab11")
        status = st.selectbox(
            "Status",
            ["Received", "Receivable"] if entry_type == "Income" else ["Paid", "Pending"],
            key="status_tab11"
        )
        description = st.text_area("Description", key="description_tab11")
        entry_date = st.date_input("Date", value=date.today(), key="entry_date_tab11")

        case_no = st.text_input("Case Number", value=selected_case.get("case_no", ""), key="case_no_tab11")
        f_no = st.text_input("File No", value=selected_case.get("f_no", ""), key="f_no_tab11")
        particulars = st.text_input("Particulars", value=selected_case.get("particulars", ""), key="particulars_tab11")

        if st.button("Log Entry", key="log_entry_tab11"):
            conn = get_connection()
            conn.execute("""
                INSERT INTO finance_log (date, type, amount, mode, description, status, case_no, f_no, particulars)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_date.strftime("%Y-%m-%d"), entry_type, amount, mode,
                description, status, case_no, f_no, particulars
            ))
            conn.commit()
            conn.close()
            st.success("✅ Entry logged successfully.")

        # ✅ Case Finance Summary
        st.subheader("📊 Case Finance Summary")
        conn = get_connection()
        df_finance = pd.read_sql("""
            SELECT id, date, type, status, amount, mode, description, case_no, f_no, particulars
            FROM finance_log
            WHERE (case_no = ? OR f_no = ?)
            ORDER BY date DESC
        """, conn, params=(case_no, f_no))
        conn.close()
        # ✅ Format dates and amounts for consistency
        df_finance["date"] = pd.to_datetime(df_finance["date"], errors="coerce").dt.strftime("%d-%m-%Y")
        df_finance["amount"] = df_finance["amount"].fillna(0).astype(int)
        
        if not df_finance.empty:
            income_received = df_finance.query("type == 'Income' and status == 'Received'")["amount"].sum()
            income_receivable = df_finance.query("type == 'Income' and status == 'Receivable'")["amount"].sum()
            expense_paid = df_finance.query("type == 'Expense' and status == 'Paid'")["amount"].sum()
            expense_pending = df_finance.query("type == 'Expense' and status == 'Pending'")["amount"].sum()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Income Received", f"₹{income_received:,.2f}")
                st.metric("Income Receivable", f"₹{income_receivable:,.2f}")
            with col2:
                st.metric("Expense Paid", f"₹{expense_paid:,.2f}")
                st.metric("Expense Pending", f"₹{expense_pending:,.2f}")

            with st.expander("📋 View Finance Entries for This Case"):
                st.dataframe(df_finance.reset_index(drop=True), use_container_width=True, hide_index=True)

            # ✅ Finance Log Editor
            st.subheader("✏️ Edit Finance Entry")
            df_finance["label"] = df_finance.apply(
                lambda row: f"{row['id']} | {row['date']} | ₹{row['amount']} | {row['type']}", axis=1
            )
            entry_map = dict(zip(df_finance["label"], df_finance["id"]))
            selected_entry = st.selectbox("🔍 Select Entry to Edit", options=[""] + list(entry_map.keys()), key="select_entry_tab11")

            if selected_entry:
                entry_id = entry_map[selected_entry]
                conn = get_connection()
                df_entry = pd.read_sql("SELECT * FROM finance_log WHERE id = ?", conn, params=(entry_id,))
                conn.close()

                if not df_entry.empty:
                    entry_data = df_entry.iloc[0].to_dict()
                    st.success("✅ Entry loaded for editing.")

                    new_date = st.date_input("Date", pd.to_datetime(entry_data["date"]).date(), key=f"edit_date_{entry_id}")
                    new_type = st.selectbox("Type", ["Income", "Expense"], index=["Income", "Expense"].index(entry_data["type"]), key=f"edit_type_{entry_id}")
                    new_amount = st.number_input("Amount", value=entry_data["amount"], min_value=0.0, format="%.2f", key=f"edit_amount_{entry_id}")
                    new_mode = st.selectbox("Mode", ["Cash", "Bank", "UPI", "Other"], index=["Cash", "Bank", "UPI", "Other"].index(entry_data["mode"]), key=f"edit_mode_{entry_id}")
                    status_options = ["Received", "Receivable"] if new_type == "Income" else ["Paid", "Pending"]
                    status_index = status_options.index(entry_data["status"]) if entry_data["status"] in status_options else 0
                    new_status = st.selectbox("Status", status_options, index=status_index, key=f"edit_status_{entry_id}")
                    new_description = st.text_area("Description", value=entry_data["description"], key=f"edit_description_{entry_id}")

                    st.markdown(f"**Case No:** {entry_data['case_no']}")
                    st.markdown(f"**File No:** {entry_data['f_no']}")
                    st.markdown(f"**Particulars:** {entry_data['particulars']}")

                    if st.button("💾 Save Changes", key=f"save_entry_{entry_id}"):
                        conn = get_connection()
                        conn.execute("""
                            UPDATE finance_log
                            SET date = ?, type = ?, amount = ?, mode = ?, description = ?, status = ?, case_no = ?, f_no = ?, particulars = ?
                            WHERE id = ?
                        """, (
                            new_date.strftime("%Y-%m-%d"), new_type, new_amount, new_mode,
                            new_description, new_status,
                            entry_data["case_no"], entry_data["f_no"], entry_data["particulars"],
                            entry_id
                        ))
                        conn.commit()
                        conn.close()
                        st.success("✅ Finance entry updated successfully.")

                    if st.button("🗑️ Delete Entry", key=f"delete_entry_{entry_id}"):
                        conn = get_connection()
                        conn.execute("DELETE FROM finance_log WHERE id = ?", (entry_id,))
                        conn.commit()
                        conn.close()
                        st.error("❌ Finance entry deleted permanently.")
        else:
            st.info("ℹ️ No finance records found for this case.")


# ✅ Tab 12: 📊 Monthly Finance Overview
with tab12:
    st.subheader("📊 Monthly Finance Overview")

    # ✅ Load full finance log
    conn = get_connection()
    df_all_finance = pd.read_sql("SELECT * FROM finance_log ORDER BY date DESC", conn)
    conn.close()

    # ✅ Format dates and amounts for consistency
    df_all_finance["date"] = pd.to_datetime(df_all_finance["date"], errors="coerce").dt.strftime("%d-%m-%Y")
    df_all_finance["amount"] = df_all_finance["amount"].fillna(0).astype(int)

    # ✅ Add month column for grouping
    df_all_finance["month"] = pd.to_datetime(df_all_finance["date"], errors="coerce").dt.strftime("%B %Y")
    available_months = sorted(df_all_finance["month"].dropna().unique(), reverse=True)

    selected_month = st.selectbox("📅 Filter by Month", options=["All"] + available_months)
    if selected_month != "All":
        df_all_finance = df_all_finance[df_all_finance["month"] == selected_month]

    income_received = df_all_finance.query("type == 'Income' and status == 'Received'")["amount"].sum()
    income_receivable = df_all_finance.query("type == 'Income' and status == 'Receivable'")["amount"].sum()
    expense_paid = df_all_finance.query("type == 'Expense' and status == 'Paid'")["amount"].sum()
    expense_pending = df_all_finance.query("type == 'Expense' and status == 'Pending'")["amount"].sum()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Income Received", f"₹{income_received:,.2f}")
        st.metric("Income Receivable", f"₹{income_receivable:,.2f}")
    with col2:
        st.metric("Expense Paid", f"₹{expense_paid:,.2f}")
        st.metric("Expense Pending", f"₹{expense_pending:,.2f}")

    with st.expander("📋 View All Finance Entries"):
        st.dataframe(df_all_finance.reset_index(drop=True), use_container_width=True, hide_index=True)

# ✅ Tab 13: Summary Chart
with tab13:
    st.subheader("📊 Case Status Summary by Jurisdiction")

    conn = get_connection()
    # ✅ Overall status summary
    df = pd.read_sql("""
        SELECT jurisdiction, status, COUNT(*) as count
        FROM cases
        WHERE jurisdiction IS NOT NULL AND status IN ('Pending', 'Closed', 'Awaited')
        GROUP BY jurisdiction, status
        ORDER BY jurisdiction ASC
    """, conn)

    # ✅ Pending cases day-of-week summary
    df_pending_days = pd.read_sql("""
        SELECT jurisdiction, court_location,
               strftime('%w', next_date) AS weekday_num,
               COUNT(*) as pending_count
        FROM cases
        WHERE status = 'Pending'
          AND jurisdiction IS NOT NULL
          AND court_location IS NOT NULL
          AND next_date IS NOT NULL
        GROUP BY jurisdiction, court_location, weekday_num
        ORDER BY weekday_num ASC
    """, conn)
    conn.close()

    if not df.empty:
        import matplotlib.pyplot as plt
        import numpy as np

        # ---------- Stacked bar chart of totals ----------
        pivot_df = df.pivot(index="jurisdiction", columns="status", values="count").fillna(0)
        statuses = ["Pending", "Closed", "Awaited"]
        colors = {"Pending": "#034516", "Closed": "#b65d0a", "Awaited": "#6218b6"}

        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(pivot_df.index))
        bottom = np.zeros(len(pivot_df.index))

        for status in statuses:
            values = pivot_df[status] if status in pivot_df else np.zeros(len(pivot_df.index))
            bars = ax.bar(x, values, bottom=bottom, label=status, color=colors[status])
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2,
                            bar.get_y() + height/2,
                            f'{int(height)}',
                            ha='center', va='center',
                            fontsize=10, color='white')
            bottom += values

        ax.set_xticks(x)
        ax.set_xticklabels(pivot_df.index, rotation=15)
        ax.set_ylabel("Number of Cases")
        ax.set_xlabel("Jurisdiction")
        ax.set_title("Case Counts by Jurisdiction and Status")
        ax.legend()
        st.pyplot(fig)

        # ---------- Totals table ----------
        summary = pivot_df.copy()
        summary["Total Cases"] = summary.sum(axis=1)
        for col in ["Pending", "Closed", "Awaited"]:
            if col not in summary.columns:
                summary[col] = 0
        summary = summary[["Pending", "Closed", "Awaited", "Total Cases"]].reset_index()

        st.subheader("📊 Jurisdiction Summary (Pending, Closed, Awaited, Total)")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        # ---------- Grand totals ----------
        grand_totals = summary[["Pending", "Closed", "Awaited", "Total Cases"]].sum().to_dict()
        st.markdown(
            f"**Grand Totals → Pending: {grand_totals['Pending']}, "
            f"Closed: {grand_totals['Closed']}, "
            f"Awaited: {grand_totals['Awaited']}, "
            f"Total: {grand_totals['Total Cases']}**"
        )

        # ---------- Weekday pivot table ----------
        if not df_pending_days.empty:
            weekday_map = {
                "0": "Sunday", "1": "Monday", "2": "Tuesday",
                "3": "Wednesday", "4": "Thursday", "5": "Friday", "6": "Saturday"
            }
            df_pending_days["Weekday"] = df_pending_days["weekday_num"].map(weekday_map)

            # ✅ Build pivot: rows = Weekday, columns = Court Location
            df_pivot_days = df_pending_days.pivot_table(
                index="Weekday",
                columns="court_location",
                values="pending_count",
                aggfunc="sum",
                fill_value=0
            )

            # ✅ Ensure weekdays are ordered properly
            ordered_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            df_pivot_days = df_pivot_days.reindex(ordered_days).fillna(0)

            # ✅ Add grand totals row + column
            df_pivot_days["Grand Total"] = df_pivot_days.sum(axis=1)
            grand_totals = df_pivot_days.sum(axis=0).to_frame(name="Grand Total").T

            # ✅ Display main table
            st.subheader("📅 Pending Cases by Day of Week and Court Location")
            st.dataframe(df_pivot_days.reset_index(), use_container_width=True, hide_index=True)

            # ✅ Display grand totals row below
            st.markdown("### 🏛️ Grand Totals by Court Location")
            st.dataframe(grand_totals, use_container_width=True, hide_index=True)
        else:
            st.info("📭 No pending cases with next dates found.")

    else:
        st.info("📭 No data to summarize.")

with tab14:
    st.subheader("🗑️ Database Cleanup (Drop Unwanted Tables)")

    # Show all tables in the DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    st.write("📋 Current tables in database:")
    st.dataframe(pd.DataFrame(tables, columns=["Table Name"]), use_container_width=True, hide_index=True)

    # Protect the valid tables
    protected = {"cases", "finance_log", "proceedings_log"}
    unwanted = [t for t in tables if t not in protected]

    if unwanted:
        st.warning("⚠️ The following tables look unwanted:")
        selected_table = st.selectbox("Select table to drop", [""] + unwanted, key="cleanup_select")

        if selected_table:
            if st.button("🗑️ Drop Selected Table", key="cleanup_drop"):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(f"DROP TABLE IF EXISTS {selected_table}")
                conn.commit()
                conn.close()
                st.success(f"✅ Table '{selected_table}' dropped successfully.")
    else:
        st.info("🎉 No unwanted tables found. Only valid tables are present.")

with tab6:
    st.subheader("✏️ Jurisdiction‑Wise Cases")

    # ✅ Load all cases with jurisdiction
    conn = get_connection()
    df_all = pd.read_sql("""
        SELECT s_no, f_no, case_no, particulars, court, court_location,
               jurisdiction, status, next_date, last_date, remarks, todo_flag, todo_details
        FROM cases
        WHERE jurisdiction IS NOT NULL
        ORDER BY s_no ASC
    """, conn)
    conn.close()

    if not df_all.empty:
        # Normalize jurisdiction
        df_all["jurisdiction"] = df_all["jurisdiction"].str.upper().str.strip()

        # ✅ Dropdown for jurisdiction
        jurisdictions = sorted(df_all["jurisdiction"].dropna().unique())
        selected_jurisdiction = st.selectbox("Select Jurisdiction", jurisdictions)

        # ✅ Filter records
        sub_df = df_all[df_all["jurisdiction"] == selected_jurisdiction].copy()

        # ✅ Add checkpoint: All vs Pending
        view_mode = st.radio(
            "Choose view mode:",
            ["All Cases", "Pending Only","Closed Only"],
            index=0,
            horizontal=True
        )
        if view_mode == "Closed Only":
            sub_df = sub_df[sub_df["status"].str.upper() == "CLOSED"]
        
        if view_mode == "Pending Only":
            sub_df = sub_df[sub_df["status"].str.upper() == "PENDING"]

        # Format dates
        sub_df["last_date_str"] = pd.to_datetime(sub_df["last_date"], errors="coerce").dt.strftime("%d-%m-%Y")
        sub_df["next_date_str"] = pd.to_datetime(sub_df["next_date"], errors="coerce").dt.strftime("%d-%m-%Y")

        # ✅ Display table
        st.markdown(f"### 📋 Records for {selected_jurisdiction.title()} — {view_mode}")
        st.dataframe(sub_df[[
            "f_no","case_no","particulars","court","court_location",
            "status","last_date_str","next_date_str","remarks"
        ]].reset_index(drop=True), use_container_width=True, hide_index=True)

        st.markdown(f"**Total cases in {selected_jurisdiction.title()} ({view_mode}): {len(sub_df)}**")

        # ✅ Build dropdown for search/update
        sub_df["label"] = (
            sub_df["jurisdiction"].fillna("") + " | " +
            sub_df["f_no"].fillna("") + " | " +
            sub_df["particulars"].fillna("") + " | " +
            sub_df["case_no"].fillna("") + " | " +
            sub_df["next_date_str"].fillna("")
        )
        case_map = dict(zip(sub_df["label"], sub_df["s_no"]))
        selected_label = st.selectbox("Select a case", sub_df["label"])
        selected_s_no = case_map.get(selected_label)

        if selected_s_no:
            df_meta = load_case_metadata(selected_s_no)
            if not df_meta.empty:
                row = df_meta.iloc[0].to_dict()
                st.session_state.selected_row = row

                st.subheader("📌 Case Record")

                # ✅ Ask if update is required
                update_required = st.radio(
                    "Do you want to update this case?",
                    ["No", "Yes"],
                    index=0,
                    horizontal=True,
                    key=f"juris_update_required_{row['s_no']}"
                )

                if update_required == "Yes":
                    # ✅ Editable fields only shown if update required
                    new_case_no = st.text_input("Case Number", row.get("case_no",""), key=f"juris_case_no_{row['s_no']}")
                    particulars = st.text_area("Particulars", row.get("particulars",""), key=f"juris_particulars_{row['s_no']}")
                    court = st.text_input("Court", row.get("court",""), key=f"juris_court_{row['s_no']}")

                    # ✅ Last Date
                    last_date = st.date_input("Last Date", parse_date_safe(row.get("last_date")), key=f"juris_last_date_{row['s_no']}")

                    # ✅ Next Date with Awaited option
                    next_date_mode = st.selectbox("Next Date", ["Date Awaited","Pick a Date"],
                                                  key=f"juris_next_date_mode_{row['s_no']}")
                    if next_date_mode == "Pick a Date":
                        next_date_val = parse_date_safe(row.get("next_date"))
                        next_date = st.date_input("📅 Select Next Date",
                                                  value=next_date_val if next_date_val else date.today(),
                                                  key=f"juris_next_date_picker_{row['s_no']}")
                        next_date_db = next_date.strftime("%Y-%m-%d")
                    else:
                        next_date_db = "Awaited"

                    # ✅ Proceeding + status
                    proceeding = st.text_area("Proceeding Note", row.get("proceeding",""), key=f"juris_proceeding_{row['s_no']}")
                    status_value = row.get("status") or "Pending"
                    status = st.selectbox("Status", ["Pending","Closed","Awaited"],
                                          index=["Pending","Closed","Awaited"].index(status_value),
                                          key=f"juris_status_{row['s_no']}")

                    proc_date = st.date_input("Proceeding Date", date.today(), key=f"juris_proc_date_{row['s_no']}")

                    # ✅ To‑Do fields
                    todo_flag = st.selectbox("Add to To‑Do List?", ["No","Yes"],
                                             index=0 if row.get("todo_flag")!="Yes" else 1,
                                             key=f"juris_todo_flag_{row['s_no']}")
                    todo_details = st.text_area("To‑Do Details", row.get("todo_details",""),
                                                key=f"juris_todo_details_{row['s_no']}")

                    # ✅ Update button
                    if st.button("Update Case", key=f"update_juris_button_{row['s_no']}"):
                        update_full_case(
                            s_no=row.get("s_no"),
                            case_no=new_case_no,
                            ref_fileno=row.get("ref_fileno", ""),
                            fir_no=row.get("fir_no", ""),
                            ps=row.get("ps", ""),
                            particulars=particulars,
                            court_location=row.get("court_location", ""),
                            court=court,
                            legal_offer_ws_filed=row.get("legal_offer_ws_filed", ""),
                            last_date=last_date.strftime("%Y-%m-%d"),
                            next_date=next_date_db,
                            proceeding=proceeding,
                            settle_contest=row.get("settle_contest", "Unknown"),
                            remarks=row.get("remarks", ""),
                            status=status,
                            f_no=row.get("f_no", ""),
                            todo_flag=todo_flag,
                            todo_details=todo_details
                        )
                        log_proceeding(new_case_no or row.get("case_no",""),
                                       row.get("f_no",""),
                                       row.get("particulars",""),
                                       proceeding,
                                       proc_date.strftime("%Y-%m-%d"))
                        st.success("✅ Case record updated and proceeding logged.")
            else:
                st.warning("⚠️ No metadata found for this case.")
    else:
        st.info("📭 No cases found with jurisdiction.")


# ✅ Expander: Inspect Raw Dates
with st.expander("🔍 Inspect Raw next_date Values"):
    conn = get_connection()
    df_check = pd.read_sql("SELECT case_no, next_date FROM cases ORDER BY next_date ASC", conn)
    conn.close()
    st.dataframe(df_check.reset_index(drop=True), use_container_width=True, hide_index=True)


# ✅ Expander: Sanitize next_date Format
with st.expander("🧼 Sanitize next_date Format"):
    conn = get_connection()
    df_fix = pd.read_sql("SELECT case_no, next_date FROM cases", conn)
    df_fix["next_date"] = pd.to_datetime(df_fix["next_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    cursor = conn.cursor()
    for _, row in df_fix.iterrows():
        if pd.notna(row["next_date"]):
            cursor.execute("UPDATE cases SET next_date = ? WHERE case_no = ?", (row["next_date"], row["case_no"]))
    conn.commit()
    conn.close()
    st.success("✅ All next_date values sanitized to YYYY-MM-DD.")

if st.button("🔧 Normalize Statuses"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE cases SET status = 'Pending' WHERE status = 'Open'")
    conn.commit()
    conn.close()
    st.success("✅ All 'Open' statuses changed to 'Pending'.")