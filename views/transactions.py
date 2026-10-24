from datetime import date, datetime

import pandas as pd
import streamlit as st

from spendwise.services.transactions import (
    MAX_DESCRIPTION,
    ValidationError,
    add_transaction,
    delete_transaction,
    get_categories,
    list_transactions,
    update_transaction,
)
from spendwise.ui import EXPENSE, INCOME, format_money, metric_card, page_header

SORT_OPTIONS = {"Date": "date", "Amount": "amount", "Category": "category", "Type": "type"}
ORDER_OPTIONS = ["Newest / highest first", "Oldest / lowest first"]


def transaction_form(existing=None):
    """The add/edit form. 'existing' is a transaction dict when editing."""
    key = f"tx_{existing['id']}" if existing else "tx_new"

    tx_type = st.radio(
        "Type",
        ["expense", "income"],
        index=1 if existing and existing["type"] == "income" else 0,
        format_func=str.capitalize,
        horizontal=True,
        key=f"{key}_type",
    )

    categories = {c["name"]: c["id"] for c in get_categories(tx_type)}
    names = list(categories)
    default_index = names.index(existing["category"]) if existing and existing["category"] in names else 0
    category_name = st.selectbox("Category", names, index=default_index, key=f"{key}_category")

    amount = st.number_input(
        "Amount",
        min_value=0.0,
        step=10.0,
        format="%.2f",
        value=float(existing["amount"]) if existing else 0.0,
        key=f"{key}_amount",
    )
    tx_date = st.date_input(
        "Date",
        value=datetime.strptime(existing["date"], "%Y-%m-%d").date() if existing else date.today(),
        key=f"{key}_date",
    )
    description = st.text_input(
        "Description",
        value=existing["description"] if existing else "",
        max_chars=MAX_DESCRIPTION,
        placeholder="e.g. Weekly groceries",
        key=f"{key}_description",
    )

    if st.button("Save", type="primary", key=f"{key}_save", width="stretch"):
        try:
            if existing:
                update_transaction(existing["id"], tx_date, tx_type, amount, categories[category_name], description)
                st.session_state["flash"] = "Transaction updated."
            else:
                add_transaction(tx_date, tx_type, amount, categories[category_name], description)
                st.session_state["flash"] = "Transaction added."
            st.rerun()
        except ValidationError as error:
            st.error(str(error))


def _clear_tx_form():
    """Forget add/edit form values when a dialog is dismissed.

    Dialogs are fragments, so their widgets keep their session state after the X is
    clicked. Without this, the next dialog opens showing the previous values, which is
    an easy way to save a transaction with the wrong type, category or amount.
    """
    suffixes = ("_type", "_category", "_amount", "_date", "_description")
    for name in list(st.session_state):
        if name.startswith("tx_") and name.endswith(suffixes):
            del st.session_state[name]


@st.dialog("Add transaction", on_dismiss=_clear_tx_form)
def add_dialog():
    transaction_form()


@st.dialog("Edit transaction", on_dismiss=_clear_tx_form)
def edit_dialog(transaction):
    transaction_form(transaction)


@st.dialog("Delete transaction", on_dismiss="rerun")
def delete_dialog(transaction):
    label = transaction["description"] or transaction["category"]
    st.write(
        f"Delete **{label}** ({transaction['date']}, {format_money(transaction['amount'])})? "
        "This cannot be undone."
    )
    left, right = st.columns(2)
    if left.button("Yes, delete", type="primary", width="stretch"):
        try:
            delete_transaction(transaction["id"])
            st.session_state["flash"] = "Transaction deleted."
        except ValidationError as error:
            st.session_state["flash"] = str(error)
        st.rerun()
    if right.button("Cancel", width="stretch"):
        st.rerun()


def reset_filters():
    """Runs when 'Clear filters' is clicked."""
    st.session_state["f_search"] = ""
    st.session_state["f_type"] = "All"
    for label in ("All", "Income", "Expense"):
        st.session_state[f"f_category_{label}"] = "All categories"
    st.session_state["f_from"] = None
    st.session_state["f_to"] = None
    st.session_state["f_sort"] = "Date"
    st.session_state["f_order"] = ORDER_OPTIONS[0]


