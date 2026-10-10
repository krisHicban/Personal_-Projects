from __future__ import annotations

import math
import sqlite3
from decimal import Decimal
from numbers import Real
from typing import Any


STATUSES = ("draft", "listed", "sold", "reserved", "archived")
ITEM_FIELDS = (
    "title", "platform", "category", "size", "condition",
    "purchase_price", "listing_price", "status", "listing_url", "notes",
)


def _validate_text(values: dict[str, Any], key: str, *, required: bool = False) -> None:
    if key not in values:
        if required:
            raise ValueError(f"{key} is required")
        return
    value = values[key]
    if value is None and not required:
        return
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    values[key] = value.strip()
    if required and not values[key]:
        raise ValueError(f"{key} must not be empty")
    if not required and not values[key]:
        values[key] = None


def _validate_price(values: dict[str, Any], key: str) -> None:
    if key not in values or values[key] is None:
        return
    value = values[key]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{key} must be a non-negative number")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be a non-negative finite number")
    values[key] = value


def _validate_item_values(values: dict[str, Any]) -> None:
    unknown = set(values) - set(ITEM_FIELDS)
    if unknown:
        raise ValueError(f"Unknown item field(s): {', '.join(sorted(unknown))}")
    _validate_text(values, "title", required=True)
    if "platform" in values:
        _validate_text(values, "platform", required=True)
    for key in ("category", "size", "condition", "listing_url", "notes"):
        _validate_text(values, key)
    _validate_price(values, "purchase_price")
    _validate_price(values, "listing_price")
    if "status" in values and values["status"] not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")


def add_item(connection: sqlite3.Connection, values: dict[str, Any]) -> int:
    values = dict(values)
    _validate_item_values(values)

    cursor = connection.execute(
        """INSERT INTO items (
            title, platform, category, size, condition, purchase_price,
            listing_price, status, listing_url, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            values["title"], values.get("platform", "vinted"), values.get("category"),
            values.get("size"), values.get("condition"), values.get("purchase_price"),
            values.get("listing_price"), values.get("status", "draft"),
            values.get("listing_url"), values.get("notes"),
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def update_item(connection: sqlite3.Connection, item_id: int, values: dict[str, Any]) -> bool:
    if not values:
        raise ValueError("At least one item field is required")
    unknown = set(values) - set(ITEM_FIELDS)
    if unknown:
        raise ValueError(f"Unknown item field(s): {', '.join(sorted(unknown))}")

    existing = connection.execute(
        "SELECT title, platform, category, size, condition, purchase_price, "
        "listing_price, status, listing_url, notes FROM items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if existing is None:
        return False

    merged = {field: existing[field] for field in ITEM_FIELDS}
    merged.update(values)
    _validate_item_values(merged)

    assignments = ", ".join(f"{field} = ?" for field in values)
    parameters = [merged[field] for field in values]
    parameters.append(item_id)
    cursor = connection.execute(
        f"UPDATE items SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        parameters,
    )
    connection.commit()
    return cursor.rowcount == 1


def list_items(connection: sqlite3.Connection, status: str | None = None):
    if status:
        return connection.execute(
            "SELECT * FROM items WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    return connection.execute("SELECT * FROM items ORDER BY id DESC").fetchall()


def update_status(connection: sqlite3.Connection, item_id: int, status: str) -> bool:
    if status not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
    cursor = connection.execute(
        "UPDATE items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, item_id),
    )
    connection.commit()
    return cursor.rowcount == 1


def _validate_money(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a non-negative number")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} must be a non-negative finite number")
    return value


def record_sale(
    connection: sqlite3.Connection,
    item_id: int,
    sold_price: Real,
    shipping_cost: Real = 0,
    platform_fee: Real = 0,
) -> bool:
    sold_price = _validate_money(sold_price, "sold_price")
    shipping_cost = _validate_money(shipping_cost, "shipping_cost")
    platform_fee = _validate_money(platform_fee, "platform_fee")
    item = connection.execute(
        "SELECT status, purchase_price FROM items WHERE id = ?", (item_id,)
    ).fetchone()
    if item is None:
        return False
    if item["status"] in ("sold", "archived"):
        raise ValueError("only active items can be sold")
    if item["purchase_price"] is None:
        raise ValueError("purchase price is required before recording a sale")
    connection.execute(
        """UPDATE items
           SET sold_price = ?, shipping_cost = ?, platform_fee = ?,
               status = 'sold', sold_at = CURRENT_TIMESTAMP,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (sold_price, shipping_cost, platform_fee, item_id),
    )
    connection.commit()
    return True


def item_profit(item: sqlite3.Row) -> Decimal | None:
    sale_price = item["sold_price"] if item["status"] == "sold" else item["listing_price"]
    if sale_price is None or item["purchase_price"] is None:
        return None
    shipping = item["shipping_cost"] or 0
    fee = item["platform_fee"] or 0
    return (
        Decimal(str(sale_price))
        - Decimal(str(item["purchase_price"]))
        - Decimal(str(shipping))
        - Decimal(str(fee))
    )


def get_item(connection: sqlite3.Connection, item_id: int):
    return connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def profit_report(connection: sqlite3.Connection) -> dict[str, Decimal | int]:
    items = connection.execute("SELECT * FROM items ORDER BY id").fetchall()
    sold_items = [item for item in items if item["status"] == "sold"]
    active_items = [item for item in items if item["status"] not in ("sold", "archived")]
    realized_profit = sum((item_profit(item) or Decimal("0") for item in sold_items), Decimal("0"))
    estimated_profit = sum((item_profit(item) or Decimal("0") for item in active_items), Decimal("0"))
    purchase_cost = sum(
        (Decimal(str(item["purchase_price"])) for item in sold_items if item["purchase_price"] is not None),
        Decimal("0"),
    )
    revenue = sum(
        (Decimal(str(item["sold_price"])) for item in sold_items if item["sold_price"] is not None),
        Decimal("0"),
    )
    shipping = sum((Decimal(str(item["shipping_cost"] or 0)) for item in sold_items), Decimal("0"))
    fees = sum((Decimal(str(item["platform_fee"] or 0)) for item in sold_items), Decimal("0"))
    return {
        "items": len(items),
        "sold_items": len(sold_items),
        "purchase_cost": purchase_cost,
        "revenue": revenue,
        "shipping": shipping,
        "fees": fees,
        "realized_profit": realized_profit,
        "estimated_profit": estimated_profit,
    }

