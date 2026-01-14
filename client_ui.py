
import streamlit as st
import pandas as pd
from database import get_connection

def client_management_ui():
    """Renders the UI for client management."""
    st.subheader("💼 Client Management")

    with st.form(key="add_client_form", clear_on_submit=True):
        st.subheader("Add New Client")
        name = st.text_input("Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        address = st.text_area("Address")
        submitted = st.form_submit_button("Add Client")
        if submitted:
            add_client(name, email, phone, address)
            st.toast("Client added successfully.", icon="✅")

    st.subheader("Existing Clients")
    df_clients = get_clients()
    st.dataframe(df_clients, width='stretch')

def add_client(name, email, phone, address):
    """Adds a new client to the database."""
    with get_connection() as conn:
        conn.execute("INSERT INTO clients (name, email, phone, address) VALUES (?, ?, ?, ?)", (name, email, phone, address))
        conn.commit()

def get_clients():
    """Retrieves all clients from the database."""
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM clients", conn)
    return df
