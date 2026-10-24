import calendar
from datetime import date, datetime

import pandas as pd
import streamlit as st

from spendwise import charts
from spendwise.services.analytics import (
    available_months,
    category_spending,
    cumulative_spending,
    month_summary,
    monthly_totals,
)
from spendwise.services.budgets import previous_month
from spendwise.services.insights import get_insights
from spendwise.services.transactions import list_transactions
from spendwise.ui import format_money, insight_card, metric_card, page_header


def month_label(month):
    return datetime.strptime(month, "%Y-%m").strftime("%B %Y")


def short_label(month):
    return datetime.strptime(month, "%Y-%m").strftime("%b %Y")


def change_note(current, previous, higher_is_good):
    """('▲ 12.5% vs last month', 'good') or ('', 'neutral') when there is nothing to compare."""
    if previous <= 0:
        return "", "neutral"
    pct = (current - previous) / previous * 100
    arrow = "▲" if pct >= 0 else "▼"
    tone = "good" if (pct >= 0) == higher_is_good else "bad"
    return f"{arrow} {abs(pct):.1f}% vs last month", tone


# ---------- Empty state: no data at all ----------
if not list_transactions():
    page_header("Dashboard", "Your money at a glance.")
    st.info("Nothing to show yet. Add your first transaction and your dashboard will come to life.")
    st.page_link("views/transactions.py", label="Add your first transaction", icon="➕")
    st.stop()

# ---------- Header and month picker ----------
top_left, top_right = st.columns([3, 1], vertical_alignment="bottom")
with top_left:
    page_header("Dashboard", "Your money at a glance.")
# available_months() is newest first and may include future months that only have a
# budget. Default to the newest month that is not in the future, so the dashboard
# doesn't open on an empty month.
months = available_months()
this_month = date.today().strftime("%Y-%m")
default_index = min((i for i, m in enumerate(months) if m <= this_month), default=0)
month = top_right.selectbox("Month", months, index=default_index, format_func=month_label)
current = month_summary(month)
previous = month_summary(previous_month(month))

# ---------- KPI cards ----------
cards = st.columns(5)

with cards[0]:
    note, tone = change_note(current["income"], previous["income"], higher_is_good=True)
    metric_card("Income", format_money(current["income"]), note, tone)

with cards[1]:
    note, tone = change_note(current["expenses"], previous["expenses"], higher_is_good=False)
    metric_card("Expenses", format_money(current["expenses"]), note, tone)

with cards[2]:
    metric_card(
        "Balance (this month)",
        format_money(current["balance"]),
        f"All-time: {format_money(current['balance_all_time'])}",
        "good" if current["balance"] >= 0 else "bad",
    )

with cards[3]:
    rate = current["savings_rate"]
    if rate is None:
        metric_card("Savings rate", "—", "No income this month", "neutral")
    else:
        tone = "good" if rate >= 20 else ("warn" if rate >= 0 else "bad")
        metric_card("Savings rate", f"{rate:.1f}%", "Share of income kept", tone)

with cards[4]:
    if current["budget_total"] == 0:
        metric_card("Budget remaining", "—", "No budgets set", "neutral")
    elif current["budget_remaining"] >= 0:
        metric_card(
            "Budget remaining",
            format_money(current["budget_remaining"]),
            f"of {format_money(current['budget_total'])} budgeted",
            "good",
        )
    else:
        metric_card(
            "Budget remaining",
            format_money(current["budget_remaining"]),
            f"Over by {format_money(-current['budget_remaining'])}",
            "bad",
        )

st.write("")

# ---------- Charts row 1 ----------
left, right = st.columns(2)

with left:
    with st.container(key="card_category_chart"):
        st.subheader("Spending by category")
        category_rows = category_spending(month)
        if category_rows:
            st.plotly_chart(
                charts.category_donut(category_rows),
                width="stretch",
                config={"displayModeBar": False},
            )
        else:
            st.info(f"No expenses recorded in {month_label(month)}.")

with right:
    with st.container(key="card_monthly_chart"):
        st.subheader("Income vs expenses")
        st.plotly_chart(
            charts.income_expense_bars(monthly_totals()[-12:]),
            width="stretch",
            config={"displayModeBar": False},
        )

st.write("")

# ---------- Row 2: spending trend + insights ----------
trend_col, insight_col = st.columns([2, 1])

with trend_col:
    with st.container(key="card_trend"):
        st.subheader("Spending trend")
        is_current_month = month == date.today().strftime("%Y-%m")
        through_day = date.today().day if is_current_month else None
        this_month = cumulative_spending(month, through_day)
        last_month = cumulative_spending(previous_month(month))

        if this_month[-1]["total"] == 0 and last_month[-1]["total"] == 0:
            st.info("No spending in this month or the one before it.")
        else:
            st.plotly_chart(
                charts.spending_trend(
                    this_month,
                    last_month,
                    short_label(month),
                    short_label(previous_month(month)),
                ),
                width="stretch",
                config={"displayModeBar": False},
            )
            day = len(this_month)
            spent_now = this_month[-1]["total"]
            spent_before = last_month[min(day, len(last_month)) - 1]["total"]
            st.caption(
                f"By day {day} you've spent {format_money(spent_now)}, "
                f"compared with {format_money(spent_before)} at the same point last month."
            )

with insight_col:
    st.subheader("Insights")
    insights = get_insights(month)
    if not insights:
        st.info("Add income and expenses for this month to see insights.")
    for item in insights[:6]:
        insight_card(item["title"], item["detail"], item["severity"])

st.write("")

# ---------- Recent transactions ----------
with st.container(key="card_recent"):
    head_left, head_right = st.columns([3, 1], vertical_alignment="center")
    head_left.subheader(f"Recent transactions · {month_label(month)}")
    head_right.page_link("views/transactions.py", label="View all →")

    last_day = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
    recent = list_transactions(start_date=f"{month}-01", end_date=f"{month}-{last_day:02d}")[:8]
    if not recent:
        st.info(f"No transactions in {month_label(month)}.")
    else:
        table = pd.DataFrame(recent)
        table["amount"] = [
            ("+" if t == "income" else "-") + format_money(a)
            for t, a in zip(table["type"], table["amount"])
        ]
        table["type"] = table["type"].str.capitalize()
        st.dataframe(
            table[["date", "type", "category", "description", "amount"]],
            hide_index=True,
            width="stretch",
            column_config={
                "date": "Date",
                "type": "Type",
                "category": "Category",
                "description": "Description",
                "amount": "Amount",
            },
        )