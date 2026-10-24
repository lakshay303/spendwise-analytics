"""Checks that income, expenses and budgets are calculated correctly.

Runs against a temporary database, so your real data is never touched.
Run from the project folder: python tests/test_calculations.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spendwise.database as db

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"  # temporary database
db.init_db()

from spendwise.services import budgets, transactions as tx  # noqa: E402

failures = 0


def check(label, actual, expected):
    global failures
    if isinstance(expected, (int, float)):
        ok = abs(actual - expected) < 0.005
    else:
        ok = actual == expected
    print("PASS" if ok else "FAIL", "-", label, "" if ok else f"(expected {expected}, got {actual})")
    if not ok:
        failures += 1


def budget(month, category):
    return {b["category"]: b for b in budgets.get_budget_status(month)}[category]


def total(**filters):
    return sum(r["amount"] for r in tx.list_transactions(**filters))


ids = {(c["name"], c["type"]): c["id"] for c in tx.get_categories()}
FOOD = ids[("Food & Dining", "expense")]
TRANSPORT = ids[("Transport", "expense")]
SALARY = ids[("Salary", "income")]
FREELANCE = ids[("Freelance", "income")]

# Setup: every amount is different on purpose
tx.add_transaction("2026-10-05", "income", 50000, SALARY, "Salary")
food_1 = tx.add_transaction("2026-10-06", "expense", 1200, FOOD, "Groceries")
food_2 = tx.add_transaction("2026-10-10", "expense", 800, FOOD, "Restaurant")
tx.add_transaction("2026-10-11", "expense", 300, TRANSPORT, "Metro")
tx.add_transaction("2026-10-12", "income", 2000, FREELANCE, "Freelance")
tx.add_transaction("2026-09-30", "expense", 5000, FOOD, "Last month food")

budgets.set_budget(FOOD, "2026-10", 3000)
budgets.set_budget(TRANSPORT, "2026-10", 1000)
budgets.set_budget(FOOD, "2026-09", 4000)

print("\n1. Only expenses in the right category and month count as spent")
check("Oct Food spent", budget("2026-10", "Food & Dining")["spent"], 2000)
check("Oct Food remaining", budget("2026-10", "Food & Dining")["remaining"], 1000)
check("Oct Food percent used", budget("2026-10", "Food & Dining")["pct_used"], 66.7)
check("Oct Food status", budget("2026-10", "Food & Dining")["status"], "on_track")
check("Oct Transport spent", budget("2026-10", "Transport")["spent"], 300)
check("Oct Transport remaining", budget("2026-10", "Transport")["remaining"], 700)
check("Sept Food spent (kept separate from Oct)", budget("2026-09", "Food & Dining")["spent"], 5000)
check("Sept Food status", budget("2026-09", "Food & Dining")["status"], "over")

print("\n2. Adding income never changes spent")
tx.add_transaction("2026-10-20", "income", 9999, SALARY, "Bonus")
check("Oct Food spent unchanged", budget("2026-10", "Food & Dining")["spent"], 2000)
check("Oct Transport spent unchanged", budget("2026-10", "Transport")["spent"], 300)

print("\n3. Editing an expense updates the budget")
tx.update_transaction(food_2, "2026-10-10", "expense", 2000, FOOD, "Restaurant")
check("Oct Food spent after edit", budget("2026-10", "Food & Dining")["spent"], 3200)
check("Oct Food remaining after edit", budget("2026-10", "Food & Dining")["remaining"], -200)
check("Oct Food status after edit", budget("2026-10", "Food & Dining")["status"], "over")

print("\n4. Moving an expense to another month updates both months")
tx.update_transaction(food_1, "2026-09-15", "expense", 1200, FOOD, "Groceries")
check("Oct Food spent after move", budget("2026-10", "Food & Dining")["spent"], 2000)
check("Sept Food spent after move", budget("2026-09", "Food & Dining")["spent"], 6200)

print("\n5. Deleting an expense updates the budget")
tx.delete_transaction(food_2)
check("Oct Food spent after delete", budget("2026-10", "Food & Dining")["spent"], 0)
check("Oct Food remaining after delete", budget("2026-10", "Food & Dining")["remaining"], 3000)

print("\n6. Totals and filters")
check("Total income", total(tx_type="income"), 61999)
check("Total expenses", total(tx_type="expense"), 6500)
check("Balance", total(tx_type="income") - total(tx_type="expense"), 55499)
check("October expenses only", total(tx_type="expense", start_date="2026-10-01", end_date="2026-10-31"), 300)

print("\n7. Invalid combinations are rejected")
bad_cases = [
    ("income in an expense category", lambda: tx.add_transaction("2026-10-20", "income", 100, FOOD, "")),
    ("expense in an income category", lambda: tx.add_transaction("2026-10-20", "expense", 100, SALARY, "")),
    ("budget on an income category", lambda: budgets.set_budget(SALARY, "2026-10", 500)),
]
for label, action in bad_cases:
    try:
        action()
        check(label + " is rejected", "accepted", "rejected")
    except tx.ValidationError:
        check(label + " is rejected", "rejected", "rejected")

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)