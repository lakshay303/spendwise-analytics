import math
from datetime import datetime

from spendwise.database import get_connection, query
from spendwise.services.transactions import MAX_AMOUNT, ValidationError

# At or above this share of the budget, a category shows "Near limit".
WARNING_THRESHOLD = 0.8


def _check_month(month):
    """Return the month as 'YYYY-MM' or raise ValidationError."""
    try:
        return datetime.strptime(str(month).strip(), "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise ValidationError("Month must be in YYYY-MM format, e.g. 2026-10.")


def previous_month(month):
    """'2026-01' -> '2025-12'."""
    parsed = datetime.strptime(month, "%Y-%m")
    if parsed.month == 1:
        return f"{parsed.year - 1:04d}-12"
    return f"{parsed.year:04d}-{parsed.month - 1:02d}"


def set_budget(category_id, month, amount):
    """Create a budget, or update it if one already exists for that category and month."""
    month = _check_month(month)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValidationError("Budget must be a number.")
    if math.isnan(amount) or math.isinf(amount) or amount <= 0:
        raise ValidationError("Budget must be greater than zero.")
    if amount > MAX_AMOUNT:
        raise ValidationError("Budget is too large.")
    amount = round(amount, 2)

    rows = query("SELECT type FROM categories WHERE id = ?", (category_id,))
    if not rows or rows[0]["type"] != "expense":
        raise ValidationError("Budgets can only be set for expense categories.")

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO budgets (category_id, month, amount) VALUES (?, ?, ?) "
            "ON CONFLICT (category_id, month) DO UPDATE SET amount = excluded.amount",
            (category_id, month, amount),
        )


def delete_budget(budget_id):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        if cursor.rowcount == 0:
            raise ValidationError("That budget no longer exists.")


def copy_budgets(from_month, to_month):
    """Copy budgets between months without overwriting existing ones. Returns how many were added."""
    from_month = _check_month(from_month)
    to_month = _check_month(to_month)
    if not query("SELECT 1 FROM budgets WHERE month = ?", (from_month,)):
        raise ValidationError("There are no budgets in the previous month to copy.")
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO budgets (category_id, month, amount) "
            "SELECT category_id, ?, amount FROM budgets WHERE month = ?",
            (to_month, from_month),
        )
        return cursor.rowcount


def get_budget_status(month):
    """Return each budget for the month with spent, remaining, percent used and a status."""
    month = _check_month(month)
    rows = query(
        "SELECT b.id, b.category_id, c.name AS category, b.amount AS budget, "
        "COALESCE(SUM(t.amount), 0) AS spent "
        "FROM budgets b "
        "JOIN categories c ON c.id = b.category_id "
        "LEFT JOIN transactions t ON t.category_id = b.category_id "
        "  AND t.type = 'expense' AND substr(t.date, 1, 7) = b.month "
        "WHERE b.month = ? GROUP BY b.id ORDER BY c.name",
        (month,),
    )
    for row in rows:
        row["spent"] = round(row["spent"], 2)
        row["remaining"] = round(row["budget"] - row["spent"], 2)
        ratio = row["spent"] / row["budget"]
        row["pct_used"] = round(ratio * 100, 1)
        if ratio > 1:
            row["status"] = "over"
        elif ratio >= WARNING_THRESHOLD:
            row["status"] = "warning"
        else:
            row["status"] = "on_track"
    return rows