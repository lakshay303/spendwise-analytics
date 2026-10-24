import math
from datetime import date, datetime

from spendwise.database import get_connection, query

VALID_TYPES = ("income", "expense")
MAX_AMOUNT = 1_000_000_000
MAX_DESCRIPTION = 200

# Only these sort options are allowed. This keeps the SQL safe.
SORT_COLUMNS = {
    "date": "t.date",
    "amount": "t.amount",
    "category": "c.name",
    "type": "t.type",
}


class ValidationError(ValueError):
    """Raised when the user gives invalid data. The message is safe to show."""


def get_categories(tx_type=None):
    """Return categories, optionally only 'income' or 'expense' ones."""
    if tx_type:
        return query(
            "SELECT id, name, type FROM categories WHERE type = ? ORDER BY name",
            (tx_type,),
        )
    return query("SELECT id, name, type FROM categories ORDER BY type, name")


def _clean(date_value, tx_type, amount, category_id, description):
    """Check every field. Return cleaned values or raise ValidationError."""
    # Date
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    if isinstance(date_value, date):
        date_text = date_value.isoformat()
    else:
        try:
            date_text = datetime.strptime(str(date_value).strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ValidationError("Date must be in YYYY-MM-DD format, e.g. 2026-10-20.")

    # Type
    tx_type = str(tx_type).strip().lower()
    if tx_type not in VALID_TYPES:
        raise ValidationError("Type must be 'income' or 'expense'.")

    # Amount
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValidationError("Amount must be a number.")
    if math.isnan(amount) or math.isinf(amount):
        raise ValidationError("Amount must be a valid number.")
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if amount > MAX_AMOUNT:
        raise ValidationError("Amount is too large.")
    amount = round(amount, 2)

    # Category must exist and match the transaction type
    rows = query("SELECT type FROM categories WHERE id = ?", (category_id,))
    if not rows:
        raise ValidationError("Please choose a valid category.")
    if rows[0]["type"] != tx_type:
        raise ValidationError(f"That category is not an {tx_type} category.")

    # Description
    description = (description or "").strip()
    if len(description) > MAX_DESCRIPTION:
        raise ValidationError(f"Description must be {MAX_DESCRIPTION} characters or fewer.")

    return date_text, tx_type, amount, category_id, description


def add_transaction(date_value, tx_type, amount, category_id, description=""):
    """Add a transaction and return its new id."""
    values = _clean(date_value, tx_type, amount, category_id, description)
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (date, type, amount, category_id, description) "
            "VALUES (?, ?, ?, ?, ?)",
            values,
        )
        return cursor.lastrowid


def update_transaction(tx_id, date_value, tx_type, amount, category_id, description=""):
    """Replace the fields of an existing transaction."""
    values = _clean(date_value, tx_type, amount, category_id, description)
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE transactions SET date = ?, type = ?, amount = ?, "
            "category_id = ?, description = ? WHERE id = ?",
            values + (tx_id,),
        )
        if cursor.rowcount == 0:
            raise ValidationError("That transaction no longer exists.")


def delete_transaction(tx_id):
    """Delete a transaction."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        if cursor.rowcount == 0:
            raise ValidationError("That transaction no longer exists.")


def get_transaction(tx_id):
    """Return one transaction as a dictionary, or None if not found."""
    rows = query(
        "SELECT t.id, t.date, t.type, t.amount, t.category_id, "
        "c.name AS category, t.description "
        "FROM transactions t JOIN categories c ON c.id = t.category_id "
        "WHERE t.id = ?",
        (tx_id,),
    )
    return rows[0] if rows else None


def list_transactions(
    search=None,
    tx_type=None,
    category_id=None,
    start_date=None,
    end_date=None,
    sort_by="date",
    descending=True,
):
    """Return transactions matching the filters, newest first by default."""
    sql = (
        "SELECT t.id, t.date, t.type, t.amount, t.category_id, "
        "c.name AS category, t.description "
        "FROM transactions t JOIN categories c ON c.id = t.category_id WHERE 1=1"
    )
    params = []

    if search:
        # Escape LIKE wildcards so a literal % or _ in the search text is not a wildcard.
        escaped = (
            search.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        sql += " AND (t.description LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')"
        like = f"%{escaped}%"
        params += [like, like]
    if tx_type in VALID_TYPES:
        sql += " AND t.type = ?"
        params.append(tx_type)
    if category_id:
        sql += " AND t.category_id = ?"
        params.append(category_id)
    if start_date:
        sql += " AND t.date >= ?"
        params.append(str(start_date))
    if end_date:
        sql += " AND t.date <= ?"
        params.append(str(end_date))

    column = SORT_COLUMNS.get(sort_by, "t.date")
    direction = "DESC" if descending else "ASC"
    sql += f" ORDER BY {column} {direction}, t.id {direction}"

    return query(sql, tuple(params))