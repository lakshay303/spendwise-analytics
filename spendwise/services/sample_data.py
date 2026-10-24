import random
from datetime import date

from spendwise.database import query
from spendwise.services.budgets import previous_month, set_budget
from spendwise.services.csv_io import import_rows
from spendwise.services.transactions import ValidationError, get_categories

SAMPLE_BUDGETS = {
    "Rent & Utilities": 18000,
    "Food & Dining": 7000,
    "Transport": 2500,
    "Shopping": 6000,
    "Entertainment": 2000,
}

FOOD_NOTES = ["Groceries", "Lunch", "Dinner out", "Coffee", "Snacks", "Weekly vegetables", "Takeaway"]
TRANSPORT_NOTES = ["Metro card", "Auto ride", "Fuel", "Cab", "Bus pass"]
SHOPPING_NOTES = ["Clothes", "Headphones", "Home supplies", "Books"]
ENTERTAINMENT_NOTES = ["Movie", "Streaming subscription", "Concert", "Games"]


def _sample_months(today):
    """Two months back, last month and this month, as 'YYYY-MM' (oldest first)."""
    current = today.strftime("%Y-%m")
    middle = previous_month(current)
    return [previous_month(middle), middle, current]


def _month_rows(month, max_day):
    """Example transactions for one month. Days after max_day are skipped (they'd be in the future)."""
    rng = random.Random(month)  # seeded by the month, so the same month always gives the same data
    rows = []

    def add(day, kind, category, amount, note):
        if day <= max_day:
            rows.append(
                {
                    "date": f"{month}-{day:02d}",
                    "type": kind,
                    "category": category,
                    "amount": float(amount),
                    "description": note,
                }
            )

    add(1, "income", "Salary", 60000, "Monthly salary")
    add(10, "income", "Freelance", rng.randrange(8000, 15001, 500), "Freelance project")
    add(3, "expense", "Rent & Utilities", 15000, "Rent")
    add(12, "expense", "Rent & Utilities", rng.randrange(1800, 2501, 50), "Electricity and internet")
    for _ in range(10):
        add(rng.randint(1, 28), "expense", "Food & Dining", rng.randrange(120, 901, 10), rng.choice(FOOD_NOTES))
    for _ in range(6):
        add(rng.randint(1, 28), "expense", "Transport", rng.randrange(40, 401, 10), rng.choice(TRANSPORT_NOTES))
    for _ in range(2):
        add(rng.randint(1, 28), "expense", "Shopping", rng.randrange(800, 3501, 50), rng.choice(SHOPPING_NOTES))
    for _ in range(2):
        add(rng.randint(1, 28), "expense", "Entertainment", rng.randrange(300, 901, 50), rng.choice(ENTERTAINMENT_NOTES))
    if rng.random() < 0.5:
        add(rng.randint(5, 25), "expense", "Health", rng.randrange(300, 1501, 50), "Pharmacy")
    return rows


def generate_sample_rows(today=None):
    """Return (months, rows). Nothing is saved."""
    today = today or date.today()
    months = _sample_months(today)
    rows = []
    for month in months:
        max_day = today.day if month == months[-1] else 31
        rows += _month_rows(month, max_day)

    # One clearly unusual expense this month, so the insights have something to flag
    rows.append(
        {
            "date": f"{months[-1]}-{min(today.day, 3):02d}",
            "type": "expense",
            "category": "Transport",
            "amount": 3200.0,
            "description": "Airport cab",
        }
    )
    rows.sort(key=lambda r: (r["date"], r["type"], r["description"]))
    return months, rows


def load_sample_data(today=None):
    """Save sample transactions and budgets. Only works on an empty database. Returns the row count."""
    if query("SELECT 1 FROM transactions LIMIT 1") or query("SELECT 1 FROM budgets LIMIT 1"):
        raise ValidationError("Sample data can only be loaded into an empty database.")

    months, rows = generate_sample_rows(today)
    ids = {(c["name"], c["type"]): c["id"] for c in get_categories()}
    for row in rows:
        row["category_id"] = ids[(row["category"], row["type"])]

    saved = import_rows(rows)
    for month in months[1:]:
        for name, amount in SAMPLE_BUDGETS.items():
            set_budget(ids[(name, "expense")], month, amount)
    return saved