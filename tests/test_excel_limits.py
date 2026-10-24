"""Checks the Excel upload safety limits. Uses a temporary database.
Run from the project folder: python tests/test_excel_limits.py
"""
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spendwise.database as db

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
db.init_db()

from openpyxl import Workbook  # noqa: E402

from spendwise.services import csv_io, transactions as tx  # noqa: E402

failures = 0


def check(label, actual, expected):
    global failures
    ok = actual == expected
    print("PASS" if ok else "FAIL", "-", label, "" if ok else f"(expected {expected!r}, got {actual!r})")
    if not ok:
        failures += 1


def rejects(label, action):
    try:
        action()
        check(label, "accepted", "rejected")
    except tx.ValidationError:
        check(label, "rejected", "rejected")


def workbook_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["date", "type", "category", "amount", "description"])
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def rows_read(result):
    return len(result["new"]) + len(result["duplicates"]) + len(result["errors"])


row = ["2026-10-01", "expense", "Food & Dining", 10, "x"]

print("\nNormal files still work")
normal = workbook_bytes([row] * 3)
check("small workbook is read", rows_read(csv_io.parse_xlsx(normal)), 3)
check("template still has no problems", len(csv_io.parse_xlsx(csv_io.template_xlsx())["errors"]), 0)

print("\nRow limit")
original = csv_io.MAX_ROWS
csv_io.MAX_ROWS = 3
rejects("more rows than the limit", lambda: csv_io.parse_xlsx(workbook_bytes([row] * 10)))
rejects("far more rows than the limit", lambda: csv_io.parse_xlsx(workbook_bytes([row] * 2500)))
check("exactly at the limit is accepted", rows_read(csv_io.parse_xlsx(workbook_bytes([row] * 3))), 3)
csv_io.MAX_ROWS = original

print("\nSize limits")
original = csv_io.MAX_UNZIPPED_BYTES
csv_io.MAX_UNZIPPED_BYTES = 1000
rejects("larger than the unpacked limit", lambda: csv_io.parse_xlsx(normal))
csv_io.MAX_UNZIPPED_BYTES = original
check("normal file is under the default unpacked limit", rows_read(csv_io.parse_xlsx(normal)), 3)
rejects("file over 5 MB", lambda: csv_io.parse_xlsx(b"x" * (csv_io.MAX_BYTES + 1)))
rejects("not a real Excel file", lambda: csv_io.parse_xlsx(b"this is not an excel file"))
rejects("empty file", lambda: csv_io.parse_xlsx(b""))

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)