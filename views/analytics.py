from datetime import datetime

import pandas as pd
import streamlit as st

from spendwise import charts
from spendwise.services.analytics import (
    available_months,
    category_by_month,
    category_comparison,
    monthly_series,
    monthly_totals,
    months_ending,
    range_stats,
    top_categories,
)
from spendwise.services.budgets import previous_month
from spendwise.ui import EXPENSE, INCOME, format_money, metric_card, page_header

PERIODS = {"Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12}


def month_label(month):
    return datetime.strptime(month, "%Y-%m").strftime("%B %Y")


def show_change(value):
    return ("+" if value > 0 else "") + format_money(value)


def show_pct(value):
    return f"{value:+.1f}%"


def color_change(value):
    """More spending is red, less spending is green."""
    if pd.isna(value) or value == 0:
        return ""
    return f"color: {EXPENSE if value > 0 else INCOME}; font-weight: 600"


# ---------- Empty state ----------
if not monthly_totals():
    page_header("Analytics", "Spot trends in how you earn, spend and save.")
    st.info("Analytics needs some data first. Add a few transactions and come back.")
    st.page_link("views/transactions.py", label="Add a transaction", icon="➕")
    st.stop()

# ---------- Header and controls ----------
top = st.columns([3, 1, 1], vertical_alignment="bottom")
with top[0]:
    page_header("Analytics", "Spot trends in how you earn, spend and save.")
period = top[1].selectbox("Period", list(PERIODS), index=1)
month_options = available_months()
this_month = datetime.today().strftime("%Y-%m")
# Default to the newest month that isn't in the future (future-dated budgets can be listed).
end_index = next((i for i, m in enumerate(month_options) if m <= this_month), 0)
end_month = top[2].selectbox("Ending in", month_options, index=end_index, format_func=month_label)

months = months_ending(end_month, PERIODS[period])
series = monthly_series(months)
stats = range_stats(series)

st.caption(f"{month_label(months[0])} to {month_label(months[-1])}")

if stats is None:
    st.info("There is no income or spending in this period. Try a different period or ending month.")
    st.stop()

category_rows = category_by_month(months)
top_rows = top_categories(months)

# ---------- Summary cards ----------
cards = st.columns(4)
with cards[0]:
    metric_card(
        "Average monthly spending",
        format_money(stats["avg_expenses"]),
        f"Across {stats['active_months']} month{'s' if stats['active_months'] != 1 else ''} with data",
    )
with cards[1]:
    rate = stats["avg_savings_rate"]
    if rate is None:
        metric_card("Average savings rate", "—", "No income in this period")
    else:
        tone = "good" if rate >= 20 else ("warn" if rate >= 0 else "bad")
        metric_card("Average savings rate", f"{rate:.1f}%", "Of income, in months with income", tone)
with cards[2]:
    if stats["highest_spending_amount"] > 0:
        metric_card(
            "Highest spending month",
            month_label(stats["highest_spending_month"]),
            format_money(stats["highest_spending_amount"]),
        )
    else:
        metric_card("Highest spending month", "—", "No expenses in this period")
with cards[3]:
    if top_rows:
        metric_card("Top category", top_rows[0]["category"], f"{top_rows[0]['share']:.0f}% of spending")
    else:
        metric_card("Top category", "—", "No expenses in this period")

st.write("")

# ---------- Charts ----------
left, right = st.columns([3, 2])
with left:
    with st.container(key="card_savings_trend"):
        st.subheader("Savings trend")
        st.plotly_chart(charts.savings_trend(series), width="stretch", config={"displayModeBar": False})
        st.caption("Bars show income minus expenses. The line shows the share of income you kept.")
with right:
    with st.container(key="card_top_categories"):
        st.subheader("Top spending categories")
        if top_rows:
            st.plotly_chart(
                charts.top_categories_bar(top_rows), width="stretch", config={"displayModeBar": False}
            )
        else:
            st.info("No expenses in this period.")

st.write("")

with st.container(key="card_category_months"):
    st.subheader("Spending by category over time")
    if category_rows:
        st.plotly_chart(
            charts.category_stacked(category_rows, months),
            width="stretch",
            config={"displayModeBar": False},
        )
    else:
        st.info("No expenses in this period.")

st.write("")

# ---------- Month comparison ----------
with st.container(key="card_comparison"):
    st.subheader(f"{month_label(end_month)} vs {month_label(previous_month(end_month))}")
    comparison = category_comparison(end_month)
    if not comparison:
        st.info("There are no expenses in either month.")
    else:
        table = pd.DataFrame(comparison).rename(
            columns={
                "category": "Category",
                "current": "This month",
                "previous": "Last month",
                "change": "Change",
                "pct": "Change %",
            }
        )
        styled = table.style.format(
            {
                "This month": format_money,
                "Last month": format_money,
                "Change": show_change,
                "Change %": show_pct,
            },
            na_rep="New",
        ).map(color_change, subset=["Change", "Change %"])
        st.dataframe(styled, hide_index=True, width="stretch")
        st.caption("More spending shows in red, less in green. 'New' means nothing was spent last month.")