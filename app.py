import os
import streamlit as st

from spendwise.database import init_db
from spendwise.ui import apply_theme

st.set_page_config(page_title="SpendWise Analytics", page_icon="💰", layout="wide")

# Creates the database and tables on first run. Safe to run every time.
init_db()
apply_theme()

pages = [
    st.Page("views/dashboard.py", title="Dashboard", icon="📊", default=True),
    st.Page("views/analytics.py", title="Analytics", icon="📈"),
    st.Page("views/transactions.py", title="Transactions", icon="🧾"),
    st.Page("views/budgets.py", title="Budgets", icon="🎯"),
    st.Page("views/import_export.py", title="Import / Export", icon="📁"),
]

if os.environ.get("DEMO_MODE") == "1":
    st.warning(
        "Public demo with sample data. Everyone who visits sees the same data, and it can be reset at "
        "any time. Please don't enter personal financial information.",
        icon="⚠️",
    )

navigation = st.navigation(pages)
navigation.run()