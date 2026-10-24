"""Checks CSV import and export. Uses a temporary database, never your real data.
Run from the project folder: python tests/test_csv.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spendwise.database as db

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
db.init_db()

from spendwise.services import csv_io, transactions as tx  # noqa: E402

failures = 0


def check(label, actual, expected):
    global failures
    ok = actual == expected
    print("PASS" if ok else "FAIL", "-", label, "" if ok else f"(expected {expected!r}, got {actual!r})")
    if not ok:
        failures += 1


def rejects(label, data):
    try:
        csv_io.parse_csv(data)
        check(label, "accepted", "rejected")
    except tx.ValidationError:
        check(label, "rejected", "rejected")


HEADER = "date,type,category,amount,description\n"
GOOD = (
    HEADER
    + "2026-10-01,income,Salary,50000,Salary\n"
    + '2026-10-02,expense,Food & Dining,"₹1,200.50",Groceries\n'
    + "03/10/2026,expense,transport,300,Metro\n"
)

print("\nGood file")
result = csv_io.parse_csv(GOOD.encode("utf-8"))
check("3 new rows", len(result["new"]), 3)
check("no errors", len(result["errors"]), 0)
check("no duplicates", len(result["duplicates"]), 0)
check("currency symbol and comma removed", result["new"][1]["amount"], 1200.5)
check("DD/MM/YYYY date converted", result["new"][2]["date"], "2026-10-03")
check("category matched case-insensitively", result["new"][2]["category"], "Transport")

print("\nOther file formats")
check("UTF-8 BOM file", len(csv_io.parse_csv(b"\xef\xbb\xbf" + GOOD.encode("utf-8"))["new"]), 3)
semicolons = "date;type;category;amount;description\n2026-10-12;expense;Food & Dining;40;Tea\n"
check("semicolon-separated file", len(csv_io.parse_csv(semicolons.encode())["new"]), 1)
check("header-only file has zero rows", csv_io.parse_csv(HEADER.encode())["total_rows"], 0)

print("\nBad rows are reported, good rows still read")
BAD = (
    HEADER
    + "2026-13-45,expense,Food & Dining,100,bad date\n"        # line 2
    + "2026-10-04,expense,Food & Dining,abc,bad amount\n"      # line 3
    + "2026-10-05,expense,Food & Dining,-50,negative\n"        # line 4
    + "2026-10-06,expense,Food & Dining,0,zero\n"              # line 5
    + "2026-10-07,transfer,Food & Dining,100,bad type\n"       # line 6
    + "2026-10-08,expense,Salary,100,income category\n"        # line 7
    + "2026-10-09,expense,Mystery,100,unknown category\n"      # line 8
    + "2026-10-10,expense,Food & Dining,,missing amount\n"     # line 9
    + ",expense,Food & Dining,100,missing date\n"              # line 10
    + ",,,,\n"                                                 # line 11 (blank, skipped)
    + "2026-10-11,expense,Food & Dining,75,Valid\n"            # line 12
    + "2026-10-12,expense,Food & Dining,40,Tea,extra\n"        # line 13
)
result = csv_io.parse_csv(BAD.encode("utf-8"))
check("one valid row", len(result["new"]), 1)
check("valid row amount", result["new"][0]["amount"], 75)
check("error rows", [e["row"] for e in result["errors"]], [2, 3, 4, 5, 6, 7, 8, 9, 10, 13])
check("blank row not counted", result["total_rows"], 11)
check("date error mentions date", "date" in result["errors"][0]["message"].lower(), True)

print("\nWhole-file problems are rejected")
rejects("missing column", b"date,type,amount\n2026-10-01,income,100\n")
rejects("empty file", b"")
rejects("only whitespace", b"  \n \n")
rejects("file over 5 MB", b"x" * (csv_io.MAX_BYTES + 1))
csv_io.MAX_ROWS = 3
rejects("too many rows", (HEADER + "2026-10-01,income,Salary,1,a\n" * 4).encode())
csv_io.MAX_ROWS = 5000

print("\nImporting and duplicate protection")
check("import saves 3 rows", csv_io.import_rows(GOOD and csv_io.parse_csv(GOOD.encode())["new"]), 3)
check("database has 3 rows", len(tx.list_transactions()), 3)
again = csv_io.parse_csv(GOOD.encode("utf-8"))
check("same file again: 3 duplicates", len(again["duplicates"]), 3)
check("same file again: 0 new", len(again["new"]), 0)
check("importing nothing returns 0", csv_io.import_rows([]), 0)

food = {c["name"]: c["id"] for c in tx.get_categories("expense")}["Food & Dining"]
tx.add_transaction("2026-10-20", "expense", 10, food, "Chai")
tx.add_transaction("2026-10-20", "expense", 10, food, "Chai")
three = HEADER + "2026-10-20,expense,Food & Dining,10,Chai\n" * 3
result = csv_io.parse_csv(three.encode())
check("3 identical rows vs 2 in database: 2 duplicates", len(result["duplicates"]), 2)
check("3 identical rows vs 2 in database: 1 new", len(result["new"]), 1)

print("\nExport")
tx.add_transaction("2026-10-21", "expense", 5, food, "=SUM(A1)")
exported = csv_io.export_csv()
lines = exported.strip().splitlines()
check("header line", lines[0], "date,type,category,amount,description")
check("one line per transaction plus header", len(lines), len(tx.list_transactions()) + 1)
check("formula-like description is protected", "'=SUM(A1)" in exported, True)
round_trip = csv_io.parse_csv(exported.encode("utf-8"))
check("export re-imports with no errors", len(round_trip["errors"]), 0)
check("export re-imports as all duplicates", len(round_trip["duplicates"]), len(tx.list_transactions()))
check("export re-imports with nothing new", len(round_trip["new"]), 0)
only_income = csv_io.export_csv(tx.list_transactions(tx_type="income"))
check("filtered export", len(only_income.strip().splitlines()), 2)

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)