from datetime import date, datetime

import streamlit as st

from spendwise.services.budgets import (
    ValidationError,
    copy_budgets,
    delete_budget,
    get_budget_status,
    previous_month,
    set_budget,
)
from spendwise.services.transactions import get_categories
from spendwise.ui import format_money, insight_card, metric_card, page_header, progress_bar, status_pill


def month_options():
    """Last 11 months, this month, and next 2 months, as 'YYYY-MM'. This month is index 11."""
    today = date.today()
    options = []
    for offset in range(-11, 3):
        total = today.year * 12 + (today.month - 1) + offset
        options.append(f"{total // 12:04d}-{total % 12 + 1:02d}")
    return options


def month_label(month):
    return datetime.strptime(month, "%Y-%m").strftime("%B %Y")


def _clear_budget_form():
    """Forget the dialog values when it is dismissed (fragment widgets keep state)."""
    for name in list(st.session_state):
        if name.startswith("budgetform_"):
            del st.session_state[name]


@st.dialog("Set budget", on_dismiss=_clear_budget_form)
def budget_dialog(month, existing=None):
    categories = {c["name"]: c["id"] for c in get_categories("expense")}
    names = list(categories)
    index = names.index(existing["category"]) if existing and existing["category"] in names else 0
    form_key = f"budgetform_{existing['id']}" if existing else "budgetform_new"

    category_name = st.selectbox(
        "Category", names, index=index, disabled=existing is not None,
        key=f"{form_key}_category",
    )
    amount = st.number_input(
        "Monthly budget",
        min_value=0.0,
        step=100.0,
        format="%.2f",
        value=float(existing["budget"]) if existing else 0.0,
        key=f"{form_key}_amount",
    )
    if not existing:
        st.caption("Setting a budget for a category that already has one replaces it.")
    if st.button("Save budget", type="primary"):
        try:
            set_budget(categories[category_name], month, amount)
            st.session_state["flash"] = f"Budget saved for {category_name}."
            st.rerun()
        except ValidationError as error:
            st.error(str(error))


@st.dialog("Delete budget", on_dismiss="rerun")
def delete_dialog(budget):
    st.write(
        f"Delete the **{budget['category']}** budget ({format_money(budget['budget'])})? "
        "Your transactions are not affected."
    )
    left, right = st.columns(2)
    if left.button("Yes, delete", type="primary", width="stretch"):
        try:
            delete_budget(budget["id"])
            st.session_state["flash"] = f"Budget deleted for {budget['category']}."
        except ValidationError as error:
            st.session_state["flash"] = str(error)
        st.rerun()
    if right.button("Cancel", width="stretch"):
        st.rerun()


# ---------- Page ----------

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

page_header("Budgets", "Set monthly limits and see how you're doing.")

top = st.columns([2, 1, 1], vertical_alignment="bottom")
month = top[0].selectbox("Month", month_options(), index=11, format_func=month_label)

if top[1].button("➕ Set budget", type="primary", width="stretch"):
    budget_dialog(month)

if top[2].button("📋 Copy last month", width="stretch"):
    try:
        added = copy_budgets(previous_month(month), month)
        if added:
            st.session_state["flash"] = f"Copied {added} budget(s) from last month."
        else:
            st.session_state["flash"] = "Last month's budgets are already set here."
        st.rerun()
    except ValidationError as error:
        st.error(str(error))

budgets = get_budget_status(month)

if not budgets:
    st.write("")
    st.info(
        f"No budgets set for {month_label(month)}. "
        "Click **Set budget** to create one, or **Copy last month** to reuse last month's budgets."
    )
    st.stop()

# ---------- Summary cards ----------
total_budget = sum(b["budget"] for b in budgets)
total_spent = sum(b["spent"] for b in budgets)
total_remaining = total_budget - total_spent
used_pct = total_spent / total_budget * 100

st.write("")
m1, m2, m3 = st.columns(3)
with m1:
    category_word = "category" if len(budgets) == 1 else "categories"
    metric_card("Total budgeted", format_money(total_budget), f"{len(budgets)} {category_word}")
with m2:
    metric_card("Spent so far", format_money(total_spent), f"{used_pct:.0f}% of budget used")
with m3:
    if total_remaining >= 0:
        metric_card("Remaining", format_money(total_remaining), "Still available", "good")
    else:
        metric_card("Remaining", format_money(total_remaining), f"Over by {format_money(-total_remaining)}", "bad")

# ---------- Alerts ----------
alerts = [b for b in budgets if b["status"] in ("over", "warning")]
if alerts:
    st.write("")
    for b in sorted(alerts, key=lambda item: item["pct_used"], reverse=True):
        if b["status"] == "over":
            insight_card(
                f"{b['category']} is over budget",
                f"Spent {format_money(b['spent'])} of {format_money(b['budget'])}, "
                f"over by {format_money(-b['remaining'])}.",
                "bad",
            )
        else:
            insight_card(
                f"{b['category']} is near its limit",
                f"{b['pct_used']:.0f}% used, {format_money(b['remaining'])} left.",
                "warn",
            )

# ---------- Budget cards (closest to the limit first) ----------
st.write("")
columns = st.columns(3)
for i, b in enumerate(sorted(budgets, key=lambda item: item["pct_used"], reverse=True)):
    with columns[i % 3].container(key=f"card_budget_{b['id']}"):
        name_col, pill_col = st.columns([3, 2], vertical_alignment="center")
        name_col.markdown(f"**{b['category']}**")
        pill_col.markdown(
            f"<div style='text-align:right'>{status_pill(b['status'])}</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"<div class='sw-value' style='font-size:1.45rem'>{format_money(b['spent'])}</div>"
            f"<div class='sw-label'>spent of {format_money(b['budget'])}</div>",
            unsafe_allow_html=True,
        )
        progress_bar(b["pct_used"], b["status"])

        if b["remaining"] >= 0:
            st.caption(f"{b['pct_used']:.0f}% used  ·  {format_money(b['remaining'])} left")
        else:
            st.caption(f"{b['pct_used']:.0f}% used  ·  {format_money(-b['remaining'])} over")

        edit_col, delete_col = st.columns(2)
        if edit_col.button("✏️ Edit", key=f"edit_{b['id']}", width="stretch"):
            budget_dialog(month, existing=b)
        if delete_col.button("🗑️ Delete", key=f"delete_{b['id']}", width="stretch"):
            delete_dialog(b)