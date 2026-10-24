"""Checks the analytics numbers. Uses a temporary database, never your real data.
Run from the project folder: python tests/test_analytics.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spendwise.database as db

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
db.init_db()

from spendwise.services import analytics, budgets, transactions as tx  # noqa: E402

failures = 0


def check(label, actual, expected):
    global failures
    if isinstance(expected, (int, float)) and actual is not None:
        ok = abs(actual - expected) < 0.005
    else:
        ok = actual == expected
    print("PASS" if ok else "FAIL", "-", label, "" if ok else f"(expected {expected}, got {actual})")
    if not ok:
        failures += 1


ids = {(c["name"], c["type"]): c["id"] for c in tx.get_categories()}
FOOD = ids[("Food & Dining", "expense")]
TRANSPORT = ids[("Transport", "expense")]
SALARY = ids[("Salary", "income")]
FREELANCE = ids[("Freelance", "income")]

tx.add_transaction("2026-10-05", "income", 50000, SALARY, "Salary")
tx.add_transaction("2026-10-12", "income", 2000, FREELANCE, "Freelance")
tx.add_transaction("2026-10-06", "expense", 1200, FOOD, "Groceries")
tx.add_transaction("2026-10-10", "expense", 800, FOOD, "Restaurant")
tx.add_transaction("2026-10-11", "expense", 300, TRANSPORT, "Metro")
tx.add_transaction("2026-09-30", "expense", 5000, FOOD, "Last month food")
budgets.set_budget(FOOD, "2026-10", 3000)
budgets.set_budget(TRANSPORT, "2026-10", 1000)

print("\nOctober summary")
s = analytics.month_summary("2026-10")
check("income", s["income"], 52000)
check("expenses", s["expenses"], 2300)
check("balance", s["balance"], 49700)
check("savings rate", s["savings_rate"], 95.6)
check("all-time balance", s["balance_all_time"], 44700)
check("budget total", s["budget_total"], 4000)
check("budget spent", s["budget_spent"], 2300)
check("budget remaining", s["budget_remaining"], 1700)

print("\nSeptember summary (no income)")
s = analytics.month_summary("2026-09")
check("income", s["income"], 0)
check("expenses", s["expenses"], 5000)
check("balance", s["balance"], -5000)
check("savings rate is None when there is no income", s["savings_rate"], None)

print("\nEmpty month")
s = analytics.month_summary("2026-01")
check("income", s["income"], 0)
check("expenses", s["expenses"], 0)
check("budget total", s["budget_total"], 0)

print("\nMonthly totals")
m = analytics.monthly_totals()
check("number of months", len(m), 2)
check("Sept expenses", m[0]["expenses"], 5000)
check("Oct income", m[1]["income"], 52000)
check("Oct expenses", m[1]["expenses"], 2300)
check("Oct net", m[1]["net"], 49700)

print("\nCategory spending, October")
c = analytics.category_spending("2026-10")
check("number of categories (income never appears)", len(c), 2)
check("top category", c[0]["category"], "Food & Dining")
check("top category total", c[0]["total"], 2000)
check("top category share", c[0]["share"], 87.0)
check("second category total", c[1]["total"], 300)
check("second category share", c[1]["share"], 13.0)

print("\nInvalid month")
try:
    analytics.month_summary("October")
    check("bad month is rejected", "accepted", "rejected")
except tx.ValidationError:
    check("bad month is rejected", "rejected", "rejected")

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)