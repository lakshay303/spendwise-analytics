import calendar
from datetime import date
from statistics import median

from spendwise.database import query
from spendwise.services.analytics import category_spending, month_summary
from spendwise.services.budgets import _check_month, get_budget_status, previous_month
from spendwise.ui import format_money

MIN_HISTORY = 5          # other expenses needed in a category before we judge one as unusual
ANOMALY_MULTIPLE = 3     # flagged if larger than 3x the typical (median) amount
CHANGE_THRESHOLD = 20    # minimum % change to report a category change
PACE_MARGIN = 20         # budget used must be this many points ahead of the calendar

SEVERITY_ORDER = {"bad": 0, "warn": 1, "good": 2, "info": 3}


def find_anomalies(month):
    """Expenses in the month that are far larger than usual for their category."""
    month = _check_month(month)
    rows = query(
        "SELECT t.id, t.date, t.amount, t.description, t.category_id, c.name AS category "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.type = 'expense'"
    )
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category_id"], []).append(row)

    anomalies = []
    for items in by_category.values():
        for row in items:
            if row["date"][:7] != month:
                continue
            others = [o["amount"] for o in items if o["id"] != row["id"]]
            if len(others) < MIN_HISTORY:
                continue
            typical = median(others)
            if typical > 0 and row["amount"] > ANOMALY_MULTIPLE * typical:
                anomalies.append(
                    {
                        "id": row["id"],
                        "date": row["date"],
                        "category": row["category"],
                        "description": row["description"],
                        "amount": row["amount"],
                        "typical": round(typical, 2),
                        "multiple": round(row["amount"] / typical, 1),
                    }
                )
    anomalies.sort(key=lambda a: a["multiple"], reverse=True)
    return anomalies


def get_insights(month, today=None):
    """Return a list of insights for the month, most important first.

    Each insight is a dict: kind, severity ('bad', 'warn', 'good', 'info'), title, detail.
    """
    month = _check_month(month)
    today = today or date.today()
    current = month_summary(month)
    previous = month_summary(previous_month(month))

    if current["income"] == 0 and current["expenses"] == 0:
        return []

    insights = []

    def add(kind, severity, title, detail):
        insights.append({"kind": kind, "severity": severity, "title": title, "detail": detail})

    # --- Savings ---
    rate = current["savings_rate"]
    if current["income"] == 0:
        add("savings", "warn", "No income recorded",
            f"You spent {format_money(current['expenses'])} but recorded no income this month.")
    elif rate < 0:
        add("savings", "bad", "You spent more than you earned",
            f"Expenses exceeded income by {format_money(-current['balance'])}.")
    elif rate >= 20:
        add("savings", "good", "Healthy savings rate",
            f"You saved {rate:.0f}% of your income ({format_money(current['balance'])}).")
    else:
        add("savings", "info", f"Savings rate is {rate:.0f}%",
            "A common target is to save 20% or more of your income.")

    # --- Spending vs last month ---
    if previous["expenses"] > 0:
        pct = (current["expenses"] - previous["expenses"]) / previous["expenses"] * 100
        detail = (f"{format_money(current['expenses'])} this month, "
                  f"{format_money(previous['expenses'])} last month.")
        if pct >= 10:
            add("spending_change", "bad", f"Spending is up {pct:.0f}% vs last month", detail)
        elif pct <= -10:
            add("spending_change", "good", f"Spending is down {abs(pct):.0f}% vs last month", detail)
        else:
            add("spending_change", "info", "Spending is steady vs last month", detail)

    # --- Biggest category change ---
    now = {r["category"]: r["total"] for r in category_spending(month)}
    before = {r["category"]: r["total"] for r in category_spending(previous_month(month))}
    best = None
    for name, old in before.items():
        new = now.get(name, 0)
        pct = (new - old) / old * 100
        if abs(pct) >= CHANGE_THRESHOLD and (best is None or abs(new - old) > best[3]):
            best = (name, old, new, abs(new - old), pct)
    if best:
        name, old, new, _, pct = best
        verb = "rose" if pct > 0 else "fell"
        add("category_change", "warn" if pct > 0 else "good",
            f"{name} spending {verb} {abs(pct):.0f}%",
            f"{format_money(new)} this month vs {format_money(old)} last month.")

    # --- Top category ---
    top = category_spending(month)
    if top:
        add("top_category", "info", f"{top[0]['category']} is your biggest expense",
            f"{format_money(top[0]['total'])}, which is {top[0]['share']:.0f}% of this month's spending.")

    # --- Budget health ---
    statuses = get_budget_status(month)
    flagged = False
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    elapsed = today.day / days_in_month * 100
    for b in statuses:
        if b["status"] == "over":
            flagged = True
            add("budget_over", "bad", f"{b['category']} is over budget",
                f"Spent {format_money(b['spent'])} of {format_money(b['budget'])}, "
                f"over by {format_money(-b['remaining'])}.")
        elif b["status"] == "warning":
            flagged = True
            add("budget_near", "warn", f"{b['category']} is near its limit",
                f"{b['pct_used']:.0f}% used, {format_money(b['remaining'])} left.")
        elif month == today.strftime("%Y-%m") and b["pct_used"] > elapsed + PACE_MARGIN:
            flagged = True
            add("budget_pace", "warn", f"{b['category']} is running ahead of schedule",
                f"{b['pct_used']:.0f}% of budget used, {elapsed:.0f}% of the month gone.")
    if statuses and not flagged:
        add("budget_ok", "good", "All budgets on track",
            f"{len(statuses)} budget(s) are within their limits.")

    # --- Unusual expenses ---
    for a in find_anomalies(month)[:3]:
        what = f" ({a['description']})" if a["description"] else ""
        add("anomaly", "warn", f"Unusually large {a['category']} expense",
            f"{format_money(a['amount'])} on {a['date']}{what}, about {a['multiple']:.1f}× "
            f"your typical {format_money(a['typical'])}.")

    insights.sort(key=lambda i: SEVERITY_ORDER[i["severity"]])
    return insights