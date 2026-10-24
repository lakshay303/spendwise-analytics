import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from spendwise.services.csv_io import (
    export_csv,
    export_xlsx,
    import_rows,
    parse_file,
    template_xlsx,
)
from spendwise.services.transactions import ValidationError, get_categories, list_transactions
from spendwise.ui import CURRENCY, format_money, metric_card, page_header

TEMPLATE = (
    "date,type,category,amount,description\n"
    "2026-10-01,income,Salary,50000,October salary\n"
    "2026-10-02,expense,Food & Dining,250.00,Lunch\n"
)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PREVIEW_LIMIT = 200
ERROR_LIMIT = 100


def render_import():
    with st.container(key="card_import_help"):
        st.markdown("**File format**")
        st.markdown(
            "Your CSV or Excel file needs the columns `date`, `type`, `category` and `amount`. "
            "`description` is optional. Dates can be `2026-10-23` or `23/10/2026`. "
            "Category names must match exactly one of the names below (capital letters don't matter)."
        )
        st.caption("For Excel files the first sheet is read, with the column names in the first row.")
        income = ", ".join(c["name"] for c in get_categories("income"))
        expense = ", ".join(c["name"] for c in get_categories("expense"))
        st.caption(f"Income categories: {income}")
        st.caption(f"Expense categories: {expense}")
        templates = st.columns(2)
        templates[0].download_button("Download a CSV template", TEMPLATE, "spendwise_template.csv", "text/csv")
        templates[1].download_button(
            "Download an Excel template", template_xlsx(), "spendwise_template.xlsx", XLSX_MIME
        )

    st.write("")
    uploaded = st.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx"],
        key=f"csv_upload_{st.session_state.get('upload_round', 0)}",
    )
    if uploaded is None:
        return

    try:
        result = parse_file(uploaded.getvalue(), uploaded.name)
    except ValidationError as error:
        st.error(str(error))
        return

    new, duplicates, errors = result["new"], result["duplicates"], result["errors"]

    cols = st.columns(4)
    with cols[0]:
        metric_card("Rows read", str(result["total_rows"]))
    with cols[1]:
        metric_card("Ready to import", str(len(new)), "", "good" if new else "neutral")
    with cols[2]:
        metric_card("Already saved", str(len(duplicates)), "Will be skipped" if duplicates else "")
    with cols[3]:
        if errors:
            metric_card("Problems", str(len(errors)), "Will not be imported", "bad")
        else:
            metric_card("Problems", "0", "All rows are valid", "good")

    if errors:
        st.write("")
        st.subheader("Rows with problems")
        st.caption("Row numbers match the line numbers in your file (the header is line 1).")
        problems = pd.DataFrame(errors).rename(columns={"row": "Row in file", "message": "Problem"})
        st.dataframe(problems.head(ERROR_LIMIT), hide_index=True, width="stretch")
        if len(errors) > ERROR_LIMIT:
            st.caption(f"Showing the first {ERROR_LIMIT} of {len(errors)} problems.")

    if not new:
        st.write("")
        st.info("There are no new transactions to import from this file.")
        return

    st.write("")
    st.subheader("Ready to import")
    preview = pd.DataFrame(new)[["row", "date", "type", "category", "description", "amount"]]
    preview["type"] = preview["type"].str.capitalize()
    st.dataframe(
        preview.head(PREVIEW_LIMIT),
        hide_index=True,
        width="stretch",
        column_config={
            "row": "Row in file",
            "date": "Date",
            "type": "Type",
            "category": "Category",
            "description": "Description",
            "amount": st.column_config.NumberColumn("Amount", format=f"{CURRENCY}%.2f"),
        },
    )
    if len(new) > PREVIEW_LIMIT:
        st.caption(f"Showing the first {PREVIEW_LIMIT} of {len(new)} rows. All {len(new)} will be imported.")

    if errors:
        st.caption(f"{len(errors)} row(s) with problems will be skipped.")

    if st.button(f"Import {len(new)} transaction(s)", type="primary"):
        try:
            saved = import_rows(new)
        except sqlite3.Error as error:
            st.error(f"The import failed and nothing was saved. Details: {error}")
            return
        skipped = len(errors) + len(duplicates)
        message = f"Imported {saved} transaction(s)."
        if skipped:
            message += f" {skipped} row(s) skipped."
        st.session_state["flash"] = message
        st.session_state["upload_round"] = st.session_state.get("upload_round", 0) + 1
        st.rerun()


def render_export():
    scope = st.radio("What to export", ["All transactions", "A date range"], horizontal=True)

    start = end = None
    if scope == "A date range":
        left, right = st.columns(2)
        start = left.date_input("From", value=None, key="export_from")
        end = right.date_input("To", value=None, key="export_to")
        if start and end and start > end:
            st.error("The 'From' date must be on or before the 'To' date.")
            return

    rows = list_transactions(start_date=start, end_date=end, sort_by="date", descending=False)
    if not rows:
        st.info("There are no transactions to export for this selection.")
        return

    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")
    st.caption(
        f"{len(rows)} transaction(s)  ·  Income {format_money(income)}  ·  Expenses {format_money(expenses)}"
    )
    downloads = st.columns(2)
    downloads[0].download_button(
        "⬇️ Download CSV",
        data=export_csv(rows).encode("utf-8-sig"),
        file_name=f"spendwise_transactions_{date.today():%Y-%m-%d}.csv",
        mime="text/csv",
        type="primary",
    )
    downloads[1].download_button(
        "⬇️ Download Excel",
        data=export_xlsx(rows),
        file_name=f"spendwise_transactions_{date.today():%Y-%m-%d}.xlsx",
        mime=XLSX_MIME,
    )
    st.caption("Exported CSV and Excel files can be imported again later. Rows already in SpendWise are skipped automatically.")


# ---------- Page ----------

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

page_header("Import / Export", "Move your data in and out with CSV and Excel files.")

import_tab, export_tab = st.tabs(["⬆️ Import", "⬇️ Export"])
with import_tab:
    render_import()
with export_tab:
    render_export()