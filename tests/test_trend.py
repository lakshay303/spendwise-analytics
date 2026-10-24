"""Checks the cumulative spending trend. Uses a temporary database.
Run from the project folder: python tests/test_trend.py
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
SALARY = ids[("Salary", "income")]

tx.add_transaction("2026-10-05", "expense", 100, FOOD, "")
tx.add_transaction("2026-10-10", "expense", 250, TRANSPORT, "")
tx.add_transaction("2026-10-10", "income", 999, SALARY, "")  # must be ignored
tx.add_transaction("2026-10-12", "expense", 50, FOOD, "")

october = analytics.cumulative_spending("2026-10")
total_on = lambda day: october[day - 1]["total"]  # noqa: E731

check("October has 31 days", len(october), 31)
check("day 4 total", total_on(4), 0)
check("day 5 total", total_on(5), 100)
check("day 9 total", total_on(9), 100)
check("day 10 total (income ignored)", total_on(10), 350)
check("day 11 total", total_on(11), 350)
check("day 12 total", total_on(12), 400)
check("day 31 total", total_on(31), 400)
check("matches the monthly summary", october[-1]["total"], analytics.month_summary("2026-10")["expenses"])

check("through_day stops early", len(analytics.cumulative_spending("2026-10", through_day=10)), 10)
check("through_day total", analytics.cumulative_spending("2026-10", through_day=10)[-1]["total"], 350)
check("through_day beyond month end is capped", len(analytics.cumulative_spending("2026-09", through_day=40)), 30)
check("February has 28 days in 2026", len(analytics.cumulative_spending("2026-02")), 28)
check("month with no data stays at zero", analytics.cumulative_spending("2026-02")[-1]["total"], 0)

try:
    analytics.cumulative_spending("October")
    check("bad month is rejected", "accepted", "rejected")
except tx.ValidationError:
    check("bad month is rejected", "rejected", "rejected")

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)