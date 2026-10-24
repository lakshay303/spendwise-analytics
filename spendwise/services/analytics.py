from spendwise.database import query
from spendwise.services.budgets import _check_month, get_budget_status, previous_month


def month_summary(month):
    """Income, expenses, balance, savings rate and budget totals for one month ('YYYY-MM')."""
    month = _check_month(month)

    rows = query(
        "SELECT type, COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE substr(date, 1, 7) = ? GROUP BY type",
        (month,),
    )
    totals = {row["type"]: row["total"] for row in rows}
    income = round(totals.get("income", 0), 2)
    expenses = round(totals.get("expense", 0), 2)
    balance = round(income - expenses, 2)
    savings_rate = round(balance / income * 100, 1) if income > 0 else None

    # Balance across all months (money you actually have)
    all_rows = query("SELECT type, COALESCE(SUM(amount), 0) AS total FROM transactions GROUP BY type")
    all_totals = {row["type"]: row["total"] for row in all_rows}
    balance_all_time = round(all_totals.get("income", 0) - all_totals.get("expense", 0), 2)

    # Budget numbers come from the same function the Budgets page uses
    budgets = get_budget_status(month)
    budget_total = round(sum(b["budget"] for b in budgets), 2)
    budget_spent = round(sum(b["spent"] for b in budgets), 2)

    return {
        "month": month,
        "income": income,
        "expenses": expenses,
        "balance": balance,
        "savings_rate": savings_rate,
        "balance_all_time": balance_all_time,
        "budget_total": budget_total,
        "budget_spent": budget_spent,
        "budget_remaining": round(budget_total - budget_spent, 2),
    }


def monthly_totals():
    """One row per month that has transactions: income, expenses, net. Oldest first."""
    rows = query(
        "SELECT substr(date, 1, 7) AS month, "
        "SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income, "
        "SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expenses "
        "FROM transactions GROUP BY month ORDER BY month"
    )
    for row in rows:
        row["income"] = round(row["income"], 2)
        row["expenses"] = round(row["expenses"], 2)
        row["net"] = round(row["income"] - row["expenses"], 2)
    return rows


def category_spending(month):
    """Expenses per category for one month, largest first, with each category's share (%)."""
    month = _check_month(month)
    rows = query(
        "SELECT c.name AS category, SUM(t.amount) AS total "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.type = 'expense' AND substr(t.date, 1, 7) = ? "
        "GROUP BY c.id ORDER BY total DESC",
        (month,),
    )
    grand_total = sum(row["total"] for row in rows)
    for row in rows:
        row["total"] = round(row["total"], 2)
        row["share"] = round(row["total"] / grand_total * 100, 1) if grand_total else 0
    return rows

def available_months():
    """Months that have transactions or budgets, plus the current month. Newest first."""
    from datetime import date

    rows = query(
        "SELECT substr(date, 1, 7) AS month FROM transactions "
        "UNION SELECT month FROM budgets"
    )
    months = {row["month"] for row in rows}
    months.add(date.today().strftime("%Y-%m"))
    return sorted(months, reverse=True)

def cumulative_spending(month, through_day=None):
    """Running total of expenses for each day of the month: [{'day': 1, 'total': 0}, ...].

    through_day stops the list at that day (used for the current, unfinished month).
    """
    import calendar

    month = _check_month(month)
    year, mon = (int(part) for part in month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]
    last_day = min(through_day, days_in_month) if through_day else days_in_month

    rows = query(
        "SELECT CAST(substr(date, 9, 2) AS INTEGER) AS day, SUM(amount) AS total "
        "FROM transactions WHERE type = 'expense' AND substr(date, 1, 7) = ? GROUP BY day",
        (month,),
    )
    spent_on = {row["day"]: row["total"] for row in rows}

    running = 0.0
    result = []
    for day in range(1, last_day + 1):
        running += spent_on.get(day, 0)
        result.append({"day": day, "total": round(running, 2)})
    return result


def months_ending(end_month, count):
    """The last `count` months ending at end_month, oldest first. ('2026-10', 3) -> Aug, Sep, Oct."""
    end_month = _check_month(end_month)
    year, mon = (int(part) for part in end_month.split("-"))
    total = year * 12 + (mon - 1)
    result = []
    for offset in range(count - 1, -1, -1):
        t = total - offset
        result.append(f"{t // 12:04d}-{t % 12 + 1:02d}")
    return result


def monthly_series(months):
    """Income, expenses, net and savings rate for each month in the list (zeros if no data)."""
    by_month = {row["month"]: row for row in monthly_totals()}
    series = []
    for month in months:
        row = by_month.get(month)
        income = row["income"] if row else 0.0
        expenses = row["expenses"] if row else 0.0
        net = round(income - expenses, 2)
        rate = round(net / income * 100, 1) if income > 0 else None
        series.append(
            {"month": month, "income": income, "expenses": expenses, "net": net, "savings_rate": rate}
        )
    return series


def range_stats(series):
    """Averages over the months that have data. Returns None if no month has any."""
    active = [r for r in series if r["income"] > 0 or r["expenses"] > 0]
    if not active:
        return None
    n = len(active)
    rates = [r["savings_rate"] for r in active if r["savings_rate"] is not None]
    peak = max(active, key=lambda r: r["expenses"])
    return {
        "active_months": n,
        "avg_income": round(sum(r["income"] for r in active) / n, 2),
        "avg_expenses": round(sum(r["expenses"] for r in active) / n, 2),
        "avg_net": round(sum(r["net"] for r in active) / n, 2),
        "avg_savings_rate": round(sum(rates) / len(rates), 1) if rates else None,
        "highest_spending_month": peak["month"],
        "highest_spending_amount": peak["expenses"],
    }


def category_by_month(months):
    """Expenses per category per month, for the given months only."""
    if not months:
        return []
    marks = ",".join("?" * len(months))
    rows = query(
        "SELECT substr(t.date, 1, 7) AS month, c.name AS category, SUM(t.amount) AS total "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        f"WHERE t.type = 'expense' AND substr(t.date, 1, 7) IN ({marks}) "
        "GROUP BY month, c.id ORDER BY month, total DESC",
        tuple(months),
    )
    for row in rows:
        row["total"] = round(row["total"], 2)
    return rows


def top_categories(months):
    """Total spending per category across the months, largest first, with each share (%)."""
    totals = {}
    for row in category_by_month(months):
        totals[row["category"]] = totals.get(row["category"], 0) + row["total"]
    grand = sum(totals.values())
    rows = [
        {
            "category": name,
            "total": round(total, 2),
            "share": round(total / grand * 100, 1) if grand else 0,
        }
        for name, total in totals.items()
    ]
    rows.sort(key=lambda r: (-r["total"], r["category"]))
    return rows


def category_comparison(month):
    """Each category's spending this month vs the month before, biggest change first."""
    month = _check_month(month)
    now = {r["category"]: r["total"] for r in category_spending(month)}
    before = {r["category"]: r["total"] for r in category_spending(previous_month(month))}
    rows = []
    for name in set(now) | set(before):
        current = now.get(name, 0.0)
        previous = before.get(name, 0.0)
        change = round(current - previous, 2)
        pct = round(change / previous * 100, 1) if previous > 0 else None
        rows.append(
            {"category": name, "current": current, "previous": previous, "change": change, "pct": pct}
        )
    rows.sort(key=lambda r: (-abs(r["change"]), r["category"]))
    return rows