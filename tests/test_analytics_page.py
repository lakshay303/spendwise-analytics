"""Checks the Analytics calculations. Uses a temporary database, never your real data.
Run from the project folder: python tests/test_analytics_page.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spendwise.database as db

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
db.init_db()

from spendwise.services import analytics, transactions as tx  # noqa: E402

failures = 0


def check(label, actual, expected):
    global failures
    ok = actual == expected
    print("PASS" if ok else "FAIL", "-", label, "" if ok else f"(expected {expected!r}, got {actual!r})")
    if not ok:
        failures += 1


ids = {(c["name"], c["type"]): c["id"] for c in tx.get_categories()}
FOOD = ids[("Food & Dining", "expense")]
TRANSPORT = ids[("Transport", "expense")]
SHOPPING = ids[("Shopping", "expense")]
SALARY = ids[("Salary", "income")]

tx.add_transaction("2026-06-15", "expense", 999, FOOD, "June, no income")
# August
tx.add_transaction("2026-08-01", "income", 10000, SALARY, "")
tx.add_transaction("2026-08-05", "expense", 2000, FOOD, "")
tx.add_transaction("2026-08-06", "expense", 500, TRANSPORT, "")
# September
tx.add_transaction("2026-09-01", "income", 10000, SALARY, "")
tx.add_transaction("2026-09-05", "expense", 3000, FOOD, "")
tx.add_transaction("2026-09-06", "expense", 1000, SHOPPING, "")
# October
tx.add_transaction("2026-10-01", "income", 20000, SALARY, "")
tx.add_transaction("2026-10-05", "expense", 1500, FOOD, "")
tx.add_transaction("2026-10-06", "expense", 500, TRANSPORT, "")
tx.add_transaction("2026-10-07", "expense", 2500, SHOPPING, "")

print("\nMonth lists")
months = analytics.months_ending("2026-10", 4)
check("4 months ending Oct 2026", months, ["2026-07", "2026-08", "2026-09", "2026-10"])
check("crosses a year boundary", analytics.months_ending("2026-02", 3), ["2025-12", "2026-01", "2026-02"])
check("single month", analytics.months_ending("2026-10", 1), ["2026-10"])
try:
    analytics.months_ending("October", 3)
    check("bad month is rejected", "accepted", "rejected")
except tx.ValidationError:
    check("bad month is rejected", "rejected", "rejected")

print("\nMonthly series")
series = analytics.monthly_series(months)
check("empty month is all zeros", series[0], {"month": "2026-07", "income": 0.0, "expenses": 0.0, "net": 0.0, "savings_rate": None})
check("Aug income", series[1]["income"], 10000)
check("Aug expenses", series[1]["expenses"], 2500)
check("Aug net", series[1]["net"], 7500)
check("Aug savings rate", series[1]["savings_rate"], 75.0)
check("Sep savings rate", series[2]["savings_rate"], 60.0)
check("Oct expenses", series[3]["expenses"], 4500)
check("Oct net", series[3]["net"], 15500)
check("Oct savings rate", series[3]["savings_rate"], 77.5)
june = analytics.monthly_series(["2026-06"])[0]
check("expenses without income: net is negative", june["net"], -999)
check("expenses without income: no savings rate", june["savings_rate"], None)

print("\nRange statistics")
stats = analytics.range_stats(series)
check("months with data", stats["active_months"], 3)
check("average income", stats["avg_income"], 13333.33)
check("average expenses", stats["avg_expenses"], 3666.67)
check("average net", stats["avg_net"], 9666.67)
check("average savings rate", stats["avg_savings_rate"], 70.8)
check("highest spending month", stats["highest_spending_month"], "2026-10")
check("highest spending amount", stats["highest_spending_amount"], 4500)
check("no data gives None", analytics.range_stats(analytics.monthly_series(["2026-01"])), None)

print("\nCategories by month")
rows = analytics.category_by_month(["2026-08", "2026-09", "2026-10"])
lookup = {(r["month"], r["category"]): r["total"] for r in rows}
check("7 rows (June is outside the range)", len(rows), 7)
check("Sep food", lookup[("2026-09", "Food & Dining")], 3000)
check("Oct shopping", lookup[("2026-10", "Shopping")], 2500)
check("income categories never appear", {r["category"] for r in rows}, {"Food & Dining", "Transport", "Shopping"})
check("all rows add up to total spending", sum(r["total"] for r in rows), 11000)
check("no months gives no rows", analytics.category_by_month([]), [])

print("\nTop categories")
top = analytics.top_categories(["2026-08", "2026-09", "2026-10"])
check("order", [r["category"] for r in top], ["Food & Dining", "Shopping", "Transport"])
check("totals", [r["total"] for r in top], [6500, 3500, 1000])
check("shares", [r["share"] for r in top], [59.1, 31.8, 9.1])

print("\nCategory comparison")
oct_vs_sep = analytics.category_comparison("2026-10")
check(
    "Oct vs Sep",
    [(r["category"], r["current"], r["previous"], r["change"], r["pct"]) for r in oct_vs_sep],
    [
        ("Food & Dining", 1500, 3000, -1500, -50.0),
        ("Shopping", 2500, 1000, 1500, 150.0),
        ("Transport", 500, 0, 500, None),
    ],
)
sep_vs_aug = analytics.category_comparison("2026-09")
check(
    "Sep vs Aug (new and dropped categories)",
    [(r["category"], r["current"], r["previous"], r["change"], r["pct"]) for r in sep_vs_aug],
    [
        ("Food & Dining", 3000, 2000, 1000, 50.0),
        ("Shopping", 1000, 0, 1000, None),
        ("Transport", 0, 500, -500, -100.0),
    ],
)
check("month with no data", analytics.category_comparison("2026-01"), [])

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)