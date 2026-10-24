"""Checks the sample data. Uses temporary databases, never your real data.
Run from the project folder: python tests/test_sample_data.py
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spendwise.database as db


def fresh_db():
    db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
    db.init_db()


fresh_db()

from spendwise.services import analytics, budgets, csv_io, insights, transactions as tx  # noqa: E402
from spendwise.services.budgets import previous_month  # noqa: E402
from spendwise.services.sample_data import generate_sample_rows, load_sample_data  # noqa: E402

failures = 0


def check(label, actual, expected):
    global failures
    ok = actual == expected
    print("PASS" if ok else "FAIL", "-", label, "" if ok else f"(expected {expected!r}, got {actual!r})")
    if not ok:
        failures += 1


TODAYS = [date(2026, 10, 24), date(2026, 10, 1), date(2027, 1, 15), date(2026, 3, 31), date(2026, 2, 28)]

for today in TODAYS:
    print(f"\nToday = {today}")
    fresh_db()
    current = today.strftime("%Y-%m")
    middle = previous_month(current)
    oldest = previous_month(middle)

    count = load_sample_data(today)
    rows = tx.list_transactions()
    check("saved count matches the database", count, len(rows))
    check("has a useful amount of data", count >= 45, True)
    check("no dates in the future", max(r["date"] for r in rows) <= today.isoformat(), True)
    check("starts two months back", min(r["date"] for r in rows)[:7], oldest)
    check("has income and expenses", {r["type"] for r in rows}, {"income", "expense"})

    summary = analytics.month_summary(current)
    check("this month has at least the salary", summary["income"] >= 60000, True)
    check("this month has spending", summary["expenses"] > 0, True)
    check("an unusual expense is detected this month", len(insights.find_anomalies(current)) >= 1, True)
    check("5 budgets this month", len(budgets.get_budget_status(current)), 5)
    check("5 budgets last month", len(budgets.get_budget_status(middle)), 5)
    check("no budgets in the oldest month", len(budgets.get_budget_status(oldest)), 0)

    again = csv_io.parse_csv(csv_io.export_csv().encode("utf-8"))
    check(
        "every row is valid (export re-imports with no errors or new rows)",
        (len(again["errors"]), len(again["new"]), len(again["duplicates"])),
        (0, 0, count),
    )

    try:
        load_sample_data(today)
        check("refuses to load twice", "loaded", "refused")
    except tx.ValidationError:
        check("refuses to load twice", "refused", "refused")

print("\nDeterminism and safety")
check(
    "same date gives the same data",
    generate_sample_rows(date(2026, 10, 24)),
    generate_sample_rows(date(2026, 10, 24)),
)
fresh_db()
budgets.set_budget(tx.get_categories("expense")[0]["id"], "2026-10", 100)
try:
    load_sample_data(date(2026, 10, 24))
    check("refuses when only a budget exists", "loaded", "refused")
except tx.ValidationError:
    check("refuses when only a budget exists", "refused", "refused")

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)