def color_amount(value):
    return f"color: {INCOME}; font-weight: 600" if value >= 0 else f"color: {EXPENSE}; font-weight: 600"


def show_amount(value):
    return ("+" if value > 0 else "") + format_money(value)


# ---------- Page ----------

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

head_left, head_right = st.columns([4, 1], vertical_alignment="bottom")
with head_left:
    page_header("Transactions", "Every income and expense in one place.")
if head_right.button("➕ Add transaction", type="primary", width="stretch"):
    add_dialog()

# ---------- Filters ----------
all_categories = get_categories()
with st.container(key="card_filters"):
    c1, c2, c3 = st.columns([2, 1, 1])
    search = c1.text_input("Search", key="f_search", placeholder="Search description or category")
    type_label = c2.selectbox("Type", ["All", "Income", "Expense"], key="f_type")
    tx_type = None if type_label == "All" else type_label.lower()

    category_labels = {"All categories": None}
    for c in all_categories:
        if tx_type is None or c["type"] == tx_type:
            label = c["name"] if tx_type else f"{c['name']} ({c['type']})"
            category_labels[label] = c["id"]
    category_label = c3.selectbox("Category", list(category_labels), key=f"f_category_{type_label}")

    c4, c5, c6, c7 = st.columns(4)
    start_date = c4.date_input("From", value=None, key="f_from")
    end_date = c5.date_input("To", value=None, key="f_to")
    sort_label = c6.selectbox("Sort by", list(SORT_OPTIONS), key="f_sort")
    order = c7.selectbox("Order", ORDER_OPTIONS, key="f_order")

    st.button("Clear filters", on_click=reset_filters)

if start_date and end_date and start_date > end_date:
    st.error("The 'From' date must be on or before the 'To' date.")
    st.stop()

category_id = category_labels[category_label]
rows = list_transactions(
    search=search or None,
    tx_type=tx_type,
    category_id=category_id,
    start_date=start_date,
    end_date=end_date,
    sort_by=SORT_OPTIONS[sort_label],
    descending=order.startswith("Newest"),
)

filters_active = bool(search or tx_type or category_id or start_date or end_date)

if not rows:
    st.write("")
    if filters_active:
        st.info("No transactions match your filters. Try changing or clearing them.")
    else:
        st.info("No transactions yet. Click **Add transaction** to create your first one.")
    st.stop()

# ---------- Summary cards (follow the filters) ----------
total_income = sum(r["amount"] for r in rows if r["type"] == "income")
total_expense = sum(r["amount"] for r in rows if r["type"] == "expense")
net = total_income - total_expense
scope = "matching your filters" if filters_active else "all time"

st.write("")
m1, m2, m3 = st.columns(3)
with m1:
    metric_card("Income", format_money(total_income), f"{len(rows)} transaction(s), {scope}")
with m2:
    metric_card("Expenses", format_money(total_expense), scope)
with m3:
    metric_card("Net", format_money(net), "Income minus expenses", "good" if net >= 0 else "bad")

# ---------- Table ----------
st.write("")
table = pd.DataFrame(rows)
table["amount"] = [a if t == "income" else -a for t, a in zip(table["type"], table["amount"])]
table["type"] = table["type"].str.capitalize()
table = table[["date", "type", "category", "description", "amount"]]
table.columns = ["Date", "Type", "Category", "Description", "Amount"]

styled = table.style.format({"Amount": show_amount}).map(color_amount, subset=["Amount"])

with st.container(key="card_table"):
    event = st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
    )

    selected = event.selection.rows
    if selected and selected[0] < len(rows):
        chosen = rows[selected[0]]
        b1, b2, _ = st.columns([1, 1, 4])
        if b1.button("✏️ Edit selected", width="stretch"):
            edit_dialog(chosen)
        if b2.button("🗑️ Delete selected", width="stretch"):
            delete_dialog(chosen)
    else:
        st.caption("Tick the checkbox at the left of a row to edit or delete it.")