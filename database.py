
import sqlite3
import pandas as pd
import streamlit as st
from contextlib import contextmanager
from datetime import date, timedelta
import re
import io

DB_PATH = "case_diary.db"

@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def initialize_tables():
    """Initializes all required tables in the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Create 'cases' table
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
        # Create 'update_log' table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS update_log (
                case_no TEXT, field TEXT, old_value TEXT, new_value TEXT,
                updated_on TEXT, updated_by TEXT, particulars TEXT
            )
        """)
        # Add new columns to 'cases' table if they don't exist
        for alter_sql in [
            "ALTER TABLE cases ADD COLUMN closed_date TEXT",
            "ALTER TABLE cases ADD COLUMN bills_raised TEXT DEFAULT 'No'",
            "ALTER TABLE cases ADD COLUMN fee_status TEXT DEFAULT 'Awaited'"
        ]:
            try:
                cursor.execute(alter_sql)
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()

def create_finance_table():
    """Creates the 'finance_log' table if it doesn't exist."""
    with get_connection() as conn:
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

def create_clients_table():
    """Creates the 'clients' table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT
            )
        """)
        conn.commit()

def patch_finance_table():
    """Adds the 'particulars' column to the 'finance_log' table if it doesn't exist."""
    with get_connection() as conn:
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

def create_proceedings_table():
    """Creates the 'proceedings_log' table if it doesn't exist."""
    with get_connection() as conn:
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

def insert_case_row(row: dict):
    """Inserts a new case row into the 'cases' table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cases (
                f_no, jurisdiction, court_location, month_year, fy,
                case_through, ref_fileno, case_type, fir_no, ps, case_no,
                particulars, court, legal_offer_ws_filed, last_date, next_date,
                proceeding, settle_contest, remarks, result, status,
                fee_raised_full_partial_no, fee_status, fee_receipt_month, fee_part_1,
                fee_part_2, total_fee, expense, bill_no, file_scaned_y_n,
                date_of_filing, cnr_no, opponent_advocate, opponent_advocate_contact_number,
                client_id
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, tuple(row.values()))
        conn.commit()

def update_case(old_case_no, new_case_no, next_date, status, remarks, proceeding, title, f_no=None):
    """Updates an existing case and logs the changes."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Fetch old case data
        if old_case_no:
            old = pd.read_sql("SELECT * FROM cases WHERE case_no = ?", conn, params=(old_case_no,))
        elif f_no:
            old = pd.read_sql("SELECT * FROM cases WHERE f_no = ?", conn, params=(f_no,))
        else:
            st.error("❌ Cannot update: No case_no or f_no provided.")
            return

        if old.empty:
            st.warning("⚠️ No matching record found to update.")
            return

        stored = old.iloc[0]
        where_clause = "case_no = ?" if old_case_no else "f_no = ?"
        where_val = old_case_no if old_case_no else f_no

        # Perform update
        cursor.execute(f"""
            UPDATE cases SET
                case_no = ?, next_date = ?, status = ?, remarks = ?, proceeding = ?
            WHERE {where_clause}
        """, (new_case_no, next_date, status, remarks, proceeding, where_val))
        conn.commit()

        # Log changes
        fields = ["case_no", "next_date", "status", "remarks", "proceeding"]
        new_vals = [new_case_no, next_date, status, remarks, proceeding]
        for field, new_val in zip(fields, new_vals):
            old_val = stored[field]
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

def update_case_in_db(old_case_no, new_case_no, f_no, particulars, status):
    """Updates case information in the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cases SET
                case_no = ?, f_no = ?, particulars = ?, status = ?
            WHERE f_no = ?
        """, (new_case_no, f_no, particulars, status, f_no))
        # Log update
        cursor.execute("""
            INSERT INTO update_log (
                case_no, field, old_value, new_value, updated_on, updated_by, particulars
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            new_case_no, "status", "N/A", status,
            str(date.today()), "SANDEEP JHA", particulars
        ))
        conn.commit()

def log_proceeding(case_no, f_no, particulars, proc_date, note):
    """Logs a proceeding note for a case."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO proceedings_log (case_no, f_no, particulars, date, note, updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (case_no, f_no, particulars, proc_date, note, "Sandeep Jha"))
        conn.commit()

def load_case_metadata(case_no):
    """Loads metadata for a specific case."""
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM cases WHERE s_no = ?", conn, params=(case_no,))
    if not df.empty:
        for col in ["next_date", "last_date", "date_of_filing"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d-%m-%Y")
    return df

def export_all_tables_to_excel():
    """Exports all tables from the database to an Excel file."""
    output = io.BytesIO()
    with get_connection() as conn, pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            try:
                df = pd.read_sql(f"SELECT * FROM '{table}'", conn)
                df.to_excel(writer, index=False, sheet_name=table[:31])
            except Exception as e:
                print(f"Skipping table {table}: {e}")
    return output.getvalue()

def update_full_case(**kwargs):
    """Updates a case with the given keyword arguments."""
    with get_connection() as conn:
        cursor = conn.cursor()
        s_no = kwargs.pop("s_no")
        fields = [f"{key} = ?" for key in kwargs.keys()]
        values = list(kwargs.values())
        if "status" in kwargs and kwargs["status"].strip().upper() == "CLOSED":
            fields.append("closed_date = ?")
            values.append(date.today().strftime("%Y-%m-%d"))
        if not fields:
            return
        values.append(s_no)
        sql = f"UPDATE cases SET {', '.join(fields)} WHERE s_no = ?"
        cursor.execute(sql, values)
        conn.commit()

def delete_case(s_no: int):
    """Deletes a case from the database by its s_no."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cases WHERE s_no = ?", (s_no,))
        conn.commit()

def overwrite_cases_table(df: pd.DataFrame):
    """Overwrites the 'cases' table with a new DataFrame."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cases")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'cases'")
            if "s_no" in df.columns:
                df = df.drop(columns=["s_no"])
            df.to_sql("cases", conn, if_exists="append", index=False)
            conn.commit()
            st.success(f"✅ {len(df)} rows inserted into 'cases' table with s_no starting from 1.")
            st.dataframe(df.head(10), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"❌ Error during overwrite: {e}")
