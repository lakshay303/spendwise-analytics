"""Checks the insights. Uses a temporary database, never your real data.
Run from the project folder: python tests/test_insights.py
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spendwise.database as db

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
db.init_db()

from spendwise.services import budgets, insights, transactions as tx  # noqa: E402

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
ENTERTAINMENT = ids[("Entertainment", "expense")]
SALARY = ids[("Salary", "income")]

# June: expense only (no income)
tx.add_transaction("2026-06-10", "expense", 500, FOOD, "June food")
# August: spent more than earned
tx.add_transaction("2026-08-05", "income", 1000, SALARY, "Salary")
tx.add_transaction("2026-08-10", "expense", 3000, SHOPPING, "Big shopping")
# September
tx.add_transaction("2026-09-05", "income", 40000, SALARY, "Salary")
tx.add_transaction("2026-09-08", "expense", 1000, FOOD, "Food")
for day in range(1, 6):
    tx.add_transaction(f"2026-09-0{day}", "expense", 100, TRANSPORT, "Bus")
# October
tx.add_transaction("2026-10-05", "income", 50000, SALARY, "Salary")
tx.add_transaction("2026-10-06", "expense", 1200, FOOD, "Groceries")
tx.add_transaction("2026-10-10", "expense", 800, FOOD, "Restaurant")
tx.add_transaction("2026-10-11", "expense", 900, TRANSPORT, "Taxi to airport")
tx.add_transaction("2026-10-12", "expense", 700, ENTERTAINMENT, "Concert")
budgets.set_budget(FOOD, "2026-10", 2200)
budgets.set_budget(TRANSPORT, "2026-10", 800)
budgets.set_budget(ENTERTAINMENT, "2026-10", 1000)

TODAY = date(2026, 10, 15)


def first(items, kind):
    matches = [i for i in items if i["kind"] == kind]
    return matches[0] if matches else {}


print("\nOctober insights")
october = insights.get_insights("2026-10", today=TODAY)
check("most important insight comes first", october[0]["severity"], "bad")

savings = first(october, "savings")
check("savings severity", savings.get("severity"), "good")
check("savings title", savings.get("title"), "Healthy savings rate")
check("savings detail has 93%", "93%" in savings.get("detail", ""), True)

change = first(october, "spending_change")
check("spending change title", change.get("title"), "Spending is up 140% vs last month")
check("spending change severity", change.get("severity"), "bad")

cat_change = first(october, "category_change")
check("category change title", cat_change.get("title"), "Food & Dining spending rose 100%")

top = first(october, "top_category")
check("top category title", top.get("title"), "Food & Dining is your biggest expense")
check("top category share 56%", "56%" in top.get("detail", ""), True)

over = first(october, "budget_over")
check("over budget title", over.get("title"), "Transport is over budget")
check("over by 100", "₹100.00" in over.get("detail", ""), True)

near = first(october, "budget_near")
check("near limit title", near.get("title"), "Food & Dining is near its limit")
check("near limit 91%", "91%" in near.get("detail", ""), True)

pace = first(october, "budget_pace")
check("pace title", pace.get("title"), "Entertainment is running ahead of schedule")
check("pace detail", pace.get("detail"), "70% of budget used, 48% of the month gone.")

check("no 'all budgets on track' when some are flagged", first(october, "budget_ok"), {})

anomaly = first(october, "anomaly")
check("anomaly title", anomaly.get("title"), "Unusually large Transport expense")
check("anomaly is 9x typical", "9.0×" in anomaly.get("detail", ""), True)
check("exactly one anomaly found", len(insights.find_anomalies("2026-10")), 1)
check("no anomalies in September", len(insights.find_anomalies("2026-09")), 0)

print("\nPace is only checked for the current month")
later = insights.get_insights("2026-10", today=date(2026, 11, 20))
check("no pace insight for a past month", first(later, "budget_pace"), {})

print("\nAugust: spent more than earned")
august = insights.get_insights("2026-08", today=TODAY)
check("savings severity", first(august, "savings").get("severity"), "bad")
check("savings title", first(august, "savings").get("title"), "You spent more than you earned")
check("over by 2000", "₹2,000.00" in first(august, "savings").get("detail", ""), True)
check("no month-over-month without last month's spending", first(august, "spending_change"), {})

print("\nJune: no income")
june = insights.get_insights("2026-06", today=TODAY)
check("savings title", first(june, "savings").get("title"), "No income recorded")
check("savings severity", first(june, "savings").get("severity"), "warn")

print("\nMonth with no data")
check("empty list", insights.get_insights("2026-01", today=TODAY), [])

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)